#!/usr/bin/env python3
from manage_products import force_auto_product_from_link

print("=== CEK AUTO NAMA DARI LINK ===")
link = input("Masukkan link produk: ").strip()
pid = input("No produk untuk test [999]: ").strip() or "999"
if not link:
    print("Link kosong.")
    raise SystemExit(1)

data = force_auto_product_from_link(link, pid)
print("\nHASIL:")
print("Nama     :", data.get("name") or "BELUM TERBACA")
print("Harga    :", data.get("price") or "-")
print("Gambar   :", data.get("image") or data.get("image_url") or "-")
print("Final URL:", data.get("final_url") or link)
print("\nDebug tersimpan di auto_link_debug_last.txt")
