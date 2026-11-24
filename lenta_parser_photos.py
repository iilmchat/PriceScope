"""
lenta_parser_photos.py — сбор цен + ссылки на фото в Excel + скачивание фото в папку.

Режимы запуска:
    python lenta_parser_photos.py              # сбор + скачивание (webp, как есть)
    python lenta_parser_photos.py --convert    # сбор + скачивание с конвертацией в JPG
    python lenta_parser_photos.py --reconvert  # только конвертация уже скачанных файлов в photos/

Перед запуском: pip install requests pandas openpyxl pillow
"""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ================== НАСТРОЙКИ ==================
BASE = "https://integration.api.lenta.com"
BRAND = "lo"        # витрина: lo = Лента Онлайн
CHANNEL = "lo"      # lo = доставка, cc = самовывоз
LAT, LON = 55.3925, 36.7323   # Наро-Фоминск (поменяйте на свою точку)
CATEGORY_ID = None  # ID категории (None — весь каталог)

PHOTO_DIR = "photos"        # папка для скачанных фото
PHOTO_SIZE = "pathLarge"    # pathIcon (100), pathPreview (250), pathMedium (500), pathLarge (900), pathOriginal (оригинал)
DOWNLOAD_PHOTOS = True      # False — только ссылки в Excel, без скачивания
MAX_WORKERS = 8             # одновременных скачиваний
TIMEOUT = 20

OUT_FILE = "lenta_prices.xlsx"
LIMIT = 50

DELETE_WEBP_AFTER_CONVERT = False  # True — удалять исходный .webp после успешной конвертации
JPEG_QUALITY = 90
# ===============================================


def rub(kopecks):
    """Копейки -> рубли."""
    return round(kopecks / 100, 2) if isinstance(kopecks, (int, float)) else None


def extract_fields(item):
    """Цены, фасовка, вес и ссылка на фото из JSON-объекта товара."""
    prices = item.get("prices") or {}
    weight = item.get("weight") or {}

    image_url = None
    images = item.get("images") or []
    if images:
        image_url = images[0].get(PHOTO_SIZE) or images[0].get("pathLarge")

    return {
        "id": item.get("id"),
        "категория_id": item.get("categoryId"),
        "название": item.get("name"),
        "цена, ₽": rub(prices.get("cost") or prices.get("price")),
        "обычная цена, ₽": rub(prices.get("costRegular") or prices.get("priceRegular")),
        "скидка, ₽": rub(prices.get("discount")),
        "скидка, %": prices.get("discountPercentage"),
        "промо": "да" if prices.get("isPromoactionPrice") else "",
        "фасовка": weight.get("package") or None,
        "вес брутто, г": weight.get("gross"),
        "вес нетто, г": weight.get("net") or None,
        "фото": image_url,
    }


def fetch_category_items(session, store_id, category_id):
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
        rows.extend(extract_fields(it) for it in items)
        offset += LIMIT
        if len(items) < LIMIT:   # последняя страница
            break
    return rows


def build_leaf_list(categories):
    """Строит дерево категорий локально, возвращает конечные: [(id, путь)]."""
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
    if not leaves:
        for c in categories:
            if not by_parent.get(c["id"]):
                leaves.append((c["id"], c["name"]))
    return leaves


def convert_to_jpg(webp_path):
    """Конвертирует webp/png в jpg. Возвращает путь к jpg или None при ошибке."""
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow не установлена: pip install pillow")
    jpg_path = os.path.splitext(webp_path)[0] + ".jpg"
    with Image.open(webp_path) as img:
        # JPEG не поддерживает прозрачность — альфа-канал накладываем на белый фон
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split("A"))
            img = background
        else:
            img = img.convert("RGB")
        img.save(jpg_path, "JPEG", quality=JPEG_QUALITY)
    if DELETE_WEBP_AFTER_CONVERT and os.path.abspath(jpg_path) != os.path.abspath(webp_path):
        os.remove(webp_path)
    return jpg_path


def download_photo(session, item_id, url, convert=False):
    """Скачивает фото как photos/{id}.<ext>; при convert=True сразу пишет .jpg."""
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    ext = os.path.splitext(url)[1] or ".webp"
    raw_path = os.path.join(PHOTO_DIR, f"{item_id}{ext}")
    with open(raw_path, "wb") as f:
        f.write(r.content)
    if convert:
        return convert_to_jpg(raw_path)
    return raw_path


def run_reconvert():
    """Режим --reconvert: конвертация уже скачанных файлов, без обращений к API."""
    if not PIL_AVAILABLE:
        print("Pillow не установлена: pip install pillow")
        return
    if not os.path.isdir(PHOTO_DIR):
        print(f"Папка {PHOTO_DIR}/ не найдена — конвертировать нечего.")
        return

    files = [f for f in os.listdir(PHOTO_DIR)
             if f.lower().endswith((".webp", ".png")) and not f.endswith(".jpg")]
    if not files:
        print(f"В {PHOTO_DIR}/ нет файлов .webp/.png для конвертации.")
        return

    print(f"Конвертация {len(files)} файлов из {PHOTO_DIR}/ ...")
    done, failed = 0, 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(convert_to_jpg, os.path.join(PHOTO_DIR, f)): f
                   for f in files}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                fut.result()
                done += 1
            except Exception as e:
                failed += 1
                print(f"  ошибка {name}: {e}")
            if done % 500 == 0 and done > 0:
                print(f"  конвертировано {done}/{len(files)}...")

    print(f"Готово: успешно {done}, с ошибками {failed}.")


def main():
    parser = argparse.ArgumentParser(description="Сбор цен и фото из каталога Ленты")
    parser.add_argument("--convert", action="store_true",
                        help="скачивать фото и сразу конвертировать в JPG")
    parser.add_argument("--reconvert", action="store_true",
                        help="конвертировать уже скачанные .webp/.png в photos/ (без сбора данных)")
    args = parser.parse_args()

    if args.reconvert:
        run_reconvert()
        return

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

    # 2. Сбор товаров по категориям (или одной категории)
    if CATEGORY_ID:
        rows = fetch_category_items(session, store_id, CATEGORY_ID)
        print(f"Категория {CATEGORY_ID}: {len(rows)} товаров")
    else:
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
            print(f"  [{i}/{len(leaf_categories)}] {path}: {len(cat_rows)} товаров (всего {len(rows)})")

    # 3. Excel со ссылками на фото
    df = pd.DataFrame(rows)
    df.to_excel(OUT_FILE, index=False)
    with_photo = df["фото"].notna().sum()
    print(f"\nExcel готов: {len(df)} строк → {OUT_FILE} (фото есть у {with_photo})")

    # 4. Скачивание фото в папку photos/
    if DOWNLOAD_PHOTOS:
        os.makedirs(PHOTO_DIR, exist_ok=True)
        to_download = df[df["фото"].notna()][["id", "фото"]].values.tolist()
        print(f"Скачивание {len(to_download)} фото в папку {PHOTO_DIR}/ "
              f"{'с конвертацией в JPG' if args.convert else ''}...")

        done, failed = 0, 0
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(download_photo, session, iid, url, args.convert): iid
                       for iid, url in to_download}
            for fut in as_completed(futures):
                iid = futures[fut]
                try:
                    fut.result()
                    done += 1
                except Exception:
                    failed += 1
                if done % 500 == 0 and done > 0:
                    print(f"  скачано {done}/{len(to_download)}...")

        print(f"Скачивание завершено: успешно {done}, с ошибками {failed}.")
        if args.convert:
            print("Файлы сохранены как photos/{ID}.jpg.")
        else:
            print("Файлы сохранены как photos/{ID}.webp.")


if __name__ == "__main__":
    main()
