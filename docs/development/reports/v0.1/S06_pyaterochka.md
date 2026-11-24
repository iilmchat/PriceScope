# S06 — адаптер Пятёрочки и captcha-политика

**Дата:** 2026-11-24 · **Статус:** Done · **Правила:** RULES.md v1.0.3

## (1) Файлы (+/−)

| Файл | Изменение |
| :--- | :--- |
| `packages/parsers/pricescope_parsers/pyaterochka/browser.py` | + порт `BrowserBackend`, `CamoufoxBackend` (ленивые импорты, env-путь, совместимость Playwright, проверка CAPTCHA) |
| `packages/parsers/pricescope_parsers/pyaterochka/parser.py` | переписан: снимок → `ProductObservation` v1, маппинг цен/фото/веса, lineage |
| `packages/parsers/pricescope_parsers/pyaterochka/captcha_policy.py` | без изменений: детект → `CaptchaDetectedError` (ADR-006) |
| `packages/parsers/pricescope_parsers/base.py` | + `ParseContext.last_raw_sha` для точного `raw_ref` |
| `packages/parsers/tests/fixtures/pyaterochka/*` | + снимок каталога, captcha-снимок, CSV для ручного импорта |
| `packages/parsers/tests/test_pyaterochka.py` | + 8 тестов (парсер, captcha, отмена, цены, localStorage, CSV) |
| `apps/api/tests/test_import_pyaterochka.py` | + 3 теста (импорт + сравнение двух магазинов, идемпотентность, live-заглушка) |

## (2) Покрытие

- Адаптер на фикстуровом `BrowserBackend`: 3 товара, копейки, старая цена, фото,
  категория, доступность, `raw_ref`/`content_hash`, метаданные точки (sapCode).
- CAPTCHA → `CaptchaDetectedError` с markers; проверка, что stop ≠ bypass.
- Отмена, `health_check` без браузера, явная ошибка при отсутствии
  `CAMOUFOX_EXECUTABLE_PATH`.
- Совместимость `localStorage` старого и нового Playwright API.
- Ручной CSV-импорт с BOM.
- Интеграция: импорт Пятёрочки в SQLite → 2 сети в `/api/v1/compare`,
  дешёвое предложение и `savings_pct`; повторный запуск без дублей.

## (3) Результаты

- `ruff check .` — All checks passed · `mypy packages apps/api` — 0 ошибок, 55 файлов
- `pytest -q -p pytest_asyncio.plugin -m "not live"` — **48 passed, 1 deselected (live)**
- Реальный запуск против 5ka.ru **не выполнялся в CI**: CAPTCHA/блокировка ожидаемы;
  политика требует остановки без обхода (ADR-006). Проверено на фикстурах.

## (4) Smoke

```powershell
# Локально при наличии Camoufox и доступа к 5ka.ru:
$env:CAMOUFOX_EXECUTABLE_PATH='C:\...\camoufox.exe'
pricescope parse --store pyaterochka
# При CAPTCHA: статус failed + error_code=CAPTCHA_DETECTED в /imports

# Без браузера — легальная альтернатива:
pricescope parse --store manual --file data/products.csv
pricescope parse --store lenta --limit 3
# Открыть http://127.0.0.1:8775/compare?query=Рексона
```

## (5) Что не так

- живой запуск требует установленный `.[parser5ka]` и доступность сайта;
  в Python 3.11 `human_requests` может падать при импорте (`typing.override`) — PL-009.
- Совместимость с Playwright/human-requests реализована как monkeypatch библиотеки —
  хрупкая зона при обновлении версий; тесты фикстуровые, не контрактные к сайту.
- Фото продавца сохраняются только как URL (скачивание в `data/photos/` — S07/S08).

## (6) Новые PL

- Новых нет. PL-003 закрыт: адаптер и captcha-политика реализованы и покрыты тестами.

## (7) Обоснование

Браузер вынесен за порт `BrowserBackend`: ядро и CI тестируются без Camoufox,
а реальный адаптер подключается только по env-конфигу. Это единственный способ
сохранить ADR-002 и одновременно не тащить тяжёлый/хрупкий стек в тесты.
Дополнительная проверка CAPTCHA и после снимка исключает ситуацию, когда страница
показала проверку уже после загрузки каталога.
