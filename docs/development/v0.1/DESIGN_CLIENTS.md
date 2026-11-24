# DESIGN_CLIENTS — локальный просмотровщик и Flutter-клиент PriceScope v0.1

**Версия:** 1.0 · **Дата:** 2026-11-24 · **Статус:** Accepted
**Связанные:** [DESIGN.md](DESIGN.md) § 9–10; [ARCHITECTURE.md](../ARCHITECTURE.md)

---

## § 1. Общая идея

Оба клиента используют **один и тот же REST API**. Разница только в точке
подключения: локальный viewer — `http://127.0.0.1:8765`, Flutter — local IP
или серверный URL. Никакой бизнес-логики в клиентах (только представление и кэш).

---

## § 2. Локальный просмотровщик (`apps/viewer`)

### § 2.1. Стек

- FastAPI `APIRouter` + `Jinja2Templates` + HTMX-атрибуты (CDN не нужен — JS/CSS
  лежат в `apps/viewer/static/`, работает офлайн). В каркасе S01 используется
  минимальный `static/htmx-lite.js` (`hx-get`/`hx-target`/`hx-trigger`);
  в S05 планируется замена на полный локальный vendor-HTMX;
- Alpine.js — только для мелких состояний (открытие модалки, toast);
- HTMX-фрагменты: `GET /viewer/fragments/products?...` → кусок HTML таблицы.

### § 2.2. Экраны

| Экран | Что показывает | Ключевые действия |
| :--- | :--- | :--- |
| `Обзор` | последний `ParseRun`, счётчики, статус БД,(last import) | «Запустить импорт» |
| `Товары` | таблица: фото, название, категория, магазин, цена, дата | поиск (debounce 250 мс), фильтр по магазину/категории, сортировка, пагинация |
| `Карточка товара` | атрибуты, фото, график/таблица истории цен | переключение периода (7/30/90 дней) |
| `Сравнение` | товар × цена в Ленте / Пятёрочке, разница % | выбор точки (lat/lon), экспорт CSV |
| `Импорты` | журнал `ParseRun`: статус, счётчики, ошибки | просмотр ошибки, повтор |
| `Совпадения` | очередь review (`0.70…0.90`) | «один товар / разные» |
| `Настройки` | координаты, channel/retailBrand, лимиты, retention | сохранить (env/локальный конфиг) |

### § 2.3. Запуск

```powershell
pip install -e ".[dev]"
pricescope init-db
pricescope parse --store lenta --lat 55.3925 --lon 36.7323
pricescope serve --local
# http://127.0.0.1:8765
```

---

## § 3. Flutter-клиент (`apps/mobile`)

### § 3.1. Архитектура и зависимости

> **Статус S08:** клиент реализован (поиск, карточка с `fl_chart`, сравнение,
> избранное, настройки). Офлайн-хранение избранного в v0.1 — `shared_preferences`;
> `drift` перенесён на v0.2 (удалён из зависимостей, чтобы не требовать codegen).

```
lib/
├── main.dart                  # инициализация, flavor-конфиг
├── app.dart                   # MaterialApp.router, темы, Riverpod Scope
├── core/
│   ├── config.dart            # --dart-define API_BASE_URL
│   ├── router.dart            # GoRouter
│   ├── api_client.dart        # Dio + interceptors (trace_id, error map)
│   └── failures.dart
├── data/
│   ├── models/                # ProductDto, ObservationDto, CompareDto (freezed/json_serializable)
│   ├── repositories/          # RepositoryImpl, Dio-источник
│   └── local/                 # shared_preferences — избранное (v0.1)
├── domain/
│   ├── entities/              # Product, PricePoint, Comparison
│   ├── usecases/              # SearchProducts, GetCompare, GetHistory, ManageFavorites
│   └── repositories.dart      # абстракции
└── presentation/
    ├── search/                # поиск + фильтры
    ├── product/               # карточка, fl_chart история цен
    ├── compare/               # сравнение магазинов
    ├── favorites/             # избранное + алерты
    ├── settings/              # URL сервера, local mode
    └── widgets/               # PriceBadge, ProductTile, EmptyState
```

Зависимости: `flutter_riverpod`, `go_router`, `dio`, `freezed`,
`shared_preferences`, `fl_chart`, `cached_network_image`, `intl`
(shimmer, cached_network_image — опционально).

### § 3.2. Экраны MVP

1. **Поиск** — запрос, фильтры по магазину/категории, результаты с фото и ценой.
2. **Карточка товара** — атрибуты, фото, история цен (fl_chart), список observation.
3. **Сравнение** — по выбранному товару/категории: цены по магазинам, «дешевле на X %»,
   дата обновления (observed_at).
4. **Избранное** — локально в `shared_preferences`; алерты на снижение цены — v0.2.
5. **Настройки** — `API_BASE_URL`, таймаут, режим (local/server), очистка кэша.

### § 3.3. Сборка и flavors

```powershell
flutter pub get
flutter analyze
flutter test
flutter build web --dart-define=API_BASE_URL=http://127.0.0.1:8765
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.1.10:8765
# flutter build appbundle --release --dart-define=API_BASE_URL=https://api.example.com
```

Android: minSdk 24, targetSdk 35, flavor `dev`/`prod` через `--dart-define`.
разрешение INTERNET добавляется в `AndroidManifest.xml`. Для Android 9+ cleartext
(при local IP) — отдельный `network_security_config.xml` только в dev-flavor.

---

## § 4. Единый контракт ошибок

Оба клиента разбирают один JSON:

```json
{"success": false, "error": {"code": "STORE_UNAVAILABLE", "message": "...", "details": {}}, "trace_id": "..."}
```

Dio interceptor и HTMX-обработчик показывают понятное сообщение и сохраняют
`trace_id` в лог — пользователь может сообщить его в issue.

---

## § 5. Ссылки

- [DESIGN.md](DESIGN.md) § 9–10 · [Карта API](../ARCHITECTURE.md) § 5
