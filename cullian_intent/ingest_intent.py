#!/usr/bin/env python
"""
User-Intent • ChromaDB ingestion

• intent_dataset.jsonl   ➜   ./chroma_db   ➜   collection: "user_intents"
• Otel koleksiyonuna *dokunmaz* çünkü ayrı dizin kullanır.
"""

from __future__ import annotations
import json, sys
from pathlib import Path
from typing import Any, Dict, List
from chromadb.errors import NotFoundError

import chromadb
import openai
from openai import OpenAI
from tenacity import (
    retry, wait_random_exponential, stop_after_attempt,
    retry_if_exception_type,
)
from tqdm import tqdm

# ────────── Ortak API anahtarı ──────────
sys.path.append("..")                    # proje kökü
from config import load_api_key          # noqa: E402
openai.api_key = load_api_key()

# ────────── Parametreler ──────────
DATA_PATH       = Path("intent_dataset.jsonl")  # JSONL, build_intent_jsonl.py üretir
PERSIST_DIR     = Path("./chroma_db")           # sadece bu klasörde
COLLECTION_NAME = "user_intents"
EMBEDDING_MODEL = "text-embedding-3-large"
BATCH_SIZE      = 100
# ───────────────────────────────────

client = OpenAI()

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
    """OpenAI embedding – otomatik retry’lı."""
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def read_dataset(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def batched(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]

def main() -> None:
    if not DATA_PATH.exists():
        sys.exit(f"❌ {DATA_PATH} yok – önce build_intent_jsonl.py çalıştırın.")
    docs = read_dataset(DATA_PATH)
    print(f"📑 {len(docs)} intent cümlesi yüklendi.")

    chroma = chromadb.PersistentClient(path=str(PERSIST_DIR))

    # Sadece "user_intents" koleksiyonunu temizle
    try:
        chroma.delete_collection(COLLECTION_NAME)
        print(f"🧹 Eski '{COLLECTION_NAME}' koleksiyonu silindi.")
    except (ValueError, KeyError, NotFoundError):
        pass

    collection = chroma.get_or_create_collection(COLLECTION_NAME)

    for batch in tqdm(list(batched(docs, BATCH_SIZE)), desc="Embedding & Insert"):
        ids       = [d["chunk_id"]           for d in batch]
        texts     = [d["text_for_embedding"] for d in batch]
        metadatas = [d["metadata"]           for d in batch]
        embeddings = embed(texts)
        collection.add(ids=ids,
                       documents=texts,
                       metadatas=metadatas,
                       embeddings=embeddings)

    print(f"✅ Tamamlandı – {collection.count()} intent vektörü kaydedildi.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

