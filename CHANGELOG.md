# Changelog

Все значимые изменения проекта фиксируются в этом файле.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- S04: Alembic (первая миграция на 9 таблиц), `pricescope init-db` + stamp для legacy-БД;
  единая пагинация, фильтры/сортировка, `GET /imports`, улучшенное сравнение цен
  (haversine, цена за кг/литр, экономия), 10 контрактных тестов и тестов миграций.
- S02: инъецируемые `clock`/`sleep` в retry/rate-limit/circuit breaker; 11 тестов
  парсеров на локальных JSON-фикстурах (без сети); реестр и raw snapshots.
- S03: адаптер Ленты доведен до рабочего состояния (hub→категории→товары→детали,
  пагинация, `--limit`, фото, lineage); интеграционный тест полного импорта в SQLite.

### Fixed
- S03: `Observation.id` (BIGINT → INTEGER variant для SQLite) — живой импорт больше не падает.
- S03: счётчики импорта различают `new / updated / unchanged` (вместо `rowcount`).
- S03: ошибка одной карточки изолируется SAVEPOINT и не отравляет транзакцию;
  `ParseRun` корректно завершается при отмене.

## [0.1.0] — 2026-11-24

### Added
- Комплект проектной документации по образцу IIChatTools: README, docs-хаб,
  RULES, ARCHITECTURE, RELEASES, DESIGN v0.1 (4 документа), KNOWN_ISSUES,
  TODO_KI, TODO_SPRINTS, USER_GUIDE, MANUAL_TESTING_GUIDE, ADR-индекс.
- Архитектурные решения ADR-001…ADR-007 (контракт observation, адаптеры,
  SQLite/PostgreSQL, HTMX, time-based split, captcha-policy, Flutter API).
- Каркас проекта: `packages/core`, `packages/parsers`, `packages/ml`,
  `apps/api`, `apps/viewer`, `apps/mobile`, CI и скрипты разработки.

### Known limitations
- Парсеры и API находятся в разработке (спринты S02–S08); поддержан только
  локальный режим. Пятёрочка — ручной запуск с остановкой на CAPTCHA.
- Legacy-скрипты `lenta_parser*.py` и Excel-файлы сохранены в корне (PL-001).

[Unreleased]: https://github.com/example/pricescope/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/example/pricescope/releases/tag/v0.1.0
