# chains/booking_url.py
from urllib.parse import urlencode, quote_plus
from datetime import datetime
from typing import List, Dict

HOTEL_ID   = 114738
DOMAIN     = "www.cullinanhotels.com"
LANGUAGEID = 1
ANCHOR     = "guestsandrooms"

def _fmt(d: str) -> str:
    """Tarihi TravelClick 'MM/DD/YYYY' biçimine çevirir."""
    fmt = "%m/%d/%Y" if "/" in d else "%Y-%m-%d"
    return datetime.strptime(d, fmt).strftime("%m/%d/%Y")

def build_url(date_in: str, date_out: str,
              adults: int,
              child_ages: List[int],
              rooms: int = 1,
              extra: Dict = None) -> str:
    params = {
        "adults": adults,
        "datein": _fmt(date_in),
        "dateout": _fmt(date_out),
        "rooms": rooms,
        "domain": DOMAIN,
        "languageid": LANGUAGEID,
    }
    if child_ages:
        params["children"] = len(child_ages)
        params["childage"] = ",".join(f"{age:02d}" for age in child_ages)
    if extra:
        params.update(extra)

    query = urlencode(params, quote_via=quote_plus)
    return f"https://bookings.travelclick.com/{HOTEL_ID}?{query}#/{ANCHOR}"
