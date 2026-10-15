import os
import sys

def rename_photos(folder_path):
    folder_name = os.path.basename(folder_path.rstrip("/\\"))
    
    extensions = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
    files = [f for f in os.listdir(folder_path) 
             if f.lower().endswith(extensions)]
    files.sort()

    for i, file in enumerate(files, start=1):
        ext = os.path.splitext(file)[1].lower()
        new_name = f"{folder_name}_{i}{ext}"
        old_path = os.path.join(folder_path, file)
        new_path = os.path.join(folder_path, new_name)
        os.rename(old_path, new_path)
        print(f"[RENAMED] {file} → {new_name}")

    print(f"\n[DONE] {len(files)} files renamed.")

# ── PUT FOLDER PATH HERE ──────────────────────────────
folder = r"C:\Users\dell\OneDrive\Desktop\FYP Module\employees\Wasay"
# ─────────────────────────────────────────────────────

rename_photos(folder)