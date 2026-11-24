# Changelog

Все значимые изменения проекта фиксируются в этом файле.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- (записи добавляются в каждом коммите с кодом — RULES § 2.1)

## [0.1.0] — 2026-11-24

**Тема:** Design & Foundation — рабочая платформа сравнения цен локально и в браузере.

### Added
- Документация: README, docs-хаб, RULES v1.0.4, ARCHITECTURE, RELEASES, DESIGN v0.1
  (4 документа), ADR-001…007, KNOWN_ISSUES, TODO_KI, TODO_SPRINTS, USER_GUIDE,
  QA-чеклист, отчёты S01–S08.
- Ядро: `ProductObservation` v1 (цена в копейках, UTC, content_hash, raw lineage),
  нормализация названий и мер, money-утилиты.
- Парсеры: порт `StoreParser`, реестр, retry/rate-limit/circuit breaker с инъецируемым
  временем, raw snapshots, адаптер Ленты (пагинация, фото, `--limit`),
  адаптер Пятёрочки за портом `BrowserBackend` с captcha-политикой, ручной CSV-импорт.
- Хранение: SQLAlchemy 2, Alembic (9 таблиц, stamp для legacy-БД), SQLite локально.
- API: FastAPI, единая пагинация и error envelope, фильтры/сортировка, сравнение цен
  с haversine и ценой за кг/литр, `/metrics`, экспорт и скачивание датасета.
- Viewer: 8 экранов (обзор, каталог, карточка с SVG-графиком, сравнение, импорты,
  review совпадений, настройки), HTMX-фрагменты без JS-сборки.
- ML: lexical entity resolution (0.70/0.90), review и подтверждение пар, JSONL
  train/val/test + manifest + checksum.
- Клиент: Flutter (web + Android) — поиск, карточка с графиком, сравнение, избранное
  (shared_preferences), настройки; Clean Architecture + Riverpod + GoRouter + Dio.
- Инфраструктура: CI (ruff/mypy/pytest/Flutter), Docker Compose, PowerShell-скрипты.

### Fixed
- SQLite BIGINT PK не автоинкрементировался при живом импорте (PL-010).
- Счётчики импорта различали insert/update через `rowcount` (PL-011).
- Ошибка одной карточки изолируется SAVEPOINT; `ParseRun` завершается при отмене.
- Legacy-скрипты с синтаксическими ошибками заменены адаптерами (PL-001/002).

### Known limitations
- Эмбеддинги CLIP/SentenceTransformers не подключены (только lexical-скоринг).
- Живой запуск Пятёрочки требует Camoufox и доступности сайта; CAPTCHA → останов.
- Flutter release-подпись Android и мультипользовательский серверный режим — v0.2+.

[Unreleased]: https://github.com/example/pricescope/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/example/pricescope/releases/tag/v0.1.0
