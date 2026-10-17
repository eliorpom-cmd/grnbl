# grnbl

**The person in your family who always knows what's on, for a whole city, inside WhatsApp.**

In my family, my mother is the one who finds the free concerts, the museum workshops, the cheapest petrol
station. Without someone like her, most people around me in Grenoble never hear about any of it, even though
all of it is public. grnbl collects that public data every day and posts it, in plain French, to WhatsApp
groups people join by topic. Nothing to install.

Built for [Neighborhood Hacks 2026](https://neighborhoodhacks.org/).

## What works today

```bash
python3 -m grnbl          # today's posts: cheapest fuel + this week's outings
python3 -m grnbl fuel     # one topic
python3 -m grnbl --json   # the collected items instead of the posts
python3 -m unittest discover -s tests -t .
```

Python 3.11+, standard library only.

| Topic | Source | Key needed |
| --- | --- | --- |
| ⛽ Cheapest fuel | French Ministry of the Economy real-time fuel price feed, 49 communes of Grenoble-Alpes Métropole | no |
| 🎭 Outings | Isère département museums agenda (Apidae export, opendata.isere.fr) | no |

## How it is built

```
sources/  one collector per source  ->  Item (one common shape)  ->  digest.py writes the post  ->  WhatsApp
```

Each collector turns its source into `Item`s (`grnbl/items.py`). Everything after that never knows where an
item came from, so another city is a list of sources, not a rewrite.

## AI use

Built with Claude Code as a pair programmer. Declared as required by the hackathon rules.
