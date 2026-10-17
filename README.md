# grnbl

**The person in your family who always knows what's on, for a whole city, inside WhatsApp.**

In my family, my mother is the one who finds the free concerts, the museum workshops, the cheapest petrol
station. Without someone like her, most people around me in Grenoble never hear about any of it, even though
all of it is public. grnbl collects that public data every day and posts it, in plain French, to WhatsApp
groups people join by topic. Nothing to install.

Built for [Neighborhood Hacks 2026](https://neighborhoodhacks.org/).

## What works today

```bash
python3 -m grnbl.daily    # the morning run: collect, check booking, review, compose the posts
python3 -m grnbl.admin    # the editor's board: http://127.0.0.1:8730
python3 -m grnbl fuel     # the fuel post alone
python3 -m grnbl.publish  # the outbox: what is approved and ready (add --send to send)
python3 -m unittest discover -s tests -t .
```

Publishing goes through `whatsapp/send.mjs` (Node, [Baileys](https://github.com/WhiskeySockets/Baileys), an
unofficial WhatsApp Web client): it connects as a linked device, sends one message and disconnects, so no
server has to stay up. `deploy/morning.sh` is the daily run for any scheduler (launchd on a Mac, cron on Linux).

Python 3.11+, standard library only. The AI steps call Claude through the `claude` CLI.

Three channels: 🆓 free outings, 🎭 outings (paid ones included), ⛽ cheapest fuel.

| Data | Source |
| --- | --- |
| Fuel prices | French Ministry of the Economy real-time feed; station brands from OpenStreetMap |
| Outings | The whole Grenoble tourist office database, ~30 city, venue and town agendas, five local papers, each event's own page, and a hand-kept calendar of yearly events |

## How it is built

```
sources -> events (one shape) -> booking timing (code) -> AI review -> AI editor-in-chief -> human check -> WhatsApp
```

- **Timing is code, not AI.** An event that needs booking is announced while people can still book, or on
  the day booking opens; a walk-in event at least the day before.
- **The AI judges interest**, the code keeps the guarantees: a paid event can never reach the free channel.
- **The editor-in-chief** picks a varied post from the best candidates, zooms into one precise moment of a
  festival's programme, and keeps reserves so a pick the human removes is replaced at once.
- **The human reads about eleven lines per channel**, not hundreds of events, and their choices teach the editor.

## AI use

Built with Claude Code as a pair programmer. Declared as required by the hackathon rules.
