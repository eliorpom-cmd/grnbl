#!/bin/bash
# Container entrypoint: what launchd does on the Mac, in one process.
# - first start on an empty volume: unpack deploy/seed/data.tgz (made by make-seed.sh)
# - the board, restarted if it ever stops
# - morning.sh at 10:00 and 14:00 Paris time (it runs at most once a day by itself)
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p data/logs

if [ ! -e data/.seeded ] && [ -f deploy/seed/data.tgz ]; then
  tar -xzf deploy/seed/data.tgz -C data && date '+%F %T' > data/.seeded
  echo "seed unpacked into data/"
fi

# claude -p signs in with this variable (set as a secret on the host, from `claude setup-token`)
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] || echo "warning: CLAUDE_CODE_OAUTH_TOKEN is not set, the AI steps will fail"

(
  while true; do
    python3 -m grnbl.admin >> data/logs/board.log 2>&1
    echo "$(date '+%F %T') board stopped, restarting" >> data/logs/board.log
    sleep 5
  done
) &

while true; do
  case "$(date +%H:%M)" in
    10:00|14:00) bash deploy/morning.sh & ;;
  esac
  sleep $((60 - 10#$(date +%S)))
done
