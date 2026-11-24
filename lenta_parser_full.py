"""
lenta_parser_full.py — сбор цен, фото и артикула по ID товаров.
"""

import requests
import pandas as pd
import time

BASE = "https://integration.api.lenta.com"
BRAND = "lo"
CHANNEL = "lo"
LAT, LON = 55.3925, 36.7323
TIMEOUT = 20
OUT_FILE = "lenta_full.xlsx"
LIMIT = 50
DELAY = 0.3  # задержка между запросами детальной карточки, чтобы не забанили


def rub(kopecks):
    return round(kopecks / 100, 2) if isinstance(kopecks, (int, float)) else None


def extract_fields(item):
    prices = item.get("prices") or {}
    weight = item.get("weight") or {}
    media = item.get("media") or 
    
    price = rub(prices.get("cost") or prices.get("price"))
    old_price = rub(prices.get("costRegular") or prices.get("priceRegular"))
    discount = rub(prices.get("discount"))
    discount_pct = prices.get("discountPercentage")
    is_promo = prices.get("isPromoactionPrice")
    package = weight.get("package")
    gross_g = weight.get("gross")
    net_g = weight.get("net")
    
    # Берём первую картинку, если есть
    image_url = media["url"] if media else None
    
    # Попытка вытащить артикул — зависит от структуры, часто в attributes или отдельной ветке
    # В этом API явного поля 'article' может не быть — тогда будет None
    article = None
    # Примерная логика поиска: иногда лежит в item["attributes"] или item["sku"]
    # Ниже — заглушка, т.к. в публичной схеме явного артикула нет
    # Если найдёте в JSON поле с артикулом — добавьте сюда маппинг
    
    return price, old_price, discount, discount_pct, is_promo, package, gross_g, net_g, image_url, article


def fetch_category_items(session, store_id, category_id=None):
    rows, offset = , 0
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
        items = data.get("items") or data.get("data") or 
        if not items:
            break
        for item in items:
            (price, old_price, discount, discount_pct,
             is_promo, package, gross_g, net_g,
             image_url, article) = extract_fields(item)
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
                "фото": image_url,
                "артикул": article,
            })
        offset += LIMIT
        if len(items) < LIMIT:
            break
    return rows


def fetch_item_detail(session, store_id, item_id):
    """Получает детальную карточку товара — фото и возможные доп. поля."""
    r = session.get(f"{BASE}/catalog/v1/items/{item_id}",
                    params={"stores": store_id, "channel": CHANNEL, "retailBrand": BRAND},
                    timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def build_leaf_list(categories):
    by_parent = {}
    for c in categories:
        by_parent.setdefault(c.get("parentId", 0), ).append(c)
    leaves = 
    def walk(parent_id, prefix):
        for c in by_parent.get(parent_id, ):
            path = f"{prefix}/{c['name']}" if prefix else c["name"]
            children = by_parent.get(c["id"], )
            if children:
                walk(c["id"], path)
            else:
                leaves.append((c["id"], path))
    walk(0, "")
    if not leaves:
        for c in categories:
            if not by_parent.get(c["id"]):
                leaves.append((c["id"], c["name"]))
    return leaves


def main():
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    session.headers["Accept"] = "application/json"

    hub = session.get(
        f"{BASE}/v1/stores/nearest/hub",
        params={"latitude": LAT, "longitude": LON, "retailBrand": BRAND},
        timeout=TIMEOUT,
    ).json()
    store = hub["hubs"]
    print(f"Магазин: {store['name']} — {store['address']} ({store['distance']} м)")
    store_id = store["id"]

    top = session.get(
        f"{BASE}/catalog/v1/categories",
        params={"stores": store_id, "channel": CHANNEL, "retailBrand": BRAND},
        timeout=TIMEOUT,
    ).json()
    all_cats = top.get("categories") or 
    leaf_categories = build_leaf_list(all_cats)
    print(f"Всего категорий: {len(all_cats)}, конечных: {len(leaf_categories)}")

    rows, seen = , set()
    for i, (cat_id, path) in enumerate(leaf_categories, 1):
        try:
            cat_rows = fetch_category_items(session, store_id, cat_id)
        except Exception as e:
            print(f"  [{i}/{len(leaf_categories)}] пропуск {path}: {e}")
            continue
        for row in cat_rows:
            row["категория"] = path
            if row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)
        print(f"  [{i}/{len(leaf_categories)}] {path}: {len(cat_rows)} товаров (всего {len(rows)})")

    # Опционально: пройтись по всем товарам и дозапросить детали (фото, артикул)
    # Внимание: это сильно увеличит время работы (1 запрос на товар)
    print("\nДозапрос детальных карточек (фото, артикул) — это займёт время...")
    for i, row in enumerate(rows):
        item_id = row["id"]
        try:
            detail = fetch_item_detail(session, store_id, item_id)
            # Пример извлечения фото (если в detail есть media)
            media = detail.get("media") or 
            row["фото"] = media["url"] if media else row.get("фото")
            # Если в detail есть артикул — раскомментируйте и подставьте правильное поле
            # row["артикул"] = detail.get("attributes", {}).get("article")
            time.sleep(DELAY)
        except Exception as e:
            print(f"  Ошибка при запросе карточки {item_id}: {e}")
        if (i + 1) % 100 == 0:
            print(f"  Обработано {i + 1} карточек...")

    df = pd.DataFrame(rows)
    df.to_excel(OUT_FILE, index=False)
    print(f"\nГотово: {len(df)} строк → {OUT_FILE}")


if __name__ == "__main__":
    main()
