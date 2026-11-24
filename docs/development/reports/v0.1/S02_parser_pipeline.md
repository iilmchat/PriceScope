# S02 — конвейер парсеров и фикстуры

**Дата:** 2026-11-24 · **Статус:** Done · **Правила:** RULES.md v1.0.1

## (1) Файлы (+/−)

| Файл | Изменение |
| :--- | :--- |
| `packages/parsers/pricescope_parsers/resilience.py` | переписан: `clock`/`sleep`/`jitter` — инъецируемые зависимости; transient-exceptions дополнены |
| `packages/parsers/tests/conftest.py` | + общие фикстуры: `load_fixture`, `make_lenta_handler`, `make_http_client`, `make_context`, `lenta_parser` |
| `packages/parsers/tests/fixtures/lenta/*.json` | + 7 локальных JSON-ответов (hub, categories, 3×items, detail, updated prices) |
| `packages/parsers/tests/test_resilience.py` | + 5 тестов retry/circuit breaker/rate limiter |
| `packages/parsers/tests/test_registry_and_snapshots.py` | + 4 теста реестра и raw snapshots |
| `packages/parsers/tests/__init__.py` | + пакет тестов (относимые импорты) |

## (2) Покрытие

- 9 новых тестов: transient-retry (503→успех, задержки 1/2 с), отказ от retry на 400,
  проброс `CancelledError`, circuit breaker open/cooldown/recover, rate limiter с fake clock,
  реестр 3 адаптеров, `UnknownStoreError`, идемпотентное сохранение snapshot, sync API.
- Тесты **не ходят в сеть**: `httpx.MockTransport` + JSON-фикстуры.

## (3) Результаты

- `ruff check .` — All checks passed
- `mypy packages apps/api` — Success, 0 ошибок
- `pytest -q -p pytest_asyncio.plugin -m "not live"` — 23 passed (после S03)

## (4) Smoke

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q -p pytest_asyncio.plugin -m "not live"
# 23 passed
```

## (5) Что не так

- PL-009 остаётся обходным решением: `human_requests` регистрирует сломанный
  pytest11 entry point, поэтому autoload плагинов отключён в CI и скриптах.
- Полные фикстуры для Пятёрочки появятся в S06; здесь проверен только общий конвейер.

## (6) Новые PL

- Новых нет (PL-009 задокументирован на этапе S01).

## (7) Обоснование

Время и ожидание вынесены в параметры конструкторов — это позволило сделать тесты
retry/limit детерминированными и мгновенными, не меняя production-поведение.
Фикстуры хранятся как байты, поэтому `content_hash` raw snapshot в тестах совпадает
с реальным путём сохранения.
