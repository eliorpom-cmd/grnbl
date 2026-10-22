# Animated clips for the demo video

Four silent 1920×1080 clips, 30 fps, in the brand colours, for what a camera can't show.
Each exists in both announcement fonts (`-host`, `-familjen`): use the one of the chosen font.

| Clip | Length | Shows |
| --- | --- | --- |
| `pipeline` | 19 s | 38 named sources → 1,203 events → booking timing → 448 kept → ≈11 lines per group → 7 posts, with who does each step (code, Claude, human) |
| `numbers` | 9 s | The four numbers of the full run (sources, events, kept, minutes) counting up |
| `before-after` | 12 s | An agenda listing ("1 January to 6 December") becomes the post line with a precise day and a booking deadline |
| `guarantees` | 12.5 s | Code / Claude / human columns, then a paid event refused by the Free group and dropped into Sorties |

- Numbers and texts: `content.js`. **The before/after event is an example**: replace it with a real event
  of the 21 October edition (its agenda page and its line from the board), then re-render.
- Open any `.html` in a browser to watch it loop (`?font=familjen` for the other font).
- Re-render: `node record.mjs` (all), `node record.mjs pipeline --font host`, or one frame to check:
  `node record.mjs pipeline --still 9`. Needs `cd ../render && npm install` once and ffmpeg.
  Frames are captured one by one (`seek(t)`), so timing is exact on any machine.
