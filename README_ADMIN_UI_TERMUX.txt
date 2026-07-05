OUTFIT KITA MANAGER - VERSI UI LEBIH RAPI

ISI UPDATE:
1. Menu Termux dibuat lebih bersih.
2. Daftar produk di terminal sudah rapi, ada pencarian dan halaman.
3. Teks yang terasa template sudah dirapikan.
4. Ditambah Dashboard Admin Web:
   - lihat produk rapi
   - cari produk
   - filter kategori/platform
   - tambah produk
   - edit produk
   - hapus produk
   - preview gambar
   - tombol buka katalog
   - tombol sinkron GitHub

==================================================
CARA EKSTRAK ZIP DI TERMUX
==================================================

1. Beri izin storage dulu:

termux-setup-storage

2. Masuk ke folder tempat ZIP berada.
   Contoh kalau ZIP ada di Download:

cd /storage/emulated/0/Download

3. Ekstrak ZIP:

unzip -o outfit-kita-katalog-admin-ui.zip -d /storage/emulated/0/Termux/

4. Masuk ke folder hasil ekstrak:

cd /storage/emulated/0/Termux/outfit-kita-katalog-main

5. Install kebutuhan:

bash setup_termux.sh

==================================================
CARA MENJALANKAN MANAGER TERMUX
==================================================

python manage_products.py

Menu penting:
1 = tambah produk otomatis
2 = edit produk manual
3 = lihat daftar produk rapi
4 = hapus produk
5 = dashboard admin web
6 = preview katalog
7 = sinkron GitHub
8 = setup Shopee API
9 = kelola kategori

==================================================
CARA MENJALANKAN DASHBOARD ADMIN WEB
==================================================

Cara 1 dari menu manager:

python manage_products.py

Lalu pilih:

5

Cara 2 langsung:

python admin_app.py

Buka di browser HP:

http://127.0.0.1:5000/admin

Katalog pembeli:

http://127.0.0.1:5000/

Catatan:
- Jangan tutup Termux selama dashboard dipakai.
- Tekan CTRL + C di Termux untuk menghentikan server.
- Dashboard admin ini berjalan lokal di HP kamu.

==================================================
KALAU COMMAND unzip BELUM ADA
==================================================

pkg install unzip -y

Lalu ulangi perintah unzip.

==================================================
KALAU MODULE FLASK/RICH ERROR
==================================================

Jalankan lagi:

bash setup_termux.sh

Atau manual:

python -m pip install flask rich requests beautifulsoup4 pillow cloudscraper

