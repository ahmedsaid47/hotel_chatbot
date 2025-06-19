#!/usr/bin/env python
"""
Fine-tune edilen embedding modeli + GPT-4o (ya da tercihiniz) ile
soru-cevap (RAG) demo-su.

Kullanım:
$ python rag_pipeline.py "Plaj uzunluğu nedir?"
"""

import sys, textwrap, chromadb, openai
from typing import List
from utils import load_api_key, resolve_finetuned_model

# -- Parametreler --------------------------------------------------------
FT_JOB_ID           = "ftjob-4PgvjKjT6FqQywNiX9qKsN8H"
PERSIST_DIR         = "./chroma_db"
COLLECTION_NAME     = "cullinan_hotel_facts"
LLM_MODEL           = "gpt-4o-mini"          # çıktıyı üretecek sohbet modeli
K_RETRIEVE          = 4
MAX_CONTEXT_CHARS   = 1500                   # LLM’e taşınacak toplam metin limiti
SYSTEM_PROMPT       = """\
Sen lüks otel uzmanı bir yardımcı asistansın.
Yanıtlarda sadece güvenilir kaynaklardan gelen bilgiler kullanılmalı.
Her iddianın sonunda [Kaynak] olarak referans numarası ver."""
# ------------------------------------------------------------------------

# -- Yardımcı ------------------------------------------------------------
def embed_texts(texts: List[str], model_name: str) -> List[List[float]]:
    """Fine-tune edilmiş OpenAI embedding modeli."""
    resp = openai.embeddings.create(model=model_name, input=texts)
    return [d.embedding for d in resp.data]

def build_context(docs: List[str], metas: List[dict]) -> str:
    """Seçilen dokümanları numaralandırıp tek gövde yap."""
    parts = []
    for idx, (doc, meta) in enumerate(zip(docs, metas), 1):
        parts.append(f"[{idx}] {doc}  (Kaynak: {meta['source']})")
    ctx = "\n".join(parts)
    # Aşırı uzun olduysa ilk MAX_CONTEXT_CHARS karakteri bırak
    return ctx[:MAX_CONTEXT_CHARS]

# -- Ana akış ------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Kullanım: python rag_pipeline.py \"soru\""); return
    question = sys.argv[1]

    # 1) OpenAI kimlik
    openai.api_key = load_api_key()

    # 2) Embedding modelini çöz
    embed_model = resolve_finetuned_model(FT_JOB_ID)

    # 3) Vektör DB -> benzer dokümanlar
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    col    = client.get_collection(
        collection_name=COLLECTION_NAME,
        embedding_function=lambda txts: embed_texts(txts, embed_model)
    )

    # embed_texts bir defa çağrılacak
    results = col.query(
        query_texts=[question],
        n_results=K_RETRIEVE,
        include=["documents", "metadatas", "distances"]
    )

    docs   = results["documents"][0]
    metas  = results["metadatas"][0]

    context_block = build_context(docs, metas)

    # 4) LLM çağrısı
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f"Soru: {question}\n\n---\n{context_block}\n\nCevabın:"}
    ]
    completion = openai.chat.completions.create(
        model=LLM_MODEL,
        messages=msgs,
        temperature=0.2,
        max_tokens=400
    )
    answer = completion.choices[0].message.content
    print("\n🔹 Yanıt:\n")
    print(textwrap.fill(answer, width=100))

if __name__ == "__main__":
    main()
