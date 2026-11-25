# PriceScope v0.1.0

**Платформа сбора, хранения и сравнения цен товаров из Ленты и Пятёрочки — локально, в браузере и в Android.**

© 2026 PriceScope · v0.1.0

---

## Что это

PriceScope превращает разрозненные парсеры и Excel-файлы в единую систему:

- **Единый контракт товара** `ProductObservation` v1 (цена в копейках, UTC, исходник + хэш);
- **Парсеры-адаптеры**: Лента (Integration API) и Пятёрочка (браузер, с жёсткой политикой «CAPTCHA → стоп»);
- **БД истории цен**: SQLite локально, PostgreSQL на сервере, Alembic-миграции;
- **Локальный просмотровщик** в браузере: таблицы, фильтры, фото, история цен, сравнение магазинов;
- **Flutter-клиент**: один код для сайта (web) и Android;
- **Данные для ML**: сопоставление товаров, ручной review, экспорт JSONL + manifest с time-based split.

Проект спроектирован по принципам *ports & adapters*, *design for failure*,
*idempotency*, *observability by default* и *docs as code*.

> Текущая папка репозитория — `ParserLenta` (историческое имя). Продуктовое имя —
> **PriceScope**; переименование каталога — отдельная задача.

---

## Документация

| Кому | Документ |
| :--- | :--- |
| Всем | **[GET_STARTED.md](GET_STARTED.md)** — разворачивание и первичная настройка |
| Всем | [docs/README.md](docs/README.md) — хаб документации (навигация по ролям) |
| Пользователям | [docs/user_guide/USER_GUIDE.md](docs/user_guide/USER_GUIDE.md) — просмотровщик, клиент, сравнение |
| Тестировщикам | [docs/qa/MANUAL_TESTING_GUIDE.md](docs/qa/MANUAL_TESTING_GUIDE.md) — чек-лист ручной приёмки |
| Разработчикам | [docs/development/RULES.md](docs/development/RULES.md) · [ARCHITECTURE.md](docs/development/ARCHITECTURE.md) · [RELEASES.md](docs/development/RELEASES.md) · [reports/](docs/development/reports/) |
| Дизайн | [v0.1 DESIGN.md](docs/development/v0.1/DESIGN.md) · [парсеры](docs/development/v0.1/DESIGN_PARSERS.md) · [данные/ML](docs/development/v0.1/DESIGN_DATA_ML.md) · [клиенты](docs/development/v0.1/DESIGN_CLIENTS.md) |
| Реестр проблем | [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) · [TODO_KI.md](docs/TODO_KI.md) · [спринты S01–S08](docs/TODO_SPRINTS.md) |
| История версий | [CHANGELOG.md](CHANGELOG.md) |

---

## Требования

| Компонент | Версия |
| :--- | :--- |
| Python | 3.11+ (рекомендуется 3.12) |
| Flutter SDK | 3.24+ (Dart 3.5+) — только для клиента |
| Android SDK | minSdk 24, targetSdk 35 — только для Android-сборки |
| PostgreSQL | 16+ — только в серверном режиме (v0.2+) |
| Camoufox + human_requests | только для парсера Пятёрочки (путь — env `CAMOUFOX_EXECUTABLE_PATH`) |
| SQLite | встроен, используется по умолчанию |

---

## Установка

```powershell
git clone <your-repo-url> ParserLenta
cd ParserLenta
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Для работы с Flutter:

```powershell
cd apps/mobile
flutter pub get
```

---

## Быстрый старт (локальный режим)

> Полное пошаговое руководство по разворачиванию, конфигурации и устранению
> проблем — [GET_STARTED.md](GET_STARTED.md).

```powershell
# 1. Создать схему БД
pricescope init-db

# 2. Собрать цены Ленты (координаты — параметры, не хардкод)
pricescope parse --store lenta --lat 55.3925 --lon 36.7323

# 3. Поднять API + локальный просмотровщик
pricescope serve --local
# открыть http://127.0.0.1:8775
```

Проверка: `GET http://127.0.0.1:8775/health` →
`{"status":"ok","mode":"local","version":"0.1.0",...}`.

> Если БД создана до S03 (схема с BIGINT PK), удалите `data/pricescope.db` и
> выполните `pricescope init-db` повторно — иначе вставка упадёт (PL-010).

> **Важно:** локальный режим слушает только `127.0.0.1`. Для доступа с телефона
> в той же сети используйте `pricescope serve --local --host 0.0.0.0` и укажите
> в Flutter-настройках IP компьютера (только в доверенной сети).

---

## CLI

| Команда | Назначение |
| :--- | :--- |
| `pricescope init-db` | применить Alembic-миграции, создать БД SQLite |
| `pricescope parse --store lenta --lat … --lon … [--limit N]` | запустить парсер, записать observations (`--limit` — для smoke) |
| `pricescope parse --store pyaterochka` | ручной запуск браузерного парсера (CAPTCHA → останов) |
| `pricescope import-legacy` | импорт `lenta_prices.xlsx` + подключение `photos/{id}.png` (без копирования 10 ГБ) |
| `pricescope import-csv --file … --store pyaterochka` | ручной импорт цен в любой магазин |
| `pricescope fetch-photos` | дозагрузка фото по URL из БД (`--concurrency`, `--limit`) |
| `pricescope serve --local [--host 127.0.0.1] [--port 8775]` | API + viewer |
| `pricescope export --name product-matching --version 1` | выгрузить датасет JSONL + manifest |
| `pricescope match --run [--embeddings --reevaluate-review]` | entity resolution и переоценка спорных пар |
| `pricescope match --review` | показать очередь спорных сопоставлений |

---

## API (основные endpoints)

| Метод | URL | Назначение |
| :--- | :--- | :--- |
| `GET` | `/health` | состояние, версия, режим |
| `GET` | `/api/v1/stores` | магазины |
| `GET` | `/api/v1/products?query=&category=&page=` | поиск товаров |
| `GET` | `/api/v1/products/{id}` | карточка товара |
| `GET` | `/api/v1/observations?product_id=&store_code=&from=&to=` | история цен |
| `GET` | `/api/v1/compare?product_id=&lat=&lon=` | сравнение цен в магазинах |
| `POST` | `/api/v1/imports` | запуск импорта (idempotency key) |
| `GET` | `/api/v1/imports/{id}` | статус импорта |
| `GET` | `/api/v1/matches/review` · `POST /api/v1/matches/{id}/decide` · `POST /api/v1/matches/review/apply` | review и массовые решения |
| `POST` | `/api/v1/exports` · `GET /api/v1/exports/{id}/download` | датасеты |

Формат ошибки: `{"success": false, "error": {"code", "message", "details"}, "trace_id": "..."}`.

---

## Архитектура (коротко)

```
источники → parsers (адаптеры) → core (Observation v1) → FastAPI → SQLite/PostgreSQL
                                                          ├─ viewer (Jinja2 + HTMX, localhost)
                                                          ├─ Flutter (web + Android)
                                                          └─ ml (matching + JSONL export)
```

Подробно — [ARCHITECTURE.md](docs/development/ARCHITECTURE.md) и
[DESIGN v0.1](docs/development/v0.1/DESIGN.md).

---

## Политика парсинга

- Соблюдаем robots.txt и условия использования магазинов.
- Частота запросов консервативная, User-Agent честный.
- **CAPTCHA/антибот-проверки не обходятся**: при обнаружении парсер останавливается,
  пишет диагностику и требует ручного решения (ADR-006).
- Альтернатива при устойчивой блокировке — официальный канал данных или ручной импорт CSV.

---

## Статус v0.1.0

- [x] Design, архитектура, правила, реестр, спринты, QA-документация
- [x] Каркас пакетов `core` / `parsers` / `api` / `viewer` / `mobile` (S01–S05)
- [x] Адаптер Ленты + импорт в SQLite (S03; проверено на живом API: 3 товара)
- [x] Конвейер парсеров и фикстуры (S02–S03)
- [x] Alembic-миграции и укреплённое API: пагинация, фильтры, сравнение (S04)
- [x] Полный локальный viewer: история цен, сравнение, приёмка совпадений (S05)
- [x] Адаптер Пятёрочки + captcha-политика + ручной CSV-импорт (S06)
- [x] Сопоставление товаров, review, метрики и JSONL-экспорт (S07)
- [x] Flutter-клиент (web + Android) и релиз v0.1.0, 56 тестов (S08)

Актуальные ограничения — [RELEASES.md § 1a](docs/development/RELEASES.md#1a-известные-ограничения-релиза-v010)
и [KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

---

## Лицензия и данные

Исходный код — по лицензии репозитория. Данные и изображения товаров принадлежат
соответствующим магазинам/производителям и используются внутренне для сравнения
и обучения; источник каждой записи сохраняется в `RawSnapshot` (lineage).
