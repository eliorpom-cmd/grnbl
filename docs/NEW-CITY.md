# Opening grnbl in a new city

grnbl was built for Grenoble, but most of what it reads is national. This guide lists what a new city
needs, from the parts that work as they are to the parts that are written for Grenoble today.

Who it takes: one person who knows the city and can run Python, and one local reviewer who reads the
week's posts on the board (a few minutes per group) and pastes them into WhatsApp (about a minute per
group). The two can be the same person.

## 1. What works for any French city

| Part | Source | What to change |
| --- | --- | --- |
| ⛽ Fuel | Government price feed, every station in France (`grnbl/sources/fuel.py`) | `METRO_EPCI`: the SIREN number of the new intercommunality |
| Station names | OpenStreetMap (`grnbl/sources/stations.py`) | `BBOX`: the area's south, west, north, east |
| 🚨 Weather warnings | Météo-France, every département (`grnbl/sources/alerts.py`) | The département number |
| Flea markets | Brocabrac, Vide-Greniers.org, organised by département (`grnbl/scrape/sources.py`) | The département in their URLs |
| Big platforms | Allevents, Eventbrite, Meetup, read through schema.org data, no AI | The city in their URLs |
| Venues on WordPress | The Events Calendar REST API (`kind: "tribe"`) | One line per venue that uses it |
| Yearly events | National days (heritage, architecture, museums night) in `grnbl/calendar.json` | Remove the Grenoble-only ones, add local ones |

## 2. What is written for Grenoble today

| Part | Where | What to do |
| --- | --- | --- |
| Agendas, venues, local press | `grnbl/scrape/sources.py`, `grnbl/scrape/press.py` | Write the new city's list. Plain pages use `kind: "ai"`: one line each, no parser to write |
| Tourist office | `grnbl/scrape/tourisme.py` reads grenoble-tourisme.com | Many tourist offices publish on the same Apidae database, but their sites differ: adapt the list and page parsing, or start with `kind: "ai"` |
| Air quality | `AIR_PAGE` in `grnbl/sources/alerts.py` (Atmo Auvergne-Rhône-Alpes) | Each region has its own Atmo body: find the town's public page |
| Transit disruptions | `TRANSIT` in `grnbl/sources/alerts.py` (Mobilités M, Grenoble) | The local network's open data, if it has some; otherwise leave it out |
| AI prompts | `grnbl/scrape/review.py`, `grnbl/editor.py` | Replace "Grenoble" and the "~30 km from Grenoble" rule |
| Post and page texts | `grnbl/digest.py`, `grnbl/site.py` | The city name in headings and footers |

## 3. Before the first edition

1. Check each new source politely: `robots.txt` allows the page, and the fetcher (`grnbl/scrape/fetch.py`)
   reads one page a second per site and says who it is.
2. Run one edition without sending anything: `python3 -m grnbl.daily`, then open the board
   (`python3 -m grnbl.admin`) and read every group. Fix the sources that return nothing or nonsense.
3. Create the WhatsApp community and its groups, and write their invite links in the README of the city.
4. Run `python3 -m unittest discover -s tests -t .`: the group rules and booking windows do not depend on
   the city.

## 4. What it costs

The 21 October 2026 edition for Grenoble (41 sources, 1,092 events) used about 0.86 M input tokens and
0.32 M output tokens, and under an hour of a computer once a week. A city with fewer sources costs less.
Cached pages and verdicts are never sent to the AI twice.

## 5. Making it known

The demand is there: the Grenoble-Alpes Métropole WhatsApp channel has about 1,900 followers, and it only
relays the Métropole's own news. The quickest way to reach people is through those who already speak to
them: local media, creators and associations that share the community link. grnbl does not advertise and
collects nothing about its members.
