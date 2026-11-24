# S08 — Flutter-клиент и релиз v0.1.0

**Дата:** 2026-11-24 · **Статус:** Done · **Правила:** RULES.md v1.0.4

## (1) Файлы (+/−)

| Файл | Изменение |
| :--- | :--- |
| `apps/mobile/pubspec.yaml` | dependencies: riverpod, go_router, dio, fl_chart, cached_network_image, shared_preferences, intl |
| `lib/core/` | config (dart-define), ApiClient с разбором envelope и trace-id, failures, GoRouter |
| `lib/domain/` | сущности, порты репозиториев, use cases (Search/Details/History/Compare/Favorites) |
| `lib/data/` | REST-реализация каталога, DTO-парсеры, избранное в shared_preferences |
| `lib/presentation/` | провайдеры, экраны поиска/карточки/сравнения/избранного/настроек, общие виджеты |
| `test/widget_test.dart` | тесты парсера DTO и PriceBadge (без сети) |
| `android/` | gradle-файлы, MainActivity.kt, manifest'ы (minSdk 24, targetSdk 35) |
| `apps/api/.../routers.py` | + фильтр `external_id` в `/observations` (для истории клиента) |
| `CHANGELOG.md`, `README.md`, `RELEASES.md`, `TODO_SPRINTS.md` | релиз v0.1.0 |

## (2) Покрытие

- Тесты Dart: разбор DTO товара из ответа API, рендер цены в `PriceBadge`.
- CI-job Flutter: `flutter analyze`, `flutter test`, `flutter build web`.
- API: контрактный тест нового фильтра `external_id`.

## (3) Результаты

- `ruff check .` — OK · `mypy packages apps/api` — 0 ошибок, 57 файлов
- `pytest -q -p pytest_asyncio.plugin -m "not live"` — **56 passed, 1 deselected**
- `pricescope --version` → 0.1.0; Alembic head, экспорт и API smoke — без регрессий.
- Flutter SDK на машине разработки отсутствует: проверки Dart-кода выполняются в CI
  (`apps/mobile` job), локальная сборка не запускалась.

## (4) Smoke

```powershell
pricescope serve --local
cd apps/mobile
flutter pub get
flutter analyze
flutter test
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8765
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.1.10:8765
```

## (5) Что не так

- Flutter SDK не установлен локально — ошибки анализа/сборки Dart могут проявиться
  только в CI; это задокументировано в RELEASES.md § 1a.
- Избранное хранится в `shared_preferences` (v0.1); `drift`/SQLite — v0.2.
- Release-подпись Android (upload keystore) — v0.2; в v0.1 используется debug signing.
- Сканер штрихкода и push-уведомления о снижении цены — v0.2.

## (6) Новые PL

- Новых нет. Все спринты S01–S08 закрыты.

## (7) Обоснование

Клиент не содержит бизнес-логики: сравнение, entity resolution и экспорт выполняет
API, а Flutter только отображает данные и кэширует избранное. Использование
`shared_preferences` вместо `drift` убрало необходимость codegen в релизной сборке
v0.1 — это осознанный компромисс ради стабильности CI.
