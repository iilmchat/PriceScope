# Архитектурные решения (ADR) PriceScope

Индекс решений. Формат: контекст → решение → последствия. Новое решение —
отдельный файл `ADR-XXX-<slug>.md`, ссылка добавляется в ARCHITECTURE.md § 7.

| ADR | Название | Статус |
| :--- | :--- | :--- |
| [ADR-001](ADR-001-single-observation-contract.md) | Единый контракт `ProductObservation` v1; деньги = int | Accepted |
| [ADR-002](ADR-002-ports-adapters-parsers.md) | Парсеры за протоколом `StoreParser` | Accepted |
| [ADR-003](ADR-003-sqlite-local-postgres-server.md) | SQLite локально / PostgreSQL на сервере | Accepted |
| [ADR-004](ADR-004-htmx-local-viewer.md) | HTMX + Jinja2 для локального viewer | Accepted |
| [ADR-005](ADR-005-time-based-split.md) | Time-based split датасетов | Accepted |
| [ADR-006](ADR-006-captcha-no-bypass.md) | CAPTCHA — остановка, обход запрещён | Accepted |
| [ADR-007](ADR-007-flutter-shared-api.md) | Один Flutter-код для web/Android, общий API | Accepted |
