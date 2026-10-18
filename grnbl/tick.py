"""The hourly run: `python3 -m grnbl.tick`, every hour by the scheduler (deploy/tick.sh).

Each hour it does what is due, and only once (data/schedule-state.json):
- fuel: sent from 10:00, every day, on its own;
- alerts: checked from 7:00 to 22:00; a new one is pinged on Discord and waits
  for the human, who sends it from the board. Nothing is sent from here;
- the edition: prepared on Tuesday from 10:00 (collect, review, editor), then
  pinged so it is read in one sitting;
- each group's posts: a reminder two hours before their slot if not approved,
  then at the slot the approved ones go out and the others are reported.
"""

from __future__ import annotations

import sys
import traceback
from datetime import date, datetime, timedelta

from . import notify, publish, schedule
from .channels import CHANNELS
from .digest import alerts_post
from .sources import alerts

PARIS = publish.PARIS
MAX_PREPARE_TRIES = 3


def _signature(a: dict, today: date) -> str:
    if a["kind"] == "weather":
        return f"weather|{a['what']}|{a['level']}|{today}"
    if a["kind"] == "air":
        return f"air|{a['day']}|{a['level']}"
    return f"transit|{a.get('code') or a['title']}"


def fuel(now: datetime) -> None:
    today = now.date()
    if now.time() < schedule.FUEL_AT:
        return
    if publish.status(today).get("carburant", {}).get("fuel", {}).get("status") == "sent":
        return
    for name, what in publish.run(today, send=True, only=["carburant"]):
        print(f"fuel: {name} {what}")


def check_alerts(now: datetime) -> None:
    if now.hour not in schedule.ALERT_HOURS:
        return
    found, failed = alerts.collect(now)
    if failed:
        print(f"alerts: could not read {', '.join(failed)}")
    seen = schedule.state().get("alerts-seen", {})
    new = [a for a in found if _signature(a, now.date()) not in seen]
    print(f"alerts: {len(found)} serious, {len(new)} new")
    if not new:
        return
    notify.ping(notify.alert(alerts_post(found, now)))
    keep_from = (now.date() - timedelta(days=14)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= keep_from}
    seen.update({_signature(a, now.date()): now.date().isoformat() for a in new})
    schedule.remember("alerts-seen", seen)


def prepare(now: datetime) -> None:
    today = now.date()
    if today.weekday() != schedule.PREPARE["weekday"] or now.time() < schedule.PREPARE["at"]:
        return
    edition = schedule.edition_for(today)
    key, tries_key = f"prepared-{edition}", f"prepare-tries-{edition}"
    s = schedule.state()
    if s.get(key) or s.get(tries_key, 0) >= MAX_PREPARE_TRIES:
        return
    schedule.remember(tries_key, s.get(tries_key, 0) + 1)
    print(f"prepare: edition {edition}")
    from . import daily  # heavy imports only when an edition is due
    try:
        daily.prepare(edition)
    except Exception as e:  # noqa: BLE001 - reported on Discord, tried again next hour
        traceback.print_exc()
        notify.ping(notify.failure(type(e).__name__, now))
        return
    schedule.remember(key)
    notify.ping(notify.summary(now, edition))


def this_week_edition(today: date) -> date | None:
    """The edition prepared on the last preparation day, if it was."""
    last = today - timedelta(days=(today.weekday() - schedule.PREPARE["weekday"]) % 7)
    edition = schedule.edition_for(last)
    return edition if edition in schedule.editions() else None


def send_slots(now: datetime) -> None:
    edition = this_week_edition(now.date())
    if not edition:
        return
    naive = now.replace(tzinfo=None)
    for slot in schedule.SLOTS:
        at = schedule.send_time(edition, slot)
        if at.date() != now.date():
            continue
        items = [i for i in publish.outbox(edition, now, fuel_text="", alerts_text="") if i["channel"] in slot["channels"]]
        sent = publish.status(edition)
        pending = [i for i in items if sent.get(i["channel"], {}).get(i["post"], {}).get("status") != "sent"]
        unapproved = sorted({CHANNELS[i["channel"]]["label"] for i in pending if not i["approved"]})
        done_key, remind_key = f"sent-{edition}-{slot['id']}", f"reminded-{edition}-{slot['id']}"
        state = schedule.state()
        if at - schedule.REMIND_BEFORE <= naive < at and unapproved and not state.get(remind_key):
            notify.ping(notify.reminder(edition, unapproved, at))
            schedule.remember(remind_key)
        if naive >= at and not state.get(done_key):
            report = publish.run(edition, send=True, only=slot["channels"])
            for name, what in report:
                print(f"slot {slot['id']}: {name} {what}")
            out = sorted({CHANNELS[n.split('-')[0]]["label"] for n, w in report if w == "envoyé"})
            if out:
                notify.ping(f"✅ *grnbl* · envoyé : {', '.join(out)}")
            if unapproved:
                notify.ping(notify.not_sent(unapproved, at))
            schedule.remember(done_key)


def main() -> int:
    now = datetime.now(PARIS)
    print(f"== {now:%F %T} tick")
    # One step failing never stops the next ones.
    for step in (fuel, check_alerts, send_slots, prepare):
        try:
            step(now)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main())
