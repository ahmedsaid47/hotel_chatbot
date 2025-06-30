#!/usr/bin/env python
"""
Cullinan Belek • ChromaDB ingestion

• data.json  ➜  ./chroma_db  ➜  collection: "cullinan_hotel_facts"
• Eski koleksiyonu siler, tamamını yeniden oluşturur.
• OpenAI 2024-03 embedding modellerinden `text-embedding-3-large` kullanır.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import chromadb                      # pip install chromadb
import openai                        # pip install openai>=1.14
from openai import OpenAI
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Ortak config modülünden API anahtarını yükle
# ---------------------------------------------------------------------------
sys.path.append("..")                # proje kökünü modül arama yoluna ekle
from config import load_api_key      # noqa: E402  (import konumu bilinçli)

openai.api_key = load_api_key()      # tek satırda kimlik doğrulama

# ---------------------------------------------------------------------------
# Kullanıcıya göre ayarlanabilir parametreler
# ---------------------------------------------------------------------------
DATA_PATH       = Path("data1_fixed.json")
PERSIST_DIR     = Path("./chroma_db")
COLLECTION_NAME = "cullinan_hotel_facts"
EMBEDDING_MODEL = "text-embedding-3-large"   # gerekirse değiştirilebilir
BATCH_SIZE      = 100                        # max 2048 token / istek
# ---------------------------------------------------------------------------

# ── OpenAI istemcisi ────────────────────────────────────────────────────────
client = OpenAI()                   # api_key global olarak şimdiden ayarlı

TRANSIENT_ERRORS = (
    openai.RateLimitError,
    openai.APIStatusError,
    openai.APIConnectionError,
    openai.Timeout,
)


@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type(TRANSIENT_ERRORS),
)
def embed(texts: List[str]) -> List[List[float]]:
    """Metin listesini embed eder, hata durumunda otomatik yeniden dener."""
    try:
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    except openai.AuthenticationError as exc:
        raise RuntimeError(
            "🚫 OpenAI kimlik doğrulaması başarısız. "
            "Geçerli bir anahtar kullandığınızdan emin olun."
        ) from exc
    return [d.embedding for d in resp.data]


def read_dataset(path: Path) -> List[Dict[str, Any]]:
    """Hem JSON array hem de satır-başı JSONL formatını destekler."""
    with path.open("r", encoding="utf-8") as f:
        first = f.readline().strip()
        f.seek(0)
        if first.startswith("{") and first.endswith("}"):
            return [json.loads(line) for line in f]  # JSONL
        return json.load(f)  # JSON array


def batched(lst: list, size: int):
    """Listeyi sabit büyüklükte yığınlara (batch) böler."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def main() -> None:
    # 1) Veri ----------------------------------------------------------------
    if not DATA_PATH.exists():
        sys.exit(f"❌ {DATA_PATH} bulunamadı.")
    docs = read_dataset(DATA_PATH)
    print(f"📑 {len(docs)} kayıt yüklendi.")

    # 2) ChromaDB ------------------------------------------------------------
    chroma = chromadb.PersistentClient(path=str(PERSIST_DIR))

    # Mevcut koleksiyonu sil → temiz başlangıç
    try:
        chroma.delete_collection(COLLECTION_NAME)
        print(f"🧹 Eski '{COLLECTION_NAME}' koleksiyonu silindi.")
    except (ValueError, KeyError):
        pass  # zaten yoksa

    collection = chroma.get_or_create_collection(COLLECTION_NAME)

    # 3) Embedding + ekleme --------------------------------------------------
    for batch in tqdm(list(batched(docs, BATCH_SIZE)),
                      desc="Embedding & Insert"):
        ids       = [d["chunk_id"]           for d in batch]
        texts     = [d["text_for_embedding"] for d in batch]
        metadatas = [d["metadata"]           for d in batch]

        embeddings = embed(texts)

        collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    print(f"✅ Tamamlandı → {collection.count()} vektör kaydedildi.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)