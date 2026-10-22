"""A read-only demo of the board, as static files: `python3 -m grnbl.demo [YYYY-MM-DD] [out_dir]`.

Freezes one edition as it stood before the human review (every picked line back to "to check",
nothing posted yet), and serves the real board page with a small script in front of it: the two
reads come from the frozen JSON, the writes stay in the visitor's tab. Nothing reaches WhatsApp,
the decisions or the AI, so the folder can go on any static host and needs no key.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from . import admin

DEFAULT_OUT = admin.DATA / "demo"

# Runs before the board's own script: answers its fetch calls from the frozen files.
SHIM = """<script>
(() => {
  const real = window.fetch.bind(window), json = (d) => new Response(JSON.stringify(d), { headers: { "content-type": "application/json" } });
  let posts = null;
  const lines = (i) => posts.channels.flatMap((c) => ["to_book", "week"].flatMap((p) => c.lists?.[p] || [])).filter((x) => x.i === i);
  window.fetch = async (url, opt = {}) => {
    const path = new URL(url, location.href).pathname.replace(/^.*\\/api\\//, "/api/");
    if (!opt.method || opt.method === "GET") {
      if (path === "/api/events") return real("api/events.json");
      if (path === "/api/posts") { posts ??= await (await real("api/posts.json")).json(); return json(posts); }
      return real(url, opt);
    }
    const body = JSON.parse(opt.body || "{}");
    if (path === "/api/review") posts.review = body;
    if (path === "/api/choose") {
      // Ticked lines in, unticked lines out of the message, as the server would recompose it.
      const c = posts.channels.find((c) => c.id === body.channel), rows = c.lists[body.post] || [], k = c.parts.findIndex((p) => p.post === body.post);
      const ids = body.ids ?? rows.filter((x) => x.editor).map((x) => x.i);
      rows.forEach((x) => (x.on = ids.includes(x.i)));
      if (k >= 0) {
        const part = c.parts[k], had = Object.fromEntries(part.blocks.map((b) => [b.i, b.text]));
        part.blocks = ids.map((i) => { const x = rows.find((y) => y.i === i); return { i, text: had[i] ?? x.block ?? x.sent ?? `*${x.title}*\\n${x.line}` }; });
        rows.forEach((x) => (x.sent = x.on ? part.blocks.find((b) => b.i === x.i).text : x.sent));
        c.posts[k] = [part.head, ...part.blocks.map((b) => b.text)].join("\\n\\n");
        if (c.en?.[k]) c.en[k].stale = true;  // translated by the AI on the real board, not here
      }
    }
    if (path === "/api/decide") lines(body.i).forEach((x) => Object.assign(x, { status: body.decision?.status ?? null, block: body.decision?.block ?? x.block, line: body.decision?.line ?? x.line }));
    if (path === "/api/publish") {
      const c = posts.channels.find((c) => c.id === body.channel);
      for (const p of ["to_book", "week"]) c.outbox[p] = { status: "sent", by_hand: true, sent_at: new Date().toISOString() };
    }
    return json({ ok: true, report: [], failed: [] });
  };
})();
</script>
"""

BANNER = """<div class="demo-note">Demo: the board as it stood on {day}, before the review. Try it freely:
nothing you do is saved, and nothing is posted to WhatsApp.</div>
<style>.demo-note { background: #2f4bff; color: #fff; font-size: 13px; padding: 8px 16px; text-align: center; }</style>
"""


def snapshot(day: date) -> tuple[dict, dict]:
    """The board's two reads for that edition, from a private server on a free port."""
    admin.Handler.pinned = day
    server = ThreadingHTTPServer(("127.0.0.1", 0), admin.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        def get(path):
            req = Request(f"http://127.0.0.1:{server.server_port}{path}", headers={"Cookie": f"{admin.COOKIE}={admin.board_key()}"})
            with urlopen(req) as r:
                return json.load(r)
        return get("/api/events"), get("/api/posts")
    finally:
        server.shutdown()


def before_review(posts: dict, day: date) -> dict:
    """Every picked line back to "to check", the review and the outbox empty."""
    for c in posts["channels"]:
        for items in (c.get("lists") or {}).values():
            for x in items:
                if x.get("status") == "keep":
                    x["status"] = None
        c["outbox"] = {}
    posts["review"] = {"pending": [], "passed": [], "later": [], "verdicts": {}}
    posts["translating"] = False
    # The daily posts change every ten minutes; show the one sent that morning.
    fuel = admin.DATA / "outbox" / day.isoformat() / "carburant-fuel.json"
    for c in posts["channels"]:
        if c["id"] == "carburant" and not c["posts"] and fuel.exists():
            c["posts"] = [json.loads(fuel.read_text())["text"]]
    return posts


def build(day: date, out: Path) -> Path:
    events, posts = snapshot(day)
    (out / "api").mkdir(parents=True, exist_ok=True)
    (out / "api" / "events.json").write_text(json.dumps(events, ensure_ascii=False))
    (out / "api" / "posts.json").write_text(json.dumps(before_review(posts, day), ensure_ascii=False))
    page = admin.PAGE.read_text()
    page = page.replace("<script>", SHIM + "<script>", 1)
    page = page.replace('<header class="top">', BANNER.replace("{day}", day.strftime("%-d %B %Y")) + '<header class="top">', 1)
    page = page.replace("<title>grnbl · editor</title>", '<title>grnbl · demo board</title><link rel="icon" href="data:,">', 1)
    (out / "index.html").write_text(page)
    return out


def main(argv: list[str]) -> int:
    day = date.fromisoformat(argv[0]) if argv else admin.schedule.current_edition(date.today())
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    print(f"grnbl demo: {build(day, out)}/index.html ({day})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
