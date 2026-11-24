# PriceScope Mobile (Flutter: web + Android)

Клиент сравнения цен поверх REST API `pricescope serve --local`.

## Запуск

```powershell
flutter pub get
flutter analyze
flutter test

flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8765
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8765
flutter build web --dart-define=API_BASE_URL=http://127.0.0.1:8765
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.1.10:8765
```

## Структура

- `lib/core` — конфиг, Dio-клиент, ошибки, роутер.
- `lib/data` — DTO и реализации репозиториев.
- `lib/domain` — абстракции репозиториев (чистая архитектура).
- `lib/presentation` — экраны поиска, сравнения, настроек.

Подробности — [DESIGN_CLIENTS.md](../../docs/development/v0.1/DESIGN_CLIENTS.md).
