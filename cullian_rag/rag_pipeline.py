#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cullinan Belek • RAG demo 2.0  (İzlenebilir Hibrit Arama)
──────────────────────────────────────────────────────────
- Embedding  : OpenAI text-embedding-3-large
- Retriever  : ChromaDB (./chroma_db, collection: cullinan_hotel_facts)
- LLM        : gpt-4o-mini
"""

from __future__ import annotations
import argparse, logging, sys, re, json, textwrap
from pathlib import Path
from typing import Any, Dict, List

import chromadb               # pip install chromadb
from openai import OpenAI      # pip install openai>=1.14
from tenacity import retry, wait_random_exponential, stop_after_attempt
from rich import print, box
from rich.table import Table

sys.path.append("..")
from config import load_api_key  # kendi util’iniz

# ╭─ Genel Ayarlar ───────────────────────────────────────────────────────╮
PERSIST_DIR      = Path("./chroma_db")
COLLECTION_NAME  = "cullinan_hotel_facts"
EMBEDDING_MODEL  = "text-embedding-3-large"
LLM_MODEL        = "gpt-4o-mini"
MAX_TOKENS_OUT   = 500

LOG_DIR          = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE         = LOG_DIR / "pipeline.log"

# Metadata alan isimlerini tek yerde tutalım
FIELD_CAP_ADULT  = "maks_kapasite_yetiskin"
FIELD_CAP_CHILD  = "maks_kapasite_cocuk"
FIELD_SWIM_UP    = "swim_up"
FIELD_VIEW       = "manzara"
FIELD_BATHROOMS  = "banyo_sayisi"
# ╰───────────────────────────────────────────────────────────────────────╯


# ───── Loglama (terminal + dosya) ────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("RAGPipeline")


# ───── Sistem Promptu ────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "Sen Cullinan Belek oteli hakkında bir uzmansın. Sana SAĞLANAN NUMARALANDIRILMIŞ KAYNAKLARI kullanarak kullanıcının sorusunu yanıtla. "
    "Kaynaklarda hem doğal dil metinleri hem de yapısal veriler (kapasite, metrekare, yatak tipleri vb.) bulunabilir. "
    "Özellikle sayısal veya kesin bilgi istenen sorularda metinden ziyade YAPISAL VERİLERİ temel al. "
    "Cevabında ilgili kaynak numaralarını köşeli parantezle belirt (örn. [1]). "
    "Eğer kaynaklarda cevap yoksa 'Bu konuda bilgim yok.' de."
)


# ───── Yardımcı Fonksiyonlar ─────────────────────────────────────────────
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def embed_texts(ai: OpenAI, texts: List[str]) -> List[List[float]]:
    resp = ai.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


class OpenAIEmbeddingFunction(chromadb.EmbeddingFunction):
    def __init__(self, ai_client: OpenAI):
        self._ai = ai_client

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        return embed_texts(self._ai, input)


# ───── Filtre Çıkarma ────────────────────────────────────────────────────
def extract_filters(question: str) -> Dict[str, Any]:
    """
    Soru -> Chroma 'where' filtresi.
    Farklı senaryolar düşünülerek OR/AND yapıları eklenmiştir.
    """
    q = question.lower()
    clauses: List[Dict[str, Any]] = []

    # Yetişkin kapasitesi (>=)
    if m := re.search(r'(\d+)\s*(kişilik|yetişkin)', q):
        num = int(m.group(1))
        clauses.append({
            "$or": [
                {FIELD_CAP_ADULT: {"$gte": num}},         # numerik ise
                {FIELD_CAP_ADULT: str(num)}               # metin ise (eşit)
            ]
        })

    # Swim-up
    if "swim-up" in q or "swim up" in q:
        clauses.append({FIELD_SWIM_UP: True})

    # Manzara
    if "deniz manzaralı" in q:
        clauses.append({FIELD_VIEW: {"$in": ["Deniz", "Bahçe + Deniz"]}})
    if "golf manzaralı" in q:
        clauses.append({FIELD_VIEW: "Golf"})

    # Banyo sayısı (>=)
    if m := re.search(r'(en az|min(?:imum)?)\s*(\d+)\s*banyo', q):
        num = int(m.group(2))
        clauses.append({FIELD_BATHROOMS: {"$gte": num}})

    if not clauses:
        return {}
    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


# ───── Bağlam Birleştirme ────────────────────────────────────────────────
def build_context(docs: List[str], metas: List[dict]) -> str:
    parts = []
    for idx, (doc, meta) in enumerate(zip(docs, metas), 1):
        oda = meta.get("oda_tipi", "Genel Bilgi")
        cap_a = meta.get(FIELD_CAP_ADULT)
        cap_c = meta.get(FIELD_CAP_CHILD, 0)
        cap_txt = f"{cap_a} yetişkin" if cap_a is not None else "Kapasite belirsiz"
        if cap_c:
            cap_txt += f" + {cap_c} çocuk"

        yatak_txt = ""
        if (raw := meta.get("yatak_opsiyonlari_json")):
            try:
                j = json.loads(raw)
                yatak_txt = " / ".join(
                    f"{opt['opsiyon_adi']}: " +
                    ", ".join(f"{y['adet']}×{y['boyut']}" for y in opt["yataklar"])
                    for opt in j
                )
            except Exception:
                yatak_txt = "Yatak detayı okunamadı"

        ctx = (
            f"[{idx}] Oda Tipi: {oda} | Kapasite: {cap_txt}\n"
            f"    Metin: {doc}\n"
            f"    Yataklar: {yatak_txt}\n"
            f"    (Kaynak: {meta.get('source_document', '?')})"
        )
        parts.append(ctx)
    return "\n\n".join(parts)


# ───── Ana Çalışma ───────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Cullinan Belek • RAG Pipeline 2.0",
        formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("question", nargs="+", help="Kullanıcı sorusu")
    ap.add_argument("-k", "--top-k", type=int, default=4, help="Dönüş adedi (vars: 4)")
    ap.add_argument("-T", "--temperature", type=float, default=0.1, help="LLM sıcaklığı")
    ap.add_argument("--inspect", action="store_true",
                    help="Koleksiyondan örnek meta alanlarını yazdır ve çık")
    args = ap.parse_args()

    q_text = " ".join(args.question).strip()

    # ── OpenAI bağlantısı
    try:
        ai = OpenAI(api_key=load_api_key())
    except Exception as e:
        logger.error("API anahtarı yüklenemedi: %s", e)
        sys.exit(1)

    # ── Chroma bağlantısı
    chroma = chromadb.PersistentClient(path=str(PERSIST_DIR))
    col = chroma.get_collection(
        name=COLLECTION_NAME,
        embedding_function=OpenAIEmbeddingFunction(ai)
    )

    if args.inspect:
        sample = col.get(limit=3, include=["metadatas"])
        table = Table(title="Örnek Metadata", box=box.SIMPLE, show_edge=False)
        for i, meta in enumerate(sample["metadatas"], 1):
            table.add_row(f"[{i}]", json.dumps(meta, ensure_ascii=False, indent=2))
        print(table)
        sys.exit(0)

    # ── Filtre çıkar + logla
    where = extract_filters(q_text)
    logger.info("Filtre: %s", where or "Yok")

    # ── Sorgu 1: filtreli
    res = col.query(query_texts=[q_text], n_results=args.top_k,
                    where=where, include=["documents", "metadatas"])

    # Geri dönüş yoksa filtresiz dene
    if not res["documents"][0]:
        logger.warning("Filtreli sorguda sonuç yok, filtresiz deniyorum…")
        res = col.query(query_texts=[q_text], n_results=args.top_k,
                        include=["documents", "metadatas"])
        if not res["documents"][0]:
            print("[bold red]Hiç sonuç bulunamadı.[/bold red]")
            sys.exit(0)

    docs, metas = res["documents"][0], res["metadatas"][0]
    context = build_context(docs, metas)

    # ── LLM çağrısı
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": f"Soru: {q_text}\n\n--- KAYNAKLAR ---\n{context}\n\nCevabın:"}
    ]
    reply = ai.chat.completions.create(
        model=LLM_MODEL,
        messages=msgs,
        temperature=args.temperature,
        max_tokens=MAX_TOKENS_OUT
    ).choices[0].message.content

    # ── Çıktılar
    print(f"\n[bold yellow]❓ Soru:[/bold yellow] {q_text}\n")
    print("[bold cyan]🔍 Kaynaklar:[/bold cyan]")
    for i, m in enumerate(metas, 1):
        print(f"  [{i}] {m.get('oda_tipi', 'Bilinmeyen')}  "
              f"(Kaynak: {m.get('source_document', '?')})")
    print("\n[bold green]💬 Yanıt:[/bold green]\n")
    print(textwrap.fill(reply, width=100))


# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        logger.exception("Beklenmedik hata: %s", exc)
        sys.exit(1)
