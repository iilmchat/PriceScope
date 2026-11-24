# Архитектура PriceScope

**Версия:** 0.1.0 (обновлено 2026-11-24)
**Статус:** Living document — обновляется при значимых архитектурных изменениях.
**Связанные документы:** [RULES.md](RULES.md), [RELEASES.md](RELEASES.md),
[DESIGN v0.1](v0.1/DESIGN.md), [DESIGN_PARSERS](v0.1/DESIGN_PARSERS.md),
[DESIGN_DATA_ML](v0.1/DESIGN_DATA_ML.md), [DESIGN_CLIENTS](v0.1/DESIGN_CLIENTS.md).

---

## § 1. Обзор

**PriceScope** — платформа сбора, нормализации, хранения и сравнения цен товаров
из нескольких магазинов (Лента, Пятёрочка) с локальным веб-просмотровщиком,
Flutter-клиентом (веб + Android) и экспортом данных для обучения моделей.

**Ключевая идея:** один контракт `ProductObservation` v1 + один REST API;
парсеры — взаимозаменяемые адаптеры, БД — взаимозаменяемый провайдер
(SQLite локально / PostgreSQL на сервере), клиенты — тонкие.

**Стек:**

| Слой | Технологии |
| :--- | :--- |
| Парсеры | Python 3.11+, requests/httpx, Camoufox + human_requests (5ka), Pydantic v2 |
| Ядро | `pricescope_core`: DTO, money (minor units), normalization, hashing |
| API | FastAPI, Uvicorn, Pydantic Settings, structlog, Prometheus (опц.) |
| Данные | SQLAlchemy 2 (async), Alembic, SQLite (local) / PostgreSQL 16 (server), pgvector (план) |
| Фон | asyncio + `BackgroundTasks` (v0.1); Celery/ARQ — v0.2+ |
| Viewer | Jinja2 + HTMX + Alpine.js (без сборки) |
| Клиент | Flutter 3.24+, Dart 3.5+, Riverpod, GoRouter, Dio, drift, fl_chart |
| ML | SentenceTransformers + CLIP (эмбеддинги), numpy, JSONL/Parquet export |
| Инфраструктура | Docker Compose, GitHub Actions, ruff, mypy, pytest, pre-commit |

---

## § 2. Слои

```
┌─────────────────────────────────────────────────────────────────────┐
│  Источники: Lenta Integration API · 5ka.ru (браузер) · CSV (manual) │
└────────────────────────────▲────────────────────────────────────────┘
                             │ HTTP / Browser
┌────────────────────────────┴────────────────────────────────────────┐
│  packages/parsers                                                   │
│  ├── StoreParser (Protocol) + ParseContext                          │
│  ├── registry.py: get_parser(name)                                  │
│  ├── lenta/: client.py, parser.py, fixtures/                        │
│  ├── pyaterochka/: browser.py, parser.py, captcha_policy.py          │
│  └── manual/: csv_parser.py                                         │
│  Обвязка: retry, rate limit, circuit breaker, raw snapshot, metrics │
└────────────────────────────▲────────────────────────────────────────┘
                             │ ProductObservation v1 (async generator)
┌────────────────────────────┴────────────────────────────────────────┐
│  packages/core                                                      │
│  observation.py (Pydantic v1-schema) · money.py · normalization.py   │
│  hashing.py · errors.py · enums.py                                  │
└────────────────────────────▲────────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────────┐
│  apps/api — FastAPI (net: local 127.0.0.1:8775 / server HTTPS)      │
│  ├── routers/: health, stores, products, observations, compare,     │
│  │             imports, matches, exports, favorites, alerts         │
│  ├── services/: ingest, search, compare, matching, export, jobs     │
│  ├── repositories/: SQLAlchemy 2 async, UoW                         │
│  ├── db/: base, session, models, alembic/                           │
│  ├── config.py (Pydantic Settings), logging.py (structlog+trace)    │
│  └── middleware.py (error envelope, correlation-id, timing)         │
└────────────────────────────▲────────────────────────────────────────┘
              ┌──────────────┼───────────────┐
              ▼              ▼               ▼
      apps/viewer      apps/mobile      packages/ml
      Jinja2+HTMX      Flutter web/     matching, embeddings,
      (локальный UI)   Android          dataset export
              │              │               │
              └──────────────┴───────────────┘
                     общий REST API /api/v1/*

        SQLite (local)  ──── Alembic ────►  PostgreSQL (server)
        data/photos/                        S3 (server, план)
```

**Принцип слоистости:** `routers → services → repositories → db`.
Обратных зависимостей нет: `core` не знает про FastAPI, `parsers` не знает про
БД, `apps/*` не импортируют внутренности друг друга.

---

## § 3. Схема БД

### § 3.1.{Stores и локации

| Entity | Ключевые поля | Индексы |
| :--- | :--- | :--- |
| `Store` | `id`, `code` (unique), `name`, `currency`, `active`, `site_url` | `uq_store_code` |
| `StoreLocation` | `id`, `store_id`, `external_id`, `lat`, `lon`, `address`, `last_used_at` | `(store_id, external_id)` |

### § 3.2. Данные о товарах

| Entity | Ключевые поля | Индексы |
| :--- | :--- | :--- |
| `RawSnapshot` | `id`, `sha256` (unique), `store_code`, `payload` (JSON/TEXT), `uri`, `parser_version`, `fetched_at` | `uq_snapshot_sha`, `(store_code, fetched_at)` |
| `Product` | `id`, `canonical_name`, `brand`, `category_path`, `attributes_json`, `image_urls_json`, `created_at`, `updated_at` | `(brand, canonical_name)` |
| `Observation` | `id`, `store_code`, `external_id`, `location_id`, `product_id` (nullable), `price_minor`, `old_price_minor`, `currency`, `package`, `net_weight_g`, `gross_weight_g`, `image_urls_json`, `available`, `observed_at`, `raw_sha256`, `parser_version`, `schema_version`, `content_hash`, `created_at` | **`uq_observation`** `(store_code, external_id, location_id, observed_on)`, `(product_id, observed_at DESC)`, `(store_code, observed_at DESC)` |
| `ProductMatch` | `id`, `observation_id`, `product_id`, `method`, `score`, `model_version`, `status` (`auto|review|confirmed|rejected`), `decided_by`, `created_at` | `(status, score DESC)`, `(observation_id)` |

### § 3.3. Процессы и выводы

| Entity | Назначение |
| :--- | :--- |
| `ParseRun` | `id`, `store_code`, `status`, `idempotency_key`, `new/updated/skipped/error_code`, `error_message`, `started_at`, `finished_at`, `trace_id`, `parser_version` |
| `TrainingExport` | `id`, `name`, `version`, `manifest_json`, `rows_json`, `created_at`, `path` |
| `AuditLog` | `id`, `action`, `actor`, `entity_id`, `details_json`, `trace_id`, `created_at` |
| `Favorite` / `PriceAlert` | пользовательские списки (local: без auth; server: `user_id`) |

### § 3.4. Миграции

- Alembic, папка `apps/api/migrations/versions/`; единая цепочка для SQLite и PostgreSQL
  (типы через `SQLAlchemy` generic + compile-features, без `ENUM`-зависимостей).
- Первая миграция `5c70c265161b_initial_schema` сгенерирована autogenerate и
  создаёт все 9 таблиц (S04).
- Команды (из каталога `apps/api`, чтобы `script_location` резолвился):
  ```powershell
  cd apps/api
  alembic -c alembic.ini revision --autogenerate -m "add column"
  alembic -c alembic.ini upgrade head
  alembic -c alembic.ini downgrade base   # только для тестов
  ```
- `pricescope init-db` = `upgrade head` через `init_db(settings)`; при запуске API
  миграции применяются автоматически (`auto_migrate=true`, в тестах отключается).
- Для БД, созданной старым `create_all` без `alembic_version`, выполняется `stamp head`
  без пересоздания таблиц — история цен сохраняется (PL-010).
- Миграции **обязательны** при изменении модели; `create_all` в проде запрещён.

---

## § 4. Dependency injection

| Компонент | Lifetime | Почему |
| :--- | :--- | :--- |
| `Settings` | Singleton (app state) | читается один раз из env |
| `AsyncEngine` / `sessionmaker` | Singleton | пул соединений |
| `AsyncSession` (UoW) | per request | транзакция границы запроса |
| `StoreParser` | transient (per run) | состояние прогона (счётчики, HTTP-сессия) |
| `IRateLimiter` / `ICircuitBreaker` | Singleton | общий state между запросами |
| `IMatchingService` | Singleton | тяжёлая загрузка моделей, кэш эмбеддингов |
| `IExportService` | per request | генерирует файл, пишет manifest |
| `structlog` logger | Singleton | `trace_id` через `ContextVar` |

---

## § 5. Потоки (end-to-end)

### § 5.1. Импорт цен

```
CLI/POST /api/v1/imports
  → IngestService.start(store, location, idempotency_key)
  → ParseRun(pending → running)
  → get_parser(store).parse(ctx)  [raw snapshot → normalize → validate]
  → async for observation: Repository.upsert(observation)
  → ParseRun(success|partial|failed) + AuditLog + метрики
  → HTTP 202 + Location: /api/v1/imports/{id} (для server) или синхронный результат (local)
```

### § 5.2. Сравнение цен

```
GET /api/v1/compare?product_id=…|query=…&lat=…&lon=…
  → CompareService: отобрать Observation по товару/подстроке названия
  → сгруппировать по store_code; выбрать ближайшую StoreLocation (haversine)
    и самое свежее наблюдение в ней
  → цена за кг/литр из package/net_weight_g; savings_pct от минимума
  → ответ: [{store_code, price_minor, price_per_kg_minor, price_per_l_minor,
             distance_m, observed_at, is_cheapest, savings_pct}, ...]
  → 400 INVALID_QUERY, если не заданы ни product_id, ни query
```

### § 5.3. Сопоставление товаров (matching)

```
Observation без product_id
  → Normalizer + blocking
  → MatchingService.score(candidates)
  → ≥0.90 auto-link | 0.70–0.90 → review queue | <0.70 → new Product
  → ProductMatch(method, score, model_version, status)
  → Review UI → confirmed/rejected → пересчёт product_id у Observation
```

### § 5.4. Экспорт датасета

```
POST /api/v1/exports
  → ExportService: собрать пары по confirmed ProductMatch + time-based split
  → записать train/val/test JSONL + manifest.json + checksums
  → TrainingExport(row counts, path) + AuditLog
  → GET /api/v1/exports/{id}/download
```

---

## § 6. Внешние зависимости и отказы

| Зависимость | Роль | При отказе |
| :--- | :--- | :--- |
| Lenta API | каталог и цены | ParseRun.failed, retry → circuit breaker, алерт |
| 5ka.ru + Camoufox | цены Пятёрочки | CAPTCHA → останов (Не обходить!), manual import |
| PostgreSQL (server) | основная БД | readiness=unhealthy, запросы 503 |
| CLIP/SentenceTransformers | эмбеддинги | fallback на лексический matching, метка в `model_version` |
| S3 (план) | фото | локальный путь фото |

---

## § 7. Известные архитектурные решения (ADR-style)

| ADR | Решение |
| :--- | :--- |
| [ADR-001](adr/ADR-001-single-observation-contract.md) | Единый контракт `ProductObservation` v1, money = int (копейки) |
| [ADR-002](adr/ADR-002-ports-adapters-parsers.md) | Парсеры за протоколом `StoreParser`; адаптер ≠ бизнес-логика |
| [ADR-003](adr/ADR-003-sqlite-local-postgres-server.md) | SQLite локально / PostgreSQL на сервере, один слой SQLAlchemy |
| [ADR-004](adr/ADR-004-htmx-local-viewer.md) | HTMX + Jinja2 для локального viewer без JS-сборки |
| [ADR-005](adr/ADR-005-time-based-split.md) | Time-based split датасетов во избежание утечки будущего |
| [ADR-006](adr/ADR-006-captcha-no-bypass.md) | CAPTCHA — остановка, обход запрещён |
| [ADR-007](adr/ADR-007-flutter-shared-api.md) | Один Flutter-код для web/Android, общий REST API |

---

## § 8. Структура каталогов

```
ParserLenta/                     # историческое имя репозитория
├── README.md · CHANGELOG.md · pyproject.toml · docker-compose.yml
├── packages/
│   ├── core/pricescope_core/    # DTO, money, normalization, hashing
│   ├── parsers/pricescope_parsers/  # StoreParser, lenta, pyaterochka, manual
│   └── ml/pricescope_ml/        # matching, embeddings, export
├── apps/
│   ├── api/pricescope_api/      # FastAPI: routers, services, repositories, db
│   ├── api/migrations/          # Alembic
│   ├── api/tests/               # pytest
│   ├── viewer/pricescope_viewer/# Jinja2 + HTMX
│   └── mobile/                  # Flutter (web + Android)
├── data/                        # gitignored: *.db, photos/, raw/
├── datasets/exports/            # gitignored: JSONL + manifest
├── logs/                        # gitignored
├── docs/                        # этот комплект документации
└── scripts/{setup,dev,ci}/      # bootstrap, smoke, проверка ссылок
```

Legacy-скрипты (`lenta_parser*.py`, Excel-файлы, `photos/`) остаются в корне
до переноса функциональности в адаптеры (PL-001). Не удаляются без решения в KI.

---

## § 9. Ссылки

- [Обзор](../../README.md) · [Хаб документации](../README.md)
- [Правила](RULES.md) · [Релизы](RELEASES.md) · [Реестр проблем](../KNOWN_ISSUES.md)
- [Дизайн v0.1](v0.1/DESIGN.md)
