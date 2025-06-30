"""
ChromaDB – Çoklu Veritabanı Test ve Rapor Aracı (db_test.py)
===========================================================
Bu betik, **birden fazla Chroma veritabanını** (ör. `./db/hotel_db`,
`./db/intent_db` gibi) tek seferde tarar, her biri için koleksiyon/UUID
eşleşmesini ve kayıt önizlemelerini gösterir.

Neler Yapıyor?
--------------
1. Belirttiğiniz kök klasörde (`--root` veya varsayılan `./db`) `chroma.sqlite3`
   dosyası içeren tüm alt klasörleri otomatik bulur.
2. Her veritabanı kökü için
   * Koleksiyon adı ↔ UUID eşleşmesini listeler.
   * Toplam kayıt sayısını ve ilk **3** belgenin özetini gösterir.
3. Veritabanlarında görünmeyen ("yetim") UUID klasörlerini tespit eder.

Komut Satırı
------------
```bash
# db/ altındaki tüm veritabanlarını tara
python db_test.py

# Farklı bir kök dizin tara (recursively)
python db_test.py --root /path/to/any_dir

# Yalnızca belirtilen iki veritabanını tara
python db_test.py --db /path/to/hotel_db --db /path/to/intent_db
```

Gereksinimler
-------------
* Python >= 3.8
* `pip install chromadb` (>= 1.0.12)
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import List, Dict, Any, Tuple

####################
# KÜRESEL AYARLAR #
####################
DEFAULT_ROOT_DIR = Path("./db")    # Varsayılan arama kökü (otel & intent vb.)
SAMPLE_SIZE      = 3               # Her koleksiyondan gösterilecek örnek belge sayısı

###############
# YARDIMCILAR #
###############

def require_chromadb():
    """chromadb paketini dinamik olarak içe aktarır."""
    try:
        import chromadb  # noqa: F401
        from chromadb import PersistentClient  # noqa: F401
        return chromadb
    except ImportError:
        sys.exit("❌ chromadb paketi yok. Kurmak için: pip install --upgrade chromadb")


def safe(text: str, length: int = 80) -> str:
    """Uzun string'leri kısaltır."""
    return text if len(text) <= length else text[: length - 3] + "..."


def find_chroma_roots(root: Path) -> List[Path]:
    """Alt dizinlerde 'chroma.sqlite3' içeren klasörleri döndür."""
    roots: List[Path] = []
    for p in root.rglob("chroma.sqlite3"):
        roots.append(p.parent)
    return roots


########################
# VERITABANI İŞLEMCİSİ #
########################

def get_uuid_mapping(sqlite_file: Path) -> List[Tuple[str, str]]:
    con = sqlite3.connect(sqlite_file)
    cur = con.cursor()
    rows = cur.execute("SELECT id, name FROM collections;").fetchall()
    con.close()
    return rows  # [(uuid, name), ...]


def preview_collection(col, sample_size: int = SAMPLE_SIZE) -> None:
    print(f"\n📂  Koleksiyon: {col.name}")
    try:
        total = col.count()
    except Exception:
        total = "?"
    print(f"   Toplam kayıt: {total}")

    try:
        sample = col.peek(limit=sample_size)
        docs: List[str]            = sample.get("documents", [])
        metas: List[Dict[str, Any]] = sample.get("metadatas", [])
        for i, (doc, meta) in enumerate(zip(docs, metas), 1):
            print(f"     {i}. doc : {safe(str(doc))}")
            print(f"        meta: {safe(str(meta))}")
    except Exception as exc:
        print(f"   (Örnek alınamadı: {exc})")


def analyze_db(persist_dir: Path, chromadb_mod) -> None:
    """Tek bir Chroma kök klasörü (içinde chroma.sqlite3 var) analiz eder."""
    sqlite_path = persist_dir / "chroma.sqlite3"
    mapping     = get_uuid_mapping(sqlite_path)
    if not mapping:
        print("(Veritabanında koleksiyon kaydı yok.)")
        return

    uuid_to_name = {uuid: name for uuid, name in mapping}
    print("Koleksiyon ↔ UUID:")
    for uuid, name in mapping:
        print(f"  {name}  ←→  {uuid}")

    # Detaylı önizleme
    try:
        client = chromadb_mod.PersistentClient(path=str(persist_dir))
    except Exception as exc:
        print(f"❌ İstemci başlatılamadı: {exc}\n")
        return

    print("-" * 60)
    for _uuid, name in mapping:
        try:
            col = client.get_collection(name)
            preview_collection(col)
        except Exception as exc:
            print(f"(Koleksiyon alınamadı: {exc})")

    # Yetim klasör tespiti
    dirs36 = [d for d in persist_dir.iterdir() if d.is_dir() and len(d.name) == 36]
    orphans = [d.name for d in dirs36 if d.name not in uuid_to_name]
    if orphans:
        print("\n⚠️  Yetim klasörler:")
        for o in orphans:
            print("  -", o)
    print("\n==============================\n")


########
# MAIN #
########

def main():
    parser = argparse.ArgumentParser(description="Çoklu Chroma veritabanı test aracı.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT_DIR), help="Veritabanlarını arayacağımız kök klasör")
    parser.add_argument("--db", action="append", help="Belirli veritabanı klasörü (birden çok kez kullan)")
    args = parser.parse_args()

    chromadb_mod = require_chromadb()

    # 1) Hangi klasörleri test edeceğiz?
    db_dirs: List[Path]
    if args.db:
        db_dirs = [Path(p).expanduser().resolve() for p in args.db]
    else:
        root_dir = Path(args.root).expanduser().resolve()
        if not root_dir.exists():
            sys.exit(f"❌ Kök klasör bulunamadı: {root_dir}")
        db_dirs = find_chroma_roots(root_dir)
        if not db_dirs:
            sys.exit("Belirtilen kökte chroma.sqlite3 içeren bir klasör bulunamadı.")

    print("\n### Toplam", len(db_dirs), "veritabanı bulunudu ###\n")

    for db_path in db_dirs:
        if not (db_path / "chroma.sqlite3").exists():
            print(f"(Atla) {db_path} içinde chroma.sqlite3 yok.")
            continue
        print("Veritabanı:", db_path)
        analyze_db(db_path, chromadb_mod)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        traceback.print_exc()
        sys.exit(f"\nHata: {err}")
