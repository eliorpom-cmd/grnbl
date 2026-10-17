#!/bin/bash
# The daily run, for any scheduler: launchd on the Mac now (deploy/dev.byelior.grnbl.plist),
# cron on a Linux server later:  0 10 * * *  /path/to/grnbl/deploy/morning.sh
# Fuel goes out first and on its own (no review, no AI); the outings are prepared
# for the board, where they are sent once approved. Runs once a day at most.
set -u
cd "$(dirname "$0")/.." || exit 1
day=$(date +%F)
mkdir -p data/logs data/runs
marker="data/runs/$day.done"
[ -e "$marker" ] && exit 0
log="data/logs/$day.log"
{
  echo "== $(date '+%F %T') morning run"
  python3 -m grnbl.publish carburant --send
  python3 -m grnbl.daily
  status=$?
  echo "== $(date '+%F %T') done, exit $status"
} >> "$log" 2>&1
[ "${status:-1}" -eq 0 ] && touch "$marker"
exit 0
