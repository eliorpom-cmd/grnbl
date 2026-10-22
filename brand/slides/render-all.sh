#!/bin/bash
# Renders every slide of the demo video to MP4 (1920 x 1080, 30 fps). Usage: ./render-all.sh <out dir>
set -e
cd "$(dirname "$0")"; OUT="${1:-export}"; mkdir -p "$OUT"
r() { node render.mjs "$1" "$OUT/$2.mp4" "$3"; echo "ok $2"; }
r title.html 1-title 5
r sources.html 2-sources 9
r beforeafter.html 4-before-after 10
r numbers.html 5a-numbers 9.5
r rules.html 5b-rules 8
r "title.html?end=1" 6-end 6
