// Records each clip frame by frame (seek(t) then a screenshot) and encodes it with ffmpeg:
// exact timing whatever the machine's speed. Uses the Playwright installed in ../render.
//   node record.mjs                     every clip, both fonts -> export/<clip>-<font>.mp4
//   node record.mjs pipeline --font host
//   node record.mjs pipeline --still 9  one PNG at 9 s -> export/<clip>-<font>-9s.png (to check a frame)
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("../render/node_modules/playwright");
const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "export");
const CLIPS = ["pipeline", "numbers", "before-after", "guarantees"];
const FONTS = ["host", "familjen"];
const FPS = 30;

const args = process.argv.slice(2);
const opt = name => { const i = args.indexOf(name); return i >= 0 ? args.splice(i, 2)[1] : null; };
const font1 = opt("--font");
const fonts = font1 ? [font1] : FONTS;
const still = opt("--still");
const clips = args.length ? args : CLIPS;
const ffmpeg = process.env.FFMPEG || "ffmpeg";

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
for (const clip of clips) {
  for (const font of fonts) {
    await page.goto(pathToFileURL(join(HERE, `${clip}.html`)).href + `?record&font=${font}`);
    await page.evaluate(() => window.ready);
    const duration = await page.evaluate(() => DURATION);
    if (still !== null) {
      await page.evaluate(t => window.seek(t), Number(still));
      await page.screenshot({ path: join(OUT, `${clip}-${font}-${still}s.png`) });
      console.log(`${clip}-${font}-${still}s.png`);
      continue;
    }
    const file = join(OUT, `${clip}-${font}.mp4`);
    const enc = spawn(ffmpeg, ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow", "-movflags", "+faststart", file],
      { stdio: ["pipe", "inherit", "inherit"] });
    const done = new Promise((ok, ko) => enc.on("close", c => (c ? ko(new Error("ffmpeg " + c)) : ok())));
    const frames = Math.round(duration * FPS);
    for (let i = 0; i <= frames; i++) {
      await page.evaluate(t => window.seek(t), i / FPS);
      const png = await page.screenshot({ type: "png" });
      if (!enc.stdin.write(png)) await new Promise(r => enc.stdin.once("drain", r));
    }
    enc.stdin.end();
    await done;
    console.log(`${clip}-${font}.mp4  ${duration} s`);
  }
}
await browser.close();
