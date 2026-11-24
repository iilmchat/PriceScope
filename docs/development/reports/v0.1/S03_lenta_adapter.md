# S03 — адаптер Ленты и живой импорт в SQLite

**Дата:** 2026-11-24 · **Статус:** Done · **Правила:** RULES.md v1.0.1

## (1) Файлы (+/−)

| Файл | Изменение |
| :--- | :--- |
| `packages/parsers/pricescope_parsers/lenta/client.py` | один HTTP-клиент на прогон + `aclose()`, `page_delay`, raw snapshots, `last_items_sha` |
| `packages/parsers/pricescope_parsers/lenta/parser.py` | инъекция `LentaConfig`, пагинация, `--limit`, detail-фото, `finally: aclose()` |
| `apps/api/pricescope_api/services.py` | `run_import(limit, http_client)`, SAVEPOINT на строку, завершение ParseRun в `finally` |
| `apps/api/pricescope_api/repositories.py` | явный upsert: `new / updated / unchanged` по уникальному ключу |
| `apps/api/pricescope_api/db/models.py` | `Observation.id`: `BigInteger().with_variant(Integer, "sqlite")` |
| `apps/api/pricescope_api/schemas.py`, `routers.py`, `cli.py` | + `limit` в API и CLI |
| `packages/parsers/tests/test_lenta_parser.py` | + 6 тестов адаптера на фикстурах |
| `apps/api/tests/test_import_lenta.py` | + 2 интеграционных теста (идемпотентность, CAPTCHA → failed) |

## (2) Покрытие

- 6 тестов адаптера: все категории и 2 страницы пагинации, маппинг цен/веса/фото,
  дозапрос деталей, фильтр категории, `limit`, пустой hub, отмена, дерево категорий.
- 2 интеграционных теста: полный цикл импорт → повтор → смена цены (проверка счётчиков
  `new=4/0/0`, `updated=0/0/2`, отсутствия дублей) и CAPTCHA → `ParseRun.failed`.

## (3) Результаты

- `ruff check .` — All checks passed
- `mypy packages apps/api` — Success, 0 ошибок
- `pytest -q -p pytest_asyncio.plugin -m "not live"` — **23 passed**
- Живой запуск (реальный Integration API Ленты):
  - `pricescope parse --store lenta --limit 3` → `success, new=3, updated=0, skipped=0`
  - повтор → `success, new=0, updated=0, skipped=0`
  - в SQLite: 3 observation, 2 ParseRun, raw snapshots на месте
- Viewer с реальными данными: `GET /viewer/fragments/products?query=DEONICA` → 200, 3 строки;
  `GET /api/v1/observations?page_size=3` → 200, 3 записи.

## (4) Smoke

```powershell
Remove-Item -Force data\pricescope.db   # если БД создана до исправления PK (PL-010)
pricescope init-db
pricescope parse --store lenta --limit 3
pricescope parse --store lenta --limit 3   # new=0
pricescope serve --local                   # http://127.0.0.1:8765
```

## (5) Что не так

- Живой прогон сделан с `--limit 3` (консервативный rate limit); полный каталог
  не выгружался — это будет сделано в S05 при приёмке viewer.
- PL-010: старый `data/pricescope.db` не мигрируется, удаляется вручную; Alembic — S04.
- Адаптер Пятёрочки остаётся заготовкой (S06); CAPTCHA-политика уже проверена тестом.
- `RawSnapshot` сохраняются на диск, но retention (90 дней) ещё не реализован.

## (6) Новые PL

- **PL-010** — устаревшая SQLite-схема с BIGINT PK (Documented).
- **PL-011** — `rowcount` ON CONFLICT не различал INSERT/UPDATE (Fixed в этом же спринте).

## (7) Обоснование

Явный `SELECT` перед upsert выбран вместо `rowcount` и dialect-specific `RETURNING`:
он одинаково работает в SQLite и PostgreSQL и даёт честные счётчики для аудита.
`SAVEPOINT` на каждую строку сохраняет уже импортированные данные при единичной ошибке.
Инъекция `http_client` в `run_import` позволила прогнать полный конвейер через
MockTransport, не подменяя реестр и не обращаясь к сети в CI.
