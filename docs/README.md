# Документация PriceScope v0.1.x

**Обновлено:** 2026-11-24
**Назначение:** единая точка входа в документацию проекта. Выберите роль —
и переходите по ссылке.

---

## С чего начать

| Роль | Куда идти |
| :--- | :--- |
| **Пользователь** | [user_guide/USER_GUIDE.md](user_guide/USER_GUIDE.md) — локальный viewer, Flutter-клиент, сравнение |
| **Тестировщик** | [qa/MANUAL_TESTING_GUIDE.md](qa/MANUAL_TESTING_GUIDE.md) — чек-лист ручной приёмки |
| **Разработчик** | [development/RULES.md](development/RULES.md) → [development/ARCHITECTURE.md](development/ARCHITECTURE.md) → [development/RELEASES.md](development/RELEASES.md) |
| **Впервые в проекте** | [README.md](../README.md) — установка, CLI, API, обзор |

---

## Структура

```text
docs/
├── README.md                    ← этот хаб
├── KNOWN_ISSUES.md              ← реестр проблем (PL-XXX)
├── TODO_KI.md                   ← план устранения PL
├── TODO_SPRINTS.md              ← разбивка на спринты S01–S08
├── user_guide/
│   └── USER_GUIDE.md            ← пользовательские сценарии
├── qa/
│   └── MANUAL_TESTING_GUIDE.md  ← ручная приёмка
└── development/
    ├── RULES.md                 ← правила разработки (v1.0.2)
    ├── ARCHITECTURE.md          ← слои, БД, DI, потоки, ADR
    ├── RELEASES.md              ← процесс релиза
    ├── adr/                     ← архитектурные решения (ADR-001…007)
    ├── reports/                 ← отчёты по задачам/спринтам
    ├── v0.1/                    ← дизайн v0.1
    │   ├── DESIGN.md            ← общий дизайн платформы
    │   ├── DESIGN_PARSERS.md    ← слой парсеров
    │   ├── DESIGN_DATA_ML.md    ← данные, matching, экспорт
    │   └── DESIGN_CLIENTS.md    ← viewer и Flutter
    └── archive/                 ← устаревшие документы
```

---

## Пользователям

- [Руководство пользователя](user_guide/USER_GUIDE.md) — локальный просмотр,
  сравнение цен, история, клиент.
- [Реестр известных проблем](KNOWN_ISSUES.md) — формат `PL-XXX`.
- [История версий](../CHANGELOG.md) · [Установка](../README.md).

## Тестировщикам

- [Чек-лист ручной приёмки](qa/MANUAL_TESTING_GUIDE.md) — smoke, regression, UI/UX.
- Автотесты: `pytest -q` (unit/contract/integration, без сети) +
  `flutter test` (клиент).
- Найденный дефект → запись `PL-XXX` в [KNOWN_ISSUES.md](KNOWN_ISSUES.md) (RULES § 1.13).

## Разработчикам

- [RULES.md](development/RULES.md) — обязательные правила (v1.0.2).
- [ARCHITECTURE.md](development/ARCHITECTURE.md) — слои, схема БД, DI, потоки, ADR.
- [RELEASES.md](development/RELEASES.md) — чек-лист релиза.
- [ADR-индекс](development/adr/README.md) — архитектурные решения.
- Дизайн v0.1: [общий](development/v0.1/DESIGN.md),
  [парсеры](development/v0.1/DESIGN_PARSERS.md),
  [данные/ML](development/v0.1/DESIGN_DATA_ML.md),
  [клиенты](development/v0.1/DESIGN_CLIENTS.md).

---

## Правила работы с документацией

1. **RULES § 2.1–2.4** — документация обновляется в том же коммите, что и код.
2. **RULES § 2.10** — Markdown с code-блоками в чате оборачивается в 4 бэктика снаружи.
3. **RULES § 2.11** — большие MD-файлы не выводятся в чат целиком, только точечные diff'ы.
4. **Ссылки** — только относительные; проверка: `scripts/ci/check-doc-links.ps1`.
5. **Новый PL** — в [KNOWN_ISSUES.md](KNOWN_ISSUES.md), формат `### PL-XXX — Название`.
