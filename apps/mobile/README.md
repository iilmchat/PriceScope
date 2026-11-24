# PriceScope Mobile (Flutter: web + Android)

Клиент сравнения цен поверх REST API `pricescope serve --local`.

## Запуск

```powershell
flutter pub get
flutter analyze
flutter test

flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8775
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8775
flutter build web --dart-define=API_BASE_URL=http://127.0.0.1:8775
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.1.10:8775
```

## Экраны

- **Поиск** — товары по названию, добавление в избранное.
- **Карточка товара** — атрибуты, график истории цен (`fl_chart`), список наблюдений.
- **Сравнение** — цены по магазинам, подсветка дешёвого, разница в процентах.
- **Избранное** — сохраняется локально через `shared_preferences` (работает офлайн).
- **Настройки** — адрес API и версия (из `--dart-define`).

## Архитектура

```
lib/core/         — конфиг, Dio-клиент с envelope, ошибки, GoRouter
lib/domain/       — сущности, порты репозиториев, use cases
lib/data/         — реализации поверх REST API и shared_preferences
lib/presentation/ — Riverpod-провайдеры, экраны, общие виджеты
```

Бизнес-логики в клиенте нет: сравнение и сопоставление выполняет API.
Подробности — [DESIGN_CLIENTS.md](../../docs/development/v0.1/DESIGN_CLIENTS.md).
