# DESIGN_DATA_ML — данные, сопоставление товаров и ML-экспорт PriceScope v0.1

**Версия:** 1.0 · **Дата:** 2026-11-24 · **Статус:** Accepted
**Связанные:** [DESIGN.md](DESIGN.md) § 5, § 11; [ARCHITECTURE.md](../ARCHITECTURE.md) § 3

---

## § 1. Цели подсистемы

1. Хранить **историю цен** как неизменяемые факты (observations), а не «последний Excel».
2. Сопоставлять один и тот же товар в разных магазинах (entity resolution).
3. Формировать воспроизводимые датасеты для обучения моделей: «цена → товар»,
   «похожие товары», «какая цена аномальна», мультимодальные (текст + фото).

---

## § 2. Слои данных

| Слой | Содержание | Изменяемость |
| :--- | :--- | :--- |
| **Raw** | `RawSnapshot`: исходный JSON/HTML, `sha256`, `parser_version`, `fetched_at` | immutable, retention 90 дней |
| **Normalized** | `Observation`: `ProductObservation` v1 + `content_hash` | immutable (upsert по ключу) |
| **Canonical** | `Product`, `ProductMatch`, `Brand`, `Category` | редактируемый (review) |
| **Derived** | агрегаты (min/median price за день), эмбеддинги, датасеты | пересчитываемые, версионируемые |

**Никогда** не перезаписываем observation: новая цена = новая строка. Это даёт
корректную историю и_corpus для обучения.

---

## § 3. Идемпотентная загрузка

```
content_hash = sha256(canonical_json({
  store_code, external_id, location_id, price_minor,
  old_price_minor, package, net_weight_g, observed_at.date(), schema_version
}))

INSERT ... ON CONFLICT (store_code, external_id, location_id, observed_on)
DO UPDATE SET price_minor=..., raw_ref=..., content_hash=...
  WHERE observation.content_hash IS DISTINCT FROM excluded.content_hash
```

* Повторный запуск парсера не создаёт дубликатов.
* Если контент изменился — обновляется существующая запись и пишется AuditLog.
* `ParseRun` хранит `new`, `updated`, `skipped` — легко заметить аномалии.

---

## § 4. Entity resolution: конвейер

> **Статус S07:** реализован `run_matching` на lexical-скоринге
> (`MODEL_VERSION=lexical-v1`), пороги 0.90 / 0.70, очередь review и привязка
> observation к `Product`. Эмбеддинги (CLIP/SentenceTransformers) — следующий этап.

```
Observation
  → normalize_name (NFKC, lower, пунктуация, бренд)
  → extract_measures ("100мл"→volume_ml, "1кг"→weight_g)
  → blocking (категория + токены + вес)
  → score:
      1.0  GTIN/barcode совпадение (если есть)
      0.95 имя+объём точное
      0.85 text embedding cosine (SentenceTransformers, модель фиксирована)
      0.80 image embedding cosine (CLIP, модель фиксирована)
      0.60 token Jaccard/Levenshtein
  → solve: ≥0.90 auto, 0.70–0.90 review, <0.70 new Product
  → write ProductMatch(method, score, model_version, status, decided_by)
```

**Ручной review** (via API/viewer): список пар «название Ленты ↔ название
Пятёрочки», confidence, фото, кнопки «один товар / разные». Решение пишется в
`ProductMatch` с `status=confirmed|rejected` — это одновременно размеченный
датасет для обучения matching-модели.

**Контроль качества:** ежемесячно на 100 вручную размеченных пар считаем
precision/recall/F1; при падении > 5 п.п. — пересмотр порогов/модели. Версия
модели и пороги — в конфиге, изменение = новая версия `ProductMatch.model_version`.

---

## § 5. Экспорт датасета

> **Статус S07:** `pricescope export` / `POST /api/v1/exports` формируют пары
> «разные магазины — один товар», time-based split, `manifest.json` с checksum
> и `GET /api/v1/exports/{id}/download` (только файлы из манифеста).

**Запуск:** `pricescope export --name product-matching --version 1`.

**Структура:**

```
datasets/exports/product-matching-v1/
├── manifest.json
├── train.jsonl
├── val.jsonl
├── test.jsonl
└── checksums.sha256
```

**`manifest.json`:**

```json
{
  "dataset": "product-matching",
  "version": "1.0.0",
  "schema_version": 1,
  "created_at": "2026-11-24T10:00:00Z",
  "split_policy": "time-based",
  "split_boundaries": { "val_from": "2026-10-01", "test_from": "2026-11-01" },
  "rows": { "train": 12345, "val": 2000, "test": 2000 },
  "parsers": { "lenta": "0.1.0", "pyaterochka": "0.1.0" },
  "models": { "text": "paraphrase-multilingual-MiniLM-L12-v2", "image": "clip-ViT-B-32" },
  "source_count": 15432,
  "sha256": { "train.jsonl": "...", "val.jsonl": "...", "test.jsonl": "..." }
}
```

**Строка `*.jsonl` (пример):**

```json
{"product_id": 42, "left": {"store":"lenta","external_id":"736811","name":"Дезодорант РЕКСОНА 100мл","price_minor":22999,"image_url":"..."}, "right": {"store":"pyaterochka","external_id":"...","name":"Рексона спрей 100 мл","price_minor":19990,"image_url":"..."}, "label":"match","match_method":"review","exported_at":"2026-11-24T10:00:00Z"}
```

**Правила:**

- time-based split (утечки будущего в прошлое нет);
- дедупликация по `(product_id, left.external_id, right.external_id)`;
- PII отсутствует (нет пользователей/координат клиентов);
- checksum + версии моделей/парсеров → воспроизводимость;
- экспорт — read-only операция, аудит в `TrainingExport` + `AuditLog`.

---

## § 6. Метрики и мониторинг качества данных

| Метрика | Как считается | Цель |
| :--- | :--- | :--- |
| `observations_per_run` | счётчик ParseRun | стабильность парсера |
| `match_auto_rate` | auto / all matches | ≥ 70 % |
| `match_precision` | ручная выборка | ≥ 0.95 |
| `price_outlier_rate` | цена вне 3σ внутри товара | ≤ 2 % |
| `raw_retention_days` | политика хранения | 90 дней |
| `dataset_rows` | manifest | растёт монотонно |

---

## § 7. Ссылки

- [DESIGN.md](DESIGN.md) § 5, § 11 · [Архитектура](../ARCHITECTURE.md) § 3
