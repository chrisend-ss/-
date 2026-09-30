from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class RentListing:
    source: str
    title: str = ""
    community: str = ""
    rent: Optional[float] = None
    area_sqm: Optional[float] = None
    layout: str = ""
    rent_type: str = ""
    metro_station: str = ""
    walk_to_metro_m: Optional[float] = None
    address: str = ""
    tags: str = ""
    description: str = ""
    published_at: str = ""
    url: str = ""

    def to_dict(self):
        return asdict(self)
