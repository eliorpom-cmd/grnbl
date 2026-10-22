// Renders a slide frame by frame to MP4: node render.mjs <slide.html> <out.mp4> <seconds> [--still t]
import { chromium } from '../render/node_modules/playwright/index.mjs';
import { spawn } from 'node:child_process';
import path from 'node:path';
const [file, out, dur] = process.argv.slice(2), si = process.argv.indexOf('--still');
const FPS = process.env.FPS || '30', fps = eval(FPS);
const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await p.goto('file://' + path.resolve(file)); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(400);
if (si > 0) { await p.evaluate(t => frame(t), +process.argv[si + 1]); await p.screenshot({ path: out }); await b.close(); process.exit(0); }
const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', FPS, '-i', '-', '-c:v', 'libx264', '-profile:v', 'high', '-level', '4.1', '-pix_fmt', 'yuv420p', '-crf', '14', '-preset', 'slow', '-movflags', '+faststart', out]);
for (let i = 0, n = Math.round(+dur * fps); i < n; i++) { await p.evaluate(t => frame(t), i / fps); ff.stdin.write(await p.screenshot({ type: 'png' })); }
ff.stdin.end(); await new Promise(r => ff.on('close', r)); await b.close();
