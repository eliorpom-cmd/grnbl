"""The admin board: `python3 -m grnbl.admin` then open http://127.0.0.1:8730

Shows today's reviewed events with the AI's verdict, lets the human approve,
drop or rewrite each one, and previews the posts exactly as they will go out.
Decisions are kept in data/decisions/<day>.json; the AI never publishes alone.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from .digest import fuel_post, outings_post_reviewed, to_book_post
from .sources import fuel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PAGE = Path(__file__).with_name("admin.html")
PARIS = ZoneInfo("Europe/Paris")


def day_folder(day: date) -> Path:
    return DATA / "events" / day.isoformat()


def load(day: date) -> dict:
    folder = day_folder(day)
    reviewed = folder / "reviewed.json"
    events = json.loads(reviewed.read_text()) if reviewed.exists() else []
    decisions_path = DATA / "decisions" / f"{day.isoformat()}.json"
    decisions = json.loads(decisions_path.read_text()) if decisions_path.exists() else {}
    for i, e in enumerate(events):
        e["i"] = i
        e["decision"] = decisions.get(str(i))
    return {"day": day.isoformat(), "events": events}


def save_decision(day: date, i: int, decision: dict | None) -> None:
    path = DATA / "decisions" / f"{day.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    decisions = json.loads(path.read_text()) if path.exists() else {}
    if decision is None:
        decisions.pop(str(i), None)
    else:
        decisions[str(i)] = decision
    path.write_text(json.dumps(decisions, ensure_ascii=False, indent=1))


class Handler(BaseHTTPRequestHandler):
    day = date.today()

    def _send(self, code: int, body: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/events":
            return self._json(load(self.day))
        if self.path == "/api/posts":
            now = datetime.now(PARIS)
            data = load(self.day)["events"]
            try:
                fuel_text = fuel_post(fuel.collect(), now)
            except Exception as e:  # noqa: BLE001 - the board still shows the outings
                fuel_text = f"(carburant indisponible : {e})"
            watch_path = day_folder(self.day) / "watch.json"
            watch = json.loads(watch_path.read_text()) if watch_path.exists() else []
            return self._json({"fuel": fuel_text, "to_book": to_book_post(data, now),
                               "outings": outings_post_reviewed(data, now), "watch": watch})
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/decide":
            return self._send(404, b"not found", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        i = body.get("i")
        if not isinstance(i, int):
            return self._json({"ok": False}, 400)
        decision = body.get("decision")
        if decision is not None:
            decision = {"status": decision.get("status"), "line": decision.get("line")}
        save_decision(self.day, i, decision)
        self._json({"ok": True})

    def log_message(self, *args):  # quiet
        pass


def main(argv: list[str]) -> int:
    if argv:
        Handler.day = date.fromisoformat(argv[0])
    server = ThreadingHTTPServer(("127.0.0.1", 8730), Handler)
    print(f"grnbl admin: http://127.0.0.1:8730  ({Handler.day})")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
