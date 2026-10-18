#!/bin/bash
# Pack the Mac's data/ for the server's first start (deploy/seed/data.tgz, git-ignored).
# Keeps what cannot be rebuilt (WhatsApp session, group ids, board key, posted memory,
# decisions, outbox) and the AI caches (they save tokens); leaves out raw pages and logs.
# Run it right before the switch: the WhatsApp session must be the latest one.
set -eu
cd "$(dirname "$0")/.."
mkdir -p deploy/seed
tar -czf deploy/seed/data.tgz -C data \
  --exclude ./raw --exclude ./logs --exclude ./secrets \
  --exclude ./whatsapp-qr.html --exclude ./.seeded .
du -h deploy/seed/data.tgz
