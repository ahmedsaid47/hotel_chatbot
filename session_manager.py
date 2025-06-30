# session_manager.py  – mini in-memory state; prod’da Redis önerilir
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

@dataclass
class BookingState:
    step: str = "date_in"          # sıradaki alan
    date_in: Optional[str] = None
    date_out: Optional[str] = None
    rooms: int = 1
    adults: int = 2
    child_ages: List[int] = field(default_factory=list)

# {user_id: BookingState}
_SESSIONS: Dict[str, BookingState] = {}

def get_state(user_id: str) -> BookingState:
    return _SESSIONS.setdefault(user_id, BookingState())

def clear_state(user_id: str):
    _SESSIONS.pop(user_id, None)
