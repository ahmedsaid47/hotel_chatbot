from chains.booking_dialog import handle_booking_intent

from collections import Counter
from pathlib import Path
import chromadb, openai, json
from tenacity import retry, wait_random_exponential, stop_after_attempt

from config import load_api_key
from chains.rag_hotel import answer_hotel
from chains.booking_api import handle_booking
from chains.small_talk import respond_small_talk
from chains.ticket_system import create_ticket
import openai
from openai import OpenAI

openai.api_key = load_api_key()
client = OpenAI()
EMBED_MODEL = "text-embedding-3-large"

# -- Chroma istemcileri -------------------------------------------------
intent_db  = chromadb.PersistentClient(path="db/intent_db")
hotel_db   = chromadb.PersistentClient(path="db/hotel_db")
booking_db = chromadb.PersistentClient(path="db/booking_db")

intent_col  = intent_db.get_or_create_collection("user_intents")
hotel_col   = hotel_db.get_or_create_collection("hotel_facts")
booking_col = booking_db.get_or_create_collection("booking_logs")

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def embed(texts: list[str]) -> list[list[float]]:
    """OpenAI 1.x uyumlu embedding üretir."""
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [obj.embedding for obj in resp.data]

def predict_intent(query: str, k=5) -> str:
    vec = embed([query])[0]
    res = intent_col.query(query_embeddings=[vec], n_results=k, include=["metadatas"])
    intents = [m["intent"] for m in res["metadatas"][0]]
    return Counter(intents).most_common(1)[0][0]

def router(user_id: str, query: str) -> str:
    intent = predict_intent(query)

    if intent in {"fiyat_sorgulama", "rezervasyon_oluşturma"}:
        reply, done = handle_booking_intent(user_id, query)
        return reply



def router(query: str) -> str:
    intent = predict_intent(query)
    match intent:
        case "selamla" | "veda" | "teşekkür":
            return respond_small_talk(intent)
        case "yardım":
            return respond_small_talk(intent, query)
        case "rezervasyon_oluşturma" | "rezervasyon_değiştirme" | "rezervasyon_iptali":
            return handle_booking(intent, query)
        case "rezervasyon_durumu":
            return handle_booking(intent, query, check_only=True)
        case ("fiyat_sorgulama" | "oda_bilgisi" | "yemek_bilgisi" |
              "havalimanı_transferi" | "otopark_bilgisi" |
              "yol_tarifi" | "adres_bilgisi"):
            return answer_hotel(query, hotel_col)
        case "şikayet" | "geri_bildirim":
            return create_ticket(query)
        case _:
            return "Üzgünüm, sorununuzu anlayamadım. Biraz daha ayrıntı verebilir misiniz?"

# CLI test
if __name__ == "__main__":
    while True:
        q = input("👤> ")
        print("🤖", router(q))
