"""The morning run: `python3 -m grnbl.daily`.

Scrape every source, open event pages for booking, add the yearly calendar,
let the AI review what can go out today, then let the editor compose the posts.
The admin board (python3 -m grnbl.admin) shows the result for the human's last word.
"""

from __future__ import annotations

import time

from . import editor
from .scrape import review
from .scrape.run import run_all


def main() -> None:
    t = time.time()
    report, events, _ = run_all()
    failed = [r for r in report if r[2]]
    print(f"{len(events)} events from {len(report)} steps, {len(failed)} failed {[r[0] for r in failed]}")
    reviewed = review.run()
    kept = sum(1 for e in reviewed if (e.get("review") or {}).get("keep"))
    print(f"review: {kept} kept")
    picks = editor.run()
    print(f"editor: {len(picks)} picks, {round(time.time() - t)} s in all")


if __name__ == "__main__":
    main()
