# grnbl

A WhatsApp community for Grenoble that posts the week's outings, deals and the cheapest fuel, the way the
person in your family who always knows what's on would tell you.

Built for [Neighborhood Hacks 2026](https://neighborhoodhacks.org/).

## The problem

In my family, my mum is the one who finds the outings and the deals: free concerts, concerts inside museums,
things we would never have heard of otherwise. This October she found that the Tour Perret, a concrete tower
in Grenoble that is normally a paid visit, was free on Sunday 18 October for the national architecture days,
on booked time slots. The tourist office agenda did not list it; a local newspaper did. Without someone like her, nobody
around me thinks of it. All of this information is public, but it is spread over dozens of agendas,
newspapers and price feeds, and it is often found too late: a free tower visit is worthless if its slots
filled up days before.

grnbl reads those public sources, keeps what is worth going to, and posts it in plain French to WhatsApp
groups people join by topic. There is nothing to install for the people who read it.

## What it does

A WhatsApp community called GRNBL with one group per topic, plus the community's announcement group:

| Group | Content | When |
| --- | --- | --- |
| 🆓 Gratuit | free outings only | Wednesday 12:00 |
| 🎭 Sorties | the best outings, paid ones included | Wednesday 12:00 |
| 👨‍👩‍👧 Famille | outings for children and families | Wednesday 12:00 |
| 🛍️ Bons plans | flea markets, jumble sales, ski swaps | Thursday 18:00 |
| 🏔️ Nature | hikes, nature outings, mountain events | Thursday 18:00 |
| ⛽ Carburant | the 3 cheapest stations per fuel type in the Métropole | every day from 10:00, automatic |
| 🚨 Alerts (announcement group) | red weather warning, air quality "très mauvaise" or worse, strike or stop of the whole tram network | only when it happens, sent by a human |

Each outings group gets two posts per edition:

- **📅 À réserver maintenant** (book now): events that need booking, announced while there is still time.
- **🎭 Cette semaine** (this week): walk-in events of the coming days.

The posts are in French because the readers are in Grenoble. The admin board is in English, and shows an
English translation under each post (not published), so non-French readers can follow.

## How it works

One edition per week. It is prepared on Tuesday at 10:00, read once by a human, then each group's posts go
out on their own day.

```
41 sources (36 agendas and venues, 5 local newspapers) + a calendar of yearly events
   |
   |  read by code where a site publishes structured data (JSON-LD, The Events Calendar API,
   |  the tourist office's event pages), by Claude Haiku where it is plain HTML
   v
events in one shape (title, dates, venue, price, booking fields)
   |  merge duplicates, fold repeated sessions into one event with its dates   (code)
   |  open each event's own page for booking information                       (code + Haiku)
   v
booking-window status for each event: book_now / opens_soon / this_week / later / too_late / sold_out   (code)
   |
   v
AI review of what can be posted today: keep or drop, why, score 1-5, free, family, duplicates   (Claude Sonnet)
   |
   v
which group may carry which event   (code: a paid event can never reach the free group)
   |
   v
editor-in-chief: per group, compares the 40 best candidates and composes the two posts,
with the reason for each pick and 3 reserves per post   (Claude Sonnet)
   |  fact-check of each line against the event's data and page   (code)
   |  English translation for the board   (Haiku)
   v
admin board: about 11 lines per group to read, untick to remove, "All good" to approve   (human)
   |
   v
outbox -> whatsapp/send.mjs -> WhatsApp groups, at the group's slot, once
```

An hourly job (`deploy/tick.sh`, launchd on the Mac) runs `grnbl/tick.py`, which does what is due this hour
and records it in `data/schedule-state.json` so nothing happens twice:

- **Tuesday from 10:00**: prepare the edition (about 27 minutes on the first full run), then ping Discord.
- **Two hours before a slot**: Discord reminder if a post is not approved yet.
- **At the slot** (Wednesday 12:00, Thursday 18:00): send the approved posts. A post nobody approved does not
  go out, and the ping says so.
- **Every day from 10:00**: the fuel post, sent on its own.
- **Every hour from 7:00 to 22:00**: check the alerts. An alert is only raised if it is seen on two checks in a
  row at least 45 minutes apart. It is then pinged on Discord and waits for a human click on the board.
  Nothing is sent automatically.

### Rules that make a tip useful (`grnbl/editorial.py`)

- An event that requires booking is posted at least 4 days ahead, and up to 60 days ahead.
- Booking that opens within 7 days is announced now, with its opening date.
- A walk-in event is posted the day before at the latest. "This week" covers the next 8 days.
- When the next session of a series is too close to book, the following one is posted instead.
- A long festival or a year-long programme is reduced to one precise moment (day, time, what, where): the
  editor reads the event's page and its "programme" link. In the free group, that moment must be free.

### Memory and taste (`grnbl/memory.py`)

- What was already posted (`data/posted.json`) is not posted again.
- An event seen at 3 or more different dates is marked routine, so the rare goes before the routine.
- The human's keep and drop decisions on the board are given to the review and the editor as examples.
- One event goes to one group only, unless the review scored it 5.

## What is code and what is AI

| Code (same result every time, tested) | AI (judgement on text) |
| --- | --- |
| reading structured sources (JSON-LD, WordPress API, fuel feed, alerts) | extracting events from plain HTML agendas and press articles (Haiku) |
| booking-window rules and dates | finding booking information on an event page (Haiku) |
| which group may carry an event (free, family, flea market, nature) | judging whether an event is worth going to (Sonnet) |
| deduplication of identical titles, series of sessions | spotting the same event under two names (Sonnet) |
| fuel ranking, alert thresholds and double check | choosing a varied post and writing each line (Sonnet) |
| fact-check of names, numbers and weekdays in each line | English translation for the board (Haiku) |
| schedule, outbox, "never send twice" | |

The reason: anything that must be guaranteed (a paid event never in the free group, a deadline never missed,
an alert never sent alone) is code, because the AI's output varies from one run to the next. The AI is used
where the job is reading or judging text, which would otherwise mean writing and maintaining thirty
site-specific parsers.

Every line still gets a human read before it is posted. The fact-check (`grnbl/factcheck.py`) flags any
proper name or number that appears in neither the event's data nor its page, and any weekday that does not
match the date. The board shows these as "check on the page".

## AI cost

The AI steps call Claude through the `claude` CLI (`claude -p`), with Claude Code's own instructions, tools
and MCP servers turned off (31,067 tokens of wrapper per call down to 560) and with thinking off for Haiku
(9 times less output for the same events). Pages, booking answers and review verdicts are cached on disk, so
an unchanged page is never sent to the AI twice. Every call is logged in `data/usage.jsonl`;
`extract.usage()` gives a day's total.

Full trial run of 18 October 2026, real data (folder `data/events/2026-10-19/`):

- 1,203 events collected, 38 of the 41 sources returned events, 448 kept by the review, about 27 minutes, no
  error.
- About 0.72 M tokens in and 0.17 M out for Haiku, 0.36 M in and 0.30 M out for Sonnet, for that afternoon
  (trial plus editor re-runs, from `data/usage.jsonl`, cached input included).

## Run it locally

Requirements: Python 3 (tested on 3.14, standard library only), the `claude` CLI signed in, and Node.js for
the WhatsApp side.

```bash
# prepare an edition (collect, booking pages, calendar, review, editor, translation)
python3 -m grnbl.daily                 # or: python3 -m grnbl.daily 2026-10-21

# one hourly pass by hand (what the scheduler runs)
python3 -m grnbl.tick

# steps on their own
python3 -c 'from grnbl.scrape.run import run_all; run_all()'   # all sources -> data/events/<day>/all.json
python3 -c 'from grnbl.scrape import review; review.run()'      # AI review -> reviewed.json
python3 -m grnbl.translate [YYYY-MM-DD]                         # English translations for the board
python3 -m grnbl fuel                                           # print the fuel post

# the admin board, http://127.0.0.1:8730 (open the link it prints, it carries the key)
python3 -m grnbl.admin

# Discord ping preview
python3 -m grnbl.notify --print

# outbox: dry run by default, --send to send, group names to filter
python3 -m grnbl.publish
python3 -m grnbl.publish gratuit sorties --send

# WhatsApp, once per machine
cd whatsapp && npm install
node whatsapp/send.mjs link [phone]    # link the account as a device (QR code or pairing code)
node whatsapp/send.mjs groups          # list the groups and their ids for data/whatsapp.json
```

The first collection is slow (the tourist office alone is about 95 list pages, plus about 100 press
articles); the caches make later runs faster.

## Configuration

Versioned:

- `grnbl/scrape/sources.py`: every source. Adding an agenda is adding a line.
- `grnbl/calendar.json`: 12 yearly rendez-vous (architecture days, heritage days, first Sunday of the month at
  the museums, Christmas market...). A date marked `confirmed: false` is never posted; it only appears under
  "To watch" on the board with the official pages to check.
- `grnbl/channels.py`: the groups and which events each may carry.
- `grnbl/schedule.py`: preparation day, sending slots, reminder delay, fuel and alert hours.
- `grnbl/editorial.py`: the booking-window thresholds.

Not versioned (`data/`):

- `data/whatsapp.json`: group ids, `{"gratuit": "...@g.us", ...}` (keys: gratuit, sorties, carburant,
  famille, bonsplans, nature, infos).
- `data/whatsapp-auth/`: the WhatsApp linked-device session.
- `data/notify.json`: `{"discord": "<webhook URL>", "board": "<board URL>"}`. Without a webhook, nothing is
  pinged.
- `data/board-key`: the board's key. Opening `/?key=...` sets an HttpOnly cookie; every other request gets a
  403.
- `data/decisions/`, `data/outbox/`, `data/posted.json`, `data/schedule-state.json`, caches and logs.

Environment: `GRNBL_HOST` and `PORT` for the board (default `127.0.0.1:8730`), `CLAUDE_CODE_OAUTH_TOKEN` on a
server (from `claude setup-token`).

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

58 tests, all passing (booking windows, group rules, schedule, outbox, parsing, sources, board choices). They
run offline in under a second.

## Hosting

During the hackathon, everything runs on my Mac, which is on from 9:00 to 21:00:

- `deploy/dev.byelior.grnbl.plist`: launchd job running `deploy/tick.sh` every hour on the hour. Journal in
  `data/logs/<day>.log`.
- `deploy/dev.byelior.grnbl.board.plist`: the board, kept alive by launchd, published through a Cloudflare
  tunnel and protected by its key.
- Publishing goes through `whatsapp/send.mjs` (Node, [Baileys](https://github.com/WhiskeySockets/Baileys)
  7.0.0-rc14): it connects as a linked device, sends one message and disconnects. No server stays up for
  WhatsApp.

The same folder runs in a container: `Dockerfile` plus `deploy/serve.sh` (board kept alive, `tick.sh` every
hour, Paris time), with `data/` on a persistent volume. `deploy/make-seed.sh` packs the Mac's data for a first
start.

## Limits

- **Unofficial WhatsApp client.** Baileys is not Meta's API and goes against WhatsApp's terms; the number can be
  banned. It sends to groups of a normal WhatsApp account on a dedicated landline number.
- **The Mac is the server.** If it is off at 10:00 on Tuesday or at a sending slot, that work waits for the next
  hourly pass.
- **Scraping.** Most agendas have no API; a site redesign breaks its extraction until the source line is
  adjusted. Le Petit Bulletin's Grenoble agenda and Chamrousse's (JavaScript only) are not read.
- **The AI can embellish a line.** The fact-check and the human read are there for that; one real error in the
  18 October audit (a wrong weekday) led to the weekday check.
- **French only** for the posts. Fuel and alerts are not translated.
- **Grenoble only.** The source list is local.

## What's next

- A page per event on a short link, with a "Book" button to the source and click counts.
- Moving to the official WhatsApp Business Cloud API.
- An English group for international students, and an SMS version.
- Other cities: fuel prices, Météo-France, Brocabrac and vide-greniers.org (by département), Apidae tourist
  offices and The Events Calendar sites exist across France; a new city is a new source list.
- Hosting on a small server so it runs with the Mac off.

## AI use

Built with Claude Code as a pair programmer. The product itself uses Claude Haiku and Claude Sonnet through
the `claude` CLI, as described above. Declared as required by the hackathon rules.
