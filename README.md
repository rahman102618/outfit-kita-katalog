# OK Outfit Kita - Web Katalog Affiliate

File ini sudah berisi:
- `index.html` = tampilan web katalog
- `script.js` = fitur pencarian, filter, dan membaca produk
- `public/products.json` = data produk
- `public/assets/logo.jpeg` = logo toko
- `manage_products.py` = script Termux untuk tambah/edit/hapus produk

## Cara pakai di Termux HP

### 1. Pindahkan ZIP ke HP lalu ekstrak

Misalnya file ZIP ada di folder Download.

```bash
cd /sdcard/Download
unzip ok-outfit-kita-katalog.zip
cd ok-outfit-kita-katalog
```

Kalau perintah `unzip` belum ada:

```bash
pkg install unzip
```

### 2. Install Python dan library

```bash
pkg update
pkg install python
pip install requests beautifulsoup4
```

### 3. Jalankan menu manager produk

```bash
python manage_products.py
```

Nanti muncul menu:

```text
1. Tambah produk otomatis
2. Edit produk manual
3. Lihat daftar produk
4. Hapus produk
5. Jalankan preview web
0. Keluar
```

## Alur tambah produk

Pilih menu:

```text
1. Tambah produk otomatis
```

Masukkan:

```text
No Produk
Link Affiliate TikTok
```

Produk akan langsung disimpan otomatis.

Kalau ada data yang gagal atau salah, masuk ke:

```text
2. Edit produk manual
```

Lalu pilih No Produk yang mau diedit.

## Preview web di HP

Pilih menu:

```text
5. Jalankan preview web
```

Lalu buka browser HP dan masuk ke:

```text
http://127.0.0.1:8000
```

## Upload agar bisa dipasang di Bio TikTok

Link `127.0.0.1` hanya bisa dibuka di HP kamu sendiri.

Agar bisa dipasang di Bio TikTok, upload folder ini ke:
- Vercel
- Netlify
- GitHub Pages

Setelah online, link yang dipasang di bio adalah link website katalog, misalnya:

```text
https://ok-outfit-kita.vercel.app
```

Bukan link produk satu-satu.
