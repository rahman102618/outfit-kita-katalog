#!/usr/bin/env python3
"""Dashboard admin lokal untuk Outfit Kita.
Jalankan: python admin_app.py
Buka: http://127.0.0.1:5000/admin
"""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from flask import Flask, jsonify, request, send_from_directory
except ModuleNotFoundError:
    print("Flask belum terinstall.")
    print("Jalankan dulu: bash setup_termux.sh")
    print("Atau manual: python -m pip install flask")
    raise SystemExit(1)

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_FILE = PUBLIC_DIR / "products.json"
CATEGORIES_FILE = PUBLIC_DIR / "categories.json"
ASSET_DIR = PUBLIC_DIR / "assets"

DEFAULT_CATEGORIES = ["Atasan", "Bawahan", "Hijab", "Gamis", "Tas", "Sepatu", "Tumbler"]


def ensure_files():
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")
    if not CATEGORIES_FILE.exists():
        CATEGORIES_FILE.write_text(json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False, indent=2), encoding="utf-8")


def load_products():
    ensure_files()
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_products(products):
    ensure_files()
    backup = DATA_FILE.with_suffix(".backup.json")
    if DATA_FILE.exists():
        try:
            shutil.copy2(DATA_FILE, backup)
        except Exception:
            pass
    DATA_FILE.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")


def load_categories():
    ensure_files()
    cats = []
    try:
        data = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cats.extend(str(x).strip() for x in data if str(x).strip())
    except Exception:
        pass
    for p in load_products():
        cat = str(p.get("category") or p.get("type") or p.get("badge") or "").strip()
        if cat:
            cats.append(cat)
    seen, out = set(), []
    for cat in cats or DEFAULT_CATEGORIES:
        key = cat.lower()
        if key not in seen:
            seen.add(key)
            out.append(cat)
    return out


def save_categories(categories):
    clean, seen = [], set()
    for cat in categories:
        text = str(cat or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(text)
    CATEGORIES_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(value):
    return " ".join(str(value or "").replace("\n", " ").split()).strip()


def detect_platform(link):
    link = str(link or "").lower()
    if "shopee" in link:
        return "Shopee"
    if "tokopedia" in link or "tokopedia" in link:
        return "Tokopedia"
    if "tiktok" in link:
        return "TikTok"
    return "Affiliate"


def normalize_price(value):
    raw = clean_text(value)
    if not raw:
        return "Cek harga"
    if raw.lower().startswith("rp"):
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return raw
    return "Rp" + f"{int(digits):,}".replace(",", ".")


def normalize_product(data):
    p = dict(data or {})
    link = clean_text(p.get("link") or p.get("tiktokLink") or p.get("productLink"))
    category = clean_text(p.get("category") or p.get("type") or p.get("badge") or "Atasan")
    platform = clean_text(p.get("platform") or detect_platform(link))
    p["id"] = clean_text(p.get("id"))
    p["name"] = clean_text(p.get("name") or p.get("title") or "Produk")
    p["price"] = normalize_price(p.get("price"))
    p["category"] = category
    p["type"] = category
    p["badge"] = category
    p["image"] = clean_text(p.get("image") or "public/assets/no-image.svg")
    p["link"] = link
    p["tiktokLink"] = link
    p["platform"] = platform
    p["tags"] = [category, platform]
    return p


def numeric_id(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return int(digits) if digits else -1


def next_product_id(products):
    max_id = max([numeric_id(p.get("id")) for p in products] + [0])
    return str(max_id + 1).zfill(2)


def git_sync():
    if not (BASE_DIR / ".git").exists():
        return False, "Folder ini belum terhubung ke GitHub. Jalankan sinkron dari folder repo asli."
    try:
        subprocess.run(["git", "add", "."], cwd=BASE_DIR, check=True, text=True, capture_output=True)
        msg = f"update produk {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        commit = subprocess.run(["git", "commit", "-m", msg], cwd=BASE_DIR, text=True, capture_output=True)
        commit_out = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" not in commit_out.lower():
            if commit.returncode != 0:
                return False, commit_out.strip() or "Commit gagal."
        pull = subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=BASE_DIR, text=True, capture_output=True)
        if pull.returncode != 0:
            return False, ((pull.stdout or "") + (pull.stderr or "")).strip() or "Pull gagal."
        push = subprocess.run(["git", "push"], cwd=BASE_DIR, text=True, capture_output=True)
        if push.returncode != 0:
            return False, ((push.stdout or "") + (push.stderr or "")).strip() or "Push gagal."
        return True, "Data berhasil disinkronkan."
    except Exception as exc:
        return False, str(exc)


ADMIN_HTML = r'''
<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Outfit Kita Admin</title>
  <style>
    :root{
      --bg:#0f0f10;--panel:#18181b;--card:#ffffff;--text:#f8fafc;--muted:#a1a1aa;
      --line:rgba(255,255,255,.12);--gold:#facc15;--gold2:#d97706;--danger:#ef4444;
      --green:#22c55e;--blue:#38bdf8;--shadow:0 22px 60px rgba(0,0,0,.24);
    }
    *{box-sizing:border-box} body{margin:0;font-family:Inter,Arial,sans-serif;background:
      radial-gradient(circle at top left,rgba(250,204,21,.18),transparent 34%),
      radial-gradient(circle at bottom right,rgba(56,189,248,.12),transparent 35%),var(--bg);color:var(--text)}
    button,input,select,textarea{font:inherit} button{cursor:pointer}
    .wrap{max-width:1220px;margin:0 auto;padding:18px 14px 60px}.top{display:flex;gap:14px;justify-content:space-between;align-items:center;margin-bottom:16px;position:sticky;top:0;z-index:10;padding:10px 0;background:linear-gradient(to bottom,rgba(15,15,16,.96),rgba(15,15,16,.72));backdrop-filter:blur(14px)}
    .brand{display:flex;gap:12px;align-items:center}.logo{width:46px;height:46px;border-radius:15px;background:linear-gradient(135deg,#111,#facc15);box-shadow:var(--shadow)}h1{font-size:18px;line-height:1;margin:0}.sub{margin:4px 0 0;color:var(--muted);font-size:13px;font-weight:700}
    .actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.btn{border:0;border-radius:14px;padding:11px 14px;background:#fff;color:#111;font-weight:900}.btn.dark{background:rgba(255,255,255,.08);color:#fff;border:1px solid var(--line)}.btn.gold{background:linear-gradient(135deg,var(--gold),#fb923c);color:#111}.btn.danger{background:rgba(239,68,68,.15);color:#fecaca;border:1px solid rgba(239,68,68,.35)}
    .stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.stat{background:rgba(255,255,255,.08);border:1px solid var(--line);border-radius:18px;padding:14px}.stat b{font-size:22px}.stat span{display:block;color:var(--muted);font-weight:800;font-size:12px;margin-top:4px}
    .grid{display:grid;grid-template-columns:1fr 390px;gap:14px}.panel{background:rgba(255,255,255,.08);border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow);overflow:hidden}.panel-head{padding:14px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;justify-content:space-between}.panel-head h2{margin:0;font-size:16px}.tools{display:grid;grid-template-columns:1fr 150px 130px;gap:8px;padding:14px;border-bottom:1px solid var(--line)}
    input,select,textarea{width:100%;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.95);color:#111;border-radius:14px;padding:12px;font-weight:800;outline:0}textarea{min-height:88px;resize:vertical}.form{padding:14px;display:grid;gap:10px}.form label{display:grid;gap:6px;color:var(--muted);font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.5px}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}.preview{height:190px;border-radius:18px;overflow:hidden;border:1px solid var(--line);background:#111}.preview img{width:100%;height:100%;object-fit:cover}.hint{color:var(--muted);font-size:12px;line-height:1.45}.msg{display:none;margin:0 14px 14px;padding:12px;border-radius:15px;font-weight:900}.msg.show{display:block}.msg.ok{background:rgba(34,197,94,.14);color:#bbf7d0;border:1px solid rgba(34,197,94,.26)}.msg.err{background:rgba(239,68,68,.13);color:#fecaca;border:1px solid rgba(239,68,68,.3)}
    .table-wrap{overflow:auto;max-height:72vh}.table{width:100%;border-collapse:separate;border-spacing:0}.table th{position:sticky;top:0;background:#19191c;color:#fde68a;text-align:left;font-size:12px;padding:12px;border-bottom:1px solid var(--line);z-index:2}.table td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle}.product{display:flex;align-items:center;gap:10px;min-width:270px}.thumb{width:54px;height:54px;border-radius:14px;object-fit:cover;background:#222;flex:none}.name{font-weight:900;color:#fff}.small{font-size:12px;color:var(--muted);font-weight:700;margin-top:3px}.chip{display:inline-flex;border:1px solid var(--line);background:rgba(255,255,255,.08);border-radius:999px;padding:7px 9px;font-size:12px;font-weight:900;white-space:nowrap}.row-actions{display:flex;gap:6px}.icon{border:1px solid var(--line);background:rgba(255,255,255,.08);color:#fff;border-radius:12px;padding:8px 10px;font-weight:900}.empty{padding:32px;text-align:center;color:var(--muted);font-weight:900}.footer-note{margin-top:14px;color:var(--muted);font-size:12px;text-align:center}
    @media(max-width:880px){.top{align-items:flex-start}.grid{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}.tools{grid-template-columns:1fr}.actions{width:100%;justify-content:flex-start}.table-wrap{max-height:none}.two{grid-template-columns:1fr}.wrap{padding-bottom:30px}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand"><div class="logo"></div><div><h1>Outfit Kita Admin</h1><p class="sub">Tambah, edit, hapus, cari produk dari browser</p></div></div>
      <div class="actions"><button class="btn dark" onclick="openCatalog()">Buka Katalog</button><button class="btn gold" onclick="syncGit()">Sinkron GitHub</button></div>
    </div>

    <div class="stats">
      <div class="stat"><b id="totalProducts">0</b><span>Total produk</span></div>
      <div class="stat"><b id="totalCategories">0</b><span>Kategori</span></div>
      <div class="stat"><b id="shopeeCount">0</b><span>Shopee</span></div>
      <div class="stat"><b id="tokopediaCount">0</b><span>Tokopedia</span></div>
    </div>

    <div class="grid">
      <section class="panel">
        <div class="panel-head"><h2>Daftar Produk</h2><button class="btn dark" onclick="resetForm()">Produk Baru</button></div>
        <div class="tools"><input id="search" placeholder="Cari nomor, nama, kategori, harga..." oninput="render()" /><select id="catFilter" onchange="render()"><option value="">Semua kategori</option></select><select id="platformFilter" onchange="render()"><option value="">Semua platform</option><option>Shopee</option><option>Tokopedia</option><option>TikTok</option><option>Affiliate</option></select></div>
        <div class="table-wrap"><table class="table"><thead><tr><th>Produk</th><th>Kategori</th><th>Harga</th><th>Platform</th><th>Aksi</th></tr></thead><tbody id="rows"></tbody></table></div>
      </section>

      <aside class="panel">
        <div class="panel-head"><h2 id="formTitle">Tambah Produk</h2></div>
        <form class="form" onsubmit="saveProduct(event)">
          <div class="two"><label>No Produk<input id="id" placeholder="contoh 122"></label><label>Platform<select id="platform"><option>Shopee</option><option>Tokopedia</option><option>TikTok</option><option>Affiliate</option></select></label></div>
          <label>Nama Produk<textarea id="name" placeholder="Nama produk"></textarea></label>
          <div class="two"><label>Harga<input id="price" placeholder="Rp99.000"></label><label>Kategori<select id="category"></select></label></div>
          <label>Link Produk<input id="link" placeholder="https://..."></label>
          <label>Link / path gambar<input id="image" placeholder="public/assets/122.jpg" oninput="updatePreview()"></label>
          <div class="preview"><img id="imagePreview" src="/public/assets/no-image.svg" onerror="this.src='/public/assets/no-image.svg'"></div>
          <p class="hint">Gambar lokal yang paling aman: <b>public/assets/NO.jpg</b>. Setelah simpan, file <b>public/products.json</b> langsung diperbarui.</p>
          <button class="btn gold" type="submit">Simpan Produk</button>
          <button class="btn danger" type="button" onclick="deleteFromForm()">Hapus Produk Ini</button>
        </form>
        <div id="message" class="msg"></div>
      </aside>
    </div>
    <p class="footer-note">Dashboard ini hanya berjalan di HP/komputer kamu saat server Termux aktif.</p>
  </div>

<script>
let products = [];
let categories = [];
const $ = (id) => document.getElementById(id);
function clean(v){return String(v||'').trim()}
function imgSrc(v){v=clean(v); if(!v) return '/public/assets/no-image.svg'; if(v.startsWith('http')) return v; if(v.startsWith('/')) return v; if(v.startsWith('public/')) return '/' + v; return '/' + v;}
function showMsg(text, ok=true){const m=$('message'); m.textContent=text; m.className='msg show ' + (ok?'ok':'err'); setTimeout(()=>m.className='msg', 4200)}
async function load(){
  const [p,c] = await Promise.all([fetch('/api/products').then(r=>r.json()), fetch('/api/categories').then(r=>r.json())]);
  products = p.products || []; categories = c.categories || [];
  fillCategories(); render(); resetForm(false);
}
function fillCategories(){
  $('category').innerHTML = categories.map(c=>`<option>${escapeHtml(c)}</option>`).join('');
  $('catFilter').innerHTML = '<option value="">Semua kategori</option>' + categories.map(c=>`<option>${escapeHtml(c)}</option>`).join('');
}
function escapeHtml(s){return String(s||'').replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function render(){
  const q = clean($('search').value).toLowerCase(); const cat=$('catFilter').value; const plat=$('platformFilter').value;
  const filtered = products.filter(p=>{
    const hay = [p.id,p.name,p.category,p.price,p.platform,p.link].join(' ').toLowerCase();
    return (!q || hay.includes(q)) && (!cat || p.category===cat) && (!plat || p.platform===plat)
  });
  $('totalProducts').textContent = products.length;
  $('totalCategories').textContent = categories.length;
  $('shopeeCount').textContent = products.filter(p=>p.platform==='Shopee').length;
  $('tokopediaCount').textContent = products.filter(p=>p.platform==='Tokopedia').length;
  $('rows').innerHTML = filtered.length ? filtered.map(p=>`
    <tr>
      <td><div class="product"><img class="thumb" src="${imgSrc(p.image)}" onerror="this.src='/public/assets/no-image.svg'"><div><div class="name">${escapeHtml(p.name)}</div><div class="small">No ${escapeHtml(p.id)}${p.link ? ' • ada link' : ''}</div></div></div></td>
      <td><span class="chip">${escapeHtml(p.category)}</span></td><td><b>${escapeHtml(p.price)}</b></td><td>${escapeHtml(p.platform)}</td>
      <td><div class="row-actions"><button class="icon" onclick="editProduct('${escapeHtml(p.id)}')">Edit</button><button class="icon" onclick="deleteProduct('${escapeHtml(p.id)}')">Hapus</button></div></td>
    </tr>`).join('') : '<tr><td colspan="5"><div class="empty">Produk tidak ditemukan</div></td></tr>';
}
function resetForm(scroll=true){
  $('formTitle').textContent='Tambah Produk'; ['id','name','price','link','image'].forEach(id=>$(id).value=''); $('platform').value='Shopee'; if(categories[0]) $('category').value=categories[0]; updatePreview(); if(scroll) window.scrollTo({top:0,behavior:'smooth'});
}
function editProduct(id){
  const p = products.find(x=>String(x.id)===String(id)); if(!p) return;
  $('formTitle').textContent='Edit Produk No ' + p.id; $('id').value=p.id; $('name').value=p.name||''; $('price').value=p.price||''; $('category').value=p.category||categories[0]||''; $('platform').value=p.platform||'Affiliate'; $('link').value=p.link||''; $('image').value=p.image||''; updatePreview();
  document.querySelector('aside.panel').scrollIntoView({behavior:'smooth', block:'start'});
}
function updatePreview(){ $('imagePreview').src = imgSrc($('image').value); }
async function saveProduct(ev){
  ev.preventDefault();
  const payload = {id:clean($('id').value), name:clean($('name').value), price:clean($('price').value), category:clean($('category').value), platform:clean($('platform').value), link:clean($('link').value), tiktokLink:clean($('link').value), image:clean($('image').value)};
  if(!payload.name){showMsg('Nama produk wajib diisi.', false); return;}
  const res = await fetch('/api/products', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}).then(r=>r.json());
  if(!res.ok){showMsg(res.message||'Gagal simpan.', false); return;}
  products = res.products || []; categories = res.categories || categories; fillCategories(); render(); $('id').value = res.product.id; showMsg('Produk berhasil disimpan.');
}
async function deleteProduct(id){
  if(!confirm('Hapus produk no ' + id + '?')) return;
  const res = await fetch('/api/products/' + encodeURIComponent(id), {method:'DELETE'}).then(r=>r.json());
  if(!res.ok){showMsg(res.message||'Gagal hapus.', false); return;} products=res.products||[]; render(); resetForm(false); showMsg('Produk berhasil dihapus.');
}
function deleteFromForm(){ const id=clean($('id').value); if(!id){showMsg('Pilih produk dulu.', false); return;} deleteProduct(id); }
async function syncGit(){
  showMsg('Sedang sinkron GitHub...');
  const res = await fetch('/api/sync', {method:'POST'}).then(r=>r.json()); showMsg(res.message || (res.ok?'Selesai.':'Gagal.'), !!res.ok);
}
function openCatalog(){ window.open('/', '_blank'); }
load().catch(err=>showMsg('Gagal memuat data: '+err, false));
</script>
</body>
</html>
'''


@app.get("/")
def catalog():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/script.js")
def script_js():
    return send_from_directory(BASE_DIR, "script.js")


@app.get("/public/<path:filename>")
def public_files(filename):
    return send_from_directory(PUBLIC_DIR, filename)


@app.get("/admin")
def admin():
    return ADMIN_HTML


@app.get("/api/products")
def api_products():
    products = [normalize_product(p) for p in load_products()]
    products.sort(key=lambda p: numeric_id(p.get("id")))
    return jsonify({"ok": True, "products": products})


@app.post("/api/products")
def api_save_product():
    payload = request.get_json(silent=True) or {}
    product = normalize_product(payload)
    products = [normalize_product(p) for p in load_products()]
    if not product["name"] or product["name"].lower() == "produk":
        return jsonify({"ok": False, "message": "Nama produk wajib diisi."}), 400
    if not product["id"]:
        product["id"] = next_product_id(products)
    updated = False
    for i, item in enumerate(products):
        if str(item.get("id")) == str(product["id"]):
            products[i] = product
            updated = True
            break
    if not updated:
        products.append(product)
    products.sort(key=lambda p: numeric_id(p.get("id")))
    save_products(products)
    if product["category"] not in load_categories():
        save_categories(load_categories() + [product["category"]])
    return jsonify({"ok": True, "product": product, "products": products, "categories": load_categories()})


@app.delete("/api/products/<product_id>")
def api_delete_product(product_id):
    products = [normalize_product(p) for p in load_products()]
    before = len(products)
    products = [p for p in products if str(p.get("id")) != str(product_id)]
    if len(products) == before:
        return jsonify({"ok": False, "message": "Produk tidak ditemukan."}), 404
    save_products(products)
    return jsonify({"ok": True, "products": products})


@app.get("/api/categories")
def api_categories():
    return jsonify({"ok": True, "categories": load_categories()})


@app.post("/api/categories")
def api_save_categories():
    payload = request.get_json(silent=True) or {}
    categories = payload.get("categories") or []
    save_categories(categories)
    return jsonify({"ok": True, "categories": load_categories()})


@app.post("/api/sync")
def api_sync():
    ok, message = git_sync()
    return jsonify({"ok": ok, "message": message})


if __name__ == "__main__":
    ensure_files()
    print("\nDashboard admin aktif")
    print("Buka: http://127.0.0.1:5000/admin")
    print("Katalog: http://127.0.0.1:5000/")
    print("Tekan CTRL+C untuk berhenti\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
