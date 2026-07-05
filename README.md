# Outfit Kita Katalog - Termux Color UI + Admin Web

Versi ini sudah ditambah tampilan Termux berwarna dan dashboard admin web agar pengelolaan produk lebih enak dilihat.

## Fitur utama

- Menu Termux berwarna, tidak polos.
- Header lebih rapi dengan border warna.
- Daftar produk terminal lebih rapi, berwarna, ada pencarian dan halaman.
- Detail produk, kategori, edit, warning, info, dan error dibuat lebih jelas.
- Tetap ada Dashboard Admin Web lokal.
- Tambah, edit, hapus produk dari browser.
- Search dan filter kategori/platform.
- Preview gambar produk.
- Katalog pembeli tetap bisa dibuka.
- Sinkron GitHub dari dashboard atau menu Termux.

## Install di Termux

```bash
termux-setup-storage
pkg install unzip -y
cd /storage/emulated/0/Download
unzip -o outfit-kita-katalog-termux-color-ui.zip -d /storage/emulated/0/Termux/
cd /storage/emulated/0/Termux/outfit-kita-katalog-main
bash setup_termux.sh
```

## Jalankan manager Termux

```bash
python manage_products.py
```

## Jalankan dashboard admin web

```bash
python admin_app.py
```

Buka browser:

```text
http://127.0.0.1:5000/admin
```

Katalog pembeli:

```text
http://127.0.0.1:5000/
```

## Catatan

Jangan tutup Termux selama dashboard atau katalog lokal sedang dipakai.
Tekan CTRL+C di Termux untuk menghentikan server.
