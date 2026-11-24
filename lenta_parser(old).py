import requests
import pandas as pd

BASE = "https://integration.api.lenta.com"
BRAND = "lo"        # витрина: lo = Лента Онлайн
CHANNEL = "lo"      # lo = доставка, cc = самовывоз
LAT, LON = 55.3925, 36.7323   # Наро-Фоминск, поменяйте на свою точку
CATEGORY_ID = None  # ID категории; если None — соберётся весь доступный ассортимент

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 1. Ближайший магазин — цены зависят от точки
hub = session.get(f"{BASE}/v1/stores/nearest/hub",
                  params={"latitude": LAT, "longitude": LON, "retailBrand": BRAND}).json()
store = hub["hubs"][0]
print("Магазин:", store["name"], "—", store["address"], f"({store['distance']} м)")
store_id = store["id"]

# 2. Категории (чтобы узнать нужный categoryId)
cats = session.get(f"{BASE}/catalog/v1/categories",
                   params={"stores": store_id, "channel": CHANNEL, "retailBrand": BRAND}).json()

def extract_price(obj):
    """Рекурсивно ищет первое поле, похожее на цену."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if "price" in key.lower() and isinstance(value, (int, float)):
                return value
        for value in obj.values():
            found = extract_price(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = extract_price(value)
            if found is not None:
                return found
    return None

# 3. Сбор товаров с пагинацией
rows, offset, limit = [], 0, 50
while True:
    params = {"stores": store_id, "channel": CHANNEL, "retailBrand": BRAND,
              "limit": limit, "offset": offset}
    if CATEGORY_ID:
        params["categoryId"] = CATEGORY_ID
    r = session.get(f"{BASE}/catalog/v1/items", params=params)
    r.raise_for_status()
    data = r.json()
    items = data.get("items") or data.get("data") or []
    if not items:
        break

    for item in items:
        rows.append({
            "id": item.get("id"),
            "название": item.get("name") or item.get("title"),
            "цена": extract_price(item),
            "вес/объём": item.get("quantity") or item.get("size"),
        })
    offset += limit
    print(f"Собрано {len(rows)} товаров...")

df = pd.DataFrame(rows)
df.to_excel("lenta_prices.xlsx", index=False)
print("Готово:", len(df), "строк → lenta_prices.xlsx")
