# grnbl — notes for AI coding sessions

grnbl collects what's on in Grenoble (outings, free events, flea markets, fuel prices, serious alerts)
and posts it, in plain French, to WhatsApp groups people join by topic. Built for Neighborhood Hacks 2026.
Private working notes (deployment, account details, schedule) live in `CLAUDE.local.md`, which is not
published.

## Conventions
- Python 3.11+, standard library only (Node only for the Claude Code CLI and the brand renderers).
- Posting to WhatsApp is by hand from the board: no automatic sender (an unofficial client breaks WhatsApp's terms).
- Code, comments, README and commits in English; the posts themselves are in French.
- Timing and guarantees are code, never AI: booking deadlines (`editorial.py`), which channel an event
  belongs to (`channels.home`: exactly one group per event, bargains > kids > nature > free > paid; checked
  again when the outbox and the board's preview are built, `publish.in_their_group`).
- AI calls go through `claude -p` (`grnbl/scrape/extract.py`, `ask`), bare (no tools or settings), with
  caches so nothing already read or judged is sent again. Every call is logged in `data/usage.jsonl`.
- `data/` is never committed (raw pages, events, decisions, WhatsApp session, board key, webhook).
  Secrets and group ids are read from `data/` at run time, never written in code.

## Pipeline
sources (`grnbl/scrape/`, `grnbl/sources/`) -> one event shape -> repeated sessions merged (`run.collapse`)
-> booking status (`editorial.py`) -> AI review (`scrape/review.py`) -> AI editor-in-chief per channel
(`editor.py`, with reserves and a fact check, `factcheck.py`) -> human check on the board (`admin.py`)
-> outbox, then pasted by hand into WhatsApp (`publish.py`, `mark_posted`). Weekly rhythm and slots: `schedule.py`,
driven hourly by `tick.py` (`deploy/tick.sh`).

## Commands
- `python3 -m grnbl.daily [YYYY-MM-DD]`: prepare an edition. `python3 -m grnbl.tick`: one hourly pass.
- `python3 -m grnbl.admin`: the board on http://127.0.0.1:8730. `python3 -m grnbl.demo [YYYY-MM-DD]`: a read-only
  static copy of the board for one edition, in `data/demo/` (no key, nothing saved or sent).
- `python3 -m grnbl.publish [channel…] [--send]`: outbox (dry run by default).
- `python3 -m grnbl fuel`: the fuel post. `python3 -m grnbl.translate [YYYY-MM-DD]`: English translations.
- Tests: `python3 -m unittest discover -s tests -t .`

## Pitfalls
- macOS has no `timeout`; run long commands in the background with a log.
- Python 3.13+ rejects some French government certificates (VERIFY_X509_STRICT): `http.py` drops that
  one flag, verification stays on.
- The AI can embellish a line: the human check on the board is there for that, and `factcheck.py`
  flags names, numbers and weekdays absent from the source page.
- In `digest.py`, compare at midnight with `second=0, microsecond=0`, or same-day events without a time
  disappear.
