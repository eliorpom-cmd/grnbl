#!/bin/bash
# The hourly run, for any scheduler: launchd on the Mac now (deploy/dev.byelior.grnbl.plist),
# cron on a Linux server later:  0 * * * *  /path/to/grnbl/deploy/tick.sh
# grnbl/tick.py decides what is due this hour (fuel, alerts, the weekly edition,
# each group's slot) and does each thing once. Journal: data/logs/<day>.log.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p data/logs
python3 -m grnbl.tick >> "data/logs/$(date +%F).log" 2>&1
exit 0
