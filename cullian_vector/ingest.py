#!/usr/bin/env python
"""
data.json'daki kayıtları, OpenAI’nin embedding modeliyle vektörleştirip ChromaDB'ye ekler.
"""

import json, os, sys, time
from typing import List
import chromadb
from tqdm import tqdm
import openai
from utils import load_api_key  # resolve_finetuned_model artık kullanılmıyor

# -- Parametreler --------------------------------------------------------
DATA_PATH       = "data.json"
COLLECTION_NAME = "cullinan_hotel_facts"
PERSIST_DIR     = "./chroma_db"

# Embedding için fine-tune edilmiş model *kullanılamaz*; uygun bir baz model seçin
EMBEDDING_MODEL = "text-embedding-3-small"   # dilediğiniz başka gömülü modelle değiştirebilirsiniz

BATCH_SIZE      = 100          # OpenAI Embeddings max 2048 token/toplu
# ------------------------------------------------------------------------


def load_docs(path: str):
    with open(path, "r", encoding="utf-8") as f:
        first = f.readline().strip()
        f.seek(0)
        if first.startswith("{") and first.rstrip().endswith("}"):
            return [json.loads(l) for l in f]
        return json.load(f)


def chunk(lst: List, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def main():
    # 1) API key / model --------------------------------------------------
    openai.api_key = load_api_key()
    model_name = EMBEDDING_MODEL
    print(f"🧩 Kullanılacak embedding modeli: {model_name}")

    # 2) Verileri oku -----------------------------------------------------
    docs = load_docs(DATA_PATH)
    print(f"Toplam {len(docs)} kayıt.")

    # 3) ChromaDB ---------------------------------------------------------
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    # 4) Toplu embedding + insert -----------------------------------------
    for batch in tqdm(list(chunk(docs, BATCH_SIZE)), desc="Yükleniyor"):
        ids = [d["id"] for d in batch]
        texts = [d["text"] for d in batch]
        metadatas = [d["metadata"] for d in batch]

        # --- OpenAI Embeddings çağrısı -----------------------------------
        resp = openai.embeddings.create(
            model=model_name,
            input=texts,
        )
        embeds = [d.embedding for d in resp.data]

        collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeds,
        )
        time.sleep(0.2)  # Yumuşak rate-limit için

    print(f"✅ Tamamlandı → {PERSIST_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)