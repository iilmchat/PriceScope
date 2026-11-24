# S07 — entity resolution, review и экспорт датасета

**Дата:** 2026-11-24 · **Статус:** Done · **Правила:** RULES.md v1.0.4

## (1) Файлы (+/−)

| Файл | Изменение |
| :--- | :--- |
| `packages/ml/pricescope_ml/matching.py` | + `MatchCandidate`, `MatchingDecision`, `score_candidates`, `decide`, пороги и `MODEL_VERSION` |
| `packages/ml/pricescope_ml/export.py` | time-based split для малых выборок, `split_boundaries`, `extra` в манифест |
| `apps/api/pricescope_api/services.py` | + `run_matching`, `get_review_rows`, `decide_match`, `get_metrics`; обогащённый `export_dataset` |
| `apps/api/pricescope_api/repositories.py` | + `create_product_match` |
| `apps/api/pricescope_api/routers.py` | + `POST /matches/run`, `GET /metrics`, `GET /exports/{id}/download`; review с названиями |
| `apps/api/pricescope_api/cli.py` | `pricescope match --run [--review]` |
| `apps/viewer/...` | очередь совпадений показывает названия/цены; решение идёт через сервис (связывает observation) |
| `packages/ml/tests/test_matching.py`, `apps/api/tests/test_matching_export.py` | + 11 тестов |

## (2) Покрытие

- Юнит: точное имя → auto, фасовка повышает/понижает оценку, пороги 0.70/0.90,
  candidate scoring с учётом `package`.
- Интеграция: первое наблюдение → новый Product (`new`), похожее → `review`,
  точное → `auto`; очередь review с `left_name/right_name/left_price_minor`;
  подтверждение связывает observation; метрики покрытия; экспорт JSONL + manifest
  + checksums + time split; скачивание только файлов из манифеста (path traversal → 404).

## (3) Результаты

- `ruff check .` — All checks passed · `mypy packages apps/api` — 0 ошибок, 57 файлов
- `pytest -q -p pytest_asyncio.plugin -m "not live"` — **56 passed, 1 deselected**
- Smoke на живой БД: `pricescope match --run` → `auto=0 review=1 new=2`;
  `pricescope export` → каталог с `train/val/test.jsonl`, `manifest.json`, `checksums.sha256`;
  `/matches`, `/api/v1/matches/review`, `/api/v1/metrics` → 200.

## (4) Smoke

```powershell
pricescope match --run
pricescope match --review
pricescope export --name product-matching --version 1
pricescope serve --local
# http://127.0.0.1:8775/matches
# GET /api/v1/metrics
# GET /api/v1/exports/1/download?file=train.jsonl
```

## (5) Что не так

- Эмбеддинги (CLIP/SentenceTransformers) не подключены: сейчас только lexical-скоринг
  (`MODEL_VERSION=lexical-v1`). Текстовые/визуальные модели — следующий этап после v0.1.
- Live-экспорт на трёх товарах одной сети дал 0 пар «разные магазины» — для
  обучающего датасета нужен импорт обеих сетей и подтверждённые пары (S06 + review).
- `Product` создаётся автоматически с name observation; ручное объединение
  дублей пока не реализовано (todo v0.2).

## (6) Новые PL

- Новых нет. PL-006 и PL-007 закрыты.

## (7) Обоснование

Решение сопоставления пишется в `ProductMatch` вместе с `method/score/model_version` —
это и аудит, и готовая разметка датасета. Time-based split исключает утечку будущих цен
в обучение. Скачивание ограничено whitelist из `manifest.sha256`, поэтому имя файла
не может выйти за каталог выгрузки.
