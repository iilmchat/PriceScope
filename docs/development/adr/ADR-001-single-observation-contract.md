# ADR-001. Единый контракт `ProductObservation` v1; деньги = int

**Статус:** Accepted · **Дата:** 2026-11-24

## Контекст

Лента отдаёт цены в копейках, Пятёрочка — в другом формате; в legacy-коде цена
преобразуется в float (`round(kopecks/100, 2)`) и пишется в Excel с русскими
заголовками. Сравнение и идентичность записей невозможны (PL-002, PL-005).

## Решение

Ввести версионированную Pydantic-схему `ProductObservation` v1:

- `price_minor: int`, `old_price_minor: int | None` (копейки), `currency="RUB"`;
- `observed_at` — UTC timezone-aware;
- `store_code`, `external_id`, `location_id`, `content_hash`, `raw_ref`,
  `parser_version`, `schema_version`;
- `model_config = ConfigDict(extra="forbid")`.

Все адаптеры возвращают только этот контракт. Изменения — новая версия схемы
и адаптер, не «тихий» переезд.

## Последствия

+ Идемпотентность через `content_hash`, корректная история, сравнение магазинов.
+ Точные деньги без float-ошибок.
− Нужны адаптеры/миграции при смене схемы; требуется дисциплина версионирования.
