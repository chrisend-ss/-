import argparse
import csv
import json
from pathlib import Path

from rent_finder.adapters.beike_csv import load_beike_csv
from rent_finder.adapters.fang_json import load_fang_json
from rent_finder.adapters.lianjia_html import collect_source
from rent_finder.filter import run as apply_filter
from rent_finder.lianjia_sources import discover_lianjia_sources


BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
STATIONS = CONFIG["stations_priority"]


def _write_csv(path, rows):
    columns = [
        "source", "title", "community", "rent", "area_sqm", "layout",
        "rent_type", "metro_station", "walk_to_metro_m", "address",
        "published_at", "url", "_score",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _collect_lianjia_sources(sources):
    items = []
    for source in sources:
        url = str(source.get("url", "")).strip()
        station = str(source.get("station", "")).strip()
        if not url.startswith("http") or station not in STATIONS:
            continue
        try:
            items.extend(
                collect_source(
                    url=url,
                    station_hint=station,
                    pages=int(source.get("pages", 3)),
                    delay_s=float(source.get("delay_s", 2.0)),
                )
            )
        except Exception as exc:
            print(f"[WARN] {station} 抓取失败: {exc}")
    return items


def main():
    p = argparse.ArgumentParser(description="杭州钱江世纪城主城区方向租房收集器")
    p.add_argument("--sources", help="额外/覆盖的链家来源配置 JSON")
    p.add_argument(
        "--no-auto-lianjia",
        action="store_true",
        help="关闭从杭州链家站点地图自动发现目标站点",
    )
    p.add_argument("--beike-csv", action="append", default=[], help="旧贝壳爬虫 CSV，可重复")
    p.add_argument("--fang-json", action="append", default=[], help="旧 rentHouseSpider JSON，可重复")
    p.add_argument("--out-dir", default="rent_finder/output")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_items = []

    if not args.no_auto_lianjia:
        try:
            discovered = discover_lianjia_sources(STATIONS)
            (out_dir / "lianjia_sources.json").write_text(
                json.dumps({"lianjia": discovered}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"自动发现链家站点入口 {len(discovered)}/{len(STATIONS)} 个")
            all_items.extend(_collect_lianjia_sources(discovered))
        except Exception as exc:
            print(f"[WARN] 自动发现链家站点失败: {exc}")

    if args.sources:
        sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
        all_items.extend(_collect_lianjia_sources(sources.get("lianjia", [])))

    for path in args.beike_csv:
        all_items.extend(load_beike_csv(path, STATIONS))

    for path in args.fang_json:
        all_items.extend(load_fang_json(path, STATIONS))

    filtered = apply_filter(all_items)

    (out_dir / "all.json").write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "matches.json").write_text(
        json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_csv(out_dir / "matches.csv", filtered)

    print(f"采集 {len(all_items)} 条；符合条件 {len(filtered)} 条")
    print(f"最终候选: {out_dir / 'matches.csv'}")


if __name__ == "__main__":
    main()
