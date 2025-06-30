#!/usr/bin/env python
"""
CLI:
  Basit arama          →  python query.py "Otelin açılış tarihi nedir?"
  İlk 8 sonucu ister   →  python query.py -k 8 "Ultra Her Şey Dahil ne demek?"
  Arama + yanıt üret   →  python query.py -a "Odalar deniz manzaralı mı?"
"""

from __future__ import annotations
import argparse, sys
from pathlib import Path

import chromadb                   # pip install chromadb
from openai import OpenAI         # pip install openai>=1.14
from rich import print            # pip install rich

sys.path.append("..")
from config import load_api_key

# ─────────── Ayarlar ────────────────────────────────────────────────────
PERSIST_DIR     = Path("./chroma_db")
COLLECTION_NAME = "cullinan_hotel_facts"
EMBEDDING_MODEL = "text-embedding-3-large"
ANSWER_MODEL    = "gpt-4o-mini"          # yoksa gpt-3.5-turbo seçin
# ────────────────────────────────────────────────────────────────────────


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Metinleri OpenAI embedding vektörlerine dönüştürür."""
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def print_hit(rank: int, doc: str, meta: dict, dist: float):
    print(f"[bold cyan][{rank}][/bold cyan] {doc}")
    print(f"    • cosine: {dist:.3f}")
    print(f"    • kaynak: {meta.get('source_document', '?')}")
    print(f"    • konu  : {meta.get('topic', '?')}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cullinan Belek • Vektör Arama")
    parser.add_argument("question", nargs="+", help="Sorgu cümlesi")
    parser.add_argument("-k", "--top-k", type=int, default=5,
                        help="Dönen belge sayısı (vars. 5)")
    parser.add_argument("-a", "--answer", action="store_true",
                        help="Üst belgelerden LLM ile yanıt üret")
    args = parser.parse_args()

    query = " ".join(args.question).strip()
    if not query:
        parser.error("Sorgu cümlesi boş olamaz.")

    # 1) OpenAI istemcisi
    client = OpenAI(api_key=load_api_key())

    # 2) Sorgu embedding’i
    query_vec = embed_texts(client, [query])[0]

    # 3) ChromaDB araması
    chroma = chromadb.PersistentClient(path=str(PERSIST_DIR))
    col     = chroma.get_collection(COLLECTION_NAME)

    res = col.query(
        query_embeddings=[query_vec],
        n_results=args.top_k,
        include=["documents", "metadatas", "distances"],
    )

    # 4) Sonuçları göster
    print(f"\n[bold yellow]🔍 Sorgu:[/bold yellow] {query}\n")
    for rank, (doc, meta, dist) in enumerate(
        zip(res["documents"][0], res["metadatas"][0], res["distances"][0]), 1
    ):
        print_hit(rank, doc, meta, dist)

    # 5) İsteğe bağlı: LLM yanıtı
    if args.answer:
        context = "\n".join(
            f"{i+1}. {d}" for i, d in enumerate(res["documents"][0])
        )
        system_msg = (
            "Aşağıda Cullinan Belek oteli hakkında bilgi parçaları var. "
            "Kullanıcı sorusuna sadece bu bilgilerden yararlanarak Türkçe cevap ver. "
            "Kesin bilgi yoksa 'Bu konuda elimde bilgi yok.' de."
        )
        completion = client.chat.completions.create(
            model=ANSWER_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",
                 "content": f"Bilgiler:\n{context}\n\nSoru: {query}"},
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content.strip()
        print(f"[bold green]\n💬 Yanıt:[/bold green] {answer}")


if __name__ == "__main__":
    main()
