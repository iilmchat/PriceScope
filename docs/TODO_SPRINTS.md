# TODO_SPRINTS — спринты PriceScope v0.1.0

**Дата:** 2026-11-24
**Design:** [docs/development/v0.1/DESIGN.md](development/v0.1/DESIGN.md) § 15
**Правила:** [docs/development/RULES.md](development/RULES.md) v1.0.0
**Всего:** 8 спринтов (S01–S08), по 2-4 задачи на спринт.

Каждый спринт: `ruff check` + `mypy` 0/0, `pytest` зелёный, отчёт по
RULES § 2.14 в `docs/development/reports/v0.1/Sxx_<name>.md`,
коммит со ссылками на PL, пуш в `main`.

---

| Спринт | Задачи | PL | Результат |
| :--- | :--- | :--- | :--- |
| **S01** | pyproject + package layout; `core`: Observation v1, money, hashing; CI (ruff/mypy/pytest); docs-каркас | PL-004, PL-005 | ✅ каркас + зелёный CI |
| **S02** | `StoreParser` + registry; ParseContext; retry/rate-limit/circuit breaker; raw snapshot; unit-тесты | PL-009 | ✅ конвейер + фикстуры + 11 тестов |
| **S03** | Lenta adapter (hub→categories→items→detail); фикстуры; CLI `parse`; импорт в SQLite | PL-001, PL-002, PL-010, PL-011 | ✅ живой импорт 3 товаров, повтор без дублей |
| **S04** | Alembic (9 таблиц, stamp legacy-БД); пагинация/фильтры/сравнение; error envelope; контрактные тесты | — | ✅ API + миграции, 33 теста |
| **S05** | Viewer: обзор, товары, карточка, сравнение, импорты, review; HTMX-фрагменты; QA-чеклист | — | локальный веб-UI |
| **S06** | Pyaterochka adapter (Camoufox), captcha policy, manual CSV import, fixtures, safety-тесты | PL-003 | второй магазин в сравнении |
| **S07** | Normalizer+blocking+matching, review queue, JSONL-экспорт + manifest, метрики качества | PL-006, PL-007 | датасет для моделей |
| **S08** | Flutter: API client, search, card, compare, favorites, settings; web+android build; release v0.1.0 | — | клиент + релиз |

---

## Статус

| Спринт | Состояние |
| :--- | :--- |
| S01 | ✅ Завершён (документация + каркас) |
| S02 | ✅ Завершён — [отчёт](development/reports/v0.1/S02_parser_pipeline.md) |
| S03 | ✅ Завершён — [отчёт](development/reports/v0.1/S03_lenta_adapter.md) |
| S04 | ✅ Завершён — [отчёт](development/reports/v0.1/S04_api_migrations.md) |
| S05–S08 | ⬜ Не начаты |

Отчёты завершённых спринтов — в `docs/development/reports/v0.1/`.
