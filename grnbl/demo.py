"""A read-only demo of the board, as static files: `python3 -m grnbl.demo [YYYY-MM-DD] [out_dir]`.

Freezes one edition as it stood before the human review (every picked line back to "to check",
nothing posted yet), and serves the real board page with a small script in front of it: the two
reads come from the frozen JSON, the writes stay in the visitor's tab. Nothing reaches WhatsApp,
the decisions or the AI, so the folder can go on any static host and needs no key. Card texts are
translated once into English for the judges (cached in data/demo-en.json); WhatsApp posts stay French,
with the board's English translation under each.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import sys
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from . import admin
from .scrape.extract import ask

DEFAULT_OUT = admin.DATA / "demo"
CACHE = admin.DATA / "demo-en.json"  # English card texts, keyed by event and by the French they came from

# The card texts a judge reads, per event: on the row (line, why, sent) and on the event (the rest).
ROW_FIELDS, EVENT_FIELDS = ("line", "why", "sent"), ("description", "review_why", "price", "zoom")

PROMPT = """Translate the French texts in this JSON into natural English, for judges who do not speak French.
Return the same JSON, same keys and same structure, with every string value translated.
Keep exactly: line breaks, emoji, the WhatsApp formatting (*bold*, _italic_), links, numbers and prices.
Keep names of venues, towns, organisations, bands and shows as written; translate event titles made of ordinary words.
Dates and times in English: "mercredi 21" -> "Wednesday 21", "sam. 24/10 à 20h" -> "Sat 24/10 at 8pm".
Inside the texts, never write the " character (it breaks the JSON): use “ and ” instead.
Return only the JSON, with no comment and no code fence.

JSON:
{items}
"""

# Runs before the board's own script: answers its fetch calls from the frozen files.
SHIM = """<script>
(() => {
  const real = window.fetch.bind(window), json = (d) => new Response(JSON.stringify(d), { headers: { "content-type": "application/json" } });
  let posts = null;
  // Card texts in the board's language: English from `tr`, the French kept aside in `fr`.
  const lang = () => { try { return localStorage.getItem("grnbl-lang") || "en"; } catch { return "en"; } };
  const rowSwap = (x, l) => { if (!x.tr) return; x.fr ??= { line: x.line, why: x.why, sent: x.sent }; Object.assign(x, l === "en" ? { ...x.fr, ...x.tr } : x.fr); };
  const eventSwap = (e, l) => {
    if (!e.tr) return;
    e.fr ??= { description: e.description, price: e.price, review_why: e.review?.why, zoom: e.pick?.zoom?.what };
    const t = l === "en" ? { ...e.fr, ...e.tr } : e.fr;
    Object.assign(e, { description: t.description, price: t.price });
    if (e.review) e.review.why = t.review_why;
    if (e.pick?.zoom) e.pick.zoom.what = t.zoom;
  };
  const rows = (d) => d?.channels?.flatMap((c) => Object.values(c.lists || {}).flat()) || [];
  const swapAll = (l) => {
    rows(posts).forEach((x) => rowSwap(x, l));
    try { rows(data).forEach((x) => rowSwap(x, l)); (events || []).forEach((e) => eventSwap(e, l)); } catch {}
  };
  document.addEventListener("click", (ev) => { const b = ev.target.closest?.("#lang button"); if (b) swapAll(b.dataset.l); }, true);
  const lines = (i) => posts.channels.flatMap((c) => ["to_book", "week"].flatMap((p) => c.lists?.[p] || [])).filter((x) => x.i === i);
  window.fetch = async (url, opt = {}) => {
    const path = new URL(url, location.href).pathname.replace(/^.*\\/api\\//, "/api/");
    if (!opt.method || opt.method === "GET") {
      if (path === "/api/events") { const d = await (await real("api/events.json")).json(); d.events.forEach((e) => eventSwap(e, lang())); return json(d); }
      if (path === "/api/posts") { if (!posts) { posts = await (await real("api/posts.json")).json(); rows(posts).forEach((x) => rowSwap(x, lang())); } return json(posts); }
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
        part.blocks = ids.map((i) => { const x = rows.find((y) => y.i === i); return { i, text: had[i] ?? x.block ?? (x.fr || x).sent ?? `*${x.title}*\\n${(x.fr || x).line}` }; });
        rows.forEach((x) => { if (x.on) (x.fr || x).sent = part.blocks.find((b) => b.i === x.i).text; });
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

BANNER = """<div class="demo-note"><b>Demo: the board on {day}, before my review.</b> Keep a card with → or
<i>Keep</i>, remove it with ←; a replacement comes next. Then open <i>Messages</i> (key 2) to see each WhatsApp
post and its English translation. Nothing is saved, nothing is posted.</div>
<style>.demo-note { background: #2f4bff; color: #fff; font-size: 13px; line-height: 1.45; padding: 8px 16px; text-align: center; }
.demo-note i { font-style: normal; font-weight: 600; }</style>
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


def french(posts: dict, events: list[dict]) -> dict[int, dict]:
    """The French card texts of every event the demo shows, by event index."""
    by_i = {e["i"]: e for e in events}
    out: dict[int, dict] = {}
    for c in posts["channels"]:
        for rows in (c.get("lists") or {}).values():
            for x in rows:
                e = by_i.get(x["i"], {})
                texts = {"line": x.get("line"), "why": x.get("why"), "sent": x.get("sent"),
                         "description": e.get("description"), "review_why": (e.get("review") or {}).get("why"),
                         "price": e.get("price"), "zoom": ((e.get("pick") or {}).get("zoom") or {}).get("what")}
                out.setdefault(x["i"], {}).update({k: v for k, v in texts.items() if isinstance(v, str) and v.strip()})
    return out


def translate(texts: dict[int, dict], batch: int = 10) -> dict[int, dict]:
    """English for each event's texts, through Haiku, 10 events a call; unchanged French is never sent twice."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    sig = {i: hashlib.sha1(json.dumps(t, ensure_ascii=False, sort_keys=True).encode()).hexdigest() for i, t in texts.items()}
    todo = [i for i in texts if (cache.get(str(i)) or {}).get("sig") != sig[i]]

    def run(ids):
        try:
            reply = ask(PROMPT.format(items=json.dumps({str(i): texts[i] for i in ids}, ensure_ascii=False)))
            got = json.loads(reply[reply.find("{"):reply.rfind("}") + 1])
        except ValueError:
            if len(ids) == 1:
                raise
            # One broken reply: each event again on its own, so one bad text does not hold back ten.
            return {i: en for one in ids for i, en in run([one]).items()}
        return {i: got[str(i)] for i in ids if isinstance(got.get(str(i)), dict)}

    with cf.ThreadPoolExecutor(3) as pool:
        for job in [pool.submit(run, todo[k:k + batch]) for k in range(0, len(todo), batch)]:
            try:
                for i, en in job.result().items():
                    cache[str(i)] = {"sig": sig[i], "en": en}
            except (RuntimeError, ValueError) as err:  # left in French; the next run tries again
                print(f"grnbl demo: translation failed: {err}", file=sys.stderr)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return {i: cache[str(i)]["en"] for i in texts if (cache.get(str(i)) or {}).get("sig") == sig[i]}


def attach(posts: dict, events: list[dict], english: dict[int, dict]) -> None:
    """Each row and event carries its English as `tr`; the page swaps it in when the board is in English."""
    for c in posts["channels"]:
        for rows in (c.get("lists") or {}).values():
            for x in rows:
                if x["i"] in english:
                    x["tr"] = {k: v for k, v in english[x["i"]].items() if k in ROW_FIELDS}
    for e in events:
        if e["i"] in english:
            e["tr"] = {k: v for k, v in english[e["i"]].items() if k in EVENT_FIELDS}


def build(day: date, out: Path) -> Path:
    events, posts = snapshot(day)
    posts = before_review(posts, day)
    attach(posts, events["events"], translate(french(posts, events["events"])))
    (out / "api").mkdir(parents=True, exist_ok=True)
    (out / "api" / "events.json").write_text(json.dumps(events, ensure_ascii=False))
    (out / "api" / "posts.json").write_text(json.dumps(posts, ensure_ascii=False))
    page = admin.PAGE.read_text()
    page = page.replace("<script>", SHIM + "<script>", 1)
    # In English the card shows the translation: say so, the post itself goes out in French.
    for en in ("As sent on WhatsApp", "Joins the message if kept"):
        page = page.replace(f'L("{en}"', f'L("{en} (English translation)"')
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
