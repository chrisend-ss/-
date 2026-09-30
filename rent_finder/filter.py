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
    return " ".join(
        str(item.get(k, ""))
        for k in ("title", "community", "rent_type", "tags", "description", "address")
    )


def eligible(item):
    area = num(item.get("area_sqm"), -1)
    rent = num(item.get("rent"), -1)
    if area < CONFIG["area_sqm"]["min"]:
        return False
    if rent <= 0 or rent > CONFIG["rent"]["max"]:
        return False

    text = normalize_text(item)
    if any(k in text for k in CONFIG["exclude_keywords"]):
        return False

    rent_type = str(item.get("rent_type", "")).strip()
    if rent_type and "整租" not in rent_type:
        return False

    station = str(item.get("metro_station", "")).strip()
    if station not in STATION_RANK:
        return False

    walk_raw = item.get("walk_to_metro_m")
    if walk_raw not in (None, ""):
        walk = num(walk_raw, 999999)
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
        str(item.get("metro_station", "")).strip(),
    )


def score(item):
    rent = num(item.get("rent"))
    area = num(item.get("area_sqm"))
    station = str(item.get("metro_station", ""))
    station_penalty = STATION_RANK.get(station, 99) * 8

    walk_raw = item.get("walk_to_metro_m")
    walk_penalty = 12 if walk_raw in (None, "") else num(walk_raw, 1000) * 0.025

    # 你的偏好：面积大优先，同时控制在约3000元，优先离钱江世纪城更近的主城区站。
    return (
        area * 1.8
        - abs(rent - CONFIG["rent"]["target"]) * 0.025
        - walk_penalty
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
