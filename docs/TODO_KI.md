# TODO_KI — план устранения проблем PriceScope

**Дата:** 2026-11-24
**Источник:** [KNOWN_ISSUES.md](KNOWN_ISSUES.md) (единственный source of truth)
**Правила:** [development/RULES.md](development/RULES.md) v1.0.0
**Спринты:** [TODO_SPRINTS.md](TODO_SPRINTS.md)

---

## Приоритет 1 (блокеры MVP)

| PL | Проблема | Спринт | Статус |
| :--- | :--- | :--- | :--- |
| PL-004 | Тесты, CI, структура документации | S01 | Fixed |
| PL-005 | Деньги = int минорных единиц | S01 | Documented |
| PL-009 | human_requests ломает pytest-плагины на Py3.11 | S02 | Documented |
| PL-010 | Устаревшая SQLite-схема (BIGINT PK) | S03 | Documented |
| PL-011 | rowcount ON CONFLICT ≠ insert/update | S03 | Fixed |
| PL-001 | Сломанный legacy-парсер Ленты | S03 | Fixed (заменён адаптером) |
| PL-002 | Хардкод координат/канала, Excel-only | S03 | Fixed |

## Приоритет 2 (ядро платформы)

| PL | Проблема | Спринт | Статус |
| :--- | :--- | :--- | :--- |
| PL-003 | Пятёрочка: анти-бот, CAPTCHA, дубли кода | S06 | Fixed |
| PL-006 | Entity resolution / сравнение товаров | S07 | Planned |
| PL-007 | Экспорт датасета для ML | S07 | Planned |

## Приоритет 3 (после MVP)

| PL | Проблема | Спринт | Статус |
| :--- | :--- | :--- | :--- |
| PL-008 | PostgreSQL + JWT + фоновые задачи | v0.2+ | Deferred |

---

## Как работать с реестром

1. Новая проблема → `PL-XXX` в [KNOWN_ISSUES.md](KNOWN_ISSUES.md), статус `Open`.
2. При взятии в работу → `In Progress`, ссылка на спринт.
3. Исправление → `Fixed` + версия, в commit message — `PL-XXX` (RULES § 2.8).
4. Не баг, а ограничение → `Documented` с обоснованием.
5. Сводка внизу KNOWN_ISSUES обновляется в том же коммите.

Список не дублирует описания — только приоритет и маршрутизация по спринтам.
