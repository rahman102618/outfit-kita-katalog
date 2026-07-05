#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "Memasang dependency Termux yang lebih aman..."
pkg update -y
pkg install -y python git unzip curl clang make pkg-config libjpeg-turbo zlib freetype libpng

# Pillow di Termux lebih aman dari paket pkg. Kalau tersedia, pakai ini agar tidak build dari source.
pkg install -y python-pillow || true

# Jangan paksa pip install pillow kalau pkg python-pillow sudah ada.
python -m pip install requests beautifulsoup4 cloudscraper rich || true

echo "Selesai. Test dengan: python cek_nama_dari_link.py"
