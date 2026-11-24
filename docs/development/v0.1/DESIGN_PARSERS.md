# DESIGN_PARSERS — слой парсеров PriceScope v0.1

**Версия:** 1.0 · **Дата:** 2026-11-24 · **Статус:** Accepted
**Связанные:** [DESIGN.md](DESIGN.md), [ARCHITECTURE.md](../ARCHITECTURE.md)

---

## § 1. Назначение

Слой парсеров превращает разрозненные источники (Integration API, браузерные
страницы) в единый нормализованный поток `ProductObservation` v1 и сохраняет
`raw snapshot` для воспроизводимости. Ядро приложения **не знает**, откуда
взялись данные: HTTP, браузер или ручной импорт.

---

## § 2. Порт `StoreParser`

```python
# packages/parsers/pricescope_parsers/base.py
from collections.abc import AsyncIterator
from dataclasses import dataclass

@dataclass(frozen=True)
class ParserCapabilities:
    requires_browser: bool = False
    requires_location: bool = False
    supports_images: bool = True
    max_requests_per_minute: int = 60

class StoreParser(Protocol):
    name: str                       # "lenta" | "pyaterochka"
    version: str                    # semver адаптера

    def capabilities(self) -> ParserCapabilities: ...
    async def health_check(self) -> bool: ...
    def parse(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]: ...
```

`ParseContext` содержит: `location` (lat/lon), `categories` (фильтр),
`limit`, `fetch_details: bool`, `trace_id`, `cancel_event`, `http` (общий клиент
с retry/rate-limit), `raw_store` (сохранение снапшотов).

**Реализации:** `LentaParser`, `PyaterochkaParser` (v0.1), `ManualCsvParser`
(для ручного импорта и тестов). Реестр — `get_parser(name)`; неизвестный
магазин → `UnknownStoreError`.

---

## § 3. Конвейер обработки

```
ParseContext
   │
   ▼
[Adapter]  запрос → raw bytes/HTML/JSON
   │  save_raw(sha256, payload, parser_version)  ← RawSnapshot
   ▼
[Normalizer] fields → ProductObservation v1
   │  money→minor, UTC, content_hash, категория, вес/объём
   ▼
[Validator] Pydantic v2; invalid → skipped + лог
   ▼
[Emitter] async generator → API/ingest service → БД (upsert)
```

Ошибки одной карточки **не роняют** весь прогон: счётчик `skipped` +
`last_error` в `ParseRun`. Фатальные ошибки (CAPTCHA, 401, смена схемы API) —
`ParseFailed`, останов с диагностикой.

---

## § 4. Общая надёжность (не в адаптерах)

| Механизм | Политика |
| :--- | :--- |
| Timeout | 20 с на HTTP-запрос, 60 с на браузерную страницу |
| Retry | 3 попытки, `1/2/4 с` + jitter ±20 %, только transient (5xx, timeout, 429) |
| Rate limit | токенный ведёрка, `capabilities.max_requests_per_minute`, задержка между детальными карточками 300 мс |
| Circuit breaker | 5 ошибок подряд → 5 мин skip источника, полуоткрытый пробный запрос |
| Отмена | `asyncio.CancelledError` пробрасывается, `ParseRun.status = cancelled` |
| Идемпотентность | `content_hash` + `uq_observation`; `import_idempotency_key` в API |
| Наблюдаемость | `trace_id`, structlog, метрики `parser_requests_total`, `parser_items_total` |

---

## § 5. Адаптер Ленты (`lenta`)

**Источник:** `https://integration.api.lenta.com` (как в текущем `lenta_parser.py`).

| Шаг | Endpoint | Комментарий |
| :--- | :--- | :--- |
| 1 | `GET /v1/stores/nearest/hub?latitude&longitude&retailBrand=lo` | ближайший хаб; координаты — конфиг, не хардкод |
| 2 | `GET /catalog/v1/categories?stores&channel&retailBrand` | дерево категорий одним запросом, листья строим локально |
| 3 | `GET /catalog/v1/items?stores&channel&retailBrand&limit&offset&categoryId` | пагинация (limit 50) |
| 4 | `GET /catalog/v1/items/{id}` | опционально: фото `images[].pathLarge`, доп. поля |

**Маппинг полей:**

| Поле API | Поле DTO |
| :--- | :--- |
| `prices.cost` / `prices.price` | `price_minor` (копейки как есть) |
| `prices.costRegular` | `old_price_minor` |
| `prices.discountPercentage` | `discount_pct` (в attributes/расширении DTO v1.1) |
| `weight.package` | `package` |
| `weight.net` / `weight.gross` | `net_weight_g` / `gross_weight_g` |
| `images[0].pathLarge` | `image_urls[0]` |
| `id` | `external_id` |
| `storeId` / hub id | `location_id` |

**Отличия от legacy:** нет хардкода координат, русских колонок, Excel как
единственного результата; все габариты/цены — в типизированную схему; raw JSON
сохраняется; координаты читаются из настроек (`--lat`, `--lon`, env).

---

## § 6. Адаптер Пятёрочки (`pyaterochka`)

**Источник:** сайт `5ka.ru`, браузер Camoufox + `human_requests`
(наследуюexists код из `ParserPyaterka/parser_pyaterochka_fixed_v5.py`).

**Политика (обязательная, ADR-006):**

1. Парсер **не решает и не обходит** CAPTCHA/антибот-проверки. При обнаружении
   маркеров («капча», «подтвердите, что вы не робот», `verify you are human`, …) —
   `CaptchaDetectedError`, останов, диагностика в `ParseRun.error`, уведомление.
2. Запрещены: подмена UA/IP ради обхода блокировки, фермы капчи, обход rate limit.
3. Соблюдение robots.txt и ToS; при устойчивой блокировке — легальный канал
   (официальный API/партнёрские данные/ручной импорт) как приоритетная альтернатива.
4. Повторный запуск после CAPTCHA — только после восстановления обычного доступа.

**Технические детали:**

- совместимость с Python 3.11 (`typing.override` patch), путь к Camoufox — env
  `CAMOUFOX_EXECUTABLE_PATH`, **не хардкод** в репозитории;
- чтение `localStorage.DeliveryPanelStore` через адаптер `_get_local_storage_item`
  (поддержка старого/new Playwright API);
- извлечение каталога — из сетевых ответов страницы (не из DOM-скрейпинга цен,
  если доступен JSON); • фото — CDN 5ka, сохраняем в `data/photos/pyaterochka/`;
- конвертация в `ProductObservation` — тот же `Normalizer`, что и у Ленты;
- в v0.1 адаптер работает **только вручную** (`pricescope parse --store pyaterochka`),
  без фоновых расписаний.

---

## § 7. Тестирование парсеров

- **VCR-фикстуры** ответов Ленты и сетевых вызовов 5ka в `tests/fixtures/` —
  тесты не ходят в сеть.
- Юнит-тесты: `rub → minor`, разбор веса/объёма, выбор первой картинки,
  дедупликация, счётчики ParseRun, retry/circuit breaker (fake clock).
- Контрактный тест: каждый адаптер возвращает объекты, валидные по
  `ProductObservation` v1 (Pydantic).
- Отдельный тест captcha-policy: фикстура страницы с CAPTCHA → ожидаемый
  `CaptchaDetectedError`, **никаких** попыток обхода.

---

## § 8. Ссылки

- [Общий DESIGN](DESIGN.md) § 6 · [Архитектура](../ARCHITECTURE.md) § 6
- [Реестр проблем](../../KNOWN_ISSUES.md) (PL-001…PL-003)
