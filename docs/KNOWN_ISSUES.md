# Известные проблемы PriceScope

Файл ведётся с версии 0.1 (ноябрь 2026).
Формат: `PL-XXX` — название, приоритет, статус, файлы.

Приоритеты: 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low
Статусы: Open / In Progress / Fixed / Documented / Deferred / Won't Fix / Resolved

---

## v0.1.0 — Design & Foundation

### PL-001 — Legacy-скрипт `lenta_parser_full.py` не запускается
- **Приоритет:** 🟠 High | **Статус:** Fixed | **Исправлено в:** v0.1.0 (S03)
- **Обнаружено:** 2026-11-24
- **Файлы:** `lenta_parser_full.py`
- **Описание:** синтаксические ошибки в строках 26, 51, 65, 105–108, 142, 146
  (`media = item.get("media") or `, `rows, offset = , 0`, `hub["hubs"]` вместо
  `hub["hubs"][0]` и т. п.). Скрипт не компилируется.
- **Решение:** функциональность перенесена в адаптер `packages/parsers/pricescope_parsers/lenta/`.
  Legacy-файлы оставлены как исторические (не удалялись).
- **Результат:** `pricescope parse --store lenta` работает с реальным API (проверено 2026-11-24,
  3 товара импортировано), повторный запуск не создаёт дубликаты.

### PL-002 — Хардкод координат, канала и Excel как единственного выхода
- **Приоритет:** 🟠 High | **Статус:** Fixed | **Исправлено в:** v0.1.0 (S03)
- **Файлы:** `lenta_parser.py`, `parser_pyaterochka*.py`
- **Описание:** координаты Наро-Фоминска, `BRAND/CHANNEL`, выход в `.xlsx`
  прописаны в коде. Нет истории цен, идентификаторов товара, lineage.
- **Решение:** конфиг через Pydantic Settings + env/CLI (`--lat`, `--lon`, `--limit`,
  `PRICESCOPE_LENTA_BRAND/CHANNEL/PAGE_LIMIT/PAGE_DELAY`); output — `Observation` в БД
  + JSONL-экспорт; сохранение `RawSnapshot`. Новый адаптер Пятёрочки тоже без хардкода (S06).

### PL-003 — Парсер Пятёрочки зависит от анти-детект стека и чувствителен к CAPTCHA
- **Приоритет:** 🔴 Critical | **Статус:** Fixed | **Исправлено в:** v0.1.0 (S06)
- **Файлы:** `ParserPyaterka/parser_pyaterochka_fixed_v5.py`
- **Описание:** 5 дублирующих версий скрипта, путь к Camoufox захардкожен,
  при CAPTCHA анализ останавливается (корректное поведение, ADR-006), но нет
  единого контракта и диагностики в БД.
- **Решение:** адаптер `pyaterochka` за портом `BrowserBackend` (браузер импортируется
  лениво, путь только из env), `CaptchaDetectedError` → `ParseRun.error_code`,
  manual CSV import как легальная альтернатива. Живой запуск — оператор вручную
  при доступности сайта; в CI — только фикстуры (отчёт S06).

### PL-004 — Отсутствуют тесты, CI и структура документации
- **Приоритет:** 🟠 High | **Статус:** Fixed | **Исправлено в:** v0.1.0 (S01–S03)
- **Описание:** в исходном репозитории не было pytest, линтеров, README и реестра проблем.
- **Решение:** S01 — pyproject, ruff/mypy/pytest, pre-commit, GitHub Actions,
  полный комплект документации.

### PL-005 — Цены хранятся как float в Excel
- **Приоритет:** 🟡 Medium | **Статус:** Documented | **Запланировано:** S01
- **Описание:** конвертация копеек в рубли через `round(kopecks / 100, 2)` теряет
  точность при агрегации и сравнении.
- **Решение:** money = `int` минорных единиц во всей системе (RULES § 4.1, ADR-001).

### PL-006 — Нет сопоставления одного товара в разных магазинах
- **Приоритет:** 🟠 High | **Статус:** Fixed | **Исправлено в:** v0.1.0 (S07)
- **Описание:** без entity resolution сравнение цен невозможно; названия и фасовки
  в Ленте и Пятёрочке различаются.
- **Решение:** `run_matching` (lexical-v1, пороги 0.70/0.90), review queue,
  `ProductMatch` с method/score/model_version; подтверждение связывает observation
  с каноническим товаром.

### PL-007 — Нет экспорта данных для обучения моделей
- **Приоритет:** 🟡 Medium | **Статус:** Fixed | **Исправлено в:** v0.1.0 (S07)
- **Решение:** `pricescope export` и `POST /api/v1/exports`: пары «два магазина — один
  товар», JSONL train/val/test + manifest (split boundaries, версии, checksum) +
  скачивание через `/exports/{id}/download`.

### PL-009 — `human_requests` ломает автозагрузку pytest-плагинов на Python 3.11
- **Приоритет:** 🟡 Medium | **Статус:** Documented | **Запланировано:** S02
- **Файлы:** `.github/workflows/ci.yml`, `scripts/dev/smoke.ps1`
- **Описание:** пакет `human_requests` (нужен только адаптеру Пятёрочки) регистрирует
  pytest11 entry point и при автозагрузке падает с `ImportError: cannot import name
  'override' from 'typing'` (тот же баг, что в legacy-парсере). Из-за этого не
  запускается весь pytest.
- **Решение:** в CI и локально задавать `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` и явно
  подключать `-p pytest_asyncio.plugin`. В S02 — вынести браузерный стек в
  отдельный extras/процесс, чтобы он вообще не импортировался в тестах ядра.

### PL-008 — Серверный режим (PostgreSQL, JWT, фоновые задачи) не реализован
- **Приоритет:** 🟡 Medium | **Статус:** Deferred | **Запланировано:** v0.2+
- **Описание:** v0.1 — только локальный режим; ARCHITECTURE § 4.1 описывает целевое
  состояние, но код роутеров авторизации и фонового планировщика отсутствует.
- **Решение:** отдельная фаза после стабилизации локального режима.

### PL-010 — Устаревший `data/pricescope.db` ломает вставку observation
- **Приоритет:** 🟠 High | **Статус:** Documented | **Обнаружено:** 2026-11-24 (S03)
- **Файлы:** `apps/api/pricescope_api/db/models.py`, `data/pricescope.db`
- **Описание:** БД, созданная до исправления PK `Observation.id` (BIGINT → INTEGER
  variant для SQLite), при первом же живом импорте падала с
  `NOT NULL constraint failed: observations.id`. Тесты на in-memory БД дефект не ловили.
- **Решение:** удалить `data/pricescope.db`, выполнить `pricescope init-db`.
  Для продуктовой схемы — Alembic-миграция (S04). Симптом повторения — та же ошибка в логе.

### PL-011 — `rowcount` ON CONFLICT не различает INSERT и UPDATE
- **Приоритет:** 🟠 High | **Статус:** Fixed | **Исправлено в:** v0.1.0 (S03)
- **Файлы:** `apps/api/pricescope_api/repositories.py`
- **Описание:** интеграционный тест показал, что при изменении цены счётчик `new`
  увеличивался вместо `updated`: `rowcount == 1` и для вставки, и для обновления.
- **Решение:** явный `SELECT` по уникальному ключу перед записью; три состояния
  `new | updated | unchanged`. Добавлен SAVEPOINT на строку, чтобы ошибка одной
  карточки не отравляла транзакцию.

### PL-012 — Некорректные версии в extras `parser5ka`
- **Приоритет:** 🟠 High | **Статус:** Fixed | **Исправлено в:** v0.1.0 (post-release)
- **Файлы:** `pyproject.toml`, `pyaterochka/browser.py`
- **Описание:** `pip install -e ".[parser5ka]"` падал: `camoufox>=0.15` и
  `human-requests>=0.4` отсутствуют в индексе; не был объявлен `pyaterochka-api`;
  `selectolax 1.0` удалил `selectolax.parser`, который импортирует `human_requests`;
  на Python 3.11 не хватает `typing.override`.
- **Решение:** версии зафиксированы (`camoufox>=0.5.3,<1`, `human-requests>=0.2.2,<1`,
  `pyaterochka-api>=0.2.2,<1`, `selectolax>=0.3.21,<1`), добавлен shim
  `typing_extensions.override`, `license` переведён на SPDX-строку.

---

## Сводка

| Статус | Количество |
| :--- | ---: |
| Fixed | 8 (PL-001…PL-004, PL-006, PL-007, PL-011, PL-012) |
| In Progress | 0 |
| Documented | 3 (PL-005, PL-009, PL-010) |
| Planned | 0 |
| Deferred | 1 (PL-008) |
| **Всего** | **12** |

> Единственный источник истины — этот файл. Сводка обновляется при каждом
> изменении статуса (RULES § 2.4).
