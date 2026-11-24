"""
test_item_736811.py — проверка детальной карточки товара Ленты.
Запуск: python test_item_736811.py
"""

import json
import requests

BASE = "https://integration.api.lenta.com"
STORE_ID = 233      # ТК277 Наро-Фоминск (из вашей отладки)
ITEM_ID = 736811
BRAND = "lo"
CHANNEL = "lo"
TIMEOUT = 20

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
session.headers["Accept"] = "application/json"

# Пробуем несколько вариантов эндпоинта — какой-то из них сработает
candidates = [
    f"{BASE}/catalog/v1/items/{ITEM_ID}",
    f"{BASE}/catalog/v1/items/{ITEM_ID}/details",
    f"{BASE}/catalog/v1/product/{ITEM_ID}",
    f"{BASE}/catalog/v1/products/{ITEM_ID}",
]

params = {"stores": STORE_ID, "channel": CHANNEL, "retailBrand": BRAND}

success = None
for url in candidates:
    print(f"\n=== GET {url} ===")
    try:
        r = session.get(url, params=params, timeout=TIMEOUT)
        print(f"HTTP {r.status_code}, длина ответа: {len(r.text)} байт")
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            success = data
            break
        elif r.status_code != 200:
            print("  тело:", r.text[:200])
    except Exception as e:
        print(f"  ошибка: {e}")

if success:
    print("\n--- ПОЛНЫЙ JSON ---")
    print(json.dumps(success, ensure_ascii=False, indent=2)[:8000])

    # Сохраняем целиком, чтобы изучить все поля
    with open("item_736811.json", "w", encoding="utf-8") as f:
        json.dump(success, f, ensure_ascii=False, indent=2)
    print("\nПолный ответ сохранён в item_736811.json")

    # Быстрая проверка интересующих полей — рекурсивно ищем ключи
    keys_of_interest = ["article", "sku", "barcode", "ean", "gtin",
                        "image", "photo", "media", "pathOriginal", "vendor"]

    def find_keys(obj, needle, path=""):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{path}.{k}"
                if needle in k.lower():
                    found.append((p, v))
                found.extend(find_keys(v, needle, p))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(find_keys(v, needle, f"{path}[{i}]"))
        return found

    print("\n--- Найденные ключи по интересам ---")
    for needle in keys_of_interest:
        hits = find_keys(success, needle)
        for p, v in hits[:3]:  # максимум 3 примера на ключ
            preview = str(v)[:120]
            print(f"  {needle}: {p} = {preview}")
else:
    print("\nНи один эндпоинт не ответил 200. Возможно, детальная карточка")
    print("отдаётся с другим путём или требует заголовок с витрины.")
