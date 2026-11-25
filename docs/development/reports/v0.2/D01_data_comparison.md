# D01 — данные и сравнение двух магазинов

**Дата:** 2026-11-25 · **Статус:** In Progress · **Правила:** RULES.md v1.0.4

## (1) Файлы (+/−)

| Файл | Изменение |
| :--- | :--- |
| `pricescope_api/search.py` | + `matches()` — casefold-поиск по подстроке вместо `ILIKE` |
| `routers.py`, `services.py`, viewer `router.py` | поиск/сравнение переведены на `matches`; `GET /categories` |
| `viewer/templates/products.html` | категория — выпадающий список из справочника |
| `viewer/templates/product.html`, `app.css` | карточка в стиле 5ka: галерея, цена/скидка, характеристики, мини-сравнение |
| `cli.py`, `services.py`, `manual/csv_parser.py` | `import-csv --store <code>` |
| `pyaterochka/browser.py` | исправлены CAPTCHA-привязка, SPA-ожидание, SAP-коды категорий |
| `docs/examples/pyaterochka_manual.csv` | пример реальной цены 5ka (99,99 ₽) |

## (2) Покрытие

- Тесты: регистронезависимый поиск (кириллица, смешанный регистр, подстрока),
  справочник категорий, выпадающий список во viewer — **68 passed**.
- Живой сценарий: `GET /api/v1/compare?query=Кефир ПРОСТОКВАШИНО` →
  Лента 112,99 ₽ и Пятёрочка 99,99 ₽, дешёвое предложение отмечено.

## (3) Результаты

- ruff 0/0, mypy 0 ошибок (63 файла), pytest 68/68, 1 live deselected.
- Pyaterochka live-парсер: после исправлений открывает страницу и каталог, но
  `fetch()` API падает с NetworkError — зафиксировано PL-017; импорт через CSV работает.
- Matching переписан с токен-блокировкой; полный прогон по 31k observation завершён:
  `auto=1982 review=6796 new=22352`; покрытие `0.782`, 6 804 пары в очереди review.
  Пара «Кефир ПРОСТОКВАШИНО» (Лента/Пятёрочка) попала в review со score 0.771 —
  решение принимает человек через `/matches`.

## (4) Smoke

```powershell
pricescope import-csv --file docs/examples/pyaterochka_manual.csv --store pyaterochka
pricescope match --run --limit 40000
pricescope serve --local
# http://127.0.0.1:8775/products → поиск «кефир», категория из списка
# http://127.0.0.1:8775/product?external_id=... → карточка с сравнением
```

## (5) Что не так

- 471 observation без URL фото — источника для скачивания нет.
- Живой парсер 5ka зависит от доступности сайта; CAPTCHA → останов (ADR-006).
- `Product` создаётся lexical-алгоритмом; эмбеддинги CLIP/text — следующий этап.

## (6) Новые PL

- PL-017 — живой парсер 5ka требует доступности сайта (Documented).

## (7) Обоснование

`ILIKE` в SQLite не понимает кириллицу, поэтому текстовый поиск перенесён в Python
через `casefold()`. Категории перестали быть свободным полем: пользователь выбирает
значение из справочника, что исключает опечатки и пустые результаты. Matching с
токен-блокировкой позволяет обработать 31k строк без O(n²) сравнений.
