# DESIGN v0.1 — PriceScope: платформа сбора, хранения и сравнения цен

**Версия документа:** 1.0
**Дата:** 2026-11-24
**Статус:** Accepted (Design phase)
**Продукт:** PriceScope (имя репозитория пока историческое — `ParserLenta`)
**Версия продукта:** v0.1.0
**Правила:** [RULES.md](../RULES.md) v1.0.0
**Связанные документы:** [DESIGN_PARSERS.md](DESIGN_PARSERS.md),
[DESIGN_DATA_ML.md](DESIGN_DATA_ML.md), [DESIGN_CLIENTS.md](DESIGN_CLIENTS.md),
[ARCHITECTURE.md](../ARCHITECTURE.md)

---

## § 1. Контекст и мотивация

Сейчас в репозитории два независимых скрипта:

| Скрипт | Что делает | Проблемы |
| :--- | :--- | :--- |
| `lenta_parser.py` | Сбор цен Ленты через Integration API → Excel | хардкод координат, только срез цены, нет истории/идентификаторов товара/линеаджа, русские имена колонок, нет тестов |
| `parser_pyaterochka*.py` (другой репо) | Сбор цен Пятёрочки через Camoufox/human_requests |Depends on anti-detect стек, чувствителен к CAPTCHA, дублирование 5 версий, нет единого контракта |
| `lenta_parser_full.py` | Попытка сбора фото/артикула | **не запускается** — синтаксические ошибки (PL-001) |

Итог: данные живут в Excel, сравнивать магазины вручную невозможно, история цен
теряется, для обучения моделей нет размеченного датасета, получить данные с
телефона/сайта нельзя.

**Цель v0.1.0:** заложить industry-grade фундамент — единую доменную модель,
слой парсеров-адаптеров, API, БД (локально SQLite / на сервере PostgreSQL),
локальный веб-просмотровщик и Flutter-клиента (веб + Android) с общим REST API.

---

## § 2. Цели и ограничения (Non-goals)

**Цели (MVP):**

1. Локальный просмотровщик: запуск одной командой, браузер, таблицы, фильтры,
   фото, сравнение цен в двух магазинах, история цен.
2. Единый контракт `ProductObservation` (версионированная схема) для всех
   магазинов; цена в **минорных единицах** (копейки), время в UTC.
3. Идемпотентная загрузка: повторный запуск парсера не дублирует данные;
   сохраняется `raw snapshot` + `content_hash` (lineage).
4. Сравнение товаров: canonical product → observations из разных магазинов →
   таблица «где дешевле» с учётом фасовки/веса.
5. Экспорт датасета для обучения моделей (JSONL + манифест, time-based split).
6. Flutter-клиент (веб + Android) поверх того же API.
7. Полная документация и процесса по образцу IIChatTools.

**Non-goals (сознательно вне Scope v0.1.0):**

- Обход CAPTCHA/антибот-защиты и обход ToS магазинов (при обнаружении — остановка и
 уведомление оператора).
-Обучение и деплой ML-моделей (только подготовка данных и контракты).
-Платёжи, покупки, льготные карты лояльности, персональные рекомендации.
-Парсерымагазинов сверх Ленты и Пятёрочки (но архитектура расширяемая).
-Мультипользовательский режим и авторизация в локальном режиме.

---

## § 3. Принципы (industry best practices)

| Принцип | Воплощение в проекте |
| :--- | :--- |
| **Ports & Adapters** | `StoreParser` — протокол; `LentaParser` / `PyaterochkaParser` — адаптеры. Ядро не знает про requests/Camoufox |
| **Design for failure** | каждая внешняя операция: timeout + retry (exponential backoff + jitter) + circuit breaker; состояние job сохраняется |
| **Explicit contracts** | `ProductObservation` v1 — Pydantic-схема; несовместимые изменения → v2 + адаптер |
| **Idempotency** | `content_hash` + уникальный индекс `(store_code, external_id, location_id, observed_on)`; import run — идемпотентный ключ |
| **Observability by default** | `structlog` + `trace_id`, health/readiness, структурированные логи job, метрики счётчиков |
| **Security by design** | секреты только env/`.env` (gitignored), никаких ключей в коде; ToS-aware парсинг |
| **Docs as code** | реестр PL и спринты — в git; линтер ссылок в CI; документация обновляется в том же коммите |
| **Small reversible steps** | спринты S01–S08, 1 задача = 1 коммит, зелёный build/test, отчёт по RULES § 2.17 |
| **Data lineage** | `raw_snapshot` + `parser_version` + `schema_version` у каждой строки;_EXPORT манифест с checksum |

---

## § 4. Архитектура верхнего уровня

```
                     ┌──────────────────────────────┐
                     │  Источники (сайты магазинов)  │
                     │  Lenta Integration API       │
                     │  5ka.ru (браузер, анти-бот)   │
                     └──────────────┬───────────────┘
                                    │ HTTP / браузер
                     ┌──────────────▼───────────────┐
                     │ packages/parsers (адаптеры)   │
                     │ StoreParser → ObservationDTO  │
                     │ retry / rate limit / captcha  │
                     └──────────────┬───────────────┘
                                    │ нормализованные DTO + raw snapshot
   ┌────────────────────────────────▼────────────────────────────────┐
   │ packages/core — домен, схема Observation v1, money/hash/utils   │
   └────────────────────────────────┬────────────────────────────────┘
                                    │
   ┌────────────────────────────────▼────────────────────────────────┐
   │ apps/api — FastAPI                                               │
   │ routers → services → repositories (SQLAlchemy) → SQLite/Postgres │
   │ /api/v1/*  ·  /health  ·  /metrics  ·  jobs  ·  export           │
   └───────┬───────────────────────────────┬─────────────────────────┘
           │ REST (localhost)              │ REST (HTTPS)
   ┌───────▼───────────────┐    ┌──────────▼──────────┐    ┌────────────────┐
   │ apps/viewer           │    │ apps/mobile         │    │ packages/ml    │
   │ локальный веб-UI      │    │ Flutter: web+Android│    │ matching/export│
   │ Jinja2 + HTMX         │    │ Riverpod + GoRouter │    │ JSONL/Parquet   │
   └───────────────────────┘    └─────────────────────┘    └────────────────┘
```

### § 4.1. Два режима запуска (один код)

| | **Local** (разработчик, v0.1) | **Server** (позже) |
| :--- | :--- | :--- |
| БД | SQLite `data/pricescope.db` | PostgreSQL 16 (+ pgvector опционально) |
| Доступ | `127.0.0.1:8765`, без авторизации | HTTPS + JWT + roles |
| Парсинг | CLI `pricescope parse` вручную | фоновый job (Celery/ARQ), расписание |
| Хранилище фото | `data/photos/` | S3-совместимое хранилище |
| Клиенты | viewer + Flutter (desktop IP) | Flutter web + Android, viewer — опционально |

Переключение — через `PRICESCOPE_MODE=local|server` (Pydantic Settings),
одинаковые роутеры и сервисы.

---

## § 5. Доменная модель и контракты

### § 5.1. Сущности (схема БД детализирована в ARCHITECTURE.md § 3)

| Entity | Назначение |
| :--- | :--- |
| `Store` | магазин (`lenta`, `pyaterochka`), валюта, активность |
| `StoreLocation` | точка (lat/lon, адрес) — цены привязаны к магазину |
| `RawSnapshot` | исходный ответ/страница, `sha256`, `parser_version`, путь |
| `Product` | канонический товар (entity resolution), бренд, категория, атрибуты |
| `Observation` | факт цены: товар × магазин × точка × время; связь с `RawSnapshot` |
| `ProductMatch` | связь `Observation → Product`: метод, confidence, статус review |
| `ParseRun` | запуск парсера: статус, счётчики, ошибки, версия парсера |
| `TrainingExport` | манифест выгрузки: версия схемы, split, checksum, число строк |
| `AuditLog` | действия импорта/экспорта/подтверждения (кто, что, когда, trace_id) |

### § 5.2. Контракт `ProductObservation` v1 (ядро системы)

```python
# packages/core/pricescope_core/observation.py (Pydantic v2)
class ProductObservation(BaseModel):
    schema_version: Literal[1] = 1
    store_code: str                 # "lenta" | "pyaterochka"
    external_id: str                # ID товара в магазине
    location_id: str | None         # ID точки/магазина
    name: str
    brand: str | None = None
    category_path: str | None = None
    price_minor: int                # копейки, НЕ float
    old_price_minor: int | None = None
    currency: Literal["RUB"] = "RUB"
    package: str | None = None      # "100мл"
    net_weight_g: int | None = None
    gross_weight_g: int | None = None
    image_urls: list[str] = []
    product_url: str | None = None
    available: bool = True
    observed_at: datetime           # UTC, timezone-aware
    raw_ref: str                    # RawSnapshot.sha256
    parser_version: str
    content_hash: str               # sha256 каноническогоRepresentation
```

**Почему так:** `int` для денег исключает ошибки округления; `observed_at` только
UTC; `content_hash` делает загрузку идемпотентной; `raw_ref` сохраняет происхождение.

### § 5.3. Entity resolution (сопоставление товаров)

1. **Нормализация:** lower, unicode NFKC, удаление пунктуации, вынесение веса/объёма
   (`100мл` → `volume_ml=100`), бренд.
2. **Blocking:** кандидаты внутри одной категории + по общим токенам/бренду/весу.
3. **Скоринг:** barcode/GTIN (если есть) > точное совпадение имени+веса >
   text embedding > image embedding (CLIP) > fuzzy token similarity.
4. **Решение:** `score ≥ 0.90` → auto-link; `0.70…0.90` → очередь ручного review;
   `< 0.70` → новый `Product`. Все варианты пишутся в `ProductMatch`.
5. **Метрики качества:** precision/recall на размеченной выборке, версия модели в
   `ProductMatch`, контроль дрейфа при смене модели.

Подробности — [DESIGN_DATA_ML.md](DESIGN_DATA_ML.md).

---

## § 6. Слой парсеров

- Протокол `StoreParser`: `name`, `version`, `capabilities`, `health_check()`,
  `async def parse(ctx: ParseContext) -> AsyncIterator[ProductObservation]`.
- Реестр адаптеров: `get_parser("lenta")`, `get_parser("pyaterochka")`.
- Общая обвязка (не в адаптерах): Timeout, retry + backoff/jitter, rate limiter,
  circuit breaker, сохранение raw snapshot, метрики, trace_id.
- **Lenta:** Integration API (`/v1/stores/nearest/hub`, `/catalog/v1/categories`,
  `/catalog/v1/items`), координаты и канал — конфиг, а не хардкод.
- **Pyaterochka:** браузерный адаптер; при признаках CAPTCHA — **остановка**,
  диагностика в `ParseRun.error`, уведомление; автоматический обход запрещён.
- Запрет на забанивание/анонимизацию ради обхода блокировок; Respect robots.txt,
  частота запросов консервативная, User-Agent честный.

Подробности — [DESIGN_PARSERS.md](DESIGN_PARSERS.md).

---

## § 7. REST API (основные endpoints)

| Метод | URL | Назначение |
| :--- | :--- | :--- |
| `GET` | `/health` | liveness/readiness + версия и режим |
| `GET` | `/api/v1/stores` | список магазинов |
| `GET` | `/api/v1/products?query=&category=&page=` | поиск канонических товаров |
| `GET` | `/api/v1/products/{id}` | товар + фото + атрибуты |
| `GET` | `/api/v1/observations?product_id=&store_code=&from=&to=` | история цен |
| `GET` | `/api/v1/compare?product_id=&lat=&lon=` | сравнение цен в магазинах |
| `POST` | `/api/v1/imports` | запуск парсинга/импорта (idempotency key) |
| `GET` | `/api/v1/imports/{id}` | статус и счётчики запуска |
| `GET` | `/api/v1/matches/review` | очередь спорных совпадений |
| `POST` | `/api/v1/matches/{id}/decide` | подтвердить/отклонить связь |
| `POST` | `/api/v1/exports` | сформировать датасет (manifest) |
| `GET` | `/api/v1/exports/{id}/download` | скачать JSONL/Parquet |
| `GET/POST` | `/api/v1/favorites`, `/api/v1/alerts` | избранное и алерты (клиенты) |

Формат ошибки единый:
`{"success": false, "error": {"code": "...", "message": "...", "details": {}}, "trace_id": "..."}`.
Пагинация: `page`, `page_size` (≤ 200), в ответе `total`, `items`, `page`.

---

## § 8. Хранение данных

- **SQLAlchemy 2** (async) + Alembic-миграции; SQLite в local, PostgreSQL в server.
- Все даты — `TIMESTAMP WITH TIME ZONE` (в SQLite — ISO-8601 UTC строка).
- Ключевые индексы:
  - `uq_observation` = `(store_code, external_id, location_id, observed_on)`;
  - `ix_observation_product_time` = `(product_id, observed_at DESC)`;
  - `ix_observation_store_time` = `(store_code, observed_at DESC)`;
  - `ix_raw_snapshot_sha` = `(sha256 UNIQUE)`.
- Хранение фото: local — `data/photos/{store}/{external_id}/{sha}.webp`;
  в БД только путь/URL.
- Retention: raw snapshots — 90 дней (настраивается), observation — бессрочно
  (история цен — актив платформы), логи — 30 дней.

Структура каталогов данных — в [ARCHITECTURE.md](../ARCHITECTURE.md) § 8.

---

## § 9. Локальный просмотровщик

`pricescope serve --local` поднимает FastAPI с подключённым `apps/viewer`:

- стек: **Jinja2 + HTMX** (без JS-сборки, работает офлайн);
- экраны: `Обзор` (последний импорт, счётчики), `Товары` (таблица с фильтрами
  по названию/магазину/категории, сортировка, фото), `Карточка` (цена по времени,
  sparkline/таблица), `Сравнение` (одна строка на товар, цены по магазинам,
  «дешевле на X %»), `Импорты` (журнал запусков), `Настройки` (координаты, лимиты).
- обновление таблиц — HTMX-фрагменты (`hx-get`, `hx-target`), поиск debounce 250 мс;
- все запросы идут в тот же API, который используют Flutter-клиенты.

Подробности — [DESIGN_CLIENTS.md](DESIGN_CLIENTS.md) § 2.

---

## § 10. Flutter-клиент (веб + Android)

- **Clean Architecture**: `data` (Dio + JSON), `domain` (entities/usecases),
  `presentation` (pages/widgets); состояние — Riverpod; навигация — GoRouter.
- Экраны MVP: поиск товара, карточка с историей цен (`fl_chart`), сравнение,
  избранное, сканер штрихкода (mobile), настройки сервера (local IP / server URL).
- Офлайн-кэш: `drift` (SQLite) для избранного и последних результатов.
- Один код для web и Android; flavor `dev`/`prod` через `--dart-define`.
- Минимальные версии: Flutter 3.24+, Dart 3.5+, Android minSdk 24, target 35.

Подробности — [DESIGN_CLIENTS.md](DESIGN_CLIENTS.md) § 3.

---

## § 11. ML и датасеты

- Канонический каталог `Product` + `ProductMatch` — источник размеченных пар
  «один товар в разных магазинах».
- Эмбеддинги: текст (название+атрибуты) и изображение (CLIP); версия модели
  фиксируется в метаданных. Хранение векторов: local — SQLite BLOB / numpy;
  server — pgvector.
- Экспорт: `datasets/exports/{version}/{split}.jsonl` + `manifest.json`
  (схема, число строк, checksum, время, версии моделей/парсеров); split —
  **time-based** (обучение на старых данных, валидация на новых) во избежание
  утечки; PII не экспортируется.
- Метрики: точность entity resolution (precision/recall/F1), покрытие сопоставлений,
  доля ручных решений. Обучение моделей — следующий этап.

---

## § 12. Безопасность и соответствие

1. Секреты — только env / `.env` (в `.gitignore`); в docs — плейсхолдеры.
2. Локальный режим слушает только `127.0.0.1`; серверный — JWT + роли.
3. Парсеры: не обходить CAPTCHA, не подменять IP/UA с целью обхода блокировок,
   соблюдать robots.txt и условия использования; при блокировке — останов + лог.
4. Аудит импортов/экспортов/решений match — в `AuditLog`.
5. Изображения товаров используются только для внутреннего сравнения/обучения;
   источник и URL сохраняются в lineage.

---

## § 13. Наблюдаемость и надёжность

- `structlog`: JSON-логи, `trace_id` сквозь CLI → parser → API → export.
- `/health` (liveness/readiness: БД доступна, last successful import) и `/metrics`
  (счётчики observations, errors, jobs, match confidence).
- `ParseRun` — end-to-end трекинг: status `pending|running|success|partial|failed`,
  counters `items/failed/skipped`, `error_code`, `finished_at`.
- Retry policy: 3 попытки, exponential backoff 1/2/4 с + jitter ±20 %, только на
  transient-ошибки; внешняя отмена (`CancellationToken`/`asyncio.CancelledError`)
  всегда пробрасывается. Circuit breaker: 5 ошибок → 5 минут skip провайдера.

---

## § 14. Тестирование и качество

| Уровень | Что | Инструменты |
| :--- | :--- | :--- |
| Unit | normalizer, money, matching, DTO | pytest |
| Contract | `ProductObservation` v1, REST-схемы | pytest + Pydantic fixtures |
| Parser | фикстуры ответов Lenta/5ka (VCR-cassettes), без сети | pytest + `pytest-recording`/fixtures |
| Integration | API + SQLite in-memory/tmp | `TestClient` |
| E2E (smoke) | local run → import fixture → compare → export | script `scripts/dev/smoke.ps1` |
| Client | Flutter widget/unit tests | `flutter test`, `flutter analyze` |
| Статика | формат, типы, security | ruff, mypy, pre-commit, `detect-secrets` (план) |

CI (GitHub Actions): `ruff check` → `mypy` → `pytest` → `flutter analyze/test`
(отдельный job) → проверка ссылок docs → отчёт.

---

## § 15. Этапы и спринты

| Спринт | Тема | Результат |
| :--- | :--- | :--- |
| S01 | Fundamental | pyproject, core DTO v1, RULES/ARCHITECTURE/README, CI |
| S02 | Parsers base | `StoreParser`, registry, retry/rate limit/raw snapshot, тесты |
| S03 | Lenta adapter | адаптер + фикстуры + импорт в SQLite |
| S04 | API + DB | SQLAlchemy-модели, Alembic, роутеры, import/compare, smoke |
| S05 | Viewer | локальный UI: таблицы, фильтры, фото, сравнение, история |
| S06 | Pyaterochka | адаптер + captcha-policy + manual run + тесты на фикстурах |
| S07 | ML/data | matching, review queue, JSONL-экспорт, manifest, метрики |
| S08 | Flutter + release | клиент web/Android, QA-чеклист, релиз v0.1.0 |

План детализирован в [TODO_SPRINTS.md](../../TODO_SPRINTS.md).

---

## § 16. Риски и ограничения

| Риск | Митигация |
| :--- | :--- |
| Блокировка/изменение API Ленты | контракт адаптера, raw snapshots, версионирование парсера, алерт в ParseRun |
| CAPTCHA/антибот Пятёрочки | останов без обхода, ручной импорт, легальный канал данных (платно) как альтернатива |
| Плохое сопоставление товаров | confidence + ручной review + метрики качества на размеченной выборке |
| Рост БД/фото | retention raw/layers, сжатие webp, лимиты export, мониторинг размера |
| Юридический статус данных | ToS-политика, внутреннее использование,source lineage в каждой строке |

---

## § 17. Критерии приёмки MVP (Definition of Done v0.1.0)

- [ ] `pricescope serve --local` поднимает API + viewer одной командой.
- [ ] `pricescope parse --store lenta` собирает ≥ 1 товара в SQLite, повтор не дублирует.
- [ ] `GET /api/v1/compare?product_id=...` возвращает цены Ленты и Пятёрочки (если есть observation).
- [ ] Viewer показывает таблицу, фото, историю цен и сравнение.
- [ ] `pricescope export` создаёт JSONL + manifest с time-based split.
- [ ] Flutter-приложение собирается в web и Android debug, подключается к API.
- [ ] `ruff check`, `mypy`, `pytest`, `flutter analyze` — зелёные; QA-чеклист § 2 пройден.
- [ ] Документация (README, RULES, ARCHITECTURE, RELEASES, DESIGN, QA) обновлена.

---

## § 18. Ссылки

- [Обзор проекта](../../../README.md)
- [Хаб документации](../../README.md)
- [Архитектура](../ARCHITECTURE.md) · [Правила](../RULES.md) · [Релизы](../RELEASES.md)
- [Дизайн парсеров](DESIGN_PARSERS.md) · [Данные и ML](DESIGN_DATA_ML.md) · [Клиенты](DESIGN_CLIENTS.md)
- [Реестр проблем](../../KNOWN_ISSUES.md) · [Спринты](../../TODO_SPRINTS.md)
