// Transparent PNG of a slide (for overlays): node shot-alpha.mjs <page.html> <out.png>
import { chromium } from '../render/node_modules/playwright/index.mjs';
import path from 'node:path';
const [file, out] = process.argv.slice(2);
const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await p.goto('file://' + path.resolve(file)); await p.waitForTimeout(300);
await p.screenshot({ path: out, omitBackground: true }); await b.close();
