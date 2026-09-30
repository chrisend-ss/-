import json

from rent_finder.normalize import detect_station, parse_area, parse_price
from rent_finder.schema import RentListing


def load_fang_json(path, stations):
    data = json.loads(open(path, "r", encoding="utf-8").read())
    if isinstance(data, dict):
        data = data.get("items", data.get("data", []))

    out = []
    for row in data:
        text = " ".join(
            str(row.get(k, ""))
            for k in ("title", "address", "traffic", "region", "rooms", "direction")
        )
        out.append(
            RentListing(
                source="rentHouseSpider_legacy",
                title=str(row.get("title", "")),
                rent=parse_price(row.get("price")),
                area_sqm=parse_area(row.get("area")),
                layout=str(row.get("rooms", "")),
                rent_type="整租" if "整租" in text else "",
                metro_station=detect_station(text, stations),
                address=str(row.get("address", "")),
                description=str(row.get("traffic", "")),
                url=str(row.get("url", "")),
            ).to_dict()
        )
    return out
