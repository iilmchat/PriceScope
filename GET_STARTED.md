# Get Started — разворачивание и первичная настройка PriceScope v0.1.0

Это пошаговое руководство: от чистого клона до работающего просмотровщика,
импорта цен и Flutter-клиента. Все команды — из корня репозитория (если не указано иначе).

**Содержание:** [1. Требования](#1-требования) · [2. Установка](#2-установка) ·
[3. Конфигурация](#3-конфигурация) · [4. База данных](#4-база-данных) ·
[5. Первый импорт](#5-первый-импорт) · [6. Запуск системы](#6-запуск-системы) ·
[7. Сопоставление и экспорт](#7-сопоставление-и-экспорт) · [8. Docker](#8-docker) ·
[9. Flutter-клиент](#9-flutter-клиент) · [10. Проверка](#10-проверка-установки) ·
[11. Устранение проблем](#11-устранение-проблем) · [12. Куда дальше](#12-куда-дальше)

---

## 1. Требования

| Компонент | Версия | Когда нужен |
| :--- | :--- | :--- |
| Python | **3.11+** (рекомендуется 3.12) | всегда |
| pip + venv | в комплекте с Python | всегда |
| SQLite | встроен | локальный режим (по умолчанию) |
| PostgreSQL | 16+ | только серверный режим (v0.2+) |
| Flutter SDK | 3.24+ (Dart 3.5+) | только клиент (веб/Android) |
| Android SDK | minSdk 24, targetSdk 35 | только сборка APK |
| Camoufox + human_requests | из extras `parser5ka` | только парсер Пятёрочки |
| Docker / Docker Compose | актуальные | опциональный способ запуска API |

Проверка:

```powershell
python --version      # Python 3.11.x или новее
git --version
```

---

## 2. Установка

### 2.1. Клонирование и виртуальное окружение

```powershell
git clone https://github.com/iilmchat/PriceScope.git
cd PriceScope

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

> Если PowerShell запрещает активацию: `Set-ExecutionPolicy -Scope Process RemoteSigned`.

### 2.2. Дополнительные зависимости (по желанию)

```powershell
# Парсер Пятёрочки (браузер; путь к Camoufox задаётся в .env)
pip install -e ".[parser5ka]"

# Эмбеддинги для будущих версий matching (в v0.1 не используются)
pip install -e ".[ml]"
```

Проверка установки:

```powershell
pricescope --version     # pricescope 0.1.0
pricescope --help        # init-db, parse, serve, export, match
```

---

## 3. Конфигурация

Скопируйте шаблон и при необходимости отредактируйте:

```powershell
Copy-Item .env.example .env
```

Основные переменные (все с префиксом `PRICESCOPE_`):

| Переменная | По умолчанию | Назначение |
| :--- | :--- | :--- |
| `PRICESCOPE_MODE` | `local` | `local` (SQLite, без авторизации) / `server` (v0.2+) |
| `PRICESCOPE_DB_PATH` | `data/pricescope.db` | файл SQLite |
| `PRICESCOPE_HOST` | `127.0.0.1` | адрес API; `0.0.0.0` — только в доверенной сети |
| `PRICESCOPE_PORT` | `8775` | порт API и просмотровщика |
| `PRICESCOPE_DEFAULT_LAT` / `..._LON` | `55.3925` / `36.7323` | точка для поиска ближайшего магазина |
| `PRICESCOPE_LENTA_BRAND` / `..._CHANNEL` | `lo` / `lo` | витрина и канал Ленты |
| `PRICESCOPE_LENTA_PAGE_LIMIT` | `50` | размер страницы каталога |
| `PRICESCOPE_LENTA_PAGE_DELAY` | `0.3` | пауза между страницами (сек) |
| `CAMOUFOX_EXECUTABLE_PATH` | — | **обязателен для Пятёрочки**, путь именно к `camoufox.exe`, например `C:\Users\Z1\AppData\Local\camoufox\camoufox-158.0.1-beta.41\camoufox.exe` |
| `PRICESCOPE_PROXY` | — | опциональный прокси для браузера |

**Секреты не коммитятся**: `.env` уже в `.gitignore`. Никогда не храните ключи/пароли
в `appsettings` или исходниках.

---

## 4. База данных

Схема управляется **только Alembic** (`create_all` в проде запрещён):

```powershell
pricescope init-db
```

Что происходит:
- применяется миграция `5c70c265161b_initial_schema` (9 таблиц);
- если БД уже существовала от старого `create_all` и в ней нет `alembic_version` —
  выполняется `stamp head` без потери истории цен (PL-010).

Проверить состояние и историю миграций (из каталога `apps/api`):

```powershell
cd apps/api
alembic -c alembic.ini current
alembic -c alembic.ini history
cd ../..
```

> Если БД создана до S04 и при импорте падает `NOT NULL constraint failed: observations.id`,
> удалите `data/pricescope.db` и снова выполните `pricescope init-db`.

---

## 5. Первый импорт

### 5.1. Лента (рекомендуемый старт)

```powershell
# Быстрая проверка: 3 товара
pricescope parse --store lenta --limit 3

# Полный каталог для своей точки
pricescope parse --store lenta --lat 55.3925 --lon 36.7323

# С дозапросом детальных карточек (фото) — медленнее
pricescope parse --store lenta --details
```

Ожидаемый вывод: `Импорт #1: success · new=3 updated=0 skipped=0 trace=...`.
Повторный запуск тех же данных даёт `new=0` — это нормально (идемпотентность).

### 5.2. Пятёрочка (опционально)

```powershell
# задайте CAMOUFOX_EXECUTABLE_PATH в .env и установите extras parser5ka
pricescope parse --store pyaterochka
```

> При обнаружении CAPTCHA парсер **останавливается** и пишет
> `error_code=CAPTCHA_DETECTED` в журнал импортов. Автоматический обход запрещён
> (ADR-006). Не запускайте повторно сразу — дождитесь восстановления доступа.

### 5.3. Ручной импорт CSV (без браузера)

Легальная альтернатива при блокировке сайта. Обязательные колонки:
`external_id,name,price_minor` (цена — **копейки**), опционально `package`, `category_path`.

```powershell
pricescope parse --store manual --file data/products.csv
```

### 5.4. Ручной импорт цен конкретного магазина

Если живой парсер магазина недоступен (например, 5ka.ru блокирует `fetch()`),
можно завести цены вручную через CSV. Обязательные колонки: `external_id,name,price_minor`
(цена в копейках), опционально `category_path`, `package`, `location_id`, `image_url`.

```powershell
pricescope import-csv --file docs/examples/pyaterochka_manual.csv --store pyaterochka
```

Пример в репозитории содержит реальную цену товара из карточки 5ka.ru (99,99 ₽).
Повторный импорт того же файла не создаёт дубликаты.

### 5.5. Импорт исторических данных из Excel и папки photos

Если в корне проекта уже лежит `lenta_prices.xlsx` из старых скриптов
(и `photos/{id}.png`), перенесите их в БД одной командой:

```powershell
pricescope import-legacy
# либо явно: pricescope import-legacy --excel lenta_prices.xlsx --photos photos
```

Что делает команда:
- читает Excel через `openpyxl`, мапит копейки/обычную цену/вес/категорию;
- создаёт `RawSnapshot` по sha256 файла; временем наблюдения считается **mtime файла**;
- подключает фото как `/legacy-photos/{id}.png` — каталог `photos/` (~10 ГБ)
  **не копируется**, а монтируется к viewer доступом только для чтения;
- повторный запуск ничего не дублирует (идемпотентно).

Результат для текущего файла: 31 228 товаров, 23 050 из них с локальным фото.

### 5.6. Дозагрузка оставшихся фото

У части товаров локального фото не было, но в Excel осталась ссылка на CDN.
Скачайте их отдельной командой:

```powershell
pricescope fetch-photos --concurrency 12
# ограничить количество: pricescope fetch-photos --limit 100
```

Файлы складываются в `data/photos/lenta/{id}/`, viewer отдаёт их через `/photos/...`.
Путь хранится в отдельном поле `photo_path` и **не меняет `content_hash` цены** —
повторный импорт Excel не откатит результат. У товаров без URL останется заглушка.

### 5.7. Проверка импорта

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/pricescope.db'); print(c.execute('select count(*) from observations').fetchone()[0])"
```

---

## 6. Запуск системы

```powershell
pricescope serve --local
# http://127.0.0.1:8775          — просмотровщик
# http://127.0.0.1:8775/health   — проверка состояния
# http://127.0.0.1:8775/docs     — OpenAPI / Swagger
```

Доступные экраны просмотровщика:

| URL | Что показывает |
| :--- | :--- |
| `/` | обзор: счётчики и последние импорты |
| `/products` | каталог с регистронезависимым поиском по подстроке, выпадающим списком категорий и пагинацией |
| `/product?external_id=…&store_code=…` | карточка с историей цен и SVG-графиком |
| `/compare?query=…` | сравнение цен в магазинах |
| `/imports` | журнал запусков парсеров, ошибки, `trace_id` |
| `/matches` | очередь спорных сопоставлений |
| `/settings` | режим, пути, политика парсинга |

**Доступ с телефона в той же сети** (только доверенная сеть!):

```powershell
pricescope serve --local --host 0.0.0.0 --port 8775
# в Flutter: --dart-define=API_BASE_URL=http://192.168.1.10:8775
```

---

## 7. Сопоставление и экспорт

```powershell
# Сопоставить товары (≥0.90 auto, 0.70–0.90 review, иначе новый Product)
pricescope match --run

# Посмотреть спорные пары
pricescope match --review

# Сформировать датасет (только при наличии пар двух магазинов)
pricescope export --name product-matching --version 1
```

Результат экспорта — `datasets/exports/product-matching-v1/`:

```
train.jsonl  val.jsonl  test.jsonl  manifest.json  checksums.sha256
```

Эквивалентно через API:

```powershell
# POST /api/v1/matches/run
# GET  /api/v1/matches/review
# POST /api/v1/exports  {"name":"product-matching","version":"1"}
# GET  /api/v1/exports/1/download?file=train.jsonl
# GET  /api/v1/metrics
```

> Если `pair_count = 0` — в базе нет подтверждённых пар из разных магазинов.
> Импортируйте обе сети и подтвердите совпадения на `/matches`.

---

## 8. Docker

```powershell
docker compose up --build
```

API и viewer будут доступны на `http://localhost:8775`. Данные монтируются
в `./data` и `./datasets` — они сохраняются между перезапусками контейнера.

---

## 9. Flutter-клиент

```powershell
cd apps/mobile
flutter pub get
flutter analyze
flutter test

# Веб
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8775
flutter build web --dart-define=API_BASE_URL=http://127.0.0.1:8775

# Android (устройство/эмулятор в той же сети)
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8775
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.1.10:8775
```

> Flutter SDK на машине разработки v0.1 не установлен — Dart-код проверяется CI-job
> (`flutter analyze` / `flutter test` / `flutter build web`). Для Android нужны
> Android SDK и `platforms/android` (в репозитории — конфигурация gradle/manifest).

---

## 10. Проверка установки

Чек-лист быстрой приёмки (полный — в [qa/MANUAL_TESTING_GUIDE.md](docs/qa/MANUAL_TESTING_GUIDE.md)):

```powershell
pricescope --version                       # 0.1.0
ruff check .                               # All checks passed
mypy packages apps/api                     # 0 ошибок
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q -p pytest_asyncio.plugin -m "not live"   # 56 passed
pwsh -File scripts/ci/check-doc-links.ps1  # Ссылки документации OK
```

После запуска сервера в браузере:

- [ ] `/health` → `status=ok`, `mode=local`
- [ ] `/products` → таблица с импортированными товарами
- [ ] `/product?external_id=…` → история цен и график
- [ ] `/compare?query=…` → строки магазинов (при наличии данных)
- [ ] `/imports` → запись ParseRun со статусом `success`

---

## 11. Устранение проблем

| Симптом | Причина | Решение |
| :--- | :--- | :--- |
| `pytest` падает с `ImportError: cannot import name 'override' from 'typing'` | `human_requests` регистрирует сломанный pytest11-плагин на Python 3.11 (PL-009) | `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest -p pytest_asyncio.plugin` — уже в CI и скриптах |
| `no such table: parse_runs` при `parse` из `apps/api` | путь к БД резолвился относительно CWD (PL-013) | после обновления пути привязаны к корню; удалить пустой `apps/api/data/pricescope.db`, повторить команду |
| `NOT NULL constraint failed: observations.id` при импорте | устаревшая SQLite-схема (PL-010) | удалить `data/pricescope.db`, `pricescope init-db` |
| `Для парсера Пятёрочки задайте CAMOUFOX_EXECUTABLE_PATH` | не задан путь к браузеру | указать путь в `.env`, установить `.[parser5ka]` |
| `CAPTCHA_DETECTED` в журнале импортов | антибот-проверка сайта | не обходить; дождаться доступа или использовать `--store manual` |
| `Адрес уже используется` | занят порт 8775 | `pricescope serve --local --port 8766` |
| Русский текст в консоли «крокозябрами» | кодировка консоли cp866 | `chcp 65001` в PowerShell перед запуском |
| `/compare` пуст | нет данных второго магазина или параметры не совпадают | импортировать Пятёрочку/CSV, проверить `query`, запустить `match --run` |
| Экспорт с 0 строками | нет подтверждённых пар разных магазинов | подтвердить пары на `/matches`, повторить экспорт |

---

## 12. Куда дальше

- [README.md](README.md) — обзор проекта, CLI и API
- [docs/README.md](docs/README.md) — хаб документации по ролям
- [docs/user_guide/USER_GUIDE.md](docs/user_guide/USER_GUIDE.md) — пользовательские сценарии
- [docs/development/ARCHITECTURE.md](docs/development/ARCHITECTURE.md) — слои, БД, потоки
- [docs/development/RELEASES.md](docs/development/RELEASES.md) — ограничения и процесс релиза
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — реестр PL-XXX
- [CHANGELOG.md](CHANGELOG.md) — история версий
