# S04 — Alembic и укрепление API

**Дата:** 2026-11-24 · **Статус:** Done · **Правила:** RULES.md v1.0.2

## (1) Файлы (+/−)

| Файл | Изменение |
| :--- | :--- |
| `apps/api/alembic.ini`, `migrations/env.py`, `migrations/script.py.mako` | + конфигурация Alembic (синхронный URL, batch mode для SQLite) |
| `apps/api/migrations/versions/5c70c265161b_initial_schema.py` | + autogenerate-миграция на 9 таблиц |
| `apps/api/pricescope_api/db/session.py` | `init_db` → Alembic; `stamp head` для наследуемых БД; `downgrade_db` |
| `apps/api/pricescope_api/config.py` | + `sync_database_url`, `auto_migrate` |
| `apps/api/pricescope_api/pagination.py` | + единый контракт пагинации |
| `apps/api/pricescope_api/routers.py` | фильтры/сортировка/пагинация, `GET /imports`, `query` в compare, валидация параметров |
| `apps/api/pricescope_api/middleware.py` | 422-ошибки в едином envelope |
| `apps/api/pricescope_api/services.py` | compare: haversine + цена за кг/литр + savings_pct; seed магазинов; сохранение StoreLocation |
| `apps/api/pricescope_api/repositories.py` | + `upsert_store_location`, `seed_stores`, `product_id` в upsert observation |
| `apps/api/tests/test_contracts.py`, `test_alembic.py` | + 10 тестов |

## (2) Покрытие

- Alembic: upgrade → downgrade → upgrade; stamp наследуемой БД без потери данных.
- Контракты: 404/422 envelope, `extra=forbid`, пагинация и сортировка товаров,
  фильтры observations по магазину/дате, сравнение (дешёвый, цена за литр, экономия),
  400 при отсутствии цели сравнения, наличие новых маршрутов в OpenAPI.

## (3) Результаты

- `ruff check .` — All checks passed · `mypy packages apps/api` — 0 ошибок, 51 файл
- `pytest -q -p pytest_asyncio.plugin -m "not live"` — **33 passed**
- Smoke на реальной БД: `/api/v1/stores` → 3; `/observations?store_code=lenta` → total=3;
  `/compare?query=DEONICA` → 1 строка; `/imports` → total=2
- `pricescope init-db` на БД, созданной до S04: `Running stamp_revision -> 5c70c265161b`,
  данные сохранены.

## (4) Smoke

```powershell
pricescope init-db
cd apps/api
alembic -c alembic.ini current
alembic -c alembic.ini history
cd ../..
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q -p pytest_asyncio.plugin -m "not live"
```

## (5) Что не так

- `GET /products` пока пуст: канонические товары создаются только в S07 (matching).
  Сравнение по `query` работает напрямую по названиям observation.
- Alembic в SQLite «не транзакционный DDL» — при сбое середины миграции возможна
  частичная схема; для prod-PostgreSQL эта проблема снимается транзакциями DDL.
- Генерация новых миграций требует запуска `alembic` из `apps/api` (относительный
  `script_location`) — зафиксировано в ARCHITECTURE.md § 3.5.

## (6) Новые PL

- Новых нет. PL-010 переведён в режим «миграция есть, старые БД stamp-ятся».

## (7) Обоснование

Единая пагинация и error envelope убирают разнобой между эндпоинтами и упрощают
Flutter-клиенту разбор ответов. Явный `stamp` для наследуемых БД сохраняет историю цен
(которая ценнее схемы) и позволяет перейти на Alembic без пересоздания данных.
Сравнение через haversine и цену за литр/кг делает результат осмысленным при разных
фасовках, а `savings_pct` — сразу понятным пользователю.
