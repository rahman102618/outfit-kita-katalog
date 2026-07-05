#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=== SETUP OUTFIT KITA MANAGER ==="
echo "Menyiapkan paket dasar Termux..."
pkg update -y
pkg install -y python git unzip curl

echo "Menginstall library Python..."
# Jangan upgrade pip di Termux.
python -m pip install requests beautifulsoup4 rich pillow cloudscraper flask || python -m pip install requests beautifulsoup4 rich pillow flask

mkdir -p public/assets

echo ""
echo "Setup selesai."
echo "Jalankan manager: python manage_products.py"
echo "Jalankan dashboard: python admin_app.py"
