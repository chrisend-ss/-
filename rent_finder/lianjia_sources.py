from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


SITEMAP_URL = "https://hz.lianjia.com/seositemap/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def discover_lianjia_sources(stations, sitemap_url=SITEMAP_URL, timeout_s=12):
    resp = requests.get(
        sitemap_url,
        headers={"User-Agent": UA},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    wanted = {f"{station}地铁租房": station for station in stations}
    found = {}

    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        station = wanted.get(label)
        if not station:
            continue
        href = urljoin(sitemap_url, a.get("href"))
        # 同名站可能出现在多条线路下，租房页面本身可复用；保留首个。
        found.setdefault(station, href)

    return [
        {"station": station, "url": found[station], "pages": 3}
        for station in stations
        if station in found
    ]
