import csv
import re

from rent_finder.normalize import detect_station, parse_area, parse_price
from rent_finder.schema import RentListing


def _value(row, *names):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return ""


def load_beike_csv(path, stations):
    out = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            title = _value(row, "房源名称", "title")
            base = _value(row, "房屋基本信息", "house_base_info")
            features = _value(row, "房屋特点", "house_feature")
            source_text = _value(row, "房屋来源", "house_src")
            text = " ".join([title, base, features, source_text])

            low = _value(row, "最低价(元/月)", "最低价", "price_min", "price")
            rent = parse_price(low)
            area = parse_area(base)
            station = detect_station(text, stations)
            rent_type = "整租" if "整租" in text else ("合租" if "合租" in text else "")
            layout_match = re.search(r"(\d+室(?:\d+厅)?(?:\d+卫)?)", text)

            out.append(
                RentListing(
                    source="beike_legacy_csv",
                    title=title,
                    rent=rent,
                    area_sqm=area,
                    layout=layout_match.group(1) if layout_match else "",
                    rent_type=rent_type,
                    metro_station=station,
                    address=_value(row, "区域", "area"),
                    tags=features,
                    description=base,
                    published_at=_value(row, "发布时间", "publish_date"),
                    url=_value(row, "租房链接", "house_url"),
                ).to_dict()
            )
    return out
