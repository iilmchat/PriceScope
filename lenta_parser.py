"""
lenta_parser.py — сбор цен из каталога Ленты через открытый Integration API.

Перед запуском: pip install requests pandas openpyxl
"""

import requests
import pandas as pd

# ================== НАСТРОЙКИ ==================
BASE = "https://integration.api.lenta.com"
BRAND = "lo"        # витрина: lo = Лента Онлайн
CHANNEL = "lo"      # lo = доставка, cc = самовывоз
LAT, LON = 55.3925, 36.7323   # Наро-Фоминск (поменяйте на свою точку)
CATEGORY_ID = None  # ID категории (None — собрать весь каталог)
TIMEOUT = 20        # секунд на один запрос

OUT_FILE = "lenta_prices.xlsx"
LIMIT = 50
# ===============================================


def rub(kopecks):
    """Копейки -> рубли."""
    return round(kopecks / 100, 2) if isinstance(kopecks, (int, float)) else None


def extract_fields(item):
    """Достаёт цену, старую цену, скидку и объём из JSON-объекта товара."""
    prices = item.get("prices") or {}
    weight = item.get("weight") or {}

    price = rub(prices.get("cost") or prices.get("price"))
    old_price = rub(prices.get("costRegular") or prices.get("priceRegular"))
    discount = rub(prices.get("discount"))
    discount_pct = prices.get("discountPercentage")
    is_promo = prices.get("isPromoactionPrice")

    package = weight.get("package") or None
    gross_g = weight.get("gross")           # вес брутто в граммах
    net_g = weight.get("net") or None       # вес нетто в граммах

    return price, old_price, discount, discount_pct, is_promo, package, gross_g, net_g


def fetch_category_items(session, store_id, category_id=None):
    """Собирает товары одной категории с пагинацией."""
    rows, offset = [], 0
    while True:
        params = {
            "stores": store_id,
            "channel": CHANNEL,
            "retailBrand": BRAND,
            "limit": LIMIT,
            "offset": offset,
        }
        if category_id:
            params["categoryId"] = category_id
        r = session.get(f"{BASE}/catalog/v1/items", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or data.get("data") or []
        if not items:
            break

        for item in items:
            (price, old_price, discount, discount_pct,
             is_promo, package, gross_g, net_g) = extract_fields(item)
            rows.append({
                "id": item.get("id"),
                "категория_id": item.get("categoryId"),
                "название": item.get("name"),
                "цена, ₽": price,
                "обычная цена, ₽": old_price,
                "скидка, ₽": discount,
                "скидка, %": discount_pct,
                "промо": "да" if is_promo else "",
                "фасовка": package,
                "вес брутто, г": gross_g,
                "вес нетто, г": net_g,
            })
        offset += LIMIT

        if len(items) < LIMIT:   # последняя страница
            break
    return rows


def build_leaf_list(categories):
    """Строит дерево категорий ЛОКАЛЬНО (без запросов по сети).

    Ответ API содержит весь список категорий с полями id, parentId, name.
    Возвращаем только конечные (без детей) категории: [(id, путь)].
    """
    by_parent = {}
    for c in categories:
        by_parent.setdefault(c.get("parentId", 0), []).append(c)

    leaves = []

    def walk(parent_id, prefix):
        for c in by_parent.get(parent_id, []):
            path = f"{prefix}/{c['name']}" if prefix else c["name"]
            children = by_parent.get(c["id"], [])
            if children:
                walk(c["id"], path)
            else:
                leaves.append((c["id"], path))

    walk(0, "")
    # На случай, если корневые категории имеют parentId не 0, а что-то своё
    if not leaves:
        for c in categories:
            if not by_parent.get(c["id"]):
                leaves.append((c["id"], c["name"]))
    return leaves


def main():
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    session.headers["Accept"] = "application/json"

    # 1. Ближайший магазин — цены зависят от точки
    hub = session.get(
        f"{BASE}/v1/stores/nearest/hub",
        params={"latitude": LAT, "longitude": LON, "retailBrand": BRAND},
        timeout=TIMEOUT,
    ).json()
    store = hub["hubs"][0]
    print(f"Магазин: {store['name']} — {store['address']} ({store['distance']} м)")
    store_id = store["id"]

    if CATEGORY_ID:
        rows = fetch_category_items(session, store_id, CATEGORY_ID)
        print(f"Категория {CATEGORY_ID}: {len(rows)} товаров")
    else:
        # 2. Все категории приходят ОДНИМ запросом — дерево строим локально
        top = session.get(
            f"{BASE}/catalog/v1/categories",
            params={"stores": store_id, "channel": CHANNEL, "retailBrand": BRAND},
            timeout=TIMEOUT,
        ).json()
        all_cats = top.get("categories") or []
        leaf_categories = build_leaf_list(all_cats)
        print(f"Всего категорий: {len(all_cats)}, конечных: {len(leaf_categories)}")

        rows, seen = [], set()
        for i, (cat_id, path) in enumerate(leaf_categories, 1):
            try:
                cat_rows = fetch_category_items(session, store_id, cat_id)
            except (requests.RequestException, ValueError) as e:
                print(f"  [{i}/{len(leaf_categories)}] пропуск {path}: {e}")
                continue
            for row in cat_rows:
                row["категория"] = path
                if row["id"] not in seen:
                    seen.add(row["id"])
                    rows.append(row)
            print(f"  [{i}/{len(leaf_categories)}] {path}: {len(cat_rows)} товаров "
                  f"(всего {len(rows)})")

    df = pd.DataFrame(rows)
    df.to_excel(OUT_FILE, index=False)
    print(f"\nГотово: {len(df)} строк → {OUT_FILE}")


if __name__ == "__main__":
    main()
