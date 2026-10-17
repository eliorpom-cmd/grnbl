"""The one shape every source is turned into.

Each collector speaks its own format (a fuel price feed, a museum agenda, a
transit alert API). Everything downstream - deduplication, ranking, writing the
post - only ever sees an Item, so adding a source never touches the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Item:
    # Stable id from the source, prefixed with it: "fuel:38000004", "musees:8026988".
    id: str
    # Which channel it belongs to: "fuel", "outings", "transit", ...
    topic: str
    title: str
    text: str = ""
    # Where, as a commune name and optional coordinates.
    place: str | None = None
    lat: float | None = None
    lon: float | None = None
    start: datetime | None = None
    end: datetime | None = None
    url: str | None = None
    # True when it costs nothing to attend.
    free: bool | None = None
    # Source-specific numbers the post writer may use (a price, a saving).
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("start", "end"):
            if d[k] is not None:
                d[k] = d[k].isoformat()
        return d
