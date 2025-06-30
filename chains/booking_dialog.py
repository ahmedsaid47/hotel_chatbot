# chains/booking_dialog.py
import re
from typing import Tuple
from session_manager import get_state, clear_state
from chains.booking_url import build_url

ASK = {
    "date_in":  "Lütfen giriş tarihini (YYYY-MM-DD) girer misiniz?",
    "date_out": "Çıkış tarihini (YYYY-MM-DD) yazar mısınız?",
    "rooms":    "Kaç oda istiyorsunuz?",
    "adults":   "Yetişkin sayısı?",
    "child":    "Varsa çocuk yaşlarını virgüllü (örn 8,5) yazın, yoksa 0.",
}

def _valid_date(s: str) -> bool:
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) is not None

def handle_booking_intent(user_id: str, user_msg: str) -> Tuple[str, bool]:
    """
    Dönen ikili:
    - bot_cevabı
    - completed = True → URL hazır, False → bilgi toplamaya devam
    """
    st = get_state(user_id)

    # 1) İlk kez gelindiyse merhaba de
    if st.step == "date_in" and st.date_in is None:
        st.step = "date_in"
        return (ASK["date_in"], False)

    # 2) Gelen mesaja göre state güncelle
    if st.step == "date_in":
        if _valid_date(user_msg):
            st.date_in = user_msg
            st.step = "date_out"
            return (ASK["date_out"], False)
        else:
            return ("Tarih biçimi yanlış, lütfen YYYY-MM-DD şeklinde girin.", False)

    if st.step == "date_out":
        if _valid_date(user_msg):
            st.date_out = user_msg
            st.step = "rooms"
            return (ASK["rooms"], False)
        else:
            return ("Tarih biçimi yanlış, lütfen YYYY-MM-DD şeklinde girin.", False)

    if st.step == "rooms":
        if user_msg.isdigit() and 1 <= int(user_msg) <= 9:
            st.rooms = int(user_msg)
            st.step = "adults"
            return (ASK["adults"], False)
        else:
            return ("Oda sayısı 1-9 arasında olmalı.", False)

    if st.step == "adults":
        if user_msg.isdigit() and 1 <= int(user_msg) <= 9:
            st.adults = int(user_msg)
            st.step = "child"
            return (ASK["child"], False)
        else:
            return ("Yetişkin sayısı 1-9 arasında olmalı.", False)

    if st.step == "child":
        ages = [int(a) for a in user_msg.split(",") if a.strip().isdigit()]
        st.child_ages = ages
        # ↑ kullanıcı “0” yazarsa boş liste
        url = build_url(
            date_in  = st.date_in,
            date_out = st.date_out,
            adults   = st.adults,
            child_ages = ages,
            rooms    = st.rooms,
        )
        clear_state(user_id)             # diyaloğu kapat
        return (f"Rezervasyon bağlantınız hazır → {url}", True)
