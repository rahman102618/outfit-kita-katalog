import json
import os
import re
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

BASE_DIR = Path(__file__).resolve().parent
PRODUCTS_FILE = BASE_DIR / "public" / "products.json"

DEFAULT_IMAGES = {
    "Hijab": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?q=80&w=1200&auto=format&fit=crop",
    "NonHijab": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?q=80&w=1200&auto=format&fit=crop",
}

def clear():
    os.system("clear" if os.name != "nt" else "cls")

def pause():
    input("\nTekan ENTER untuk lanjut...")

def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()

def load_products():
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PRODUCTS_FILE.exists():
        PRODUCTS_FILE.write_text("[]", encoding="utf-8")
    try:
        return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_products(products):
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRODUCTS_FILE.write_text(json.dumps(products, indent=2, ensure_ascii=False), encoding="utf-8")

def get_meta(soup, key, attr="property"):
    tag = soup.find("meta", attrs={attr: key})
    if tag and tag.get("content"):
        return clean_text(tag["content"])
    return ""

def extract_product_data(url):
    data = {"title": "", "desc": "", "image": "", "price": ""}

    if requests is None or BeautifulSoup is None:
        print("Module requests/beautifulsoup4 belum terinstall. Data otomatis dilewati.")
        return data

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        title = (
            get_meta(soup, "og:title")
            or get_meta(soup, "twitter:title", "name")
            or (soup.title.string if soup.title else "")
        )
        desc = (
            get_meta(soup, "og:description")
            or get_meta(soup, "twitter:description", "name")
        )
        image = (
            get_meta(soup, "og:image")
            or get_meta(soup, "twitter:image", "name")
        )

        page_text = clean_text(soup.get_text(" "))
        price_match = re.search(r"Rp\s?[\d\.\,]+", page_text)
        price = price_match.group(0).replace(" ", "") if price_match else ""

        data["title"] = clean_text(title)
        data["desc"] = clean_text(desc)
        data["image"] = image
        data["price"] = price
    except Exception as e:
        print(f"Data otomatis gagal dibaca: {e}")

    return data

def detect_type(text):
    text = text.lower()
    hijab_words = ["hijab", "pashmina", "jilbab", "kerudung", "khimar", "bergo", "bella square"]
    if any(word in text for word in hijab_words):
        return "Hijab"
    return "NonHijab"

def generate_subtitle(text):
    text = text.lower()
    items = []
    rules = {
        "cardigan": "Cardigan", "inner": "Inner", "top": "Top", "atasan": "Atasan",
        "blouse": "Blouse", "kemeja": "Kemeja", "shirt": "Shirt", "vest": "Vest",
        "celana": "Celana", "pants": "Pants", "kulot": "Kulot", "jeans": "Jeans",
        "rok": "Rok", "skirt": "Skirt", "hijab": "Hijab", "pashmina": "Pashmina",
        "belt": "Belt", "hoodie": "Hoodie"
    }
    for key, value in rules.items():
        if key in text and value not in items:
            items.append(value)
    return " + ".join(items) if items else "Fashion Set"

def generate_tags(text, product_type):
    text = text.lower()
    tags = []
    if "korea" in text or "korean" in text:
        tags.append("Korean Look")
    if "pink" in text or "pinky" in text:
        tags.append("Feminine")
    if "simple" in text or "casual" in text:
        tags.append("Daily Look")
    if "formal" in text:
        tags.append("Semi Formal")
    if "minimal" in text:
        tags.append("Minimalist")
    if "hoodie" in text or "street" in text:
        tags.append("Streetwear")
    if not tags:
        tags.append(product_type)
    return list(dict.fromkeys(tags))

def detect_colors(text):
    text = text.lower()
    colors = []
    color_rules = {
        "dusty pink": "Dusty Pink", "pink": "Pink", "cream": "Cream",
        "beige": "Beige", "coklat": "Brown", "brown": "Brown",
        "hitam": "Black", "black": "Black", "putih": "White", "white": "White",
        "biru": "Blue", "blue": "Blue", "olive": "Olive", "sage": "Sage",
        "maroon": "Maroon", "abu": "Grey", "grey": "Grey", "gray": "Grey"
    }
    for key, value in color_rules.items():
        if key in text and value not in colors:
            colors.append(value)
    return colors if colors else ["Cream"]

def input_default(label, current):
    print(f"{label} sekarang: {current}")
    value = input(f"Isi {label} baru, kosongkan jika tetap: ").strip()
    return value if value else current

def input_list_default(label, current):
    current_text = ", ".join(current or [])
    print(f"{label} sekarang: {current_text}")
    value = input(f"Isi {label} baru pisahkan koma, kosongkan jika tetap: ").strip()
    if not value:
        return current
    return [x.strip() for x in value.split(",") if x.strip()]

def tambah_produk():
    clear()
    print("=== TAMBAH PRODUK OTOMATIS ===\n")
    products = load_products()

    product_id = input("No Produk: ").strip().upper()
    link = input("Link Affiliate TikTok: ").strip()

    if not product_id or not link:
        print("No Produk dan Link wajib diisi.")
        pause()
        return

    if any(str(p.get("id", "")).upper() == product_id for p in products):
        print("No Produk sudah ada. Gunakan menu Edit Produk untuk mengubah.")
        pause()
        return

    print("\nMengambil data otomatis dari link...")
    meta = extract_product_data(link)
    combined = f"{meta['title']} {meta['desc']}"

    product_type = detect_type(combined)
    title = meta["title"] or f"Produk Outfit {product_id}"
    subtitle = generate_subtitle(combined)
    tags = generate_tags(combined, product_type)
    colors = detect_colors(combined)
    image = meta["image"] or DEFAULT_IMAGES[product_type]
    price = meta["price"] or "Cek harga di TikTok"
    desc = meta["desc"] or f"{title} cocok untuk daily outfit, hangout, kuliah, atau kegiatan santai."

    product = {
        "id": product_id,
        "type": product_type,
        "name": title,
        "subtitle": subtitle,
        "price": price,
        "size": "S - XL",
        "colors": colors,
        "tags": tags,
        "badge": tags[0] if tags else product_type,
        "desc": desc,
        "image": image,
        "tiktokLink": link
    }

    products.append(product)
    save_products(products)

    print("\nProduk langsung disimpan.")
    print(f"No Produk : {product_id}")
    print(f"Nama      : {title}")
    print(f"Harga     : {price}")
    print(f"Gambar    : {image}")
    print("\nKalau ada data yang salah, gunakan menu: 2. Edit Produk Manual")
    pause()

def list_produk():
    clear()
    products = load_products()
    print("=== DAFTAR PRODUK ===\n")
    if not products:
        print("Belum ada produk.")
    for i, p in enumerate(products, 1):
        print(f"{i}. {p.get('id')} | {p.get('name')} | {p.get('price')}")
    pause()

def pilih_produk(products):
    product_id = input("Masukkan No Produk yang ingin dipilih: ").strip().upper()
    for idx, p in enumerate(products):
        if str(p.get("id", "")).upper() == product_id:
            return idx, p
    return None, None

def edit_produk():
    clear()
    products = load_products()
    if not products:
        print("Belum ada produk.")
        pause()
        return

    print("=== EDIT PRODUK MANUAL ===\n")
    for p in products:
        print(f"- {p.get('id')} | {p.get('name')} | {p.get('price')}")
    print()

    idx, product = pilih_produk(products)
    if product is None:
        print("Produk tidak ditemukan.")
        pause()
        return

    while True:
        clear()
        print(f"=== EDIT PRODUK: {product.get('id')} ===\n")
        print(f"1. Nama        : {product.get('name')}")
        print(f"2. Harga       : {product.get('price')}")
    
        print(f"3. Kategori    : {product.get('type')}")
    
        print(f"4. Link Gambar : {product.get('image')}")
        print(f"5. Link Produk: {product.get('tiktokLink')}")
        print("0. Simpan dan kembali")

        choice = input("\nPilih yang ingin diedit: ").strip()

        if choice == "1":
            product["name"] = input_default("Nama", product.get("name", ""))
        elif choice == "2":
            product["price"] = input_default("Harga", product.get("price", ""))
        
        elif choice == "3":
            print("1. Hijab")
            print("2. NonHijab")
            c = input("Pilih kategori: ").strip()
            product["type"] = "Hijab" if c == "1" else "NonHijab"
        
        elif choice == "4":
            product["image"] = input_default("Link Gambar", product.get("image", ""))
        elif choice == "5":
            product["tiktokLink"] = input_default("Link Produk", product.get("tiktokLink", ""))
        elif choice == "0":
            products[idx] = product
            save_products(products)
            print("Produk berhasil disimpan.")
            pause()
            return
        else:
            print("Pilihan tidak valid.")
            pause()

def hapus_produk():
    clear()
    products = load_products()
    print("=== HAPUS PRODUK ===\n")
    for p in products:
        print(f"- {p.get('id')} | {p.get('name')}")
    print()

    idx, product = pilih_produk(products)
    if product is None:
        print("Produk tidak ditemukan.")
        pause()
        return

    confirm = input(f"Yakin hapus {product.get('id')}? ketik YA: ").strip().upper()
    if confirm == "YA":
        products.pop(idx)
        save_products(products)
        print("Produk berhasil dihapus.")
    else:
        print("Dibatalkan.")
    pause()

def run_server():
    clear()
    print("=== JALANKAN PREVIEW WEB ===\n")
    print("Server akan berjalan di:")
    print("http://127.0.0.1:8000")
    print("\nKalau di HP, buka browser lalu masuk ke alamat di atas.")
    print("Tekan CTRL + C untuk berhenti.\n")
    os.system("python -m http.server 8000")

def main():
    while True:
        clear()
        print("=== OK OUTFIT KITA - MANAGER PRODUK ===\n")
        print("1. Tambah produk otomatis")
        print("2. Edit produk manual")
        print("3. Lihat daftar produk")
        print("4. Hapus produk")
        print("5. Jalankan preview web")
        print("0. Keluar")

        choice = input("\nPilih menu: ").strip()

        if choice == "1":
            tambah_produk()
        elif choice == "2":
            edit_produk()
        elif choice == "3":
            list_produk()
        elif choice == "4":
            hapus_produk()
        elif choice == "5":
            run_server()
        elif choice == "0":
            print("Selesai.")
            break
        else:
            print("Pilihan tidak valid.")
            pause()

if __name__ == "__main__":
    main()
