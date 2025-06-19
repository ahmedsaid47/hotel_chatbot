#!/usr/bin/env python
"""
CLI:  python query.py "Otelin açılış tarihi nedir?"
"""

import sys, chromadb, openai
from utils import load_api_key  # resolve_finetuned_model artık kullanılmıyor

PERSIST_DIR     = "./chroma_db"
COLLECTION_NAME = "cullinan_hotel_facts"
EMBEDDING_MODEL = "text-embedding-3-small"  # Uygun başka bir embedding modeli seçebilirsiniz
TOP_K           = 5


def embed(texts):
    """Metin listesini embedding vektörlerine dönüştürür."""
    resp = openai.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def main():
    if len(sys.argv) < 2:
        print('Kullanım:  python query.py "soru"')
        return

    # 1) API anahtarını ayarla
    openai.api_key = load_api_key()

    # 2) Sorgu cümlesinden embedding üret
    query_vec = embed([sys.argv[1]])[0]

    # 3) ChromaDB'de koleksiyonu aç ve sorgu çalıştır
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    col = client.get_collection(COLLECTION_NAME)

    res = col.query(
        query_embeddings=[query_vec],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    # 4) Sonuçları yazdır
    for rank, (doc, meta, dist) in enumerate(
        zip(res["documents"][0], res["metadatas"][0], res["distances"][0]), 1
    ):
        print(f"[{rank}] {doc}  (cos={dist:.3f})")
        print(f"    ► Kaynak: {meta['source']}  Bölüm: {meta['section']}\n")


if __name__ == "__main__":
    main()