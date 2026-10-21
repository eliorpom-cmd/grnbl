"""The public site: one static page per event of an edition, plus the edition's front page.

Each event posted on WhatsApp gets a page with its facts (when, where, price, booking) and our own
line, never the source's text or photos, and a button to the organiser's page to book. The posts
can carry a short link to that page (off by default, see `post_link`).

    python3 -m grnbl.site [YYYY-MM-DD] [--out DIR]

writes `site/` (index.html, e/<slug>/index.html, 404.html, sitemap.xml, robots.txt, og.png), ready
for Cloudflare Pages. Settings, environment first, then data/site.json ({"url", "umami", "links"}):

    SITE_URL          where the site is served, the only thing to change to move domain
    UMAMI_WEBSITE_ID  the site's id on stats.byelior.dev; no tag without it
    SITE_LINKS=1      put each event's page link in the WhatsApp posts
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "site"
SETTINGS = DATA / "site.json"
# Cloudflare Pages' own address for a project named grnbl: works before any DNS change.
DEFAULT_URL = "https://grnbl.pages.dev"
UMAMI_SCRIPT = "https://stats.byelior.dev/p.js"
OG_IMAGE = ROOT / "brand" / "export" / "whatsapp" / "communaute.png"
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]
POSTS = (("to_book", "📅 À réserver maintenant"), ("week", "Cette semaine"))


def settings() -> dict:
    saved = {}
    if SETTINGS.exists():
        try:
            saved = json.loads(SETTINGS.read_text())
        except ValueError:
            saved = {}
    env = os.environ
    links = env.get("SITE_LINKS", "")
    return {"url": (env.get("SITE_URL") or saved.get("url") or DEFAULT_URL).rstrip("/"),
            "umami": env.get("UMAMI_WEBSITE_ID") or saved.get("umami") or "",
            "links": links == "1" if links else saved.get("links") is True}


def slugify(text: str, limit: int = 48) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    words = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    if len(words) > limit:
        words = words[:limit].rsplit("-", 1)[0]
    return words or "evenement"


def _start(e: dict) -> datetime | None:
    raw = e.get("start")
    try:
        return datetime.fromisoformat(str(raw)[:16]) if raw else None
    except ValueError:
        return None


def slug(e: dict) -> str:
    """Stable for an event: its title and first day, short enough to read in a post."""
    start = _start(e)
    return slugify(e.get("title") or "") + (f"-{start.day}-{start.month}" if start else "")


def page_url(e: dict, base: str | None = None) -> str:
    return f"{(base or settings()['url'])}/e/{slug(e)}"


def post_link(e: dict) -> str | None:
    """The event's page for a WhatsApp post, or None while links are off (the default)."""
    s = settings()
    return page_url(e, s["url"]) if s["links"] else None


def when(raw, with_year: bool = False) -> str:
    """"samedi 24 octobre à 15 h", or without the time when the source gives none."""
    try:
        d = datetime.fromisoformat(str(raw)[:16])
    except ValueError:
        return ""
    out = f"{DAYS[d.weekday()]} {d.day}{'er' if d.day == 1 else ''} {MONTHS[d.month - 1]}"
    if with_year:
        out += f" {d.year}"
    if len(str(raw)) > 10 and (d.hour or d.minute):
        out += f" à {d.hour} h" + (f" {d.minute:02d}" if d.minute else "")
    return out


def _plain(text: str) -> str:
    """A post line without WhatsApp's *bold* and _italic_ marks."""
    return re.sub(r"(?<!\w)[*_]|[*_](?!\w)", "", text or "").strip()


def _place(e: dict) -> str:
    where = (e.get("venue") or "").strip()
    town = (e.get("town") or "").strip()
    parts = [p.title() if p.isupper() and len(p) > 6 else p for p in (where, town) if p]
    if len(parts) == 2 and parts[1].lower() in parts[0].lower():
        parts = parts[:1]
    return ", ".join(parts)


def _price(e: dict) -> str:
    free = (e.get("review") or {}).get("free")
    if free is None:
        free = e.get("free")
    if free is True:
        return "Gratuit"
    return (e.get("price") or "").strip()


def _host(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def entries(events: list[dict], selection: list[dict] | None) -> list[dict]:
    """What the edition posts, group by group, in each post's order: one entry per (group, post, event)."""
    from .channels import CHANNELS
    from .digest import picked

    if not selection:
        return []
    index = {id(e): k for k, e in enumerate(events)}
    out = []
    for channel in CHANNELS:
        sel = [p for p in selection if p.get("channel", "sorties") == channel]
        for post, _ in POSTS:
            zooms = {p["i"]: p.get("zoom") for p in sel if p.get("post") == post and p.get("zoom")}
            for e, line in picked(events, sel, post) or []:
                out.append({"channel": channel, "post": post, "event": e, "line": _plain(line),
                            "zoom": zooms.get(index[id(e)])})
    return out


CSS = """
:root{--bg:#F5F6FA;--card:#FFFFFF;--ink:#111322;--muted:#5B6075;--line:#E3E5EE;--blue:#2F4BFF;--lime:#C6FF3D;
--on-lime:#111322;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#0D0F1A;--card:#171A2A;--ink:#F2F3F8;--muted:#A3A8BD;--line:#2A2E44}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",
Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-text-size-adjust:100%}
a{color:inherit}
.top{background:var(--blue);color:#fff}
.top .in{max-width:680px;margin:0 auto;padding:14px 16px;display:flex;align-items:center;gap:10px}
.mark{font-weight:800;font-size:22px;letter-spacing:-.02em;text-decoration:none;color:#fff}
.dots{display:inline-flex;gap:4px}.dots i{width:7px;height:7px;border-radius:50%;background:var(--lime);display:block}
main{max-width:680px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:28px;line-height:1.15;letter-spacing:-.02em;margin:4px 0 12px}
h2{font-size:19px;margin:32px 0 10px}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 8px}
.lede{color:var(--muted);margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px 18px;margin:0 0 10px}
.card a.t{font-weight:700;text-decoration:none}.card a.t:hover{text-decoration:underline}
.meta{color:var(--muted);font-size:15px;margin:2px 0 6px}
.card p:last-child{margin-bottom:0}
.tag{display:inline-block;font-size:13px;font-weight:700;padding:2px 9px;border-radius:99px;background:var(--lime);
color:var(--on-lime);margin-right:6px;vertical-align:1px}
dl{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;margin:16px 0}
dt{color:var(--muted)}dd{margin:0;font-weight:600}
.line{font-size:19px;margin:12px 0}
.moment{border-left:4px solid var(--lime);padding:4px 0 4px 12px;margin:14px 0}
.btn{display:block;text-align:center;background:var(--lime);color:var(--on-lime);font-weight:800;font-size:18px;
padding:15px 18px;border-radius:14px;text-decoration:none;margin:20px 0 8px}
.btn:focus-visible,.card a:focus-visible{outline:3px solid var(--blue);outline-offset:2px}
.note{color:var(--muted);font-size:14px}
.back{display:inline-block;margin-top:24px;color:var(--muted)}
footer{max-width:680px;margin:0 auto;padding:0 16px 32px;color:var(--muted);font-size:14px}
"""


def _head(title: str, description: str, url: str, s: dict, has_og: bool) -> str:
    esc = html.escape
    og = f"{s['url']}/og.png"
    tags = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(title)}</title>",
        f'<meta name="description" content="{esc(description)}">',
        f'<link rel="canonical" href="{esc(url)}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="grnbl">',
        '<meta property="og:locale" content="fr_FR">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:url" content="{esc(url)}">',
        '<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(description)}">',
        '<meta name="theme-color" content="#2F4BFF">',
    ]
    if has_og:
        tags += [f'<meta property="og:image" content="{og}">', '<meta property="og:image:width" content="640">',
                 '<meta property="og:image:height" content="640">',
                 '<meta property="og:image:alt" content="grnbl, les sorties de Grenoble dans WhatsApp">',
                 f'<meta name="twitter:image" content="{og}">',
                 '<link rel="icon" href="/og.png">', '<link rel="apple-touch-icon" href="/og.png">']
    if s["umami"]:
        tags.append(f'<script defer src="{UMAMI_SCRIPT}" data-website-id="{esc(s["umami"])}"></script>')
    tags.append(f"<style>{CSS}</style>")
    return "\n".join(tags)


def _page(title: str, description: str, url: str, body: str, s: dict, has_og: bool) -> str:
    return (f'<!doctype html>\n<html lang="fr">\n<head>\n{_head(title, description, url, s, has_og)}\n</head>\n<body>\n'
            '<header class="top"><div class="in"><a class="mark" href="/">grnbl</a>'
            '<span class="dots" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span></div></header>\n'
            f"<main>\n{body}\n</main>\n"
            "<footer>grnbl trie chaque semaine les agendas publics de Grenoble et les partage dans des groupes "
            "WhatsApp. Vérifiez toujours l'horaire sur la page de l'organisateur.</footer>\n</body>\n</html>\n")


def event_page(e: dict, line: str, zoom: dict | None, groups: list[str], s: dict, has_og: bool,
               today: date | None = None) -> str:
    esc = html.escape
    title = (e.get("title") or "").strip()
    start, place, price = when(e.get("start")), _place(e), _price(e)
    rows = [("Quand", start)]
    end = e.get("end")
    if end and str(end)[:10] != str(e.get("start"))[:10]:
        rows.append(("Jusqu'au", when(end)))
    others = [when(d) for d in (e.get("dates") or [])[1:6]]
    if others:
        rows.append(("Autres dates", ", ".join(others)))
    rows += [("Où", place), ("Prix", price)]
    dl = "".join(f"<dt>{k}</dt><dd>{esc(v)}</dd>" for k, v in rows if v)
    tags = "".join(f'<span class="tag">{esc(g)}</span>' for g in groups)
    body = [f"<p>{tags}</p>" if tags else "", f"<h1>{esc(title)}</h1>"]
    if line:
        body.append(f'<p class="line">{esc(line)}</p>')
    if zoom and zoom.get("what"):
        bits = [zoom.get("what"), when(zoom.get("when")) if zoom.get("when") else "", zoom.get("where") or ""]
        body.append(f'<p class="moment"><strong>Le moment à ne pas manquer :</strong> '
                    f'{esc(" · ".join(b for b in bits if b))}</p>')
    body.append(f"<dl>{dl}</dl>")
    booking, source = e.get("booking_url"), e.get("url")
    target = booking or source
    if e.get("sold_out"):
        body.append('<p class="note"><strong>Complet</strong> selon l\'organisateur.</p>')
    elif e.get("booking_opens") and str(e["booking_opens"])[:10] > (today or date.today()).isoformat():
        body.append(f'<p class="note">Réservations à partir du {esc(when(e["booking_opens"]))}.</p>')
    elif e.get("booking_deadline"):
        body.append(f'<p class="note">Réserver avant le {esc(when(e["booking_deadline"]))}.</p>')
    if target:
        label = "Réserver" if booking or e.get("booking") else "Voir la page de l'organisateur"
        body.append(f'<a class="btn" href="{esc(target)}" rel="noopener" data-umami-event="reserve_click" '
                    f'data-umami-event-event="{esc(slug(e))}">{label}</a>')
        body.append(f'<p class="note">Sur {esc(_host(target))}. Les infos ci-dessus viennent de cette page.</p>')
    body.append('<a class="back" href="/">← Toutes les sorties de la semaine</a>')
    description = " · ".join(x for x in (start, place, price) if x) or "Une sortie repérée par grnbl à Grenoble."
    return _page(f"{title} · grnbl", description, page_url(e, s["url"]), "\n".join(b for b in body if b), s, has_og)


def index_page(day: date, items: list[dict], s: dict, has_og: bool) -> str:
    from .channels import CHANNELS

    esc = html.escape
    body = [f"<h1>Cette semaine à Grenoble</h1>",
            f'<p class="lede">Édition du {esc(when(day.isoformat(), with_year=True))} · {len({slug(x["event"]) for x in items})} sorties, '
            "triées à la main parmi les agendas de la ville.</p>"]
    if not items:
        body.append('<p class="card">Pas encore d\'édition cette semaine.</p>')
    for channel, c in CHANNELS.items():
        mine = [x for x in items if x["channel"] == channel]
        if not mine:
            continue
        body.append(f"<h2>{esc(c['label'])}</h2>")
        for post, heading in POSTS:
            rows = [x for x in mine if x["post"] == post]
            if not rows:
                continue
            body.append(f"<h3>{esc(heading)}</h3>")
            for x in rows:
                e = x["event"]
                meta = " · ".join(v for v in (when(e.get("start")), _place(e), _price(e)) if v)
                body.append(f'<div class="card"><a class="t" href="/e/{esc(slug(e))}/">{esc(e.get("title", "").strip())}</a>'
                            f'<p class="meta">{esc(meta)}</p>{("<p>" + esc(x["line"]) + "</p>") if x["line"] else ""}</div>')
    return _page("grnbl · les sorties de la semaine à Grenoble",
                 "Les sorties gratuites, en famille, les brocantes et la nature à Grenoble, choisies chaque semaine.",
                 s["url"] + "/", "\n".join(body), s, has_og)


def not_found(s: dict, has_og: bool) -> str:
    body = ("<h1>Cette page n'existe plus</h1><p class=\"lede\">La sortie est peut-être passée. "
            "Les idées de la semaine sont sur l'accueil.</p><a class=\"btn\" href=\"/\">Voir les sorties de la semaine</a>")
    return _page("Page introuvable · grnbl", "Page introuvable", s["url"] + "/404", body, s, has_og)


def build(day: date, events: list[dict], selection: list[dict] | None, out: Path = OUT,
          s: dict | None = None, og_image: Path | None = OG_IMAGE) -> list[str]:
    """Writes the whole site into `out` (emptied first) and returns the event slugs."""
    from .channels import CHANNELS

    s = s or settings()
    items = entries(events, selection)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    has_og = bool(og_image and og_image.exists())
    if has_og:
        shutil.copyfile(og_image, out / "og.png")
    pages: dict[str, dict] = {}
    for x in items:
        key = slug(x["event"])
        page = pages.setdefault(key, {"event": x["event"], "line": x["line"], "zoom": x["zoom"], "groups": []})
        label = CHANNELS[x["channel"]]["label"]
        if label not in page["groups"]:
            page["groups"].append(label)
    for key, p in pages.items():
        folder = out / "e" / key
        folder.mkdir(parents=True)
        (folder / "index.html").write_text(event_page(p["event"], p["line"], p["zoom"], p["groups"], s, has_og, day))
    (out / "index.html").write_text(index_page(day, items, s, has_og))
    (out / "404.html").write_text(not_found(s, has_og))
    urls = [s["url"] + "/"] + [f"{s['url']}/e/{k}/" for k in pages]
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"  <url><loc>{html.escape(u)}</loc><lastmod>{day.isoformat()}</lastmod></url>\n"
                                               for u in urls) + "</urlset>\n")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {s['url']}/sitemap.xml\n")
    return list(pages)


def main(argv: list[str]) -> int:
    from . import publish, schedule

    out = OUT
    if "--out" in argv:
        k = argv.index("--out")
        out = Path(argv[k + 1]).resolve()
        argv = argv[:k] + argv[k + 2:]
    if argv:
        day = date.fromisoformat(argv[0])
    else:
        found = schedule.editions()
        if not found:
            print("no edition yet (data/events/<wednesday>/selection.json)")
            return 1
        day = found[-1]
    events, selection = publish.day_events(day)
    slugs = build(day, events, selection, out)
    print(f"{len(slugs)} event pages for the {day.isoformat()} edition in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
