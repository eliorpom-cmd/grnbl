"""Command line: `python3 -m grnbl [fuel|outings|all] [--json]`.

Prints today's posts, ready to publish. --json prints the collected items instead.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .digest import fuel_post, outings_post
from .sources import fuel, museums

COLLECTORS = {"fuel": [fuel.collect], "outings": [museums.collect]}


def main(argv: list[str]) -> int:
    what = next((a for a in argv if not a.startswith("-")), "all")
    names = list(COLLECTORS) if what == "all" else [what]
    if any(n not in COLLECTORS for n in names):
        print(f"usage: python3 -m grnbl [{'|'.join(COLLECTORS)}|all] [--json]", file=sys.stderr)
        return 2

    now = datetime.now(ZoneInfo("Europe/Paris"))
    items = [i for n in names for collect in COLLECTORS[n] for i in collect()]

    if "--json" in argv:
        print(json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2))
        return 0

    posts = [p for p in (fuel_post(items, now), outings_post(items, now)) if p]
    print("\n\n────────\n\n".join(posts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
