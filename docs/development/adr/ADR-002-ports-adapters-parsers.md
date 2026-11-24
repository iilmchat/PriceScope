# ADR-002. Парсеры за протоколом `StoreParser`

**Статус:** Accepted · **Дата:** 2026-11-24

## Контекст

Два парсера используют разные библиотеки (requests; Camoufox + human_requests),
имеют дублирующуюся логику retry/пагинации/логирования. Добавление магазина
требует правок в нескольких местах (PL-003).

## Решение

Протокол `StoreParser` (`name`, `version`, `capabilities`, `health_check`,
`parse(ctx) -> AsyncIterator[ProductObservation]`) + реестр `get_parser(name)`.
Общая надёжность (timeout/retry/rate limit/circuit breaker/raw snapshot/метрики)
реализуется в `ParseContext` и не зависит от адаптера.

## Последствия

+ Новый магазин = 1 класс + 1 строка в registry + фикстуры.
+ Адаптеры тестируются на фикстурах без сети; ядро не знает про HTTP/браузер.
− Адаптер ограничен возможностями протокола (расширение — через новую версию/port).
