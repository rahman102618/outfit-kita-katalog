#!/usr/bin/env python3
# OK Outfit Kita Product Manager - Shopee Share Text + Auto Image + Cache Link
# Support link: Shopee, TikTok/Tokopedia, Tokopedia, dan link affiliate lain.
# Catatan:
# - Gamis/Dress/Oneset/Oneshet/One Set diarahkan ke kategori Gamis.
# - Shopee paling stabil via Shopee Affiliate Open API jika App ID dan Secret diisi.
# - TikTok tidak memakai harga otomatis. Harga TikTok selalu diisi manual agar tidak salah harga.
# - Jika link pernah dimasukkan, data lama dipakai otomatis tanpa tanya ulang nama/harga/gambar.
# - Jika tanpa kredensial API, program tetap mencoba link/HTML publik, lalu fallback manual yang aman.

import os
import re
import json
import time
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote, parse_qs, urlencode, quote
from html import unescape
from io import BytesIO

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

try:
    import cloudscraper
except Exception:
    cloudscraper = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.align import Align
    from rich.text import Text
    from rich import box
    RICH = True
except Exception:
    RICH = False


APP_NAME = "OK OUTFIT KITA"
DATA_FILE = Path("public/products.json")
SHOPEE_CONFIG_FILE = Path("shopee_api_config.json")
SHOPEE_DEBUG_FILE = Path("shopee_debug_last.txt")
ASSET_DIR = Path("public/assets")
NO_IMAGE = ASSET_DIR / "no-image.svg"
CATEGORIES_FILE = Path("public/categories.json")

DEFAULT_CATEGORIES = ["Atasan", "Bawahan", "Hijab", "Gamis", "Tas", "Sepatu"]
# CATEGORIES tetap disediakan untuk kompatibilitas fungsi lama.
# Nilai aslinya dibaca dinamis dari public/categories.json + kategori yang sudah ada di products.json.
CATEGORIES = list(DEFAULT_CATEGORIES)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
}

console = Console() if RICH else None

# Warna ANSI untuk Termux. Ini membuat tampilan tetap berwarna walau library rich belum terpasang.
ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "gray": "\033[90m",
}

COLOR_MAP = {
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "cyan": "cyan",
    "blue": "blue",
    "magenta": "magenta",
    "white": "white",
    "grey": "gray",
    "gray": "gray",
    "bright_yellow": "yellow",
    "bright_green": "green",
    "bright_cyan": "cyan",
    "bright_red": "red",
}


def strip_rich_markup(text):
    """Hilangkan markup Rich saat mode Termux biasa dipakai."""
    text = str(text or "")
    text = re.sub(r"\[/?(?:bold|dim|italic|underline|reverse|blink)(?:\s+[^\]]+)?\]", "", text)
    text = re.sub(r"\[/?(?:red|green|yellow|cyan|blue|magenta|white|black|bright_[a-z_]+)(?:\s+[^\]]+)?\]", "", text)
    text = re.sub(r"\[/\]", "", text)
    return text


def term_color(text, color="white", bold=False, dim=False):
    text = strip_rich_markup(text)
    color = COLOR_MAP.get(str(color).lower(), str(color).lower())
    code = ANSI.get(color, ANSI["white"])
    prefix = ""
    if bold:
        prefix += ANSI["bold"]
    if dim:
        prefix += ANSI["dim"]
    return f"{prefix}{code}{text}{ANSI['reset']}"


def colored_by_style(text, style=None):
    if not style:
        return strip_rich_markup(text)
    style = str(style).lower()
    color = "white"
    for key, value in COLOR_MAP.items():
        if key in style:
            color = value
            break
    return term_color(text, color=color, bold="bold" in style, dim="dim" in style)


def box_line(width=72, color="yellow", top=False, bottom=False):
    if top:
        line = "╔" + "═" * (width - 2) + "╗"
    elif bottom:
        line = "╚" + "═" * (width - 2) + "╝"
    else:
        line = "─" * width
    return term_color(line, color=color, bold=True)


def box_center(text, width=72, color="white", bold=False, dim=False, border_color="yellow"):
    inner = strip_rich_markup(text).center(width - 2)
    return term_color("║", border_color, bold=True) + term_color(inner, color, bold=bold, dim=dim) + term_color("║", border_color, bold=True)


def box_text(text, width=72, color="white", bold=False, border_color="cyan"):
    clean = strip_rich_markup(text)
    out_lines = []
    for raw_line in clean.splitlines() or [""]:
        words = raw_line.split()
        if not words:
            out_lines.append("")
            continue
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > width - 4:
                out_lines.append(line.rstrip())
                line = word + " "
            else:
                line += word + " "
        if line.strip():
            out_lines.append(line.rstrip())
    rendered = []
    for line in out_lines:
        padded = " " + line.ljust(width - 4) + " "
        rendered.append(term_color("│", border_color, bold=True) + term_color(padded, color, bold=bold) + term_color("│", border_color, bold=True))
    return "\n".join(rendered)


def clear():
    os.system("clear")


def printx(value="", style=None):
    if RICH:
        console.print(value, style=style)
    else:
        print(colored_by_style(value, style))


def ask(label, default=None):
    if RICH:
        return Prompt.ask(label, default=default)
    clean_label = strip_rich_markup(label)
    default_text = f" [{default}]" if default is not None else ""
    prompt = term_color(clean_label, "cyan", bold=True) + term_color(default_text + ": ", "white")
    value = input(prompt).strip()
    return value if value else (str(default) if default is not None else "")


def ask_yes(label, default=True):
    if RICH:
        return Confirm.ask(label, default=default)
    clean_label = strip_rich_markup(label)
    pilihan = "Y/n" if default else "y/N"
    value = input(term_color(clean_label, "cyan", bold=True) + term_color(f" ({pilihan}): ", "white")).strip().lower()
    if not value:
        return default
    return value == "y"


def pause():
    ask("\nTekan ENTER untuk lanjut", default="")


def panel(msg, title="INFO", style="cyan"):
    if RICH:
        console.print(Panel(msg, title=title, border_style=style, box=box.ROUNDED))
    else:
        width = 72
        color = COLOR_MAP.get(str(style).lower(), "cyan")
        print("\n" + box_line(width, color=color, top=True))
        if title:
            print(box_center(str(title).upper(), width, color=color, bold=True, border_color=color))
            print(term_color("├" + "─" * (width - 2) + "┤", color, bold=True))
        print(box_text(msg, width, color="white", border_color=color))
        print(box_line(width, color=color, bottom=True))


def ok(msg):
    panel(f"[bold green]{msg}[/]" if RICH else msg, "BERHASIL", "green")


def warn(msg):
    panel(f"[bold yellow]{msg}[/]" if RICH else msg, "PERHATIAN", "yellow")


def err(msg):
    panel(f"[bold red]{msg}[/]" if RICH else msg, "ERROR", "red")


def info(msg):
    panel(f"[bold cyan]{msg}[/]" if RICH else msg, "INFO", "cyan")


def git_status_text():
    if not Path(".git").exists():
        return "Bukan Repo Git"
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip() or "main"
        status = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        return f"{branch} • {'Ada perubahan' if status else 'Bersih'}"
    except Exception:
        return "Repo Git"

def show_header():
    """Header Termux yang lebih bersih: warna seperlunya, tidak ramai."""
    meta = datetime.now().strftime("%Y-%m-%d %H:%M")
    if RICH:
        title = Text("OUTFIT KITA MANAGER", style="bold white")
        subtitle = Text("Kelola Produk Katalog", style="cyan")
        meta_text = Text(meta, style="dim white")
        console.print(
            Panel(
                Align.center(Text.assemble(title, "\n", subtitle, "\n", meta_text)),
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
    else:
        width = 72
        border = "cyan"
        print(box_line(width, color=border, top=True))
        print(box_center("OUTFIT KITA MANAGER", width, color="white", bold=True, border_color=border))
        print(box_center("Kelola Produk Katalog", width, color="cyan", bold=True, border_color=border))
        print(box_center(meta, width, color="gray", bold=False, border_color=border))
        print(box_line(width, color=border, bottom=True))


def show_menu():
    items = [
        ("1", "Tambah produk otomatis"),
        ("2", "Edit produk manual"),
        ("3", "Lihat daftar produk"),
        ("4", "Hapus produk"),
        ("5", "Preview katalog"),
        ("6", "Sinkron GitHub"),
        ("7", "Setup Shopee API"),
        ("8", "Kelola kategori"),
        ("0", "Keluar"),
    ]

    try:
        total_produk = len(load_products())
        total_kategori = len(get_categories())
    except Exception:
        total_produk = 0
        total_kategori = 0

    if RICH:
        table = Table.grid(padding=(0, 2))
        for no, label in items:
            table.add_row(f"[bold white]{no}[/]", f"[white]{label}[/]")
        footer = Text(f"Produk: {total_produk}  •  Kategori: {total_kategori}", style="dim white")
        content = Table.grid()
        content.add_row(Align.center(footer))
        content.add_row(table)
        console.print(Panel(content, title="[bold cyan]Menu Utama[/]", border_style="cyan", box=box.ROUNDED, padding=(1, 2)))
    else:
        width = 72
        border = "cyan"
        print()
        print(term_color("╔" + "═" * (width - 2) + "╗", border, bold=True))
        print(term_color("║", border, bold=True) + term_color(" MENU UTAMA ".center(width - 2), "white", bold=True) + term_color("║", border, bold=True))
        print(term_color("╠" + "═" * (width - 2) + "╣", border, bold=True))
        stats = f"Produk: {total_produk}  •  Kategori: {total_kategori}"
        print(term_color("║", border, bold=True) + term_color(stats.center(width - 2), "gray") + term_color("║", border, bold=True))
        print(term_color("╠" + "═" * (width - 2) + "╣", border, bold=True))
        for no, label in items:
            row_text = f"  {no}.  {label}"
            raw_len = len(row_text)
            padding = " " * max(0, width - 2 - raw_len)
            number_color = "gray" if no == "0" else "white"
            print(
                term_color("║", border, bold=True)
                + term_color(f"  {no}.", number_color, bold=True)
                + term_color(f"  {label}", "white")
                + padding
                + term_color("║", border, bold=True)
            )
        print(term_color("╚" + "═" * (width - 2) + "╝", border, bold=True))


def ensure_files():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")

    if not CATEGORIES_FILE.exists():
        save_categories(DEFAULT_CATEGORIES + categories_from_products())
    else:
        # Sinkronkan file kategori dengan kategori produk yang sudah ada, tanpa menghapus data lama.
        save_categories(get_categories())

    if not NO_IMAGE.exists():
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 900 900">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#111"/><stop offset="55%" stop-color="#2a2112"/><stop offset="100%" stop-color="#facc15"/></linearGradient></defs>
<rect width="900" height="900" rx="70" fill="url(#g)"/>
<text x="450" y="420" text-anchor="middle" fill="#fff" font-size="58" font-family="Arial" font-weight="800">OK OUTFIT KITA</text>
<text x="450" y="500" text-anchor="middle" fill="#ffe08a" font-size="34" font-family="Arial" font-weight="700">Gambar produk belum tersedia</text>
</svg>'''
        NO_IMAGE.write_text(svg, encoding="utf-8")


def load_products():
    ensure_files()
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_products(products):
    DATA_FILE.write_text(json.dumps(products, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_category_name(value):
    value = clean_text(value) if "clean_text" in globals() else str(value or "").strip()
    # Biarkan huruf/angka/spasi dan tanda umum saja supaya kategori tetap rapi.
    value = re.sub(r"[^0-9A-Za-zÀ-ÿĀ-žḀ-ỹ\s&/+-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -_/+")
    if not value:
        return ""
    # Rapikan kapital: TUMBLER -> Tumbler, tas wanita -> Tas Wanita.
    if value.isupper() or value.islower():
        value = value.title()
    return value[:40].strip()


def unique_category_list(values):
    out = []
    seen = set()
    for val in values:
        cat = clean_category_name(val)
        if not cat:
            continue
        low = cat.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(cat)
    return out


def read_categories_file():
    if not CATEGORIES_FILE.exists():
        return []
    try:
        data = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return unique_category_list(data)
        if isinstance(data, dict):
            return unique_category_list(data.get("categories") or [])
    except Exception:
        pass
    return []


def categories_from_products():
    cats = []
    try:
        if DATA_FILE.exists():
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for p in data:
                    if isinstance(p, dict):
                        cats.append(p.get("category") or p.get("type") or p.get("badge"))
    except Exception:
        pass
    return unique_category_list(cats)


def get_categories(sync_file=False):
    global CATEGORIES
    cats = unique_category_list(list(DEFAULT_CATEGORIES) + read_categories_file() + categories_from_products())
    CATEGORIES = cats or list(DEFAULT_CATEGORIES)
    if sync_file:
        save_categories(CATEGORIES)
    return CATEGORIES


def save_categories(categories):
    cats = unique_category_list(list(DEFAULT_CATEGORIES) + list(categories or []))
    CATEGORIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CATEGORIES_FILE.write_text(json.dumps(cats, indent=2, ensure_ascii=False), encoding="utf-8")
    global CATEGORIES
    CATEGORIES = cats
    return cats


def category_exists(category):
    low = clean_category_name(category).lower()
    return any(c.lower() == low for c in get_categories())


def canonical_category(category):
    category = clean_category_name(category)
    for cat in get_categories():
        if cat.lower() == category.lower():
            return cat
    return category


def add_category_value(category, silent=False):
    category = clean_category_name(category)
    if not category:
        return ""
    cats = get_categories()
    for cat in cats:
        if cat.lower() == category.lower():
            return cat
    cats.append(category)
    save_categories(cats)
    if not silent:
        ok(f"Kategori baru '{category}' berhasil ditambahkan.")
    return category


def delete_category_value(category, move_to=None):
    category = canonical_category(category)
    cats = [c for c in get_categories() if c.lower() != category.lower()]
    save_categories(cats)

    try:
        products = json.loads(DATA_FILE.read_text(encoding="utf-8")) if DATA_FILE.exists() else []
        if not isinstance(products, list):
            products = []
    except Exception:
        products = []
    changed = False
    if move_to:
        move_to = add_category_value(move_to, silent=True)
        for p in products:
            if str(p.get("category") or p.get("type") or "").lower() == category.lower():
                p["category"] = move_to
                p["type"] = move_to
                p["badge"] = move_to
                p["tags"] = [move_to, p.get("platform") or detect_platform(p.get("link") or p.get("tiktokLink"))]
                changed = True
    if changed:
        save_products(products)
    return True


def detect_platform(link):
    link = str(link or "").lower()
    if "shopee" in link:
        return "Shopee"
    if "tokopedia" in link:
        return "Tokopedia"
    if "tiktok" in link:
        return "TikTok"
    return "Affiliate"


def extract_first_url(value):
    """Ambil URL pertama dari input biasa atau teks share marketplace."""
    text = clean_text(value)
    match = re.search(r"https?://[^\s]+", text, flags=re.I)
    if not match:
        return ""
    url = match.group(0).strip()
    return url.rstrip(".,);]}>'\"")



def ask_multiline_links(label="Link Produk"):
    """Input banyak link satu per baris.

    Cocok untuk format:
    71. https://...
    72. https://...

    Kalau user menempel banyak baris di Termux, baris berikutnya akan
    otomatis dibaca sampai ada baris kosong.
    """
    if RICH:
        console.print(f"[bold cyan]{label}[/]")
        console.print("[dim]Boleh tempel banyak baris. Setelah selesai, tekan ENTER di baris kosong.[/]")
    else:
        print(label)
        print("Boleh tempel banyak baris. Setelah selesai, tekan ENTER di baris kosong.")

    lines = []
    while True:
        try:
            prefix = "Link: " if not lines else "     "
            line = input(prefix).strip()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def split_product_ids(value):
    """Terima nomor tunggal, range, atau daftar nomor.

    Contoh:
    71      -> ["71"]
    71-75   -> ["71", "72", "73", "74", "75"]
    71,73   -> ["71", "73"]
    B01-B03 -> ["B01", "B02", "B03"]
    """
    raw = clean_text(value)
    if not raw:
        return []

    ids = []
    for part in re.split(r"[,;\s]+", raw):
        part = part.strip()
        if not part:
            continue

        m = re.match(r"^([A-Za-z]*)(\d+)\s*-\s*([A-Za-z]*)(\d+)$", part)
        if m:
            p1, n1, p2, n2 = m.groups()
            if p2 and p1.lower() != p2.lower():
                ids.append(part)
                continue
            start, end = int(n1), int(n2)
            if start > end:
                start, end = end, start
            width = max(len(n1), len(n2))
            prefix = p1 or p2 or ""
            for n in range(start, end + 1):
                ids.append(f"{prefix}{str(n).zfill(width)}")
            continue

        ids.append(part)

    out = []
    seen = set()
    for pid in ids:
        key = str(pid).lower()
        if key not in seen:
            seen.add(key)
            out.append(str(pid))
    return out



def parse_numbered_link_entries(raw_text, requested_ids=None):
    """Ambil pasangan nomor + link dari input banyak baris.

    Mendukung format:
    01. Cek Nama Produk dengan harga Rp106.000 https://s.shopee.co.id/xxx
    02. https://vt.tokopedia.com/t/xxx/ harga 65.000
    03 - Nama Produk https://vt.tiktok.com/xxx harga 88.000
    """
    requested_ids = requested_ids or []
    lines = [x.strip() for x in str(raw_text or "").splitlines() if x.strip()]
    if not lines and raw_text:
        lines = [str(raw_text).strip()]

    entries = []
    for line in lines:
        link = extract_first_url(line)
        if not link:
            continue

        pid = ""
        # Format baru: nomor boleh diikuti teks dulu, tidak harus langsung link.
        # Contoh: 01. Cek Nama Produk ... https://link
        m = re.match(r"^\s*([A-Za-z]*\d+[A-Za-z]*)\s*[\.)\]:\-–—]+\s*", line, flags=re.I)
        if m:
            pid = m.group(1).strip()

        entries.append({"id": pid, "line": line, "link": link})

    req_iter = iter(requested_ids)
    used = {e["id"].lower() for e in entries if e.get("id")}
    for e in entries:
        if e.get("id"):
            continue
        chosen = ""
        for candidate in req_iter:
            if str(candidate).lower() not in used:
                chosen = str(candidate)
                used.add(chosen.lower())
                break
        e["id"] = chosen

    return [e for e in entries if e.get("id")]


def parse_inline_name_from_line(raw_line, pid="", link=""):
    """Ambil nama produk dari baris input jika user menempel teks lengkap.

    Contoh yang didukung:
    01. Cek Yubeli Sally maxi skirt katun poplin | Rok panjang wanita dengan harga Rp106.000 https://s.shopee.co.id/xxx
    222. Nama Produk Bagus https://vt.tokopedia.com/t/xxxxx/ harga 65.000
    """
    data = parse_input_line_data(raw_line, pid, link)
    return data.get("name", "")


def format_price_from_input(value):
    """Format harga dari teks user.

    Catatan: jika user menulis 65.00, dianggap 65.000 karena format harga Indonesia
    sering kurang satu nol ketika diketik cepat.
    """
    raw = clean_text(value)
    raw = re.sub(r"(?i)^rp\s*", "", raw).strip()
    if re.fullmatch(r"\d{1,3}\.\d{2}", raw):
        raw = raw + "0"
    return format_price(raw)


def parse_input_line_data(raw_line, pid="", link=""):
    """Parser pasti dari teks input user, tanpa bergantung scraping marketplace.

    Tujuan:
    - Shopee share text: nama dari setelah 'Cek' sampai sebelum 'dengan harga'.
    - Harga dari kata 'dengan harga' / 'harga' baik sebelum maupun sesudah link.
    - TikTok/Tokopedia: kalau user menulis nama sebelum link, nama langsung dipakai.
    - Link tetap dari URL pertama di baris.
    """
    raw = clean_text(raw_line)
    result = {"name": "", "price": "", "link": extract_first_url(raw_line) or link or ""}
    if not raw:
        return result

    # Buang nomor di depan: 01. / 01 - / B01)
    line = re.sub(r"^\s*[A-Za-z]*\d+[A-Za-z]*\s*[\.)\]:\-–—]+\s*", "", raw, flags=re.I).strip()

    url_match = re.search(r"https?://[^\s]+", line, flags=re.I)
    before_url = line[:url_match.start()].strip() if url_match else line
    after_url = line[url_match.end():].strip() if url_match else ""
    no_url = re.sub(r"https?://[^\s]+", "", line, flags=re.I).strip()
    no_url = re.sub(r"\s+", " ", no_url)

    # Harga: prioritas dari kata 'dengan harga', lalu kata 'harga', lalu angka setelah link.
    price_patterns = [
        r"(?i)\bdengan\s+harga\s+mulai\s+dari\s*(Rp\s*[\d\.]+(?:,\d+)?|\d{1,3}(?:[\.\s]\d{2,3})+(?:,\d+)?|\d{4,9}(?:,\d+)?)",
        r"(?i)\bdengan\s+harga\s*(Rp\s*[\d\.]+(?:,\d+)?|\d{1,3}(?:[\.\s]\d{2,3})+(?:,\d+)?|\d{4,9}(?:,\d+)?)",
        r"(?i)\bharga\s*[:=\-]?\s*(Rp\s*[\d\.]+(?:,\d+)?|\d{1,3}(?:[\.\s]\d{2,3})+(?:,\d+)?|\d{4,9}(?:,\d+)?)",
    ]
    for source in [after_url, no_url, line]:
        if result["price"]:
            break
        for pat in price_patterns:
            m = re.search(pat, source or "", flags=re.I)
            if m:
                result["price"] = format_price_from_input(m.group(1))
                break

    if not result["price"] and after_url:
        tail = re.sub(r"^[\s,;:/|=\-–—]+", "", after_url)
        tail = re.sub(r"(?i)^harga\s*[:=\-]?\s*", "", tail).strip()
        m = re.search(r"(?i)(?:rp\s*)?(\d{1,3}(?:[\.\s]\d{2,3})+(?:,\d+)?|\d{4,9}(?:,\d+)?)", tail)
        if m:
            result["price"] = format_price_from_input(m.group(1))

    # Nama pola Shopee share: 'Cek ... dengan harga ...'
    name = ""
    patterns = [
        r"(?is)\bCek\s+(.+?)\s+dengan\s+harga\s+mulai\s+dari\s*(?:Rp\s*)?\d",
        r"(?is)\bCek\s+(.+?)\s+dengan\s+harga\s*(?:Rp\s*)?\d",
        r"(?is)^(.+?)\s+dengan\s+harga\s*(?:Rp\s*)?\d",
    ]
    for pat in patterns:
        m = re.search(pat, no_url, flags=re.I | re.S)
        if m:
            name = m.group(1)
            break

    # Fallback nama: teks sebelum URL.
    if not name and before_url:
        name = before_url

    # Fallback lain: teks sesudah URL sebelum kata harga, jika ada.
    if not name and after_url:
        tmp = re.split(r"(?i)\bharga\b|\bdengan\s+harga\b|\bRp\s*\d", after_url, maxsplit=1)[0].strip()
        if tmp and not re.fullmatch(r"(?i)(harga|rp|cek|dapatkan|sekarang|di|shopee|tokopedia|tiktok|shop)", tmp):
            name = tmp

    if name:
        # Bersihkan kata promosi umum.
        name = re.sub(r"(?i)^\s*(cek|lihat|beli|checkout|order|pesan)\s+", "", name).strip()
        name = re.split(r"(?i)\s+dengan\s+harga\b|\s+harga\b|\s+Dapatkan\s+di\b|\s+Dapatkan\b|\s+sekarang\b|\s+di\s+Shopee\b|\s+di\s+Tokopedia\b|\s+di\s+TikTok\b", name, maxsplit=1)[0].strip()
        name = re.sub(r"(?i)\b(?:Rp\s*)?\d{1,3}(?:[\.\s]\d{3})+(?:,\d+)?\b", "", name).strip()
        name = re.sub(r"[\s\-|,.;:]+$", "", name).strip()
        name = clean_title(name, max_len=170)
        if is_probably_product_name(name) and not re.fullmatch(r"\d+", name):
            result["name"] = name

    return result


def parse_inline_price_after_link(raw_line):
    """Ambil harga dari teks input.

    Mendukung:
    - Cek Nama Produk dengan harga Rp106.000 https://s.shopee.co.id/xxx
    - https://vt.tokopedia.com/t/xxxxx/ harga 65.000
    - https://vt.tokopedia.com/t/yyyyy/ 29.787
    """
    data = parse_input_line_data(raw_line)
    if data.get("price"):
        return data["price"]

    line = clean_text(raw_line)
    if not line:
        return ""

    m_url = re.search(r"https?://[^\s]+", line, flags=re.I)
    if not m_url:
        return ""

    tail = line[m_url.end():].strip()
    if not tail:
        return ""

    tail = re.sub(r"^[\s,;:/|=\-–—]+", "", tail)
    tail = re.sub(r"^harga\s*[:=\-]?\s*", "", tail, flags=re.I).strip()

    m_price = re.search(r"(?i)(?:rp\s*)?(\d{1,3}(?:[\.\s]\d{2,3})+(?:,\d+)?|\d{4,9}(?:,\d+)?)", tail)
    if not m_price:
        return ""

    price = format_price_from_input(m_price.group(1))
    return price if price and price != "Cek harga" else ""

def fixed_asset_image_path(product_id):
    safe_id = re.sub(r"[^0-9A-Za-z_-]", "", str(product_id or "").strip()) or "produk"
    return ASSET_DIR / f"{safe_id}.jpg"


def save_image_content_as_jpg(content, product_id):
    """Simpan bytes gambar ke public/assets/<no>.jpg."""
    target = fixed_asset_image_path(product_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not content:
        return str(target).replace("\\", "/")

    if Image is not None:
        try:
            img = Image.open(BytesIO(content))
            if img.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                alpha = img.getchannel("A") if "A" in img.getbands() else None
                bg.paste(img.convert("RGBA"), mask=alpha)
                img = bg
            else:
                img = img.convert("RGB")
            img.save(target, "JPEG", quality=92, optimize=True)
            return str(target).replace("\\", "/")
        except Exception:
            pass

    # Fallback kalau Pillow belum ada. Browser biasanya tetap bisa membaca dari signature,
    # tetapi sangat disarankan install pillow lewat setup_termux.sh.
    try:
        target.write_bytes(content)
    except Exception:
        pass
    return str(target).replace("\\", "/")


def make_placeholder_jpg(product_id):
    """Buat placeholder supaya path public/assets/<no>.jpg tetap ada."""
    target = fixed_asset_image_path(product_id)
    if target.exists() and target.stat().st_size > 0:
        return str(target).replace("\\", "/")

    target.parent.mkdir(parents=True, exist_ok=True)
    if Image is not None:
        try:
            img = Image.new("RGB", (900, 900), (250, 250, 250))
            img.save(target, "JPEG", quality=90)
            return str(target).replace("\\", "/")
        except Exception:
            pass
    return str(target).replace("\\", "/")


def ensure_fixed_product_image(image_value, product_id):
    """Pastikan field image menjadi public/assets/<no>.jpg.

    Kalau gambar otomatis berhasil diunduh, gambar dikonversi/disalin.
    Kalau gagal, dibuat placeholder JPG agar website tidak broken image.
    """
    target = fixed_asset_image_path(product_id)
    image_value = str(image_value or "").replace("\\", "/")

    if target.exists() and target.stat().st_size > 0:
        return str(target).replace("\\", "/")

    if image_value and not image_value.startswith("http") and "no-image.svg" not in image_value:
        source = Path(image_value)
        if source.exists() and source.is_file():
            try:
                content = source.read_bytes()
                return save_image_content_as_jpg(content, product_id)
            except Exception:
                pass

    return make_placeholder_jpg(product_id)


def normalize_link_for_cache(value):
    """Buat kunci link agar produk yang sama mudah dikenali.

    Contoh:
    https://s.shopee.co.id/80AUJ57UIV?share_channel_code=1
    dan
    https://s.shopee.co.id/80AUJ57UIV
    dianggap sama.
    """
    raw = extract_first_url(value) or clean_text(value)
    raw = str(raw or "").strip().rstrip(".,);]}>'\"")
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)
        if not parsed.netloc:
            return raw.lower()

        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = unquote(parsed.path or "").rstrip("/")

        # Link marketplace biasanya query-nya hanya tracking/share.
        # Untuk cache, cukup host + path supaya link yang sama tetap terdeteksi.
        marketplace_hosts = ["shopee", "tiktok", "tokopedia"]
        if any(x in netloc for x in marketplace_hosts):
            return f"{netloc}{path}".lower()

        query = parsed.query or ""
        return f"{netloc}{path}?{query}".lower() if query else f"{netloc}{path}".lower()
    except Exception:
        return raw.lower()


def find_cached_product_by_link(products, link):
    """Cari produk lama dari link yang pernah dimasukkan.

    Dipakai supaya kalau user memasukkan link yang sama, data lama
    seperti nama, harga, kategori, dan gambar langsung dipakai tanpa
    bertanya lagi.
    """
    target_key = normalize_link_for_cache(link)
    if not target_key:
        return None

    for p in products:
        keys = [
            p.get("link", ""),
            p.get("tiktokLink", ""),
            p.get("productLink", ""),
            p.get("affiliateLink", ""),
        ]
        for old_link in keys:
            if old_link and normalize_link_for_cache(old_link) == target_key:
                return p
    return None


def save_or_replace_product(products, product):
    """Simpan produk. Kalau ID sama, replace; kalau tidak, tambah baru."""
    replaced = False
    for i, old in enumerate(products):
        if str(old.get("id")) == str(product.get("id")):
            products[i] = product
            replaced = True
            break
    if not replaced:
        products.append(product)

    def sort_key(x):
        return int(only_digits(x.get("id", "")) or 999999)

    products.sort(key=sort_key)
    save_products(products)
    return products


def clone_cached_product(cached_product, new_id, new_link=None):
    """Buat produk baru dari cache produk lama."""
    product = normalize_product(dict(cached_product))
    product["id"] = str(new_id)
    if new_link:
        product["link"] = new_link
        product["tiktokLink"] = new_link
        product["platform"] = detect_platform(new_link) or product.get("platform", "Affiliate")
    product["tags"] = product.get("tags") or [product.get("category", "Atasan"), product.get("platform", "Affiliate")]
    return normalize_product(product)

def parse_shopee_share_text(value):
    """Parse teks share Shopee.

    Contoh input:
    Cek NAMA PRODUK dengan harga Rp85.000. Dapatkan di Shopee sekarang! https://s.shopee.co.id/xxxxx

    Hasil:
    - name  : teks antara 'Cek' dan 'dengan harga'
    - price : harga Rp...
    - link  : URL Shopee yang ada di teks

    Fungsi ini sengaja tidak butuh AppID/Secret, karena nama dan harga sudah ada di teks share.
    Gambar tetap dicoba otomatis dari link Shopee melalui fetch_product_data().
    """
    raw = clean_text(value)
    result = {"name": "", "price": "", "link": "", "platform": ""}
    if not raw:
        return result

    link = extract_first_url(raw)
    if link:
        result["link"] = link
        result["platform"] = detect_platform(link)

    if "shopee" not in raw.lower() and "shopee" not in (link or "").lower():
        return result

    # Hapus URL supaya pola nama/harga lebih bersih.
    no_url = re.sub(r"https?://[^\s]+", "", raw, flags=re.I).strip()
    no_url = re.sub(r"\s+", " ", no_url)

    patterns = [
        # Pola bawaan tombol share Shopee. Nama diambil penuh dari setelah "Cek" sampai sebelum "dengan harga".
        r"\bCek\s+(.+)\s+dengan\s+harga\s+mulai\s+dari\s+(Rp\s*[\d\.]+(?:,\d+)?)",
        r"\bCek\s+(.+)\s+dengan\s+harga\s+(Rp\s*[\d\.]+(?:,\d+)?)",
        # Variasi kalau kalimatnya sedikit berubah.
        r"^(.+)\s+dengan\s+harga\s+(Rp\s*[\d\.]+(?:,\d+)?)",
        r"^(.+)\s+harga\s+(Rp\s*[\d\.]+(?:,\d+)?)",
    ]

    for pat in patterns:
        m = re.search(pat, no_url, flags=re.I | re.S)
        if not m:
            continue
        name = clean_title(m.group(1))
        price = format_price(m.group(2))
        if is_probably_product_name(name):
            result["name"] = name
        if price and price != "Cek harga":
            result["price"] = price
        break

    # Fallback harga: ambil Rp pertama kalau pola nama tidak ketemu.
    if not result["price"]:
        m_price = re.search(r"Rp\s*[\d\.]+(?:,\d+)?", no_url, flags=re.I)
        if m_price:
            result["price"] = format_price(m_price.group(0))

    # Fallback nama: teks sebelum harga, buang kata Cek.
    if not result["name"] and result["price"]:
        before_price = no_url.split(result["price"], 1)[0]
        before_price = re.sub(r"\bCek\b", "", before_price, flags=re.I)
        before_price = re.sub(r"\bdengan\s+harga\b", "", before_price, flags=re.I)
        before_price = re.sub(r"\bharga\b", "", before_price, flags=re.I)
        name = clean_title(before_price)
        if is_probably_product_name(name):
            result["name"] = name

    return result

def write_shopee_debug(lines):
    """Simpan log debug Shopee terakhir supaya mudah dicek di Termux."""
    try:
        if isinstance(lines, str):
            text = lines
        else:
            text = "\n".join(str(x) for x in lines)
        SHOPEE_DEBUG_FILE.write_text(text.strip() + "\n", encoding="utf-8")
    except Exception:
        pass


def read_shopee_config():
    """Baca kredensial Shopee Affiliate Open API dari file lokal.

    Format file shopee_api_config.json:
    {
      "app_id": "123456",
      "secret": "ISI_SECRET_DARI_SHOPEE",
      "endpoint": "https://open-api.affiliate.shopee.co.id/graphql"
    }
    """
    if not SHOPEE_CONFIG_FILE.exists():
        return {}
    try:
        cfg = json.loads(SHOPEE_CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            return {}
        app_id = str(cfg.get("app_id") or cfg.get("appID") or cfg.get("appId") or "").strip()
        secret = str(cfg.get("secret") or cfg.get("app_secret") or cfg.get("appSecret") or cfg.get("api_key") or "").strip()
        endpoint = str(cfg.get("endpoint") or "https://open-api.affiliate.shopee.co.id/graphql").strip()
        if not app_id or not secret:
            return {}
        return {"app_id": app_id, "secret": secret, "endpoint": endpoint}
    except Exception:
        return {}


def compact_json_payload(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def shopee_affiliate_headers(app_id, secret, payload_text):
    """Header auth Shopee Affiliate Open API: SHA256 Credential + Timestamp + Signature."""
    timestamp = int(time.time())
    factor = str(app_id) + str(timestamp) + payload_text + str(secret)
    signature = hashlib.sha256(factor.encode("utf-8")).hexdigest()
    return {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id},Timestamp={timestamp},Signature={signature}",
    }


def price_from_shopee_affiliate(value):
    """Normalisasi harga dari API Affiliate.

    Beberapa endpoint mengirim harga dalam rupiah biasa, beberapa memakai satuan lebih kecil.
    Fungsi ini menghindari harga menjadi terlalu besar.
    """
    if value is None or isinstance(value, (dict, list)):
        return ""
    try:
        n = int(float(str(value).replace("Rp", "").replace(".", "").replace(",", ".").strip()))
    except Exception:
        return first_valid_price(value)
    if n <= 0:
        return ""
    # Shopee internal sering menyimpan harga *100000. Kalau hasilnya tidak masuk akal, kecilkan.
    while n > 50_000_000:
        n = n // 100000 if n % 100000 == 0 else n // 100
    return format_price(n)


def keyword_candidates_from_url(url):
    candidates = []
    try:
        parsed = urlparse(str(url or ""))
        path = unquote(parsed.path or "")
        slug = path.strip("/").split("/")[-1]
        slug = re.sub(r"[-.]?i\.\d+\.\d+.*$", "", slug, flags=re.I)
        slug = re.sub(r"\?.*$", "", slug)
        slug = re.sub(r"[\-_]+", " ", slug).strip()
        slug = clean_title(slug)
        if is_probably_product_name(slug):
            candidates.append(slug)
        qs = parse_qs(parsed.query)
        for key in ["keyword", "productName", "product_name", "title", "name"]:
            for val in qs.get(key, []):
                val = clean_title(val)
                if is_probably_product_name(val):
                    candidates.append(val)
    except Exception:
        pass
    # Unik, buang kandidat terlalu pendek.
    out = []
    seen = set()
    for c in candidates:
        low = c.lower()
        if low not in seen and len(c) >= 4:
            seen.add(low)
            out.append(c)
    return out[:3]


def extract_shopee_ids_from_any_url(url):
    """Ambil shopId dan itemId dari URL langsung maupun affiliate Shopee."""
    text = decode_many(str(url or ""), rounds=6)
    try:
        parsed = urlparse(text)
        qs = parse_qs(parsed.query)
        shop = qs.get("shopId") or qs.get("shopid") or qs.get("shop_id")
        item = qs.get("itemId") or qs.get("itemid") or qs.get("item_id") or qs.get("productId") or qs.get("productid")
        shopid = str(shop[0]).strip() if shop else ""
        itemid = str(item[0]).strip() if item else ""
        if shopid.isdigit() and itemid.isdigit():
            return shopid, itemid
    except Exception:
        pass
    m = re.search(r"[\.-]i\.(\d+)\.(\d+)", text, re.I)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"/product/(\d+)/(\d+)", text, re.I)
    if m:
        return m.group(1), m.group(2)
    return None, None


def shopee_offer_nodes_from_response(js):
    """Ambil list nodes dari bentuk response GraphQL yang berbeda-beda."""
    try:
        if not isinstance(js, dict):
            return []
        data = js.get("data") or {}
        offer = data.get("productOfferV2") or data.get("productOffer") or data.get("productOffers") or {}
        if isinstance(offer, dict):
            nodes = offer.get("nodes") or offer.get("items") or offer.get("list") or []
            if isinstance(nodes, list):
                return [x for x in nodes if isinstance(x, dict)]
        if isinstance(offer, list):
            return [x for x in offer if isinstance(x, dict)]
    except Exception:
        pass
    return []


def normalize_shopee_offer(node):
    name = clean_title(
        node.get("productName") or node.get("product_name") or node.get("itemName") or node.get("name") or node.get("title") or ""
    )
    img = normalize_image_value(
        node.get("imageUrl") or node.get("image_url") or node.get("image") or node.get("images") or node.get("thumbnail") or ""
    )
    price = (
        price_from_shopee_affiliate(node.get("price"))
        or price_from_shopee_affiliate(node.get("priceMin"))
        or price_from_shopee_affiliate(node.get("price_min"))
        or price_from_shopee_affiliate(node.get("priceMax"))
        or price_from_shopee_affiliate(node.get("price_max"))
    )
    shop_id = str(node.get("shopId") or node.get("shop_id") or "").strip()
    product_id = str(node.get("productId") or node.get("itemId") or node.get("item_id") or "").strip()
    product_link = node.get("productLink") or node.get("offerLink") or node.get("link") or ""
    return {
        "name": name if is_probably_product_name(name) else "",
        "price": price,
        "image_url": img if img and not bad_image(img) else "",
        "shop_id": shop_id,
        "item_id": product_id,
        "product_link": product_link,
    }


def fetch_shopee_affiliate_api(link, final_url=""):
    """Ambil data Shopee lewat Affiliate Open API resmi kalau kredensial tersedia.

    Ini jalur paling stabil untuk nama, harga, dan gambar karena bukan scrape halaman Shopee.
    Program mencari produk berdasarkan keyword dari slug URL lalu mencocokkan itemId/shopId bila ada.
    """
    cfg = read_shopee_config()
    logs = ["=== DEBUG SHOPEE AFFILIATE API ==="]
    if not cfg:
        logs.append("Config tidak ada. Buat shopee_api_config.json untuk jalur API resmi.")
        write_shopee_debug(logs)
        return {}

    shopid, itemid = extract_shopee_ids_from_any_url(final_url or link)
    if not shopid or not itemid:
        shopid2, itemid2 = extract_shopee_ids_from_any_url(link)
        shopid = shopid or shopid2
        itemid = itemid or itemid2
    logs.append(f"shopid={shopid or '-'} itemid={itemid or '-'}")

    keywords = []
    for source in [final_url, link]:
        keywords.extend(keyword_candidates_from_url(source))
    # Kalau affiliate link tidak punya slug, coba query kosong agar API tetap bisa dites.
    keywords = list(dict.fromkeys([k for k in keywords if k]))
    if not keywords:
        logs.append("Tidak ada keyword dari slug URL. API resmi butuh keyword untuk productOfferV2.")
        write_shopee_debug(logs)
        return {}

    query = """
    query FetchShopeeOffer($keyword:String,$page:Int,$limit:Int){
      productOfferV2(keyword:$keyword,page:$page,limit:$limit,sortType:1){
        nodes{
          productId
          productName
          price
          priceMin
          priceMax
          imageUrl
          productLink
          offerLink
          shopId
          shopName
          commissionRate
        }
      }
    }
    """
    endpoint = cfg["endpoint"]
    best = None
    all_nodes = []

    for kw in keywords[:3]:
        payload_obj = {"query": query, "operationName": "FetchShopeeOffer", "variables": {"keyword": kw, "page": 1, "limit": 50}}
        payload_text = compact_json_payload(payload_obj)
        headers = shopee_affiliate_headers(cfg["app_id"], cfg["secret"], payload_text)
        try:
            if requests is None:
                continue
            res = requests.post(endpoint, data=payload_text.encode("utf-8"), headers=headers, timeout=35)
            logs.append(f"keyword='{kw}' status={res.status_code}")
            try:
                js = res.json()
            except Exception:
                logs.append((res.text or "")[:500])
                continue
            if js.get("errors"):
                logs.append("errors=" + json.dumps(js.get("errors"), ensure_ascii=False)[:800])
            nodes = shopee_offer_nodes_from_response(js)
            logs.append(f"nodes={len(nodes)}")
            for node in nodes:
                data = normalize_shopee_offer(node)
                if data.get("name") or data.get("image_url") or data.get("price"):
                    all_nodes.append(data)
                    if itemid and data.get("item_id") == str(itemid):
                        if (not shopid) or data.get("shop_id") == str(shopid):
                            best = data
                            break
            if best:
                break
        except Exception as e:
            logs.append(f"error keyword='{kw}': {e}")

    if not best and all_nodes:
        best = all_nodes[0]
        logs.append("Tidak ketemu match itemId persis, pakai hasil pencarian teratas dari API.")

    write_shopee_debug(logs)
    if not best:
        return {}
    return {"name": best.get("name", ""), "price": best.get("price", "") or "Cek harga", "image_url": best.get("image_url", "")}


def configure_shopee_api():
    clear()
    show_header()
    panel(
        "Isi App ID dan Secret dari Shopee Affiliate Open API.\n"
        "File ini hanya tersimpan lokal di HP kamu: shopee_api_config.json\n\n"
        "Kalau belum punya App ID/Secret, buka dashboard Shopee Affiliate > Open API.",
        "Setup Shopee API Resmi",
        "cyan"
    )
    endpoint = ask("Endpoint", default="https://open-api.affiliate.shopee.co.id/graphql").strip()
    app_id = ask("App ID", default="").strip()
    secret = ask("Secret", default="").strip()
    if not app_id or not secret:
        warn("App ID/Secret belum diisi. Setup dibatalkan.")
        pause()
        return
    cfg = {"endpoint": endpoint, "app_id": app_id, "secret": secret}
    SHOPEE_CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    ok("Shopee API berhasil disimpan. Sekarang coba tambah produk Shopee lagi.")
    pause()



def normalize_product(p):
    category = clean_category_name(p.get("category") or p.get("type") or p.get("badge") or "Atasan")
    if category.lower() in {"oneset", "one set", "oneshet"}:
        category = "Gamis"
    category = canonical_category(category) or "Atasan"

    link = p.get("link") or p.get("tiktokLink") or "#"
    platform = p.get("platform") or detect_platform(link)

    p["id"] = str(p.get("id", "")).strip()
    p["name"] = p.get("name") or f"Produk {p['id']}"
    p["price"] = p.get("price") or "Cek harga"
    p["category"] = category
    p["type"] = category
    p["image"] = p.get("image") or str(NO_IMAGE).replace("\\", "/")
    p["link"] = link
    p["tiktokLink"] = link
    p["platform"] = platform

    p["subtitle"] = p.get("subtitle", "")
    p["size"] = p.get("size", "")
    p["colors"] = p.get("colors", [])
    p["tags"] = p.get("tags") or [category, platform]
    p["badge"] = p.get("badge") or category
    p["desc"] = p.get("desc", "")
    return p


def normalize_all(products):
    return [normalize_product(p) for p in products]


def only_digits(value):
    return re.sub(r"[^\d]", "", str(value or ""))


def next_product_id(products):
    numbers = []
    for p in products:
        d = only_digits(p.get("id", ""))
        if d:
            numbers.append(int(d))
    if not numbers:
        return "01"
    return str(max(numbers) + 1).zfill(2)


def clean_text(value):
    value = unescape(str(value or ""))
    value = value.replace("\\/", "/").replace("\\u002F", "/")
    value = value.replace("\\u003D", "=").replace("\\u0026", "&")
    return re.sub(r"\s+", " ", value).strip()


def to_int_price(value):
    if value is None:
        return None
    d = only_digits(value)
    if not d:
        return None
    try:
        n = int(d)
    except Exception:
        return None

    if n > 50_000_000:
        n = int(n / 100000)

    if 100 <= n <= 50_000_000:
        return n
    return None


def format_price(value):
    if value is None:
        return "Cek harga"
    if isinstance(value, str) and value.lower().strip() == "cek harga":
        return "Cek harga"

    n = to_int_price(value)
    if n is None:
        return str(value)
    return "Rp" + f"{n:,}".replace(",", ".")


def short(value, max_len=70):
    value = clean_text(value)
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def clean_title(title, max_len=160):
    title = clean_text(title)
    # Rapikan nama dari marketplace: Jas+Kulit+halus -> Jas Kulit halus.
    # Jangan memotong nama pada tanda | atau -, karena beberapa produk memakai pembatas itu di tengah nama.
    title = title.replace("+", " ")
    title = unquote(title).replace("+", " ")

    # Buang nama platform yang biasanya muncul sebagai suffix, tanpa menghapus isi nama produk.
    title = re.sub(r"\s*\|\s*(TikTok Shop|TikTok|Tokopedia|Shopee|Shopee Indonesia)\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*-\s*(TikTok Shop|TikTok|Tokopedia|Shopee|Shopee Indonesia)\s*$", "", title, flags=re.I)
    title = re.sub(r"\b(TikTok Shop|TikTok|Tokopedia|Shopee Indonesia|shopee\.co\.id)\b", "", title, flags=re.I)

    # Kalau masih ada pembatas, jadikan spasi saja agar nama tetap terbaca sampai akhir.
    title = title.replace("|", " ")
    title = re.sub(r"\s{2,}", " ", title).strip(" -|•–—")
    return short(title or "Produk Tanpa Nama", max_len)


def title_from_url_slug(url):
    """Ambil nama produk dari slug URL marketplace.

    Ini dibuat supaya Shopee mengikuti cara umum seperti TikTok: kalau title/meta tidak kebaca,
    nama masih bisa diambil dari teks link produk, misalnya:
    nama-produk-i.123.456 -> Nama Produk
    """
    try:
        parsed = urlparse(str(url or ""))
        path = unquote(parsed.path or "")
        path = path.strip("/")
        if not path:
            return ""

        # Buang format Shopee product path.
        slug = path.split("/")[-1]
        slug = re.sub(r"-i\.\d+\.\d+.*$", "", slug, flags=re.I)
        slug = re.sub(r"\.i\.\d+\.\d+.*$", "", slug, flags=re.I)
        slug = re.sub(r"i\.\d+\.\d+.*$", "", slug, flags=re.I)
        slug = re.sub(r"\?.*$", "", slug)
        slug = re.sub(r"[\-_+]+", " ", slug)
        slug = clean_title(slug)

        if is_probably_product_name(slug):
            return slug
    except Exception:
        pass
    return ""


def extract_title_like_tiktok(soup, html, final_url=""):
    """Cari nama produk dari sumber generik yang biasa berhasil untuk TikTok/Shopee."""
    title = (
        meta(soup, "og:title")
        or meta(soup, "twitter:title")
        or meta(soup, "title")
        or (soup.title.get_text(" ", strip=True) if soup and soup.title else "")
        or ""
    )
    title = clean_title(title)
    if is_probably_product_name(title):
        return title

    # Cari pola title/name di HTML yang sudah didecode.
    decoded = decode_many(html).replace("\\u0022", '"').replace("\\u003C", "<").replace("\\u003E", ">")
    title_patterns = [
        r'"(?:name|title|itemName|item_name|productName|product_name)"\s*:\s*"([^"<>]{5,180})"',
        r'<title[^>]*>(.*?)</title>',
        r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title|title)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:title|twitter:title|title)["\']',
    ]
    for pat in title_patterns:
        for m in re.findall(pat, decoded, re.I | re.S):
            cand = clean_title(m)
            if is_probably_product_name(cand):
                return cand

    return title_from_url_slug(final_url)


def extract_webp_images_like_tiktok(html):
    """Ambil kandidat gambar .webp/CDN dari HTML seperti alur TikTok.

    Shopee sering menyisipkan gambar produk sebagai URL WebP di HTML/JSON ter-escape.
    Fungsi ini mendecode beberapa lapisan lalu memprioritaskan URL .webp produk.
    """
    if not html:
        return []
    decoded = decode_many(html, rounds=6)
    decoded = unescape(decoded)
    decoded = decoded.replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":")
    decoded = decoded.replace("\\u0026", "&").replace("\\u003D", "=").replace("\\u0022", '"')

    candidates = []

    # URL gambar lengkap, terutama .webp.
    patterns = [
        r'https?://[^\s"\'<>\\]+?\.webp(?:\?[^\s"\'<>\\]+)?',
        r'https?://[^\s"\'<>\\]+?\.(?:jpg|jpeg|png)(?:\?[^\s"\'<>\\]+)?',
        r'https?://(?:down-id|down-ws-id|cf|cf-id|deo)\.img\.susercontent\.com/[^\s"\'<>\\]+',
        r'https?://[^\s"\'<>\\]+?susercontent\.com/[^\s"\'<>\\]+',
        r'https?://[^\s"\'<>\\]+?/file/[a-z0-9_\-]{18,}(?:@[^\s"\'<>\\]+)?',
    ]
    for pat in patterns:
        for u in re.findall(pat, decoded, re.I):
            candidates.append(u)

    # Gambar hash Shopee tanpa domain.
    hash_patterns = [
        r'"(?:image|cover|thumbnail|display_image|main_image)"\s*:\s*"([a-z0-9_\-]{24,})"',
        r'"images"\s*:\s*\[\s*"([a-z0-9_\-]{24,})"',
    ]
    for pat in hash_patterns:
        for h in re.findall(pat, decoded, re.I):
            if "/" not in h and "." not in h:
                candidates.extend([
                    f"https://down-id.img.susercontent.com/file/{h}@resize_w640_nl.webp",
                    f"https://down-id.img.susercontent.com/file/{h}",
                    f"https://down-ws-id.img.susercontent.com/file/{h}@resize_w640_nl.webp",
                    f"https://cf.shopee.co.id/file/{h}",
                ])

    out = []
    seen = set()
    for u in candidates:
        u = clean_text(u)
        u = u.replace("&amp;", "&")
        u = u.rstrip(".,);]}\\'")
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            continue
        if bad_image(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)

    def score(u):
        low = u.lower()
        score = 0
        if ".webp" in low:
            score += 40
        if "susercontent.com" in low or "shopee" in low:
            score += 30
        if "/file/" in low:
            score += 15
        if "resize_w640" in low or "resize_w800" in low or "resize_w1024" in low:
            score += 10
        if any(x in low for x in ["avatar", "logo", "icon", "sprite", "favicon", "mall-horizontal"]):
            score -= 80
        if any(x in low for x in ["50x50", "64x64", "100x100", "120x120", "260:260"]):
            score -= 10
        return score

    return sorted(out, key=score, reverse=True)


CATEGORY_KEYWORDS = {
    "Tas": [
        "tas selempang", "sling bag", "slingbag", "shoulder bag", "handbag",
        "hand bag", "tote bag", "totebag", "backpack", "ransel", "dompet",
        "clutch", "pouch", "waist bag", "bucket bag", "bag", "tas"
    ],
    "Sepatu": [
        "sepatu", "sandal", "sneakers", "sneaker", "heels", "flat shoes",
        "flatshoes", "wedges", "slip on", "slipon", "loafer", "boots",
        "pantofel", "mules", "platform shoes", "kasut", "sendal"
    ],
    "Hijab": [
        "hijab", "jilbab", "kerudung", "pashmina", "khimar", "bergo",
        "ciput", "inner hijab", "segi empat", "segiempat", "paris", "voal",
        "bella square", "pasmina", "shawl"
    ],
    "Gamis": [
        "gamis", "dress", "long dress", "maxi dress", "muslim dress",
        "one set", "one-set", "oneset", "oneshet", "setelan", "stelan", "overall",
        "tunik set", "paket set", "kaftan", "abaya", "daster", "midi dress",
        "mini dress", "jumpsuit"
    ],
    "Bawahan": [
        "bawahan", "celana", "kulot", "rok", "jeans", "pants", "skirt",
        "legging", "palazzo", "chino", "cargo", "cutbray", "flare pants",
        "wide leg", "trouser", "short pants", "hot pants", "jogger", "training"
    ],
    "Atasan": [
        "atasan", "blouse", "kemeja", "baju", "kaos", "top", "shirt",
        "cardigan", "outer", "jaket", "vest", "tunik", "crop top", "jersey",
        "hoodie", "sweater", "crewneck", "polo", "tanktop", "tank top",
        "manset", "inner", "brukat", "blazer", "rompi"
    ],
    "Tumbler": [
        "tumbler", "botol minum", "botol", "cup", "mug", "thermos", "termos"
    ],
    "Topi": [
        "topi", "cap", "bucket hat", "beanie", "hat"
    ],
    "Batik": [
        "batik", "kain batik", "jarik"
    ],
    "Kaos Kaki": [
        "kaos kaki", "socks", "sock", "stocking"
    ],
}


def category_match_text(value):
    value = clean_title(value, max_len=300) if "clean_title" in globals() else clean_text(value)
    value = unquote(str(value or "")).replace("+", " ")
    value = re.sub(r"https?://\S+", " ", value, flags=re.I)
    value = re.sub(r"[^0-9A-Za-zÀ-ÿĀ-žḀ-ỹ]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def keyword_match(text, keyword):
    text = " " + category_match_text(text) + " "
    keyword = category_match_text(keyword)
    if not keyword:
        return False

    if " " in keyword:
        return f" {keyword} " in text or keyword in text

    return re.search(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])", text) is not None


def guess_category_from_title(name):
    """Ambil kategori baru dari kata inti nama produk.

    Contoh:
    - "Tumbler stainless..." -> Tumbler
    - "Timba plastik..." -> Timba
    - "Jersey Germany..." -> Jersey (kalau tidak ditangkap keyword Atasan)
    """
    text = clean_title(name)
    text = re.sub(r"https?://\S+", " ", text, flags=re.I)
    text = re.sub(r"\b(Rp|IDR)\s*[\d\.,]+\b", " ", text, flags=re.I)
    text = re.sub(r"\b(cek|jual|promo|diskon|gratis|cod|ori|original|murah|termurah|terbaru|ready|stok|stock|import)\b", " ", text, flags=re.I)
    words = re.findall(r"[A-Za-zÀ-ÿĀ-žḀ-ỹ0-9]+", text)
    skip = {
        "dan", "atau", "dengan", "untuk", "wanita", "pria", "anak", "dewasa",
        "full", "printing", "premium", "korea", "korean", "style", "fashion",
        "ukuran", "size", "warna", "model", "produk", "shop", "official"
    }
    for word in words:
        w = word.strip()
        if len(w) < 3:
            continue
        if w.lower() in skip:
            continue
        return clean_category_name(w)
    return "Atasan"


def category_words(category):
    text = category_match_text(category)
    return [w for w in text.split() if len(w) >= 3]


def infer_category_from_name(name, extra_text="", allow_new=True):
    """Tebak kategori dari nama produk dengan skor yang lebih peka.

    Prioritasnya:
    1. Kategori yang sudah ada dan muncul persis di nama produk.
       Contoh: "Celana Cargo" -> kategori Celana Cargo, bukan hanya Bawahan.
    2. Keyword besar seperti hijab/celana/tas/sepatu/gamis.
    3. Kalau tidak ada yang cocok, ambil kata inti pertama sebagai saran kategori baru.
    """
    text = f"{name} {extra_text}"
    norm_text = " " + category_match_text(text) + " "
    categories = get_categories()
    scores = {cat: 0 for cat in categories}

    # Paling kuat: cocokkan langsung dengan kategori yang sudah ada di daftar kategori.
    for cat in categories:
        cat_norm = category_match_text(cat)
        if not cat_norm:
            continue
        if f" {cat_norm} " in norm_text or cat_norm in norm_text:
            # Kategori spesifik seperti "Celana Cargo" / "Kaos Polos" harus menang.
            scores[cat] = scores.get(cat, 0) + 18 + len(cat_norm.split()) * 4
        else:
            # Jika semua kata kategori muncul, tetap beri skor tinggi.
            words = category_words(cat)
            if words and all(keyword_match(norm_text, w) for w in words):
                scores[cat] = scores.get(cat, 0) + 12 + len(words) * 3

    # Keyword bawaan untuk kategori umum dan beberapa kategori custom.
    for cat, keywords in CATEGORY_KEYWORDS.items():
        target_cat = canonical_category(cat)
        if target_cat not in scores:
            scores[target_cat] = 0
        for kw in keywords:
            if keyword_match(text, kw):
                add = 8 if " " in kw else 5
                if cat in {"Gamis", "Hijab", "Sepatu", "Tas"}:
                    add += 1
                scores[target_cat] += add

    # Aturan tambahan agar tidak salah pilih ketika nama sangat jelas.
    specific_rules = [
        ("Celana Cargo", ["celana cargo", "cargo pants", "cargo"]),
        ("Celana Kulot Kargo", ["kulot kargo", "kulot cargo"]),
        ("Baggy Jeans", ["baggy jeans", "baggy jean"]),
        ("Jaket Baseball", ["jaket baseball", "baseball jacket"]),
        ("Polo Sweater", ["polo sweater"]),
        ("Kaos Polos", ["kaos polos", "plain shirt", "basic tee"]),
        ("Kaos Kaki", ["kaos kaki", "socks", "stocking"]),
        ("Piyama Tidur", ["piyama tidur", "baju tidur", "sleepwear", "pajamas", "pyjamas"]),
        ("Kain Batik", ["kain batik", "jarik"]),
        ("Sandal", ["sandal", "sendal"]),
        ("Hoodie", ["hoodie"]),
        ("Sweater", ["sweater", "crewneck"]),
        ("Topi", ["topi", "bucket hat", "cap", "beanie"]),
    ]
    for cat, keywords in specific_rules:
        cat_real = canonical_category(cat)
        for kw in keywords:
            if keyword_match(text, kw):
                if category_exists(cat_real):
                    scores[cat_real] = scores.get(cat_real, 0) + 35
                elif allow_new:
                    return clean_category_name(cat)

    # Penyeimbang kategori custom, tapi jangan sampai kategori spesifik menang hanya
    # karena satu kata umum seperti "celana" atau "kaos".
    generic_category_words = {
        "celana", "kaos", "baju", "wanita", "pria", "anak", "panjang",
        "pendek", "premium", "polos", "korea", "style", "model"
    }
    for cat in categories:
        if cat in DEFAULT_CATEGORIES:
            continue
        words = category_words(cat)
        if not words:
            continue
        matched_words = [w for w in words if keyword_match(text, w)]
        distinctive = [w for w in matched_words if w not in generic_category_words]
        if len(matched_words) >= 2 or distinctive:
            scores[cat] = scores.get(cat, 0) + 4 * len(matched_words) + 4 * len(distinctive)

    best = max(scores, key=scores.get) if scores else "Atasan"
    if scores.get(best, 0) > 0:
        return canonical_category(best)

    if allow_new:
        return guess_category_from_title(name)
    return "Atasan"


def meta(soup, key):
    for attr in ["property", "name", "itemprop"]:
        tag = soup.find("meta", attrs={attr: key})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return ""


def get_session():
    """Session HTTP yang lebih kuat untuk Termux.

    Shopee kadang menolak request biasa. Kalau paket cloudscraper berhasil terpasang,
    kita pakai itu sebagai lapisan aman tambahan. Ini bukan malware dan tidak bypass login;
    hanya membantu mengambil halaman publik yang memang bisa dibuka browser.
    """
    if cloudscraper is not None:
        try:
            s = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "android", "mobile": True}
            )
            s.headers.update(HEADERS)
            return s
        except Exception:
            pass
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def curl_get_text(url, referer="https://www.google.com/", timeout=35):
    """Fallback pakai curl karena di Termux curl kadang lebih berhasil mengikuti redirect."""
    try:
        cmd = [
            "curl", "-L", "-sS", "--compressed", "--max-time", str(timeout),
            "-A", HEADERS["User-Agent"],
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "-H", "Accept-Language: id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "-H", f"Referer: {referer}",
            "-w", "\n__FINAL_URL__:%{url_effective}",
            url,
        ]
        res = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout + 5)
        out = res.stdout or ""
        final_url = url
        marker = "\n__FINAL_URL__:"
        if marker in out:
            out, final_url = out.rsplit(marker, 1)
            final_url = final_url.strip() or url
        return final_url, out
    except Exception:
        return url, ""


def session_get_text(session, url, referer="https://www.google.com/", timeout=30):
    headers = dict(HEADERS)
    headers["Referer"] = referer
    try:
        res = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        final_url = res.url or url
        html = res.text or ""
        # Kalau diblokir/halaman terlalu kosong, coba curl sebagai fallback.
        if res.status_code in (403, 406, 418, 429, 503) or len(html) < 500:
            c_url, c_html = curl_get_text(url, referer=referer, timeout=timeout)
            if c_html and len(c_html) > len(html):
                return c_url, c_html
        return final_url, html
    except Exception:
        return curl_get_text(url, referer=referer, timeout=timeout)


def decode_many(text, rounds=4):
    value = str(text or "")
    for _ in range(rounds):
        new_value = unquote(value)
        if new_value == value:
            break
        value = new_value
    return value.replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":").replace("\\u0026", "&")


def extract_product_urls_from_text(text):
    decoded = decode_many(text)
    patterns = [
        r'https?://(?:www\.)?shopee\.co\.id/[^\s"\'<>]+',
        r'https?://(?:id\.)?shopee\.co\.id/[^\s"\'<>]+',
        r'https?://(?:www\.)?tokopedia\.com/[^\s"\'<>]+',
        r'https?://(?:www\.)?tiktok\.com/[^\s"\'<>]+',
    ]
    found = []
    for pat in patterns:
        for m in re.finditer(pat, decoded, re.I):
            u = m.group(0).replace("\\", "")
            u = u.rstrip(".,);]}'\"")
            found.append(u)
    return found


def resolve_short_link(session, link):
    # Resolve link pendek dan cari URL produk asli di HTML redirect/deeplink.
    try:
        final_url, html = session_get_text(session, link, referer="https://www.google.com/", timeout=35)
        decoded_all = decode_many("\n".join([link, final_url, html]))

        # Banyak affiliate link menyimpan URL asli di parameter encoded seperti url/deep_link/af_dp.
        urls = [final_url]
        try:
            parsed = urlparse(final_url)
            qs = parse_qs(parsed.query)
            for key, values in qs.items():
                if key.lower() in {"url", "u", "target", "redirect", "redirect_url", "deep_link", "deeplink", "af_dp", "deep_and_deferred"}:
                    for v in values:
                        urls.extend(extract_product_urls_from_text(v))
        except Exception:
            pass

        urls.extend(extract_product_urls_from_text(decoded_all))

        # Pilih URL yang paling mungkin produk, bukan landing biasa.
        def score_url(u):
            low = u.lower()
            score = 0
            if "shopee.co.id" in low:
                score += 20
            if re.search(r"i\.\d+\.\d+", low) or "/product/" in low:
                score += 40
            if "itemid" in low or "item_id" in low:
                score += 25
            if "shopid" in low or "shop_id" in low:
                score += 25
            if "s.shopee" in low or "shp.ee" in low or "shope.ee" in low:
                score -= 10
            if any(x in low for x in ["/buyer/login", "captcha", "security"]):
                score -= 50
            return score

        urls = [u for u in urls if u and u.startswith("http")]
        urls = list(dict.fromkeys(urls))
        if urls:
            urls.sort(key=score_url, reverse=True)
            return urls[0], html

        return final_url or link, html

    except Exception:
        return link, ""


def extract_price_from_html(html):
    candidates = []

    for m in re.findall(r"Rp\s*[\d\.\,]+", html, re.I):
        n = to_int_price(m)
        if n:
            candidates.append(n)

    patterns = [
        r'"price"\s*:\s*"?(\d{4,15})"?',
        r'"price_min"\s*:\s*"?(\d{4,15})"?',
        r'"price_max"\s*:\s*"?(\d{4,15})"?',
        r'"priceBeforeDiscount"\s*:\s*"?(\d{4,15})"?',
        r'"price_min_before_discount"\s*:\s*"?(\d{4,15})"?',
        r'"price_max_before_discount"\s*:\s*"?(\d{4,15})"?',
        r'"salePrice"\s*:\s*"?(\d{4,15})"?',
        r'"finalPrice"\s*:\s*"?(\d{4,15})"?',
        r'"amount"\s*:\s*"?(\d{4,15})"?',
    ]

    for pat in patterns:
        for m in re.findall(pat, html, re.I):
            n = to_int_price(m)
            if n:
                candidates.append(n)

    candidates = [x for x in candidates if 1_000 <= x <= 50_000_000]
    if not candidates:
        return None
    return min(candidates)


def bad_image(url):
    low = str(url or "").lower()
    bad_words = [
        "logo", "favicon", "avatar", "placeholder", "default", "apple-touch-icon",
        "tiktok-logo", "tokopedia-logo", "shopee-logo", "play.google",
        "appstore", "sprite", "icon_", "/icon", "manifest", "searchfilter",
        "mall-horizontal", "shopee-logo", "shopee.sg", "brand-assets"
    ]

    if any(x in low for x in bad_words):
        return True

    # Untuk Shopee, utamakan CDN gambar produk. Jangan ambil asset halaman.
    if "shopee" in low or "susercontent" in low:
        good = (
            "/file/" in low
            or "susercontent.com" in low
            or "down-id.img" in low
            or "down-ws-id.img" in low
            or "cf.shopee" in low
            or "deo.shopeemobile" in low
        )
        if not good:
            return True

    return False


def image_candidates(soup, html):
    values = []

    # Prioritas baru: ambil URL .webp/CDN langsung dari HTML seperti alur TikTok.
    values.extend(extract_webp_images_like_tiktok(html))

    for key in ["og:image", "twitter:image", "twitter:image:src", "image"]:
        v = meta(soup, key)
        if v:
            values.append(v)

    for img in soup.find_all("img"):
        for attr in ["src", "data-src", "data-original", "data-lazy-src"]:
            v = img.get(attr)
            if v:
                values.append(v)

    decoded = unquote(unquote(html)).replace("\\/", "/")

    # Shopee sering menyimpan gambar sebagai hash tanpa URL lengkap.
    # Contoh: "image":"id-11134207-7r98o-xxxx" atau "images":["sg-11134201-..."]
    hash_patterns = [
        r'"image"\s*:\s*"([a-z0-9_\-]{24,})"',
        r'"image_url"\s*:\s*"([^"]+)"',
        r'"images"\s*:\s*\[\s*"([a-z0-9_\-]{24,})"',
        r'"cover"\s*:\s*"([a-z0-9_\-]{24,})"',
        r'"thumbnail"\s*:\s*"([a-z0-9_\-]{24,})"',
    ]

    for hp in hash_patterns:
        for h in re.findall(hp, decoded, re.I):
            h = clean_text(h)
            if h.startswith("http"):
                values.append(h)
            elif "/" not in h and len(h) >= 24:
                values.extend([
                    f"https://down-id.img.susercontent.com/file/{h}",
                    f"https://down-ws-id.img.susercontent.com/file/{h}",
                    f"https://cf.shopee.co.id/file/{h}",
                ])

    regexes = [
        r'https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*',
        r'https?://(?:cf|down|deo|down-ws-id|cf-id)\.shopee\.[^"\']+/file/[^"\']+',
        r'https?://[^"\']+susercontent\.com/file/[^"\']+',
        r'https?://[^"\']+susercontent\.com/[^"\']+',
    ]

    for reg in regexes:
        for v in re.findall(reg, decoded, re.I):
            values.append(v)

    clean_values = []
    seen = set()
    for u in values:
        u = clean_text(u)
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            continue
        if bad_image(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        clean_values.append(u)

    def score(u):
        low = u.lower()
        s = 0
        if "shopee" in low or "susercontent" in low:
            s += 25
        if "cf.shopee" in low or "/file/" in low:
            s += 12
        if "ibyteimg" in low or "tokopedia" in low or "alicdn" in low:
            s += 10
        if "product" in low or "produk" in low or "oec" in low or "tos-" in low:
            s += 8
        if any(x in low for x in ["260:260", "100:100", "50:50", "64x64", "32x32"]):
            s -= 4
        if "logo" in low or "icon" in low:
            s -= 40
        return s

    return sorted(clean_values, key=score, reverse=True)


def valid_image_response(response):
    if response.status_code != 200:
        return False
    if len(response.content) < 2000:
        return False

    ctype = response.headers.get("content-type", "").lower()
    if "image" in ctype:
        return True

    sig = response.content[:16]
    return (
        sig.startswith(b"\xff\xd8") or
        sig.startswith(b"\x89PNG") or
        sig.startswith(b"RIFF") or
        sig.startswith(b"GIF")
    )


def looks_like_shopee_logo(image_path):
    # Deteksi logo Shopee sederhana:
    # logo sering dominan oranye/merah dan putih, bukan foto produk.
    # Kalau Pillow belum ada, fungsi ini tidak menghalangi proses.
    if Image is None:
        return False

    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size

        if w < 180 or h < 180:
            return True

        img.thumbnail((120, 120))
        pixels = list(img.getdata())
        total = len(pixels)

        orange = 0
        white = 0
        dark = 0

        for r, g, b in pixels:
            if r > 210 and 45 <= g <= 130 and b < 90:
                orange += 1
            if r > 235 and g > 235 and b > 235:
                white += 1
            if r < 35 and g < 35 and b < 35:
                dark += 1

        orange_ratio = orange / total
        white_ratio = white / total
        dark_ratio = dark / total

        # Logo Shopee biasanya dominan oranye putih, variasinya rendah.
        if orange_ratio > 0.35 and white_ratio > 0.12:
            return True

        # Logo/icon kecil di tengah background putih/oranye.
        if (orange_ratio + white_ratio) > 0.82 and dark_ratio < 0.05:
            return True

        return False

    except Exception:
        return False


def download_image(url, product_id):
    if not url:
        return make_placeholder_jpg(product_id)

    urls_to_try = [url]
    m = re.search(r"/file/([^/?#]+)", url)
    if m:
        img_hash = m.group(1)
        urls_to_try.extend([
            f"https://down-id.img.susercontent.com/file/{img_hash}",
            f"https://down-ws-id.img.susercontent.com/file/{img_hash}",
            f"https://cf.shopee.co.id/file/{img_hash}",
            f"https://deo.shopeemobile.com/shopee/shopee-pcmall-live-sg/product/{img_hash}",
        ])

    seen = set()
    for test_url in urls_to_try:
        if test_url in seen:
            continue
        seen.add(test_url)

        try:
            target = fixed_asset_image_path(product_id)
            r = requests.get(test_url, headers=HEADERS, timeout=30, allow_redirects=True)

            if not valid_image_response(r):
                continue

            image_path = save_image_content_as_jpg(r.content, product_id)

            if looks_like_shopee_logo(image_path):
                try:
                    Path(image_path).unlink()
                except Exception:
                    pass
                continue

            return str(target).replace("\\", "/")

        except Exception:
            continue

    return make_placeholder_jpg(product_id)

def extract_shopee_ids(url, html):
    """Cari shopid dan itemid dari URL, query, HTML, atau deeplink affiliate Shopee."""
    text = decode_many(f"{url}\n{html}")

    # 1) Query parameters: ?shopid=...&itemid=... atau ?shop_id=...&item_id=...
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        shop = (qs.get("shopid") or qs.get("shop_id") or qs.get("shopId") or [None])[0]
        item = (qs.get("itemid") or qs.get("item_id") or qs.get("itemId") or [None])[0]
        if shop and item:
            return str(shop), str(item)
    except Exception:
        pass

    # 2) Pola URL produk umum: nama-produk-i.SHOP.ITEM atau /product/SHOP/ITEM.
    patterns = [
        (r"i\.(\d{4,})\.(\d{4,})", "shop_item"),
        (r"/product/(\d{4,})/(\d{4,})", "shop_item"),
        (r"shopid[\"'=:\s]+(\d{4,}).{0,300}?itemid[\"'=:\s]+(\d{4,})", "shop_item"),
        (r"itemid[\"'=:\s]+(\d{4,}).{0,300}?shopid[\"'=:\s]+(\d{4,})", "item_shop"),
        (r"shop_id[\"'=:\s]+(\d{4,}).{0,300}?item_id[\"'=:\s]+(\d{4,})", "shop_item"),
        (r"item_id[\"'=:\s]+(\d{4,}).{0,300}?shop_id[\"'=:\s]+(\d{4,})", "item_shop"),
        (r'"shopid"\s*:\s*(\d{4,}).{0,1000}?"itemid"\s*:\s*(\d{4,})', "shop_item"),
        (r'"itemid"\s*:\s*(\d{4,}).{0,1000}?"shopid"\s*:\s*(\d{4,})', "item_shop"),
        (r'"shop_id"\s*:\s*(\d{4,}).{0,1000}?"item_id"\s*:\s*(\d{4,})', "shop_item"),
        (r'"item_id"\s*:\s*(\d{4,}).{0,1000}?"shop_id"\s*:\s*(\d{4,})', "item_shop"),
    ]

    for pat, order in patterns:
        m = re.search(pat, text, re.I | re.S)
        if not m:
            continue
        a, b = m.group(1), m.group(2)
        if order == "shop_item":
            return a, b
        return b, a

    # 3) Coba cari URL produk yang terselip di teks affiliate lalu ulangi.
    for candidate in extract_product_urls_from_text(text):
        if candidate != url:
            shopid, itemid = extract_shopee_ids(candidate, "")
            if shopid and itemid:
                return shopid, itemid

    return None, None


def shopee_image_url(image_hash):
    if not image_hash:
        return ""
    image_hash = str(image_hash).strip()
    if image_hash.startswith("http"):
        return image_hash
    return f"https://down-id.img.susercontent.com/file/{image_hash}"


def first_valid_price(*values):
    for value in values:
        if isinstance(value, (dict, list)):
            continue
        p = format_price(value)
        if p and p != "Cek harga":
            return p
    return ""


def is_probably_product_name(value):
    value = clean_title(value)
    if len(value) < 4:
        return False
    bad_titles = [
        "security check", "akses ditolak", "access denied", "captcha",
        "login", "masuk", "shopee indonesia", "tokopedia", "tiktok shop",
        "just a moment", "please wait", "verifikasi"
    ]
    low = value.lower()
    return not any(x in low for x in bad_titles)


def normalize_image_value(value):
    """Ubah value gambar dari API/JSON menjadi URL gambar yang bisa didownload."""
    if not value:
        return ""

    if isinstance(value, dict):
        for key in ["image", "image_url", "url", "thumb_url", "thumbnail", "cover", "display_image"]:
            img = normalize_image_value(value.get(key))
            if img:
                return img
        return ""

    if isinstance(value, list):
        for item in value:
            img = normalize_image_value(item)
            if img:
                return img
        return ""

    value = clean_text(value)
    if not value:
        return ""
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("http"):
        return value

    # Shopee sering menyimpan gambar hanya berupa hash, misalnya id-11134207-7r98o-xxxx.
    if re.fullmatch(r"[a-z0-9_\-]{18,}", value, re.I):
        return shopee_image_url(value)
    return ""


def get_nested_value(data, keys):
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def best_price_from_dict(data):
    price_keys = [
        "price", "price_min", "price_max", "priceBeforeDiscount", "price_before_discount",
        "salePrice", "sale_price", "finalPrice", "final_price", "amount", "priceAmount",
        "current_price", "discounted_price", "price_min_before_discount", "price_max_before_discount"
    ]

    for key in price_keys:
        if isinstance(data, dict) and data.get(key) is not None:
            p = first_valid_price(data.get(key))
            if p:
                return p

    nested_paths = [
        ["price_info", "price"], ["price_info", "price_min"], ["price_info", "price_max"],
        ["priceInfo", "price"], ["priceInfo", "price_min"], ["priceInfo", "finalPrice"],
        ["priceRange", "minPrice"], ["priceRange", "maxPrice"],
        ["offers", "price"], ["offers", "lowPrice"], ["offers", "highPrice"],
    ]
    for path in nested_paths:
        p = first_valid_price(get_nested_value(data, path))
        if p:
            return p

    models = data.get("models") if isinstance(data, dict) else None
    if isinstance(models, list):
        for model in models:
            if isinstance(model, dict):
                p = best_price_from_dict(model)
                if p:
                    return p

    return ""


def best_image_from_dict(data):
    image_keys = [
        "image", "images", "image_url", "imageUrl", "cover", "thumbnail", "thumb_url",
        "display_image", "primary_image", "main_image", "gallery", "image_list", "images_url"
    ]
    for key in image_keys:
        if isinstance(data, dict) and data.get(key):
            img = normalize_image_value(data.get(key))
            if img and not bad_image(img):
                return img
    return ""


def best_name_from_dict(data):
    name_keys = [
        "name", "title", "itemName", "item_name", "productName", "product_name",
        "item_card_display_name", "display_name", "short_name"
    ]
    for key in name_keys:
        if isinstance(data, dict) and isinstance(data.get(key), str) and is_probably_product_name(data.get(key)):
            return clean_title(data.get(key))
    return ""


def extract_balanced_json_after_marker(text, marker):
    """Ambil object JSON setelah marker JS seperti window.__INITIAL_STATE__ = {...}."""
    results = []
    start_from = 0
    decoder = json.JSONDecoder()
    while True:
        idx = text.find(marker, start_from)
        if idx < 0:
            break
        brace = text.find("{", idx)
        bracket = text.find("[", idx)
        candidates = [x for x in [brace, bracket] if x >= 0]
        if not candidates:
            break
        start = min(candidates)
        try:
            obj, end = decoder.raw_decode(text[start:])
            results.append(obj)
            start_from = start + end
        except Exception:
            start_from = idx + len(marker)
    return results


def extract_json_from_next_data(html):
    results = []
    for m in re.finditer(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        raw = m.group(1).strip()
        try:
            results.append(json.loads(raw))
        except Exception:
            pass
    return results


def extract_json_objects_from_html(soup, html):
    objects = []
    objects.extend(extract_json_from_next_data(html))

    # JSON-LD sering berisi nama, harga, dan gambar produk.
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            objects.append(json.loads(raw))
        except Exception:
            pass

    decoded = unquote(unquote(html)).replace("\\/", "/")
    markers = [
        "window.__INITIAL_STATE__", "__INITIAL_STATE__", "window.__APOLLO_STATE__",
        "__NEXT_DATA__", "__NUXT__", "window.__data", "window.__STORE__"
    ]
    for marker in markers:
        objects.extend(extract_balanced_json_after_marker(decoded, marker))

    return objects


def walk_find_product_data(obj):
    candidates = []

    def candidate_from_dict(x):
        name = best_name_from_dict(x)
        price = best_price_from_dict(x)
        image = best_image_from_dict(x)

        score = 0
        if name:
            score += 4
        if price:
            score += 3
        if image:
            score += 3

        id_keys = ["itemid", "item_id", "shopid", "shop_id", "product_id", "productId"]
        if any(k in x for k in id_keys):
            score += 4

        # Struktur Shopee biasanya punya image/images + itemid/shopid/name.
        if any(k in x for k in ["images", "image", "item_basic", "price_info"]):
            score += 1

        return score, {"name": name, "price": price, "image": image}

    def walk(x):
        if isinstance(x, dict):
            score, data = candidate_from_dict(x)
            if score >= 3:
                candidates.append((score, data))

            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(obj)
    if not candidates:
        return {"name": "", "price": "", "image": ""}

    candidates.sort(key=lambda item: item[0], reverse=True)
    merged = {"name": "", "price": "", "image": ""}
    for _, data in candidates:
        for key in merged:
            if not merged[key] and data.get(key):
                merged[key] = data[key]
        if all(merged.values()):
            break
    return merged


def shopee_preflight(session, product_url="https://shopee.co.id/"):
    """Ambil cookie publik Shopee supaya endpoint PDP lebih sering berhasil."""
    try:
        session_get_text(session, "https://shopee.co.id/", referer="https://www.google.com/", timeout=15)
        if product_url:
            session_get_text(session, product_url, referer="https://shopee.co.id/", timeout=15)
    except Exception:
        pass


def fetch_json_url(session, url, headers, timeout=25):
    """Ambil JSON via requests, lalu fallback curl jika request biasa gagal."""
    try:
        res = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if res.status_code == 200:
            try:
                return res.json()
            except Exception:
                text = res.text or ""
                if text.strip().startswith(("{", "[")):
                    return json.loads(text)
        # fallback curl untuk response 403/empty
        c_final, c_text = curl_get_text(url, referer=headers.get("Referer", "https://shopee.co.id/"), timeout=timeout)
        if c_text.strip().startswith(("{", "[")):
            return json.loads(c_text)
    except Exception:
        try:
            c_final, c_text = curl_get_text(url, referer=headers.get("Referer", "https://shopee.co.id/"), timeout=timeout)
            if c_text.strip().startswith(("{", "[")):
                return json.loads(c_text)
        except Exception:
            pass
    return None


def fetch_shopee_api(session, shopid, itemid, product_url="https://shopee.co.id/"):
    shopee_preflight(session, product_url)
    csrf = ""
    try:
        csrf = session.cookies.get("csrftoken") or session.cookies.get("csrf_token") or ""
    except Exception:
        csrf = ""

    headers = dict(HEADERS)
    headers.update({
        "Accept": "application/json, text/plain, */*",
        "X-API-SOURCE": "pc",
        "X-Requested-With": "XMLHttpRequest",
        "If-None-Match-": "55b03-0",
        "Referer": product_url or "https://shopee.co.id/",
        "Origin": "https://shopee.co.id",
    })
    if csrf:
        headers["X-CSRFToken"] = csrf

    base_params = {
        "shop_id": shopid,
        "item_id": itemid,
        "shopid": shopid,
        "itemid": itemid,
        "tz_offset_minutes": "420",
        "detail_level": "0",
    }

    urls = [
        f"https://shopee.co.id/api/v4/pdp/get_pc?shop_id={shopid}&item_id={itemid}&tz_offset_minutes=420&detail_level=0",
        f"https://shopee.co.id/api/v4/pdp/get_pc?shopid={shopid}&itemid={itemid}&tz_offset_minutes=420&detail_level=0",
        f"https://shopee.co.id/api/v4/pdp/get_rw?shopid={shopid}&itemid={itemid}",
        f"https://shopee.co.id/api/v4/item/get?itemid={itemid}&shopid={shopid}",
        f"https://shopee.co.id/api/v2/item/get?itemid={itemid}&shopid={shopid}",
        f"https://shopee.co.id/api/v4/product/get_product_detail?item_id={itemid}&shop_id={shopid}",
        f"https://shopee.co.id/api/v4/item/get_items_by_collection?itemid={itemid}&shopid={shopid}",
    ]

    best = {"name": "", "price": "", "image": ""}
    for api_url in urls:
        js = fetch_json_url(session, api_url, headers=headers, timeout=25)
        if not js:
            continue
        data = js.get("data") if isinstance(js, dict) else js
        if data is None:
            data = js

        candidates = []
        if isinstance(data, dict):
            candidates.append(data)
            for key in [
                "item", "item_basic", "product", "product_info", "pdp_data", "product_detail",
                "item_card", "item_card_displayed_asset", "components", "product_info_store"
            ]:
                if isinstance(data.get(key), dict):
                    candidates.append(data[key])
                elif isinstance(data.get(key), list):
                    candidates.extend([x for x in data[key] if isinstance(x, dict)])
        elif isinstance(data, list):
            candidates.extend([x for x in data if isinstance(x, dict)])

        for candidate in candidates:
            jdata = walk_find_product_data(candidate)
            for k in best:
                if not best[k] and jdata.get(k):
                    best[k] = jdata[k]

        # Walk seluruh JSON juga, karena struktur PDP Shopee sering berubah.
        jdata = walk_find_product_data(js)
        for k in best:
            if not best[k] and jdata.get(k):
                best[k] = jdata[k]

        if best.get("name") and best.get("price") and best.get("image"):
            break

    if best.get("name") or best.get("price") or best.get("image"):
        return {
            "name": best.get("name", ""),
            "price": best.get("price", "") or "Cek harga",
            "image_url": best.get("image", ""),
        }

    return {}



def clean_url_candidate(url):
    """Rapikan URL hasil ekstraksi dari HTML/JSON/redirect."""
    url = decode_many(url, rounds=6)
    url = unescape(url).replace("&amp;", "&")
    url = url.strip().strip('"\'<> )]}')
    url = re.sub(r"\\+", "", url)
    return url


def is_tokopedia_product_url(url):
    """Cek apakah URL Tokopedia terlihat seperti halaman produk, bukan shortlink/login/home."""
    try:
        parsed = urlparse(str(url or ""))
        host = parsed.netloc.lower()
        path = unquote(parsed.path or "").strip("/")
        if "tokopedia.com" not in host:
            return False
        if host.startswith("vt."):
            return False
        if not path or path.lower() in {"", "login", "cart", "wishlist", "search", "promo"}:
            return False
        if any(x in path.lower() for x in ["login", "captcha", "accounts", "oauth", "help"]):
            return False
        # URL produk biasanya minimal /nama-toko/nama-produk atau ada txid di query.
        if len(path.split("/")) >= 2:
            return True
        if any(k in parsed.query.lower() for k in ["txid", "productid", "product_id"]):
            return True
    except Exception:
        pass
    return False


def extract_urls_anywhere(text):
    """Ambil URL dari HTML/JSON, termasuk URL yang sudah ter-encode beberapa lapis."""
    decoded = decode_many(text, rounds=8)
    decoded = unescape(decoded)
    decoded = decoded.replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":").replace("\\u0026", "&")
    found = []
    for m in re.finditer(r"https?://[^\s\"'<>\\]+", decoded, re.I):
        found.append(clean_url_candidate(m.group(0)))

    # URL kadang muncul sebagai nilai parameter encoded: link=https%3A%2F%2Fwww.tokopedia.com%2F...
    for m in re.finditer(r"(?:link|url|u|target|redirect|redirect_url|deep_link|deeplink|af_dp|fallback_url)=([^&\s\"'<>]+)", decoded, re.I):
        value = clean_url_candidate(m.group(1))
        found.extend([clean_url_candidate(u) for u in re.findall(r"https?://[^\s\"'<>\\]+", decode_many(value, rounds=8), re.I)])
        if value.startswith("http"):
            found.append(value)

    out = []
    seen = set()
    for u in found:
        if not u.startswith("http"):
            continue
        key = u.lower().split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def choose_best_product_url(urls, fallback=""):
    """Pilih URL produk terbaik dari daftar kandidat."""
    urls = [clean_url_candidate(u) for u in (urls or []) if u]
    urls = list(dict.fromkeys(urls))

    def score(u):
        low = u.lower()
        parsed = urlparse(u)
        path = unquote(parsed.path or "").strip("/")
        sc = 0
        if "tokopedia.com" in low:
            sc += 20
        if is_tokopedia_product_url(u):
            sc += 55
        if "www.tokopedia.com" in low:
            sc += 8
        if "product" in low or "pdp" in low or "txid" in low:
            sc += 12
        if len(path.split("/")) >= 2:
            sc += 20
        if any(x in low for x in ["vt.tokopedia", "accounts", "login", "captcha", "help", "pulsa", "topup"]):
            sc -= 80
        return sc

    if urls:
        urls.sort(key=score, reverse=True)
        if score(urls[0]) > 0:
            return urls[0]
    return fallback or (urls[0] if urls else "")


def curl_headers(url, referer="https://www.google.com/", timeout=25):
    """Ambil header redirect via curl -I; berguna untuk link pendek Tokopedia."""
    try:
        cmd = [
            "curl", "-L", "-I", "-sS", "--max-time", str(timeout),
            "-A", HEADERS["User-Agent"],
            "-H", "Accept-Language: id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "-H", f"Referer: {referer}",
            "-w", "\n__FINAL_URL__:%{url_effective}",
            url,
        ]
        res = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout + 5)
        out = (res.stdout or "") + "\n" + (res.stderr or "")
        final_url = url
        marker = "\n__FINAL_URL__:"
        if marker in out:
            out, final_url = out.rsplit(marker, 1)
            final_url = final_url.strip() or url
        urls = [final_url]
        for m in re.finditer(r"(?im)^location:\s*(.+)$", out):
            urls.append(clean_url_candidate(m.group(1)))
        urls.extend(extract_urls_anywhere(out))
        return choose_best_product_url(urls, final_url), out
    except Exception:
        return url, ""


def resolve_tokopedia_short_link(session, link):
    """Resolver khusus vt.tokopedia.com agar nama/gambar bisa otomatis lagi jika target URL terbuka."""
    urls = [link]
    html_parts = []

    # 1) Requests/cloudscraper biasa.
    final_url, html = session_get_text(session, link, referer="https://www.google.com/", timeout=35)
    urls.append(final_url)
    html_parts.append(html or "")
    urls.extend(extract_urls_anywhere("\n".join([link, final_url or "", html or ""])))

    # 2) Header redirect via curl -I.
    h_url, h_text = curl_headers(link, timeout=25)
    urls.append(h_url)
    html_parts.append(h_text or "")
    urls.extend(extract_urls_anywhere(h_text or ""))

    # 3) Coba beberapa User-Agent karena link pendek kadang beda respons mobile/desktop.
    user_agents = [
        "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    ]
    for ua in user_agents:
        try:
            headers = dict(HEADERS)
            headers["User-Agent"] = ua
            res = session.get(link, headers=headers, timeout=25, allow_redirects=True)
            urls.append(res.url or "")
            html_parts.append(res.text or "")
            urls.extend(extract_urls_anywhere("\n".join([res.url or "", res.text or ""])))
        except Exception:
            pass

    target = choose_best_product_url(urls, final_url or link)
    return target or final_url or link, "\n".join(html_parts)


def extract_tokopedia_data_from_html(soup, html, final_url=""):
    """Ekstraksi khusus Tokopedia dari meta, JSON-LD, dan state NextJS/Apollo."""
    data = {"name": "", "price": "", "image_url": ""}
    if not html:
        return data

    # Meta tags paling cepat jika halaman produk terbuka.
    if soup:
        title = (
            meta(soup, "og:title")
            or meta(soup, "twitter:title")
            or meta(soup, "title")
            or (soup.title.get_text(" ", strip=True) if soup.title else "")
            or ""
        )
        title = clean_title(title)
        if is_probably_product_name(title) and not title.lower().startswith(("tokopedia", "login")):
            data["name"] = title
        img = meta(soup, "og:image") or meta(soup, "twitter:image") or meta(soup, "image") or ""
        if img and not bad_image(img):
            data["image_url"] = img
        mp = meta(soup, "product:price:amount") or meta(soup, "og:price:amount") or ""
        if mp:
            data["price"] = format_price(mp)

    decoded = decode_many(html, rounds=8)
    decoded = unescape(decoded).replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":").replace("\\u0026", "&").replace("\\u0022", '"')

    # Pola eksplisit Tokopedia/NextJS.
    name_patterns = [
        r'"(?:productName|product_name|name|title|seoTitle|displayName|productTitle)"\s*:\s*"([^"<>]{5,220})"',
        r'"(?:product_name|productName)"\s*:\s*\{[^{}]*"text"\s*:\s*"([^"<>]{5,220})"',
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
    ]
    for pat in name_patterns:
        for raw in re.findall(pat, decoded, re.I | re.S):
            cand = clean_title(raw)
            if is_probably_product_name(cand) and not cand.lower().startswith(("tokopedia", "masuk", "login")):
                data["name"] = data["name"] or cand
                break
        if data["name"]:
            break

    price_patterns = [
        r'"(?:price|priceValue|price_value|originalPrice|original_price|finalPrice|final_price)"\s*:\s*"?(Rp\s*[\d\.,]+|\d{4,12})"?',
        r'"(?:price|priceValue|finalPrice)"\s*:\s*\{[^{}]*"(?:value|amount)"\s*:\s*"?(\d{4,12})"?',
        r'Rp\s*[\d\.]+(?:,\d+)?',
    ]
    for pat in price_patterns:
        for raw in re.findall(pat, decoded, re.I | re.S):
            price = format_price(raw)
            if price and price != "Cek harga":
                data["price"] = data["price"] or price
                break
        if data["price"]:
            break

    image_patterns = [
        r'"(?:imageUrl|image_url|image|thumbnail|thumbnailUrl|thumbnail_url|urlOriginal|urlThumbnail|largeImage)"\s*:\s*"(https?://[^"<>]+)"',
        r'https?://images\.tokopedia\.net/[^\s"\'<>\\]+',
        r'https?://ecs7\.tokopedia\.net/[^\s"\'<>\\]+',
    ]
    for pat in image_patterns:
        for raw in re.findall(pat, decoded, re.I | re.S):
            img = clean_url_candidate(raw)
            if img and not bad_image(img):
                data["image_url"] = data["image_url"] or img
                break
        if data["image_url"]:
            break

    # Fallback nama dari slug final URL kalau shortlink berhasil jadi URL produk.
    if not data["name"] and is_tokopedia_product_url(final_url):
        slug_name = title_from_url_slug(final_url)
        if slug_name:
            data["name"] = slug_name

    return data



def write_tiktok_debug(logs):
    try:
        Path("tiktok_debug_last.txt").write_text("\n".join(map(str, logs)), encoding="utf-8")
    except Exception:
        pass


def clean_tiktok_product_title(value):
    """Rapikan kandidat nama dari TikTok/TikTok Shop dan buang judul generik."""
    title = clean_title(value, max_len=180)
    if not title:
        return ""

    # Buang label umum platform tanpa memotong nama produk.
    title = re.sub(r"(?i)^\s*(TikTok\s*Shop|TikTok)\s*[-|:•]+\s*", "", title).strip()
    title = re.sub(r"(?i)\s*[-|:•]+\s*(TikTok\s*Shop|TikTok|TikTok Shop Indonesia|Make Your Day)\s*$", "", title).strip()
    title = re.sub(r"(?i)\b(TikTok Shop Indonesia|TikTok Shop|TikTok)\b", "", title).strip(" -|:•")
    title = re.sub(r"\s+", " ", title).strip()

    low = title.lower()
    bad = [
        "make your day", "log in", "login", "sign up", "for you", "security check",
        "captcha", "access denied", "akses ditolak", "unsupported browser", "watch full video",
        "original sound", "suara asli", "tiktok" , "shop"
    ]
    if not title or any(x == low or low.startswith(x + " ") for x in bad):
        return ""
    if re.fullmatch(r"(?i)(produk|product|item)\s*\d*", title):
        return ""
    return title if is_probably_product_name(title) else ""


def extract_tiktok_urls_from_text(text):
    decoded = decode_many(str(text or ""), rounds=6)
    decoded = unescape(decoded).replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":")
    urls = []
    for pat in [
        r'https?://(?:[^\s"\'<>\\]+\.)?tiktok\.com/[^\s"\'<>\\]+',
        r'https?://(?:[^\s"\'<>\\]+\.)?tiktokglobalshop\.com/[^\s"\'<>\\]+',
    ]:
        for u in re.findall(pat, decoded, re.I):
            u = u.replace("\\", "").rstrip(".,);]}>'\"")
            urls.append(u)
    return list(dict.fromkeys(urls))


def score_tiktok_url(url):
    low = str(url or "").lower()
    score = 0
    if "shop.tiktok" in low or "tiktokglobalshop" in low:
        score += 60
    if "/product/" in low or "/view/product" in low or "product_id" in low or "item_id" in low:
        score += 80
    if re.search(r"/video/\d+", low):
        score += 35
    if "vt.tiktok" in low or "/t/" in low or "vm.tiktok" in low:
        score -= 5
    if any(x in low for x in ["login", "captcha", "verify", "security", "download", "about"]):
        score -= 70
    return score


def resolve_tiktok_short_link(session, link):
    """Resolve link pendek TikTok lalu ambil URL asli/landing yang paling mungkin berisi data produk."""
    try:
        final_url, html = session_get_text(session, link, referer="https://www.tiktok.com/", timeout=35)
        decoded = decode_many("\n".join([str(link), str(final_url), str(html)]), rounds=7)
        decoded = unescape(decoded).replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":")

        urls = [final_url or link]

        # Parameter redirect/deep link yang sering muncul pada link pendek/affiliate.
        for u in list(urls):
            try:
                parsed = urlparse(u)
                qs = parse_qs(parsed.query)
                for key, vals in qs.items():
                    if key.lower() in {"url", "u", "target", "redirect", "redirect_url", "share_url", "deeplink", "deep_link", "af_dp", "link"}:
                        for val in vals:
                            urls.extend(extract_tiktok_urls_from_text(val))
                            urls.extend(extract_product_urls_from_text(val))
            except Exception:
                pass

        # Meta refresh / JS redirect.
        for pat in [
            r'http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\']+)',
            r'location\.(?:href|replace)\s*\(?\s*["\']([^"\']+)["\']',
            r'"(?:redirect_url|target_url|share_url|canonical_url|url)"\s*:\s*"(https?://[^"<>]+)"',
        ]:
            for m in re.findall(pat, decoded, re.I):
                urls.extend(extract_tiktok_urls_from_text(m) or [m])

        urls.extend(extract_tiktok_urls_from_text(decoded))
        urls = [u for u in dict.fromkeys(urls) if u and str(u).startswith("http")]
        if urls:
            urls.sort(key=score_tiktok_url, reverse=True)
            return urls[0], html
        return final_url or link, html
    except Exception:
        return link, ""


def fetch_tiktok_oembed_data(session, url):
    """Fallback ringan untuk link video TikTok: ambil title dan thumbnail dari oEmbed."""
    data = {"name": "", "image_url": ""}
    if not url:
        return data
    try:
        api = "https://www.tiktok.com/oembed?" + urlencode({"url": url})
        headers = dict(HEADERS)
        headers["Accept"] = "application/json,text/plain,*/*"
        res = session.get(api, headers=headers, timeout=25, allow_redirects=True)
        if res.status_code != 200:
            return data
        js = res.json()
        title = clean_tiktok_product_title(js.get("title") or "")
        if title:
            data["name"] = title
        img = normalize_image_value(js.get("thumbnail_url") or js.get("thumbnailUrl") or "")
        if img and not bad_image(img):
            data["image_url"] = img
    except Exception:
        pass
    return data


def extract_tiktok_image_candidates(html):
    decoded = decode_many(str(html or ""), rounds=7)
    decoded = unescape(decoded)
    decoded = decoded.replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":")
    decoded = decoded.replace("\\u0026", "&").replace("\\u003D", "=").replace("\\u0022", '"')

    candidates = []
    patterns = [
        r'https?://[^\s"\'<>\\]+(?:ibyteimg|tiktokcdn|tiktokv|byteimg|p16-oec|p19-oec|p16-sign|sf16|phinf|tos-)[^\s"\'<>\\]+?\.(?:webp|jpg|jpeg|png)(?:\?[^\s"\'<>\\]+)?',
        r'https?://[^\s"\'<>\\]+(?:ibyteimg|tiktokcdn|tiktokv|byteimg|p16-oec|p19-oec|p16-sign|sf16|phinf|tos-)[^\s"\'<>\\]+',
    ]
    for pat in patterns:
        for u in re.findall(pat, decoded, re.I):
            candidates.append(u)

    clean_values = []
    seen = set()
    for u in candidates:
        u = clean_text(u)
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http") or bad_image(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        clean_values.append(u)

    def score(u):
        low = u.lower()
        s = 0
        if any(x in low for x in ["oec", "product", "ecom", "shop", "goods"]):
            s += 35
        if ".webp" in low:
            s += 18
        if any(x in low for x in ["720", "960", "1080", "origin", "large"]):
            s += 10
        if any(x in low for x in ["avatar", "profile", "logo", "icon", "sprite", "favicon", "music"]):
            s -= 80
        if any(x in low for x in ["100x100", "120x120", "160x160", "50x50", "64x64"]):
            s -= 15
        return s

    return sorted(clean_values, key=score, reverse=True)


def extract_tiktok_data_from_html(soup, html, final_url=""):
    """Ambil nama dan gambar dari HTML/JSON TikTok/TikTok Shop."""
    data = {"name": "", "image_url": "", "price": ""}
    decoded = decode_many(str(html or ""), rounds=7)
    decoded = unescape(decoded)
    decoded = decoded.replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":")
    decoded = decoded.replace("\\u0026", "&").replace("\\u003D", "=").replace("\\u0022", '"')

    title_candidates = [
        meta(soup, "og:title") if soup else "",
        meta(soup, "twitter:title") if soup else "",
        meta(soup, "title") if soup else "",
        soup.title.get_text(" ", strip=True) if soup and soup.title else "",
        title_from_url_slug(final_url),
    ]

    # JSON-LD / hydration state / embedded API sering menyimpan product_title atau title.
    patterns = [
        r'"(?:product_title|productTitle|product_name|productName|goods_name|goodsName|item_title|itemTitle|title|name)"\s*:\s*"([^"<>]{5,220})"',
        r'"desc"\s*:\s*"([^"<>]{8,220})"',
        r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\']',
    ]
    for pat in patterns:
        for m in re.findall(pat, decoded, re.I | re.S):
            title_candidates.append(m)

    # JSON objects, kalau struktur berhasil terbaca.
    try:
        for js in extract_json_objects_from_html(soup, html):
            jdata = walk_find_product_data(js)
            if jdata.get("name"):
                title_candidates.append(jdata["name"])
            if not data["image_url"] and jdata.get("image"):
                data["image_url"] = jdata["image"]
            if not data["price"] and jdata.get("price"):
                data["price"] = jdata["price"]
    except Exception:
        pass

    for cand in title_candidates:
        title = clean_tiktok_product_title(cand)
        if title:
            data["name"] = title
            break

    imgs = []
    for key in ["og:image", "twitter:image", "twitter:image:src", "image"]:
        try:
            v = meta(soup, key)
            if v:
                imgs.append(v)
        except Exception:
            pass
    imgs.extend(extract_tiktok_image_candidates(decoded))
    if not data["image_url"]:
        for img in imgs:
            img = normalize_image_value(img)
            if img and not bad_image(img):
                data["image_url"] = img
                break

    if not data["price"]:
        price_number = extract_price_from_html(decoded[:60000])
        if price_number:
            data["price"] = format_price(price_number)

    return data


def write_tokopedia_debug(logs):
    try:
        Path("tokopedia_debug_last.txt").write_text("\n".join(map(str, logs)), encoding="utf-8")
    except Exception:
        pass



# =========================
# Tokopedia Auto Nama SUPER
# =========================
# Bagian ini sengaja dibuat agresif karena link vt.tokopedia.com kadang hanya
# mengembalikan redirect/deeplink. Alurnya:
# 1) resolve link pendek dengan requests + curl + intent/deeplink parser
# 2) baca halaman target dengan beberapa referer/User-Agent
# 3) ambil meta/JSON/slug
# 4) fallback ke layanan metadata publik tanpa API key, kalau Termux masih diblokir.

def is_bad_tokopedia_name(value, pid=""):
    title = clean_title(value or "")
    low = title.lower().strip()
    pid = str(pid or "").strip().lower()
    bad_exact = {
        "", "tokopedia", "tokopedia seller", "tokopedia affiliate", "toko online",
        "jual beli online aman dan nyaman", "login", "masuk", "daftar", "captcha",
        "access denied", "security check", "produk", "product", "item",
        "tokopedia - jual beli online", "jual beli online terlengkap"
    }
    if low in bad_exact:
        return True
    if pid and low in {f"produk {pid}", f"product {pid}", f"item {pid}", pid}:
        return True
    if low.startswith(("tokopedia", "masuk", "login", "captcha", "akses ditolak", "security")):
        return True
    if len(low) < 5:
        return True
    if len(re.findall(r"[a-zA-ZÀ-ÿ0-9]", title)) < 5:
        return True
    return False


def clean_tokopedia_product_name(value, pid=""):
    title = clean_title(value or "", max_len=180)
    title = decode_many(title, rounds=4)
    title = unescape(title)
    title = title.replace("+", " ")
    # Buang prefix/suffix marketplace, tapi jangan potong nama panjang produk.
    title = re.sub(r"(?i)^\s*(jual|beli|harga)\s+", "", title).strip()
    title = re.sub(r"(?i)\s*(\||-|—|–|•|:)\s*(tokopedia|tokopedia seller|tokopedia affiliate|tiktok shop|shopee)\s*$", "", title).strip()
    title = re.sub(r"(?i)\b(tokopedia\s*(seller|affiliate)?|jual beli online aman dan nyaman)\b", "", title).strip(" -|:•")
    title = re.sub(r"\s+", " ", title).strip()
    if is_bad_tokopedia_name(title, pid):
        return ""
    return title


def extract_intent_and_deeplink_urls(text):
    """Ambil URL produk dari intent://, tokopedia://, fallback_url, dan string encoded."""
    raw = str(text or "")
    decoded = decode_many(raw, rounds=10)
    decoded = unescape(decoded)
    decoded = decoded.replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":").replace("\\u0026", "&").replace("\\u003D", "=").replace("\\u0022", '"')
    found = []

    # URL biasa/encoded.
    found.extend(extract_urls_anywhere(decoded))

    # Intent Android sering berisi S.browser_fallback_url=https%3A%2F%2F...
    for pat in [
        r"S\.browser_fallback_url=([^;\s\"'<>]+)",
        r"browser_fallback_url=([^;&\s\"'<>]+)",
        r"(?:fallback_url|redirect_url|target_url|deeplink|deep_link|af_dp|url|u|link)=([^&;\s\"'<>]+)",
    ]:
        for val in re.findall(pat, decoded, re.I):
            val = clean_url_candidate(val)
            if val.startswith("http"):
                found.append(val)
            found.extend(extract_urls_anywhere(val))

    # Tokopedia deeplink kadang berbentuk tokopedia://product/..?...&url=https...
    for m in re.finditer(r"tokopedia://[^\s\"'<>]+", decoded, re.I):
        deeplink = clean_url_candidate(m.group(0))
        parsed = urlparse(deeplink)
        qs = parse_qs(parsed.query)
        for vals in qs.values():
            for val in vals:
                val = clean_url_candidate(val)
                if val.startswith("http"):
                    found.append(val)
                found.extend(extract_urls_anywhere(val))
        # Jika path deeplink sudah memuat /nama-toko/nama-produk, ubah ke https.
        path = unquote(parsed.path or "").strip("/")
        if path and "/" in path and not path.lower().startswith(("product", "pdp", "home")):
            found.append("https://www.tokopedia.com/" + path)

    # Relative URL yang kadang muncul sebagai //www.tokopedia.com/toko/produk
    for m in re.findall(r"(?<!:)//(?:www\.)?tokopedia\.com/[^\s\"'<>\\]+", decoded, re.I):
        found.append("https:" + clean_url_candidate(m))

    out, seen = [], set()
    for u in found:
        u = clean_url_candidate(u)
        if not u.startswith("http"):
            continue
        key = u.lower().split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def curl_get_text_strong(url, referer="https://www.google.com/", timeout=40, ua=None):
    """curl lebih kuat: ikut redirect, simpan header+body, pakai HTTP/1.1."""
    try:
        ua = ua or HEADERS["User-Agent"]
        cmd = [
            "curl", "-L", "-sS", "--compressed", "--http1.1", "--max-time", str(timeout),
            "-A", ua,
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "-H", "Accept-Language: id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "-H", "Cache-Control: no-cache",
            "-H", f"Referer: {referer}",
            "-D", "-",
            "-w", "\n__FINAL_URL__:%{url_effective}\n__HTTP_CODE__:%{http_code}",
            url,
        ]
        res = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout + 8)
        out = (res.stdout or "") + "\n" + (res.stderr or "")
        final_url = url
        marker = "\n__FINAL_URL__:"
        if marker in out:
            body, tail = out.rsplit(marker, 1)
            final_url = tail.split("\n", 1)[0].strip() or url
            out = body + "\n" + tail
        return final_url, out
    except Exception:
        return url, ""


def fetch_public_metadata_services(session, url, logs=None):
    """Fallback metadata publik. Tidak wajib berhasil, tapi sering membantu link pendek."""
    data = {"name": "", "image_url": "", "price": "", "final_url": url, "html": ""}
    logs = logs if isinstance(logs, list) else []
    if not url or requests is None:
        return data

    endpoints = [
        ("microlink", "https://api.microlink.io/?" + urlencode({"url": url, "screenshot": "false", "meta": "false", "embed": "false"})),
        ("jsonlink", "https://jsonlink.io/api/extract?" + urlencode({"url": url})),
        # Jina Reader: endpoint ini mengambil versi teks dari halaman publik. Kalau gagal, diabaikan.
        ("jina", "https://r.jina.ai/http://r.jina.ai/http://" + url),
        ("jina2", "https://r.jina.ai/http://" + url.replace("https://", "").replace("http://", "")),
    ]
    for name, api in endpoints:
        try:
            headers = dict(HEADERS)
            headers["Accept"] = "application/json,text/plain,text/html,*/*"
            res = session.get(api, headers=headers, timeout=30, allow_redirects=True)
            txt = res.text or ""
            logs.append(f"META_{name}_STATUS={res.status_code} LEN={len(txt)}")
            data["html"] += "\n" + txt[:120000]
            if not txt:
                continue
            # JSON endpoints.
            try:
                js = res.json()
            except Exception:
                js = None
            if isinstance(js, dict):
                candidates = []
                if name == "microlink":
                    d = js.get("data") or {}
                    candidates.extend([d.get("title"), d.get("description")])
                    img = d.get("image") or d.get("logo") or {}
                    if isinstance(img, dict):
                        img = img.get("url") or img.get("src")
                    if img and not data["image_url"]:
                        data["image_url"] = normalize_image_value(str(img))
                    if d.get("url"):
                        data["final_url"] = d.get("url")
                elif name == "jsonlink":
                    candidates.extend([js.get("title"), js.get("description")])
                    img = js.get("images") or js.get("image") or ""
                    if isinstance(img, list) and img:
                        img = img[0]
                    if img and not data["image_url"]:
                        data["image_url"] = normalize_image_value(str(img))
                    if js.get("url"):
                        data["final_url"] = js.get("url")
                for cand in candidates:
                    cname = clean_tokopedia_product_name(cand)
                    if cname and not data["name"]:
                        data["name"] = cname
            # Text endpoint / fallback regex.
            if not data["name"]:
                for pat in [
                    r"(?im)^Title:\s*(.+)$",
                    r"(?im)^#\s+(.+)$",
                    r'"title"\s*:\s*"([^"<>]{5,220})"',
                    r'"name"\s*:\s*"([^"<>]{5,220})"',
                ]:
                    for m in re.findall(pat, txt, re.I | re.S):
                        cname = clean_tokopedia_product_name(m)
                        if cname:
                            data["name"] = cname
                            break
                    if data["name"]:
                        break
            if not data["image_url"]:
                imgs = image_candidates(BeautifulSoup(txt, "html.parser") if BeautifulSoup else None, txt) if BeautifulSoup else []
                if imgs:
                    data["image_url"] = imgs[0]
            if data["name"]:
                break
        except Exception as e:
            logs.append(f"META_{name}_ERR={type(e).__name__}: {e}")
    return data


def tokopedia_super_extract(session, link, product_id="", logs=None):
    logs = logs if isinstance(logs, list) else []
    result = {"name": "", "price": "", "image_url": "", "final_url": link, "html": ""}
    urls = [link]
    html_parts = []

    # Ambil dengan request biasa, curl biasa, curl kuat, dan beberapa referer.
    attempts = []
    try:
        attempts.append(session_get_text(session, link, referer="https://www.google.com/", timeout=35))
    except Exception:
        pass
    for referer in ["https://www.tokopedia.com/", "https://www.google.com/", "https://m.tokopedia.com/"]:
        try:
            attempts.append(curl_get_text_strong(link, referer=referer, timeout=40))
        except Exception:
            pass

    user_agents = [
        HEADERS.get("User-Agent", "Mozilla/5.0"),
        "Mozilla/5.0 (Linux; Android 14; Mobile; rv:125.0) Gecko/125.0 Firefox/125.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    ]
    for ua in user_agents:
        try:
            attempts.append(curl_get_text_strong(link, referer="https://www.tokopedia.com/", timeout=30, ua=ua))
        except Exception:
            pass

    for final_url, html in attempts:
        if final_url:
            urls.append(final_url)
        if html:
            html_parts.append(html)
            urls.extend(extract_urls_anywhere(html))
            urls.extend(extract_intent_and_deeplink_urls(html))

    urls.extend(extract_intent_and_deeplink_urls("\n".join([link] + urls + html_parts)))
    best_url = choose_best_product_url(urls, link)
    if best_url:
        result["final_url"] = best_url
        urls.insert(0, best_url)

    # Jika berhasil dapat URL asli produk, buka halaman produk itu lagi.
    for u in list(dict.fromkeys(urls))[:8]:
        if not u or not str(u).startswith("http"):
            continue
        try:
            fu, html = session_get_text(session, u, referer="https://www.tokopedia.com/", timeout=35)
            html_parts.append(html or "")
            if fu:
                result["final_url"] = choose_best_product_url([fu, result.get("final_url")], result.get("final_url") or fu)
            # curl body tambahan
            cfu, chtm = curl_get_text_strong(u, referer="https://www.tokopedia.com/", timeout=35)
            html_parts.append(chtm or "")
            if cfu:
                result["final_url"] = choose_best_product_url([cfu, result.get("final_url")], result.get("final_url") or cfu)
        except Exception:
            pass

    combined = "\n".join(html_parts)
    result["html"] = combined
    logs.append(f"TOKPED_SUPER_URLS={len(urls)} BEST={result.get('final_url')}")
    logs.append(f"TOKPED_SUPER_HTML_LEN={len(combined)}")

    try:
        soup = BeautifulSoup(combined, "html.parser") if BeautifulSoup else None
        data = extract_tokopedia_data_from_html(soup, combined, result.get("final_url") or link)
        for k in ["name", "price", "image_url"]:
            if data.get(k) and not result.get(k):
                result[k] = data[k]
    except Exception as e:
        logs.append(f"TOKPED_SUPER_EXTRACT_ERR={type(e).__name__}: {e}")

    # Kandidat nama tambahan dari semua teks, termasuk JSON hydration dan markdown.
    if not result["name"] or is_bad_tokopedia_name(result["name"], product_id):
        decoded = decode_many(combined, rounds=10)
        decoded = unescape(decoded).replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":").replace("\\u0026", "&").replace("\\u003D", "=").replace("\\u0022", '"')
        title_candidates = []
        for pat in [
            r'"(?:productName|product_name|productTitle|product_title|itemName|item_name|goodsName|goods_name|displayName|title|name)"\s*:\s*"([^"<>]{5,260})"',
            r'"(?:seo_title|seoTitle|metaTitle)"\s*:\s*"([^"<>]{5,260})"',
            r'(?im)^Title:\s*(.+)$',
            r'(?im)^#\s+(.+)$',
            r'<title[^>]*>(.*?)</title>',
            r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title|title)["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:title|twitter:title|title)["\']',
        ]:
            for m in re.findall(pat, decoded, re.I | re.S):
                title_candidates.append(m)
        # Slug dari URL produk asli kalau ada.
        for u in [result.get("final_url"), link] + urls:
            slug = title_from_url_slug(u)
            if slug:
                title_candidates.append(slug)
        # Pilih kandidat terbaik.
        best_name = ""
        best_score = -999
        for cand in title_candidates:
            cname = clean_tokopedia_product_name(cand, product_id)
            if not cname:
                continue
            low = cname.lower()
            score = min(len(cname), 120)
            if any(w in low for w in ["gamis", "hijab", "tas", "celana", "baju", "abaya", "dress", "rok", "kemeja", "sepatu", "tumbler", "batik", "pashmina", "oneset", "kulot"]):
                score += 40
            if "tokopedia" in low:
                score -= 80
            if len(cname.split()) >= 3:
                score += 15
            if score > best_score:
                best_score = score
                best_name = cname
        if best_name:
            result["name"] = best_name

    # Harga dan gambar tambahan.
    if not result["price"]:
        pn = extract_price_from_html(combined[:120000])
        if pn:
            result["price"] = format_price(pn)
    if not result["image_url"]:
        try:
            imgs = image_candidates(BeautifulSoup(combined, "html.parser"), combined) if BeautifulSoup else []
            # Prioritas Tokopedia CDN.
            imgs = sorted(imgs, key=lambda u: ("images.tokopedia.net" in u.lower(), ".webp" in u.lower()), reverse=True)
            if imgs:
                result["image_url"] = imgs[0]
        except Exception:
            pass

    # Fallback metadata publik bila masih belum dapat nama.
    if not result["name"] or is_bad_tokopedia_name(result["name"], product_id):
        for u in list(dict.fromkeys([result.get("final_url"), link] + urls))[:4]:
            meta_data = fetch_public_metadata_services(session, u, logs)
            if meta_data.get("name") and not is_bad_tokopedia_name(meta_data["name"], product_id):
                result["name"] = meta_data["name"]
            if meta_data.get("image_url") and not result["image_url"]:
                result["image_url"] = meta_data["image_url"]
            if meta_data.get("price") and not result["price"]:
                result["price"] = meta_data["price"]
            if meta_data.get("final_url"):
                result["final_url"] = choose_best_product_url([meta_data["final_url"], result.get("final_url")], result.get("final_url") or meta_data["final_url"])
            if result.get("name") and not is_bad_tokopedia_name(result["name"], product_id):
                break

    logs.append(f"TOKPED_SUPER_NAME={result.get('name') or '-'}")
    logs.append(f"TOKPED_SUPER_PRICE={result.get('price') or '-'}")
    logs.append(f"TOKPED_SUPER_IMAGE={'yes' if result.get('image_url') else '-'}")
    return result

def fetch_product_data(link, product_id):
    default = {
        "name": f"Produk {product_id}",
        "price": "Cek harga",
        "category": "Atasan",
        "image": str(NO_IMAGE).replace("\\", "/"),
        "platform": detect_platform(link),
        "final_url": link,
    }

    if requests is None or BeautifulSoup is None:
        return default

    session = get_session()
    debug_logs = [f"INPUT_LINK={link}", f"PRODUCT_ID={product_id}"]

    try:
        if "shopee" in link.lower():
            shopee_preflight(session, "https://shopee.co.id/")

        link_lower = str(link or "").lower()
        if "tokopedia" in link_lower:
            resolved_url, redirect_html = resolve_tokopedia_short_link(session, link)
        elif "tiktok" in link_lower:
            resolved_url, redirect_html = resolve_tiktok_short_link(session, link)
        else:
            resolved_url, redirect_html = resolve_short_link(session, link)
        debug_logs.append(f"RESOLVED_URL={resolved_url}")
        final_url, page_html = session_get_text(session, resolved_url, referer="https://www.google.com/", timeout=35)
        html = (redirect_html or "") + "\n" + (page_html or "")
        final_url = final_url or resolved_url or link
        soup = BeautifulSoup(html, "html.parser")
        plat = detect_platform(final_url or link)
        debug_logs.append(f"FINAL_URL={final_url}")
        debug_logs.append(f"PLATFORM={plat}")

        title = extract_title_like_tiktok(soup, html, final_url)

        desc = (
            meta(soup, "og:description")
            or meta(soup, "description")
            or meta(soup, "twitter:description")
            or ""
        )

        name = title if title else f"Produk {product_id}"
        price = "Cek harga"
        image_url = ""
        auto_price_allowed = plat != "TikTok"

        # TikTok / TikTok Shop: ambil nama dan gambar dari HTML, state JSON, serta oEmbed.
        if plat == "TikTok":
            tiktok_data = extract_tiktok_data_from_html(soup, html, final_url)
            oembed_data = fetch_tiktok_oembed_data(session, final_url or resolved_url or link)
            debug_logs.append(f"TIKTOK_NAME={tiktok_data.get('name') or oembed_data.get('name') or '-'}")
            debug_logs.append(f"TIKTOK_IMAGE={'yes' if (tiktok_data.get('image_url') or oembed_data.get('image_url')) else '-'}")
            if tiktok_data.get("name") and is_probably_product_name(tiktok_data.get("name")):
                name = tiktok_data["name"]
            elif oembed_data.get("name") and is_probably_product_name(oembed_data.get("name")):
                name = oembed_data["name"]
            if tiktok_data.get("image_url"):
                image_url = tiktok_data["image_url"]
            elif oembed_data.get("image_url"):
                image_url = oembed_data["image_url"]
            # Harga TikTok tetap tidak dipakai otomatis kecuali user menulis harga di baris input.
            write_tiktok_debug(debug_logs)

        # Tokopedia: coba ekstraksi khusus dari URL final, meta, dan state halaman.
        if plat == "Tokopedia":
            tokped_data = extract_tokopedia_data_from_html(soup, html, final_url)
            debug_logs.append(f"TOKOPEDIA_NAME={tokped_data.get('name') or '-'}")
            debug_logs.append(f"TOKOPEDIA_PRICE={tokped_data.get('price') or '-'}")
            debug_logs.append(f"TOKOPEDIA_IMAGE={'yes' if tokped_data.get('image_url') else '-'}")
            if tokped_data.get("name") and is_probably_product_name(tokped_data.get("name")):
                name = tokped_data["name"]
            if tokped_data.get("price") and price == "Cek harga":
                price = tokped_data["price"]
            if tokped_data.get("image_url"):
                image_url = tokped_data["image_url"]

            # Super fallback khusus vt.tokopedia.com / link affiliate.
            # Ini dicoba sebelum kategori, supaya nama produk benar-benar muncul.
            if (not is_probably_product_name(name)) or is_placeholder_product_name(name, product_id):
                super_data = tokopedia_super_extract(session, link, product_id, debug_logs)
                if super_data.get("final_url"):
                    final_url = super_data["final_url"]
                if super_data.get("name") and is_probably_product_name(super_data.get("name")):
                    name = super_data["name"]
                if super_data.get("price") and price == "Cek harga":
                    price = super_data["price"]
                if super_data.get("image_url") and not image_url:
                    image_url = super_data["image_url"]
            write_tokopedia_debug(debug_logs)

        # Shopee: jalur terbaik adalah Affiliate Open API resmi (butuh App ID + Secret).
        # Kalau belum diset, lanjut ke fallback HTML/API publik.
        if plat == "Shopee":
            official_data = fetch_shopee_affiliate_api(link, final_url)
            if official_data:
                if official_data.get("name") and is_probably_product_name(official_data.get("name")):
                    name = official_data["name"]
                if official_data.get("price"):
                    price = official_data["price"]
                if official_data.get("image_url"):
                    image_url = official_data["image_url"]

        # Fallback Shopee mirip TikTok:
        # 1) gambar diprioritaskan dari WebP/CDN yang muncul di halaman/redirect
        # 2) nama dari title/meta/slug link
        # 3) API/JSON publik hanya sebagai penguat kalau Shopee tidak memblokir
        if plat == "Shopee":
            webp_imgs = extract_webp_images_like_tiktok(html)
            if webp_imgs and not image_url:
                image_url = webp_imgs[0]
            slug_name = title_from_url_slug(final_url) or title_from_url_slug(resolved_url) or title_from_url_slug(link)
            if (not is_probably_product_name(name)) and slug_name:
                name = slug_name

            shopid, itemid = extract_shopee_ids(final_url, html)
            if shopid and itemid:
                api_data = fetch_shopee_api(session, shopid, itemid, final_url)
                if api_data:
                    if (not is_probably_product_name(name)) and api_data.get("name"):
                        name = api_data["name"]
                    if price == "Cek harga" and api_data.get("price"):
                        price = api_data["price"]
                    if not image_url and api_data.get("image_url"):
                        image_url = api_data["image_url"]

        if price == "Cek harga" or not image_url or name.startswith("Produk ") or not is_probably_product_name(name):
            for js in extract_json_objects_from_html(soup, html):
                jdata = walk_find_product_data(js)
                if (name.startswith("Produk ") or not is_probably_product_name(name)) and jdata.get("name"):
                    name = jdata["name"]
                if auto_price_allowed and price == "Cek harga" and jdata.get("price"):
                    price = jdata["price"]
                if not image_url and jdata.get("image"):
                    image_url = jdata["image"]

        if auto_price_allowed and price == "Cek harga":
            meta_price = (
                meta(soup, "product:price:amount")
                or meta(soup, "og:price:amount")
                or meta(soup, "twitter:data1")
            )
            if meta_price:
                price = format_price(meta_price)

        if auto_price_allowed and price == "Cek harga":
            price_number = extract_price_from_html(f"{title} {desc} {html[:30000]}")
            if price_number:
                price = format_price(price_number)

        if not auto_price_allowed:
            # TikTok: gambar/nama boleh otomatis, tapi harga sengaja dibuat manual.
            price = "Cek harga"

        if not image_url:
            imgs = extract_tiktok_image_candidates(html) if plat == "TikTok" else []
            if not imgs:
                imgs = image_candidates(soup, html)
            image_url = imgs[0] if imgs else ""

        if not is_probably_product_name(name) or is_placeholder_product_name(name, product_id):
            if plat == "TikTok":
                extra_tiktok = extract_tiktok_data_from_html(soup, html, final_url)
                if extra_tiktok.get("name"):
                    name = extra_tiktok["name"]
            elif plat == "Tokopedia":
                super_data = tokopedia_super_extract(session, link, product_id, debug_logs)
                if super_data.get("final_url"):
                    final_url = super_data["final_url"]
                if super_data.get("name") and is_probably_product_name(super_data.get("name")):
                    name = super_data["name"]
                if super_data.get("price") and price == "Cek harga":
                    price = super_data["price"]
                if super_data.get("image_url") and not image_url:
                    image_url = super_data["image_url"]
                write_tokopedia_debug(debug_logs)
            if not is_probably_product_name(name) or is_placeholder_product_name(name, product_id):
                name = title_from_url_slug(final_url) or title_from_url_slug(resolved_url) or title_from_url_slug(link) or f"Produk {product_id}"

        image_path = download_image(image_url, product_id) if image_url else str(NO_IMAGE).replace("\\", "/")
        category = infer_category_from_name(name, desc)

        return {
            "name": name,
            "price": price,
            "category": category,
            "image": image_path,
            "platform": plat,
            "final_url": final_url,
        }

    except Exception as e:
        if "tokopedia" in str(link).lower():
            try:
                debug_logs.append(f"ERROR={type(e).__name__}: {e}")
                write_tokopedia_debug(debug_logs)
            except Exception:
                pass
        return default


def input_name(auto_name):
    auto_name = auto_name or "Produk Tanpa Nama"
    if RICH:
        panel(
            f"Nama otomatis terbaca:\n[bold yellow]{auto_name}[/]\n\n"
            "Tekan ENTER untuk memakai nama ini, atau ketik nama manual.",
            "Konfirmasi Nama",
            "yellow"
        )
    value = ask("Nama produk", default=auto_name).strip()
    return value or auto_name


def input_price(auto_price, platform=""):
    auto_price = auto_price or "Cek harga"
    platform = platform or ""

    if platform == "TikTok":
        if RICH:
            panel(
                "Link TikTok: harga otomatis dimatikan supaya tidak salah harga.\n"
                "Silakan isi harga manual. Contoh: 125000 atau Rp125.000",
                "Harga Manual TikTok",
                "magenta"
            )
        value = ask("Harga produk manual", default="").strip()
        if not value:
            warn("Harga TikTok belum diisi. Produk tetap disimpan dengan harga 'Cek harga'.")
            return "Cek harga"
        return format_price(value)

    if RICH:
        panel(
            f"Harga otomatis terbaca: [bold yellow]{auto_price}[/]\n"
            "Tekan ENTER untuk memakai harga tersebut, atau ketik manual.\n"
            "Contoh: 125000 atau Rp125.000",
            "Konfirmasi Harga",
            "yellow"
        )

    default = "" if auto_price == "Cek harga" else auto_price
    value = ask("Harga produk", default=default).strip()
    if not value and auto_price != "Cek harga":
        return auto_price
    if not value:
        return "Cek harga"
    return format_price(value)


def print_category_table_plain(categories, auto_category=""):
    """Tabel kategori rapi untuk mode Termux biasa tanpa Rich."""
    width = 72
    border = "cyan"
    col_count = 3
    col_width = (width - 4) // col_count
    print(term_color("┌" + "─" * (width - 2) + "┐", border, bold=True))
    print(term_color("│", border, bold=True) + term_color(" DAFTAR KATEGORI ".center(width - 2), "white", bold=True) + term_color("│", border, bold=True))
    print(term_color("├" + "─" * (width - 2) + "┤", border, bold=True))

    items = []
    for i, cat in enumerate(categories, start=1):
        mark = "*" if str(cat).lower() == str(auto_category or "").lower() else " "
        text = f"{i:>2}. {cat}{mark}"
        if len(text) > col_width - 1:
            text = text[:col_width - 4] + "..."
        items.append(text.ljust(col_width))

    for start in range(0, len(items), col_count):
        row = items[start:start + col_count]
        while len(row) < col_count:
            row.append("".ljust(col_width))
        content = " ".join(row)
        content = content[:width - 2].ljust(width - 2)
        print(term_color("│", border, bold=True) + term_color(content, "white") + term_color("│", border, bold=True))

    print(term_color("└" + "─" * (width - 2) + "┘", border, bold=True))
    print(term_color("Tanda * = kategori otomatis yang akan dipakai jika langsung ENTER.", "gray"))


def input_category(auto_category, product_name):
    categories = get_categories(sync_file=True)
    computed = infer_category_from_name(product_name)
    auto_category = clean_category_name(computed or auto_category or "Atasan")

    # Jangan jadikan nomor produk / nama fallback sebagai kategori baru.
    # Contoh masalah lama: nama gagal terbaca -> "Produk 222" -> kategori otomatis jadi "222".
    auto_raw = str(auto_category or "").strip()
    if (
        not auto_raw
        or re.fullmatch(r"\d+", auto_raw)
        or re.fullmatch(r"(?i)produk\s*\d+", str(product_name or "").strip())
        or not re.search(r"[A-Za-zÀ-ÿ]", auto_raw)
    ):
        auto_category = "Atasan"

    panel(
        f"Kategori otomatis: [bold yellow]{auto_category}[/]\n"
        "Tekan ENTER kalau sudah sesuai, atau ketik nomor kategori dari tabel.",
        "Konfirmasi Kategori",
        "cyan"
    )

    if auto_category and not category_exists(auto_category):
        if ask_yes(f"Kategori '{auto_category}' belum ada. Tambahkan ke daftar kategori?", default=True):
            auto_category = add_category_value(auto_category)
        else:
            manual = ask("Ubah nama kategori / pilih kategori lain", default="Atasan").strip()
            auto_category = manual or "Atasan"

    categories = get_categories(sync_file=True)

    if RICH:
        table = Table(title="Daftar Kategori", box=box.ROUNDED, border_style="cyan")
        table.add_column("No", justify="center", style="cyan", width=5)
        table.add_column("Kategori", style="white")
        table.add_column("Status", justify="center", style="yellow", width=10)
        for i, cat in enumerate(categories, start=1):
            status = "otomatis" if cat.lower() == auto_category.lower() else ""
            table.add_row(str(i), cat, status)
        console.print(table)
    else:
        print_category_table_plain(categories, auto_category)

    value = ask("Kategori produk", default=auto_category).strip()
    if not value:
        value = auto_category

    if value.isdigit():
        idx = int(value)
        if 1 <= idx <= len(categories):
            return categories[idx - 1]

    value = clean_category_name(value)
    if not value:
        return canonical_category(auto_category) or "Atasan"

    for cat in categories:
        if value.lower() == cat.lower():
            return cat

    if ask_yes(f"Tambah '{value}' sebagai kategori baru?", default=True):
        return add_category_value(value)

    warn("Kategori baru tidak ditambahkan. Kategori otomatis dipakai.")
    return canonical_category(auto_category) or "Atasan"


def run_cmd(command, show=False):
    try:
        return subprocess.run(command, shell=True, text=True, capture_output=not show)
    except Exception:
        return None


def sync_github():
    if not Path(".git").exists():
        warn("Folder ini bukan repo Git.")
        return False
    info("Mengambil data terbaru dari GitHub...")
    result = run_cmd("git pull --rebase origin main", show=True)
    if result and result.returncode == 0:
        ok("Sinkron GitHub berhasil.")
        return True
    err("Sinkron gagal. Cek koneksi atau conflict.")
    return False


def upload_github(message):
    if not Path(".git").exists():
        warn(
            "Perubahan tersimpan lokal, tapi upload otomatis tidak jalan karena folder ini bukan repo Git.\n"
            "Pakai folder project lama yang ada .git, atau jalankan: git init + git remote add origin URL_REPO."
        )
        return False

    if RICH:
        with console.status("[bold yellow]Menyiapkan upload otomatis...[/]", spinner="dots"):
            run_cmd("git add .")
            commit = run_cmd(f'git commit -m "{message}"')
    else:
        print("Menyiapkan upload otomatis...")
        run_cmd("git add .")
        commit = run_cmd(f'git commit -m "{message}"')

    output = ""
    if commit:
        output = (commit.stdout or "") + (commit.stderr or "")
    if "nothing to commit" in output.lower():
        info("Tidak ada perubahan baru untuk diupload.")
        return True

    if RICH:
        with console.status("[bold yellow]Sinkron ulang sebelum push...[/]", spinner="dots"):
            pull = run_cmd("git pull --rebase origin main")
    else:
        print("Sinkron ulang sebelum push...")
        pull = run_cmd("git pull --rebase origin main")

    if pull and pull.returncode != 0:
        err("Gagal pull sebelum push. Kemungkinan ada perubahan dari device lain atau conflict.")
        return False

    if RICH:
        with console.status("[bold yellow]Mengupload ke GitHub...[/]", spinner="dots"):
            push = run_cmd("git push")
    else:
        print("Mengupload ke GitHub...")
        push = run_cmd("git push")

    if push and push.returncode == 0:
        ok("Upload berhasil. Tunggu Vercel update 1–3 menit.")
        return True
    err("Upload gagal. Jalankan git push manual untuk melihat detail.")
    return False

def products_table(products):
    rows = [normalize_product(p) for p in products]
    if RICH:
        table = Table(
            title=f"Daftar Produk ({len(rows)} item)",
            box=box.ROUNDED,
            border_style="cyan",
            show_lines=False,
        )
        table.add_column("No", justify="center", style="white", width=6, no_wrap=True)
        table.add_column("Nama Produk", style="white", min_width=22, ratio=3)
        table.add_column("Kategori", style="cyan", width=14)
        table.add_column("Harga", style="yellow", width=14)
        table.add_column("Platform", style="white", width=10)

        for p in rows:
            table.add_row(
                str(p.get("id", "")),
                short(p.get("name", ""), 48),
                short(p.get("category", ""), 13),
                short(p.get("price", ""), 13),
                short(p.get("platform", ""), 9),
            )
        console.print(table)
    else:
        width = 98
        border = "cyan"
        print("\n" + term_color("╔" + "═" * (width - 2) + "╗", border, bold=True))
        title = f" DAFTAR PRODUK ({len(rows)} ITEM) "
        print(term_color("║", border, bold=True) + term_color(title.center(width - 2), "white", bold=True) + term_color("║", border, bold=True))
        print(term_color("╠" + "═" * (width - 2) + "╣", border, bold=True))
        header = f"{'NO':<7}{'KATEGORI':<15}{'HARGA':<15}{'PLATFORM':<11}NAMA PRODUK"
        print(term_color("║ ", border, bold=True) + term_color(header.ljust(width - 4), "gray", bold=True) + term_color(" ║", border, bold=True))
        print(term_color("╟" + "─" * (width - 2) + "╢", border, bold=True))
        for p in rows:
            no = short(str(p.get("id", "")), 6)
            kategori = short(str(p.get("category", "")), 14)
            harga = short(str(p.get("price", "")), 14)
            platform = short(str(p.get("platform", "")), 10)
            nama = short(str(p.get("name", "")), 45)
            row = (
                term_color(f"{no:<7}", "white", bold=True)
                + term_color(f"{kategori:<15}", "cyan")
                + term_color(f"{harga:<15}", "yellow", bold=True)
                + term_color(f"{platform:<11}", "white")
                + term_color(nama, "white")
            )
            plain_len = 7 + 15 + 15 + 11 + len(nama)
            print(term_color("║ ", border, bold=True) + row + " " * max(0, width - 4 - plain_len) + term_color(" ║", border, bold=True))
        print(term_color("╚" + "═" * (width - 2) + "╝", border, bold=True))


def product_summary(p, title="Detail Produk"):
    p = normalize_product(p)
    if RICH:
        table = Table.grid(padding=(0, 1))
        rows = [
            ("No Produk", p["id"]),
            ("Nama", short(p["name"], 85)),
            ("Harga", p["price"]),
            ("Kategori", p["category"]),
            ("Platform", p["platform"]),
            ("Gambar", short(p["image"], 85)),
            ("Link", short(p["link"], 85)),
        ]
        for label, value in rows:
            table.add_row(f"[bold cyan]{label}[/]", str(value))
        console.print(Panel(table, title=f"[bold white]{title}[/]", border_style="cyan", box=box.ROUNDED))
    else:
        width = 72
        border = "cyan"
        print("\n" + box_line(width, color=border, top=True))
        print(box_center(title, width, color="white", bold=True, border_color=border))
        print(term_color("├" + "─" * (width - 2) + "┤", border, bold=True))
        rows = [
            ("No Produk", p["id"], "white"),
            ("Nama", short(p["name"], 50), "white"),
            ("Harga", p["price"], "yellow"),
            ("Kategori", p["category"], "cyan"),
            ("Platform", p["platform"], "white"),
            ("Gambar", short(p["image"], 48), "gray"),
            ("Link", short(p["link"], 48), "gray"),
        ]
        for label, value, color in rows:
            label_text = f" {label:<10}: "
            plain_len = len(label_text) + len(str(value))
            print(term_color("│", border, bold=True) + term_color(label_text, "cyan", bold=True) + term_color(str(value), color, bold=(label in {"Harga", "No Produk"})) + " " * max(0, width - 2 - plain_len) + term_color("│", border, bold=True))
        print(box_line(width, color=border, bottom=True))


def build_product(pid, data, link, name, price, category):
    platform_name = data.get("platform") or detect_platform(link)
    return normalize_product({
        "id": str(pid),
        "name": name,
        "price": price,
        "category": category,
        "type": category,
        "image": data.get("image") or str(NO_IMAGE).replace("\\", "/"),
        "link": link,
        "tiktokLink": link,
        "platform": platform_name,
        "tags": [category, platform_name],
    })


def is_placeholder_product_name(name, pid=""):
    name_clean = clean_text(name).lower()
    pid_clean = str(pid or "").strip().lower()
    placeholders = {"", "produk", "produk tanpa nama", "product", "item"}
    if name_clean in placeholders:
        return True
    if pid_clean and name_clean in {f"produk {pid_clean}", f"product {pid_clean}", f"item {pid_clean}"}:
        return True
    return False


def show_product_before_category(pid, name, price, platform, link):
    """Tampilkan nama produk sebelum user memilih kategori."""
    if RICH:
        table = Table.grid(padding=(0, 1))
        rows = [
            ("No Produk", str(pid)),
            ("Nama", short(name, 105)),
            ("Harga", price or "Cek harga"),
            ("Platform", platform or detect_platform(link)),
            ("Link", short(link, 90)),
        ]
        for label, value in rows:
            table.add_row(f"[bold cyan]{label}[/]", str(value))
        console.print(Panel(
            table,
            title="[bold white]Cek Data Produk[/]",
            subtitle="[dim]Pastikan nama dan harga sudah benar sebelum memilih kategori[/]",
            border_style="cyan",
            box=box.ROUNDED,
        ))
    else:
        width = 72
        border = "cyan"
        print("\n" + box_line(width, color=border, top=True))
        print(box_center("CEK DATA PRODUK", width, color="white", bold=True, border_color=border))
        print(term_color("├" + "─" * (width - 2) + "┤", border, bold=True))
        rows = [
            ("No Produk", str(pid), "white"),
            ("Nama", short(name, 50), "white"),
            ("Harga", price or "Cek harga", "yellow"),
            ("Platform", platform or detect_platform(link), "cyan"),
            ("Link", short(link, 48), "gray"),
        ]
        for label, value, color in rows:
            label_text = f" {label:<10}: "
            plain_len = len(label_text) + len(str(value))
            print(term_color("│", border, bold=True) + term_color(label_text, "cyan", bold=True) + term_color(str(value), color, bold=(label in {"No Produk", "Harga"})) + " " * max(0, width - 2 - plain_len) + term_color("│", border, bold=True))
        print(box_line(width, color=border, bottom=True))


def build_bulk_product(products, pid, raw_line, link):
    """Buat satu produk dari input bulk.

    Nama dan gambar selalu dicoba otomatis dari link. Jika marketplace menutup data,
    program menampilkan data yang berhasil diambil terlebih dahulu dan baru meminta
    nama manual sebagai fallback supaya pemilihan kategori tetap tepat.
    """
    line_data = parse_input_line_data(raw_line, pid, link)
    share_data = parse_shopee_share_text(raw_line)
    inline_price = line_data.get("price") or parse_inline_price_after_link(raw_line)
    inline_name = line_data.get("name") or parse_inline_name_from_line(raw_line, pid, link)
    platform = detect_platform(link)
    cached_product = find_cached_product_by_link(products, link)

    if cached_product:
        data = normalize_product(dict(cached_product))
        data["platform"] = platform
        data["final_url"] = link
        data["link"] = link
        data["tiktokLink"] = link
    else:
        if RICH:
            with console.status(f"[bold yellow]Mengambil data produk no {pid} dari {platform}...[/]", spinner="dots"):
                data = fetch_product_data(link, pid)
        else:
            print(f"Mengambil data produk no {pid} dari {platform}...")
            data = fetch_product_data(link, pid)

    # Nama dari teks input dipakai sebagai jalur paling pasti ketika marketplace menutup scraping.
    # Contoh: "01. Cek Nama Produk dengan harga Rp106.000 ... link".
    if inline_name and is_probably_product_name(inline_name):
        data["name"] = inline_name

    # Prioritas Shopee share text karena lebih akurat daripada scrape halaman.
    if share_data.get("platform") == "Shopee" or platform == "Shopee":
        data["platform"] = "Shopee"
        if share_data.get("name"):
            data["name"] = share_data["name"]
        if share_data.get("price"):
            data["price"] = share_data["price"]

    platform = data.get("platform") or platform
    name = clean_title(data.get("name") or "")

    if inline_price:
        price = inline_price
        info(f"Harga no {pid} otomatis dari teks input: {price}")
    elif platform in ["TikTok", "Tokopedia"]:
        panel(
            f"No produk: [bold yellow]{pid}[/]\n"
            f"Platform: [bold magenta]{platform}[/]\n"
            "Harga setelah link tidak ditemukan, jadi harga diisi manual.",
            "Harga Manual",
            "magenta"
        )
        default_price = "" if data.get("price") in ["", "Cek harga", None] else data.get("price")
        price = ask(f"Harga produk no {pid}", default=default_price).strip()
        price = format_price(price) if price else "Cek harga"
    elif platform == "Shopee":
        price = data.get("price") or "Cek harga"
        if price == "Cek harga":
            warn(f"Harga Shopee no {pid} belum terbaca otomatis. Produk tetap disimpan dengan harga 'Cek harga'.")
    else:
        price = input_price(data.get("price"), platform)

    data["image"] = ensure_fixed_product_image(data.get("image"), pid)

    # Wajib tampilkan hasil ambil data sebelum kategori, supaya user tahu produk ini apa.
    if not is_probably_product_name(name) or is_placeholder_product_name(name, pid):
        show_product_before_category(pid, f"Produk {pid}", price, platform, link)
        warn(
            f"Nama produk no {pid} belum berhasil terbaca otomatis dari link.\n"
            "Biasanya link pendek/affiliate TikTok/Tokopedia sedang membatasi data.\n"
            "Isi nama produk dulu supaya kategori tidak salah."
        )
        name = input_name(inline_name or data.get("name") or f"Produk {pid}")
        name = clean_title(name, max_len=160)

    # Setelah nama valid, tampilkan lagi data final sebelum kategori.
    show_product_before_category(pid, name, price, platform, link)

    category = input_category(data.get("category"), name)

    product = build_product(pid, data, link, name, price, category)
    product["image"] = ensure_fixed_product_image(product.get("image"), pid)
    product["link"] = link
    product["tiktokLink"] = link
    product["platform"] = platform
    product["tags"] = [category, platform]
    return normalize_product(product)

def add_product():
    clear()
    show_header()
    products = normalize_all(load_products())
    default_id = next_product_id(products)
    panel(
        "[bold green]Tambah produk bisa satuan atau banyak sekaligus.[/]\n\n"
        "Contoh No Produk: [bold yellow]71-75[/] atau [bold yellow]71[/]\n"
        "Contoh input banyak baris:\n"
        "01. Cek Nama Produk dengan harga Rp106.000. Dapatkan di Shopee sekarang! https://s.shopee.co.id/xxxxx\n"
        "02. https://vt.tokopedia.com/t/yyyyy/ harga 65.000\n\n"
        "Shopee share text: nama diambil dari setelah Cek sampai sebelum dengan harga.\n"
        "TikTok/Tokopedia: harga diambil dari kata harga; kalau nama ditulis sebelum link, nama langsung dipakai.\n"
        "Field gambar otomatis menjadi public/assets/NO.jpg, contoh public/assets/01.jpg.",
        "Tambah Produk Otomatis",
        "green"
    )

    pid_input = ask("No Produk / range", default=default_id).strip()
    requested_ids = split_product_ids(pid_input)
    raw_input_link = ask_multiline_links("Link Produk / teks share Shopee")
    if not raw_input_link:
        err("Link atau teks share tidak boleh kosong.")
        pause()
        return

    entries = parse_numbered_link_entries(raw_input_link, requested_ids)
    if not entries:
        err("Tidak ditemukan link valid. Gunakan format: 71. https://link-produk")
        pause()
        return

    if requested_ids and len(entries) != len(requested_ids):
        warn(
            f"Jumlah nomor di input ({len(requested_ids)}) berbeda dengan jumlah link terbaca ({len(entries)}).\n"
            "Program akan memproses nomor yang ada di baris link."
        )

    saved = []
    for entry in entries:
        pid = str(entry["id"]).strip()
        link = entry["link"]
        raw_line = entry["line"]

        if not link.startswith("http"):
            warn(f"No {pid}: link tidak valid, dilewati.")
            continue

        platform = detect_platform(link)
        panel(
            f"No Produk: [bold yellow]{pid}[/]\n"
            f"Platform: [bold magenta]{platform}[/]\n"
            f"Link: {short(link, 90)}",
            "Memproses Produk",
            "cyan"
        )

        try:
            product = build_bulk_product(products, pid, raw_line, link)
            save_or_replace_product(products, product)
            saved.append(product)
            product_summary(product, f"Produk No {pid} Berhasil Disimpan")
        except Exception as e:
            err(f"Produk no {pid} gagal diproses: {e}")

    if not saved:
        err("Tidak ada produk yang berhasil disimpan.")
        pause()
        return

    ids_text = ", ".join(p.get("id", "") for p in saved)
    ok(f"Selesai menyimpan {len(saved)} produk: {ids_text}")
    upload_github(f"update produk {ids_text}")
    pause()

def choose_product(products):
    if not products:
        warn("Belum ada produk.")
        pause()
        return None, None
    products_table(products)
    pid = ask("Masukkan No Produk").strip()
    for i, p in enumerate(products):
        if str(p.get("id")) == str(pid):
            return i, normalize_product(p)
    err("Produk tidak ditemukan.")
    pause()
    return None, None


def edit_product():
    clear()
    show_header()
    products = normalize_all(load_products())
    idx, p = choose_product(products)
    if p is None:
        return

    while True:
        clear()
        show_header()
        product_summary(p, f"Edit Produk {p['id']}")
        if RICH:
            table = Table(box=box.SIMPLE_HEAVY, border_style="blue")
            table.add_column("No", justify="center", style="cyan")
            table.add_column("Field")
            for no, field in [
                ("1", "Nama Produk"),
                ("2", "Harga"),
                ("3", "Kategori"),
                ("4", "Link Gambar"),
                ("5", "Link Produk"),
                ("0", "Simpan dan kembali"),
            ]:
                table.add_row(no, field)
            console.print(table)
        else:
            print("\n" + term_color("MENU EDIT PRODUK", "cyan", bold=True))
            edit_items = [("1", "Nama Produk"), ("2", "Harga"), ("3", "Kategori"), ("4", "Link Gambar"), ("5", "Link Produk"), ("0", "Simpan dan kembali")]
            for no, label in edit_items:
                no_color = "gray" if no == "0" else "white"
                print(term_color(f"{no}. ", no_color, bold=True) + term_color(label, "white"))

        choice = ask("Pilih menu", default="0").strip()
        if choice == "1":
            p["name"] = ask("Nama baru", default=p["name"])
            auto_cat = infer_category_from_name(p["name"])
            if ask_yes(f"Nama produk berubah. Sesuaikan kategori otomatis ke '{auto_cat}'?", default=True):
                p["category"] = input_category(auto_cat, p["name"])
                p["type"] = p["category"]
                p["tags"] = [p["category"], p.get("platform", "Affiliate")]
                p["badge"] = p["category"]
        elif choice == "2":
            p["price"] = format_price(ask("Harga baru", default=p["price"]))
        elif choice == "3":
            p["category"] = input_category(p.get("category", "Atasan"), p.get("name", ""))
            p["type"] = p["category"]
            p["tags"] = [p["category"], p["platform"]]
            p["badge"] = p["category"]
        elif choice == "4":
            p["image"] = ask("Link/path gambar", default=p["image"])
        elif choice == "5":
            link = ask("Link produk", default=p["link"])
            p["link"] = link
            p["tiktokLink"] = link
            p["platform"] = detect_platform(link)
        elif choice == "0":
            products[idx] = normalize_product(p)
            save_products(products)
            ok("Perubahan disimpan.")
            upload_github(f"edit produk {p['id']}")
            pause()
            return

def list_products():
    clear()
    show_header()
    products = normalize_all(load_products())
    if not products:
        warn("Belum ada produk.")
        pause()
        return

    if RICH:
        info(
            "Ketik nomor produk, nama, kategori, atau platform.\n"
            "Kosongkan untuk menampilkan semua produk."
        )
    else:
        print(term_color("\nCari produk berdasarkan nomor, nama, kategori, atau platform.", "white"))
        print(term_color("Kosongkan lalu ENTER untuk menampilkan semua produk.", "gray"))
    keyword = ask("Cari produk", default="").strip().lower()

    if keyword:
        filtered = []
        for raw in products:
            p = normalize_product(raw)
            haystack = " ".join([
                str(p.get("id", "")),
                str(p.get("name", "")),
                str(p.get("category", "")),
                str(p.get("price", "")),
                str(p.get("platform", "")),
            ]).lower()
            if keyword in haystack:
                filtered.append(p)
    else:
        filtered = products

    if not filtered:
        warn("Produk tidak ditemukan.")
        pause()
        return

    per_page = 25
    page = 0
    while True:
        clear()
        show_header()
        total = len(filtered)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))
        chunk = filtered[page * per_page:(page + 1) * per_page]
        products_table(chunk)
        if RICH:
            print(f"\nTotal: {total} produk | Halaman {page + 1}/{total_pages}")
        else:
            info_line = f"Total: {total} produk  •  Halaman {page + 1}/{total_pages}"
            print("\n" + term_color(info_line, "cyan", bold=True))
        if total_pages == 1:
            break
        cmd = ask("n=lanjut, p=sebelumnya, q=kembali", default="q").strip().lower()
        if cmd == "n":
            page += 1
        elif cmd == "p":
            page -= 1
        else:
            return
    pause()


def delete_product():
    clear()
    show_header()
    products = normalize_all(load_products())
    idx, p = choose_product(products)
    if p is None:
        return
    product_summary(p, "Produk yang Akan Dihapus")
    if ask_yes("Yakin hapus produk ini?", default=False):
        del products[idx]
        save_products(products)
        ok("Produk dihapus.")
        upload_github(f"hapus produk {p['id']}")
    pause()


def manage_categories():
    while True:
        clear()
        show_header()
        categories = get_categories(sync_file=True)
        products = normalize_all(load_products())

        if RICH:
            table = Table(title="Kategori Katalog", box=box.ROUNDED, border_style="cyan")
            table.add_column("No", justify="center", style="cyan")
            table.add_column("Kategori", style="white")
            table.add_column("Jumlah Produk", justify="center", style="green")
            for i, cat in enumerate(categories, start=1):
                count = sum(1 for p in products if str(p.get("category", "")).lower() == cat.lower())
                table.add_row(str(i), cat, str(count))
            console.print(table)
            menu = Table(box=box.SIMPLE_HEAVY, border_style="blue")
            menu.add_column("No", justify="center", style="cyan")
            menu.add_column("Menu")
            for no, label in [("1", "Tambah kategori"), ("2", "Ubah nama kategori"), ("3", "Hapus kategori"), ("0", "Kembali")]:
                menu.add_row(no, label)
            console.print(menu)
        else:
            width = 72
            border = "cyan"
            print("\n" + term_color("╔" + "═" * (width - 2) + "╗", border, bold=True))
            print(term_color("║", border, bold=True) + term_color(" KATEGORI KATALOG ".center(width - 2), "white", bold=True) + term_color("║", border, bold=True))
            print(term_color("╠" + "═" * (width - 2) + "╣", border, bold=True))
            for i, cat in enumerate(categories, start=1):
                count = sum(1 for p in products if str(p.get("category", "")).lower() == cat.lower())
                row_text = f" {i:>2}.  {cat:<32} {count} produk"
                print(term_color("║", border, bold=True) + term_color(row_text, "white") + " " * max(0, width - 2 - len(row_text)) + term_color("║", border, bold=True))
            print(term_color("╠" + "═" * (width - 2) + "╣", border, bold=True))
            menu_cat = [("1", "Tambah kategori"), ("2", "Ubah nama kategori"), ("3", "Hapus kategori"), ("0", "Kembali")]
            for no, label in menu_cat:
                row_text = f"  {no}.  {label}"
                no_color = "gray" if no == "0" else "white"
                print(term_color("║", border, bold=True) + term_color(f"  {no}.", no_color, bold=True) + term_color(f"  {label}", "white") + " " * max(0, width - 2 - len(row_text)) + term_color("║", border, bold=True))
            print(term_color("╚" + "═" * (width - 2) + "╝", border, bold=True))

        choice = ask("Pilih menu", default="0").strip()

        if choice == "1":
            name = clean_category_name(ask("Nama kategori baru").strip())
            if not name:
                warn("Nama kategori kosong.")
                pause()
                continue
            add_category_value(name)
            upload_github(f"tambah kategori {name}")
            pause()

        elif choice == "2":
            old = ask("Kategori yang mau diubah (nomor/nama)").strip()
            if old.isdigit() and 1 <= int(old) <= len(categories):
                old_cat = categories[int(old) - 1]
            else:
                old_cat = canonical_category(old)
            if not old_cat or not category_exists(old_cat):
                err("Kategori tidak ditemukan.")
                pause()
                continue
            new_cat = clean_category_name(ask("Nama kategori baru", default=old_cat).strip())
            if not new_cat:
                warn("Nama kategori kosong.")
                pause()
                continue

            cats = [new_cat if c.lower() == old_cat.lower() else c for c in categories]
            save_categories(cats)
            for p in products:
                if str(p.get("category", "")).lower() == old_cat.lower():
                    p["category"] = new_cat
                    p["type"] = new_cat
                    p["badge"] = new_cat
                    p["tags"] = [new_cat, p.get("platform") or detect_platform(p.get("link") or p.get("tiktokLink"))]
            save_products(products)
            ok(f"Kategori '{old_cat}' diganti menjadi '{new_cat}'.")
            upload_github(f"ubah kategori {old_cat} ke {new_cat}")
            pause()

        elif choice == "3":
            target = ask("Kategori yang mau dihapus (nomor/nama)").strip()
            if target.isdigit() and 1 <= int(target) <= len(categories):
                cat = categories[int(target) - 1]
            else:
                cat = canonical_category(target)
            if not cat or not category_exists(cat):
                err("Kategori tidak ditemukan.")
                pause()
                continue
            used = sum(1 for p in products if str(p.get("category", "")).lower() == cat.lower())
            move_to = None
            if used:
                warn(f"Kategori '{cat}' masih dipakai oleh {used} produk.")
                remaining = [c for c in categories if c.lower() != cat.lower()]
                default_move = remaining[0] if remaining else "Atasan"
                move_to = ask("Pindahkan produk itu ke kategori", default=default_move).strip() or default_move
            if ask_yes(f"Yakin hapus kategori '{cat}'?", default=False):
                delete_category_value(cat, move_to=move_to)
                ok(f"Kategori '{cat}' dihapus.")
                upload_github(f"hapus kategori {cat}")
                pause()

        elif choice == "0":
            return
        else:
            err("Menu tidak valid.")
            time.sleep(1)

def preview_web():
    clear()
    show_header()
    info(
        "Preview katalog aktif.\n\n"
        "Buka dari HP yang sama:\n"
        "http://127.0.0.1:8000\n\n"
        "Tekan CTRL+C untuk berhenti."
    )
    try:
        subprocess.run("python -m http.server 8000", shell=True)
    except KeyboardInterrupt:
        pass


def run_admin_dashboard():
    clear()
    show_header()
    if not Path("admin_app.py").exists():
        err("File admin_app.py tidak ditemukan. Ekstrak ulang paket ZIP versi terbaru.")
        pause()
        return
    info(
        "Dashboard admin aktif.\n\n"
        "Buka dari HP yang sama:\n"
        "http://127.0.0.1:5000/admin\n\n"
        "Untuk melihat katalog:\n"
        "http://127.0.0.1:5000/\n\n"
        "Tekan CTRL+C untuk berhenti."
    )
    try:
        subprocess.run("python admin_app.py", shell=True)
    except KeyboardInterrupt:
        pass

def main():
    ensure_files()
    while True:
        clear()
        show_header()
        show_menu()
        choice = ask("Pilih menu", default="0").strip()
        if choice == "1":
            add_product()
        elif choice == "2":
            edit_product()
        elif choice == "3":
            list_products()
        elif choice == "4":
            delete_product()
        elif choice == "5":
            preview_web()
        elif choice == "6":
            clear()
            show_header()
            sync_github()
            pause()
        elif choice == "7":
            configure_shopee_api()
        elif choice == "8":
            manage_categories()
        elif choice == "0":
            clear()
            ok("Selesai.")
            break
        else:
            err("Menu tidak valid.")
            time.sleep(1)



if __name__ == "__main__":
    main()
