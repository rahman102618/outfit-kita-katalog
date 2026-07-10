#!/data/data/com.termux/files/usr/bin/bash
set -e
PROJECT_DIR="${1:-/storage/emulated/0/Termux/katalog-1}"
PATCH_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
cp -f manage_products.py manage_products_backup_sebelum_ui_clean.py 2>/dev/null || true
cp -f "$PATCH_DIR/manage_products.py" "$PROJECT_DIR/manage_products.py"
echo "OK: UI clean patch terpasang di $PROJECT_DIR"
echo "Jalankan: cd $PROJECT_DIR && python manage_products.py"
