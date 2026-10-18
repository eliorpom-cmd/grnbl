#!/bin/bash
# Deploy to Deployxa from a clean archive. `deployxa deploy .` would tar the whole
# folder, data/ included (raw pages, WhatsApp session); this sends the committed
# code only, plus deploy/seed/data.tgz when called with --seed (first start).
#   deploy/push.sh            code only
#   deploy/push.sh --seed     code + the Mac's data for an empty volume
set -eu
cd "$(dirname "$0")/.."
work=$(mktemp -d)
git archive --format=tar HEAD | tar -x -C "$work"
if [ "${1:-}" = "--seed" ]; then
  [ -f deploy/seed/data.tgz ] || { echo "run deploy/make-seed.sh first"; exit 1; }
  mkdir -p "$work/deploy/seed" && cp deploy/seed/data.tgz "$work/deploy/seed/"
fi
archive="$work.tgz"
tar -czf "$archive" -C "$work" .
du -h "$archive"
npx -y @deployxa/cli@1.0.4 deploy "$archive"
