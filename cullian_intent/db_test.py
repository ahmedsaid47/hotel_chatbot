"""
ChromaDB – Kapsamlı Sağlık ve Koleksiyon Kontrol Aracı
------------------------------------------------------
* PERSIST_DIR’in gerçekten var olup olmadığını, dizin izinlerini ve boş olup olmadığını kontrol eder.
* Chroma istemcisine bağlanır, mevcut koleksiyonları listeler.
* Her koleksiyon için toplam satır (embedding) sayısını gösterir.
* Belirtilen COLLECTION_NAME’in varlığını doğrular.

Not: `pip install chromadb` (>=0.4.22) gerektirir.
"""

from pathlib import Path
from typing import List
import os
import sys
import traceback

# ---------- KULLANICI AYARLARI ----------
PERSIST_DIR     = Path("./chroma_db")          # Chroma’nın kalıcı dizini
COLLECTION_NAME = "cullinan_hotel_facts"       # Aranacak koleksiyon adı
# ----------------------------------------

def require_chromadb():
    """chromadb paketi yüklü mü? Yüklü değilse kullanıcıyı bilgilendir ve çık."""
    try:
        import chromadb
        from chromadb import PersistentClient  # noqa: F401  (yalnızca kontrol için)
        return chromadb
    except ImportError:
        sys.exit(
            "❌ chromadb paketi bulunamadı. Kurmak için:\n"
            "   pip install --upgrade chromadb"
        )

def check_directory(path: Path) -> None:
    """Dizin var mı? Okunabilir mi? Boş mu? Hata varsa yükselt."""
    if not path.exists():
        raise FileNotFoundError(f"Dizin bulunamadı: {path.resolve()}")
    if not path.is_dir():
        raise NotADirectoryError(f"Yol bir dizin değil: {path.resolve()}")
    if not os.access(path, os.R_OK):
        raise PermissionError(f"Dizine okuma izni yok: {path.resolve()}")
    if not any(path.iterdir()):
        raise FileNotFoundError(f"Dizin boş: {path.resolve()} – Chroma verisi yok.")

def connect_client(chromadb_mod, persist_dir: Path):
    """Kalıcı Chroma istemcisini başlat. Bağlantı hatalarını yakalar."""
    try:
        return chromadb_mod.PersistentClient(path=str(persist_dir))
    except Exception as exc:
        traceback.print_exc()
        sys.exit(f"❌ Chroma istemcisine bağlanılamadı ({exc}).")

def list_collections(client) -> List[str]:
    """Tüm koleksiyon adlarını döndür. Hiç koleksiyon yoksa hata."""
    collections = client.list_collections()  # List[Collection]
    if not collections:
        raise ValueError("Seçili dizinde hiç koleksiyon bulunamadı.")
    return [c.name for c in collections]

def collection_summary(col) -> str:
    """Bir koleksiyonun temel istatistiklerini (kayıt sayısı) döndürür."""
    try:
        total = col.count()  # bazı sürümlerde count() desteklenir
    except Exception:
        total = "?"
    return f"- {col.name}: toplam kayıt = {total}"

def main() -> None:
    chromadb_mod = require_chromadb()
    print("### ChromaDB Sağlık Kontrolü ###")
    print(f"Chroma sürümü           : {chromadb_mod.__version__}")
    print(f"Veri dizini             : {PERSIST_DIR.resolve()}\n")

    # 1) Dizin kontrolleri
    check_directory(PERSIST_DIR)

    # 2) İstemciyi başlat
    client = connect_client(chromadb_mod, PERSIST_DIR)

    # 3) Koleksiyonları listele + özetle
    col_names = list_collections(client)
    print("Bulunan koleksiyonlar:")
    for name in col_names:
        col = client.get_collection(name)
        print(collection_summary(col))

    # 4) Belirtilen COLLECTION_NAME var mı?
    if COLLECTION_NAME in col_names:
        print(f"\n✅ İstenen koleksiyon '{COLLECTION_NAME}' mevcut.")
    else:
        print(f"\n❌ İstenen koleksiyon '{COLLECTION_NAME}' bulunamadı.")

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        # Yakalanmayan hatalar için kullanıcı dostu çıktı
        traceback.print_exc()
        sys.exit(f"\nHata: {err}")
