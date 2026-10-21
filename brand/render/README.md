# Rendering the grnbl visuals

Everything in `brand/export/` is drawn from HTML/SVG by `render.mjs` (Playwright + Chromium).

```bash
cd brand/render
npm install            # once: Playwright (a global install works too)
npx playwright install chromium   # once, if Chromium is not there yet
node render.mjs                   # everything
node render.mjs posts devpost     # only some families: whatsapp, posts, devpost, video
```

- Texts (posts, video parts, lower thirds, tagline) live in `content.mjs`. The posts are **examples**:
  paste the real ones from the board (Copy button) into `POSTS`, keeping the WhatsApp `*bold*` / `_italic_`.
- Drawing (logo 3 and icon B of `brand/logo-7.html`, group cabins, WhatsApp chat) is in `lib.js`.
- Fonts come from `brand/fonts/` (OFL), icons from `brand/icons/` (Lucide, ISC). The render fails if a font
  did not load. Intermediate pages go to `render/build/` (ignored by git).
