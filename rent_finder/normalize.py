import re
from typing import Iterable, Optional


AREA_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:㎡|平米|m²|m2)", re.I)
PRICE_RE = re.compile(r"(\d{3,6}(?:\.\d+)?)\s*(?:元/月|元|/月)?")
WALK_RE = re.compile(r"(?:距|距离)[^\d]{0,30}(\d{2,5})\s*米")


def first_number(value) -> Optional[float]:
    if value is None:
        return None
    m = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(m.group()) if m else None


def parse_area(text) -> Optional[float]:
    if text is None:
        return None
    m = AREA_RE.search(str(text))
    return float(m.group(1)) if m else first_number(text)


def parse_price(text) -> Optional[float]:
    if text is None:
        return None
    s = str(text).replace(",", "")
    m = PRICE_RE.search(s)
    return float(m.group(1)) if m else first_number(s)


def parse_walk(text) -> Optional[float]:
    if not text:
        return None
    m = WALK_RE.search(str(text))
    return float(m.group(1)) if m else None


def detect_station(text: str, stations: Iterable[str]) -> str:
    text = text or ""
    for station in stations:
        if station and station in text:
            return station
    return ""
