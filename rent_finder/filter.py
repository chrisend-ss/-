import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
STATION_RANK = {name: i for i, name in enumerate(CONFIG["stations_priority"])}

def num(v, default=0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def normalize_text(item):
    return " ".join(str(item.get(k, "")) for k in ("title", "community", "rent_type", "tags", "description"))

def eligible(item):
    if num(item.get("area_sqm")) < CONFIG["area_sqm"]["min"]:
        return False
    if num(item.get("rent")) > CONFIG["rent"]["max"] or num(item.get("rent")) <= 0:
        return False

    text = normalize_text(item)
    if any(k in text for k in CONFIG["exclude_keywords"]):
        return False

    if item.get("rent_type") and "整租" not in str(item.get("rent_type")):
        return False

    station = str(item.get("metro_station", ""))
    if station not in STATION_RANK:
        return False

    walk = num(item.get("walk_to_metro_m"), 999999)
    if walk > CONFIG["max_walk_to_metro_m"]:
        return False

    return True

def dedupe_key(item):
    url = str(item.get("url", "")).strip()
    if url:
        return ("url", url)
    return (
        str(item.get("community", "")).strip(),
        round(num(item.get("area_sqm")), 1),
        int(num(item.get("rent"))),
        str(item.get("layout", "")).strip(),
    )

def score(item):
    rent = num(item.get("rent"))
    area = num(item.get("area_sqm"))
    walk = num(item.get("walk_to_metro_m"), 1000)
    station = str(item.get("metro_station", ""))
    station_penalty = STATION_RANK.get(station, 99) * 8

    # 面积越大越好；租金越接近 3000 越好；离地铁越近越好；优先靠近钱江世纪城的主城区站点。
    return (
        area * 1.8
        - abs(rent - CONFIG["rent"]["target"]) * 0.025
        - walk * 0.025
        - station_penalty
    )

def run(items):
    seen = set()
    result = []
    for item in items:
        if not eligible(item):
            continue
        key = dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        item = dict(item)
        item["_score"] = round(score(item), 2)
        result.append(item)
    result.sort(key=lambda x: x["_score"], reverse=True)
    return result

def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法: python rent_finder/filter.py input.json")
    path = Path(sys.argv[1])
    items = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("items", [])
    print(json.dumps(run(items), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
