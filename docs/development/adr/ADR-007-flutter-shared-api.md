# ADR-007. Один Flutter-код для web/Android, общий REST API

**Статус:** Accepted · **Дата:** 2026-11-24

## Контекст

Нужны сайт и Android-приложение с одинаковыми сценариями (поиск, сравнение,
история). Две нативные кодовые базы удваивают стоимость поддержки.

## Решение

Flutter (web + Android) с Clean Architecture (data/domain/presentation),
Riverpod, GoRouter, Dio. Адрес API — `--dart-define=API_BASE_URL`; офлайн-кэш
избранного — drift. Вся бизнес-логика (сравнение, matching) — на сервере/API.

## Последствия

+ Один UI-код, общий контракт ошибок и DTO с viewer.
+ Быстрый локальный цикл: `flutter run -d chrome`.
− Flutter web «тяжелее» обычного HTML; release-подпись Android — отдельная фаза;
  требуется аккуратная работа с cleartext HTTP в dev.
