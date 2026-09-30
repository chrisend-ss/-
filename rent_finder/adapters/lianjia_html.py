import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from rent_finder.normalize import parse_area, parse_price, parse_walk
from rent_finder.schema import RentListing


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def _page_url(base_url: str, page: int) -> str:
    if "{page}" in base_url:
        return base_url.format(page=page)
    if page <= 1:
        return base_url
    marker = "/zufang/"
    if marker in base_url:
        head, tail = base_url.split(marker, 1)
        return f"{head}{marker}pg{page}{tail}"
    return base_url


def _text(node, selector: str) -> str:
    hit = node.select_one(selector)
    return hit.get_text(" ", strip=True) if hit else ""


def _parse_layout(text: str) -> str:
    m = re.search(r"(\d+室(?:\d+厅)?(?:\d+卫)?)", text or "")
    return m.group(1) if m else ""


def _parse_rent_type(title: str, full_text: str) -> str:
    text = f"{title} {full_text}"
    if "整租" in text:
        return "整租"
    if "合租" in text:
        return "合租"
    return ""


def parse_listing_page(html: str, source_url: str, station_hint: str = ""):
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div.content__list--item")
    out = []

    for item in items:
        title_node = (
            item.select_one(".content__list--item--title a")
            or item.select_one("a.content__list--item--aside")
            or item.select_one("a[href]")
        )
        title = title_node.get_text(" ", strip=True) if title_node else ""
        if not title and title_node:
            title = (title_node.get("title") or "").strip()

        href = (title_node.get("href") or "") if title_node else ""
        url = urljoin(source_url, href) if href else ""

        desc = _text(item, ".content__list--item--des")
        bottom = _text(item, ".content__list--item--bottom")
        full_text = item.get_text(" ", strip=True)

        price_node = item.select_one(".content__list--item-price em")
        price_text = price_node.get_text(strip=True) if price_node else _text(item, ".content__list--item-price")
        rent = parse_price(price_text)

        area = parse_area(desc or full_text)
        layout = _parse_layout(desc or full_text)
        rent_type = _parse_rent_type(title, full_text)
        walk = parse_walk(full_text)

        # 链家卡片中小区名的 DOM 在不同版本里不完全一致，优先从详情描述切分。
        community = ""
        parts = [p.strip() for p in re.split(r"[/|]", desc) if p.strip()]
        for p in parts:
            if "㎡" not in p and "平米" not in p and not re.search(r"\d+室", p):
                if "-" in p:
                    community = p.split("-")[-1].strip()
                elif len(p) <= 30:
                    community = p
                if community:
                    break

        out.append(
            RentListing(
                source="lianjia",
                title=title,
                community=community,
                rent=rent,
                area_sqm=area,
                layout=layout,
                rent_type=rent_type,
                metro_station=station_hint,
                walk_to_metro_m=walk,
                tags=bottom,
                description=desc,
                url=url,
            ).to_dict()
        )
    return out


def collect_source(
    url: str,
    station_hint: str,
    pages: int = 3,
    delay_s: float = 2.0,
    timeout_s: float = 12.0,
):
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    collected = []

    for page in range(1, max(1, pages) + 1):
        page_url = _page_url(url, page)
        resp = session.get(page_url, timeout=timeout_s)
        resp.raise_for_status()
        batch = parse_listing_page(resp.text, page_url, station_hint=station_hint)
        collected.extend(batch)

        # 无结果通常意味着到尾页/页面结构变化；不继续高频请求。
        if not batch:
            break
        if page < pages:
            time.sleep(delay_s)

    return collected
