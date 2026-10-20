// Renders every grnbl visual to PNG with Playwright + Chromium.
//   cd brand/render && npm install && node render.mjs            # everything
//   node render.mjs whatsapp posts                              # only some families
// Families: whatsapp, posts, devpost, video. Output: brand/export/<family>/.
import { createRequire } from "module";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";
import * as K from "./content.mjs";

const require = createRequire(import.meta.url);
function loadPlaywright() {
  const tries = ["playwright", "@playwright/test"];
  for (const t of tries) { try { return require(t); } catch {} }
  const root = execSync("npm root -g").toString().trim();
  for (const t of tries) { try { return require(path.join(root, t)); } catch {} }
  throw new Error("Playwright not found: run `npm install` in brand/render");
}
const { chromium } = loadPlaywright();

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BRAND = path.resolve(HERE, "..");
const EXPORT = path.join(BRAND, "export");
const BUILD = path.join(HERE, "build");
const FONTS = pathToFileURL(path.join(BRAND, "fonts")).href;
const ICONS = Object.fromEntries(fs.readdirSync(path.join(BRAND, "icons")).filter(f => f.endsWith(".svg")).map(f => {
  const svg = fs.readFileSync(path.join(BRAND, "icons", f), "utf8");
  return [f.replace(".svg", ""), svg.replace(/^[\s\S]*?<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "").trim()];
}));
const LIB = fs.readFileSync(path.join(HERE, "lib.js"), "utf8");

// ---------- Shared CSS ----------
const BASE = `
@font-face { font-family: 'Bagel Fat One'; src: url(${FONTS}/BagelFatOne-Regular.ttf); }
@font-face { font-family: 'Familjen Grotesk'; src: url(${FONTS}/FamiljenGrotesk.ttf); font-weight: 400 700; }
@font-face { font-family: 'Host Grotesk'; src: url(${FONTS}/HostGrotesk.ttf); font-weight: 300 800; }
@font-face { font-family: 'Inter'; src: url(${FONTS}/Inter.ttf); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 100%; height: 100%; }
body { background: #2F4BFF; color: #F4F4F6; font-family: var(--f, 'Inter'), 'Noto Color Emoji', sans-serif; -webkit-font-smoothing: antialiased; overflow: hidden; }
.transparent body, body.transparent { background: transparent; }
svg { overflow: visible; }
/* WhatsApp, iOS light look */
.wa { display: flex; flex-direction: column; height: 100%; background: #efeae2; color: #111b21; font: 14.5px/1.38 'Inter', 'Noto Color Emoji', sans-serif; letter-spacing: -.005em; }
.wa-head { display: flex; align-items: center; gap: 10px; padding: 46px 12px 9px 6px; background: #f6f5f4; border-bottom: 1px solid rgba(0,0,0,.08); flex: none; }
.wa-back { font-size: 36px; line-height: 1; color: #007aff; margin-top: -5px; width: 18px; font-weight: 300; }
.wa-t { min-width: 0; }
.wa-t b { display: block; font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wa-t small { display: block; color: #667781; font-size: 12.5px; }
.wa-body { flex: 1; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-end; padding: 8px 10px 10px; }
.wa-day { display: table; margin: 4px auto 10px; background: #fff; color: #54656f; font-size: 12px; font-weight: 500; padding: 4px 10px; border-radius: 8px; box-shadow: 0 1px .5px rgba(11,20,26,.13); }
.wa-msg { background: #fff; border-radius: 10px; border-top-left-radius: 3px; padding: 5px 9px 6px; max-width: 96%; width: fit-content; box-shadow: 0 1px .5px rgba(11,20,26,.13); margin-bottom: 8px; }
.wa-from { display: block; color: #1b8f68; font-size: 13px; font-weight: 600; margin-bottom: 1px; }
.wa-txt { white-space: pre-wrap; overflow-wrap: anywhere; }
.wa-time { display: block; text-align: right; font-size: 11px; color: #667781; margin-top: -3px; }
.wa-foot { flex: none; background: #f6f5f4; border-top: 1px solid rgba(0,0,0,.08); text-align: center; color: #667781; font-size: 13px; padding: 11px 16px 30px; }
.phone { width: 360px; height: 760px; border-radius: 54px; background: #121212; padding: 11px; box-shadow: 0 30px 80px rgba(8,14,60,.35); }
.phone .screen { width: 100%; height: 100%; border-radius: 44px; overflow: hidden; }
/* Community screen */
.cm { display: flex; flex-direction: column; height: 100%; background: #f6f5f4; color: #111b21; font: 15px/1.35 'Inter', 'Noto Color Emoji', sans-serif; }
.cm-top { padding: 52px 16px 18px; text-align: center; background: #fff8; }
.cm-top .av { margin: 0 auto 10px; }
.cm-top b { display: block; font-size: 22px; font-weight: 700; letter-spacing: -.01em; }
.cm-top small { color: #667781; font-size: 13px; }
.cm-list { background: #fbfbfb; flex: 1; }
.cm-row { display: flex; gap: 12px; align-items: center; padding: 10px 14px; }
.cm-row + .cm-row .cm-txt { border-top: 1px solid rgba(0,0,0,.07); }
.cm-txt { flex: 1; min-width: 0; padding-top: 2px; }
.cm-row .cm-l1 { display: flex; justify-content: space-between; gap: 8px; }
.cm-row b { font-weight: 600; font-size: 15.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cm-row time { color: #667781; font-size: 12.5px; flex: none; }
.cm-row p { color: #667781; font-size: 13.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cm-sec { padding: 14px 14px 4px; color: #667781; font-size: 13px; font-weight: 600; }
`;

// ---------- Page builder ----------
function doc({ css = "", body = "", script = "", font = "Inter", transparent = false }) {
  return `<!doctype html><html${transparent ? ' class="transparent"' : ""}><head><meta charset="utf-8"><style>${BASE}
:root { --f: '${font}'; } ${css}</style></head>
<body${transparent ? ' class="transparent"' : ""}>${body}
<script>window.ICONS = ${JSON.stringify(ICONS)}; window.GROUPS = ${JSON.stringify(K.GROUPS)}; window.POSTS = ${JSON.stringify(K.POSTS)};
${LIB}
const FAMILIES = ["Bagel Fat One", "Inter", "${font}"];
Promise.all(FAMILIES.map(f => document.fonts.load("700 40px '" + f + "'", "grnbl Aé€"))).then(() => document.fonts.ready).then(() => {
  ${script}
  window.__fonts = FAMILIES.map(f => [f, document.fonts.check("700 40px '" + f + "'", "grnbl")]);
  window.__ready = true;
});
</script></body></html>`;
}

const jobs = [];
const job = (family, name, w, h, page, { scale = family === "devpost" ? 2 : 1, transparent = false } = {}) =>
  jobs.push({ family, name, w, h, scale, transparent, html: doc({ ...page, transparent }) });

// Strip WhatsApp formatting for a one-line preview.
const preview = t => t.split("\n")[0].replace(/[*_]/g, "");

// ---------- WhatsApp photos ----------
for (const g of K.GROUPS) {
  job("whatsapp", g.file, 640, 640, { script: `avatar(document.body, ${JSON.stringify(g.id)}, 640, "0");` });
}

// ---------- Posts in a WhatsApp frame (1080 x 2340, phone ratio) ----------
const chatScript = (p) => `chat(document.getElementById("s"), ${JSON.stringify({
  group: p.group, title: K.GROUPS.find(g => g.id === p.group).name.replace("Annonces", "grnbl · Annonces"),
  sub: "Communauté grnbl", day: p.day, time: p.time, posts: [p.text] })});`;
for (const p of K.POSTS) {
  job("posts", p.file, 360, 780, { body: `<div id="s" style="width:360px;height:780px"></div>`, script: chatScript(p) }, { scale: 3 });
}
const communityRows = K.GROUPS.filter(g => g.id !== "community").map(g => {
  const post = K.POSTS.find(p => p.group === g.id);
  return { id: g.id, name: g.name.replace("grnbl · ", ""), time: g.id === "infos" ? "hier" : post ? post.time : "", line: post ? preview(post.text) : "" };
});
const communityBody = `<div class="cm"><div class="cm-top"><span id="cav"></span><b>grnbl</b><small>Communauté · ${communityRows.length} groupes</small></div>
  <div class="cm-list">${communityRows.map((r, i) => `${i === 1 ? '<div class="cm-sec">Groupes dont tu es membre</div>' : ""}<div class="cm-row"><span data-av="${r.id}"></span><div class="cm-txt"><div class="cm-l1"><b>${r.name}</b><time>${r.time}</time></div><p>${r.line.replace(/</g, "&lt;")}</p></div></div>`).join("")}</div></div>`;
const communityScript = `avatar(document.getElementById("cav"), "community", 84, "22px");
  document.querySelectorAll("[data-av]").forEach(n => avatar(n, n.dataset.av, 50));`;
job("posts", "communaute-liste", 360, 780, { body: `<div style="width:360px;height:780px">${communityBody}</div>`, script: communityScript }, { scale: 3 });

// ---------- Devpost (1200 x 800, exported at 2x) and video, once per announcement font ----------
const phone = (id, inner = "") => `<div class="phone"><div class="screen" id="${id}">${inner}</div></div>`;
const chatInto = (id, p) => chatScript(p).replace('"s"', `"${id}"`);
const post = f => K.POSTS.find(p => p.file === f);

const DEV = `
.k { color: #C6FF3D; font-size: 22px; font-weight: 600; letter-spacing: -.005em; }
h1 { font-weight: 700; letter-spacing: -.035em; line-height: 1.02; }
.p { color: rgba(244,244,246,.78); font-size: 23px; line-height: 1.38; letter-spacing: -.01em; }
.meta { color: rgba(244,244,246,.62); font-size: 17px; font-weight: 500; }
`;
for (const F of K.FONTS) {
  const font = F.family, sfx = "-" + F.id;

  // Cover: logo, the pitch, a phone cut by the bottom edge.
  job("devpost", "cover" + sfx, 1200, 800, { font, css: DEV + `
    .l { position: absolute; left: 76px; top: 92px; width: 600px; }
    .logo { width: 470px; display: block; margin-left: -10px; }
    .l h1 { font-size: 46px; margin-top: 44px; }
    .meta { position: absolute; left: 76px; bottom: 70px; }
    .ph { position: absolute; left: 768px; top: 92px; }`,
    body: `<div class="l"><svg class="logo"></svg><h1>${K.PITCH}</h1></div><p class="meta">Grenoble · Neighborhood Hacks 2026</p>
      <div class="ph">${phone("c1")}</div>`,
    script: `drawLogo(document.querySelector(".logo")); ${chatInto("c1", post("gratuit-cette-semaine"))}` }, { scale: 2 });

  // 1. The problem.
  const SOURCES = ["Grenoble Alpes Tourisme", "Ville de Grenoble", "Grenoble-Alpes Métropole", "Gre.mag", "ici Grenoble", "L'Essentiel Grenoble",
    "Le Dauphiné", "Place Gre'net", "ICI Isère", "Le Petit Bulletin", "Université Grenoble Alpes", "MC2", "La Belle Électrique", "Le Summum",
    "Le Ciel", "Musée de Grenoble", "La Casemate", "Cinémathèque", "L'Hexagone Meylan", "La Rampe Échirolles", "Alpexpo", "LPO Isère"];
  job("devpost", "1-problem" + sfx, 1200, 800, { font, css: DEV + `
    .w { position: absolute; inset: 76px 76px 70px; display: flex; flex-direction: column; }
    h1 { font-size: 64px; margin: 18px 0 22px; max-width: 980px; }
    .p { max-width: 860px; }
    .chips { margin-top: auto; display: flex; flex-wrap: wrap; gap: 12px; }
    .chips span { font-size: 21px; font-weight: 500; padding: 10px 18px; border-radius: 99px; background: rgba(244,244,246,.12); color: #F4F4F6; }
    .chips span.more { background: #C6FF3D; color: #121212; font-weight: 700; }`,
    body: `<div class="w"><span class="k">The problem</span><h1>Without someone like my mum, nobody hears about it.</h1>
      <p class="p">Free concerts, museum Sundays, the cheapest fuel: it is all public, but spread over 38 sources that nobody checks every week.</p>
      <div class="chips">${SOURCES.map(s => `<span>${s}</span>`).join("")}<span class="more">+ 16 more</span></div></div>` });

  // 2. The pipeline, as a cable with five cabins.
  const STEPS = [
    ["38", "public sources", "Code collects; Claude Haiku reads pages with no structured data"],
    ["1,203", "events collected", "Code reads dates, prices and booking, and merges repeats"],
    ["448", "kept after review", "Claude Sonnet judges interest; code decides the timing"],
    ["~11", "lines per group", "A human ticks or unticks, then presses All good"],
    ["7", "WhatsApp groups", "Sent on schedule: Wednesday 12:00, Thursday 18:00"],
  ];
  job("devpost", "2-pipeline" + sfx, 1200, 800, { font, css: DEV + `
    .w { position: absolute; inset: 76px 76px 70px; }
    h1 { font-size: 56px; margin: 18px 0 0; max-width: 900px; }
    .cable { position: absolute; left: -76px; right: -76px; top: 268px; height: 120px; }
    .steps { position: absolute; left: 0; right: 0; top: 398px; display: grid; grid-template-columns: repeat(5, 1fr); gap: 22px; }
    .n { font-size: 54px; font-weight: 700; letter-spacing: -.04em; color: #C6FF3D; line-height: 1; }
    .t { font-size: 21px; font-weight: 600; margin: 8px 0 10px; }
    .d { font-size: 16px; line-height: 1.38; color: rgba(244,244,246,.75); }
    .meta { position: absolute; left: 0; bottom: 0; }`,
    body: `<div class="w"><span class="k">How it works</span><h1>From 38 sources to one short post per group.</h1>
      <svg class="cable" viewBox="0 0 1200 120" preserveAspectRatio="none"><g id="cb"></g></svg>
      <div class="steps">${STEPS.map(s => `<div><div class="n">${s[0]}</div><div class="t">${s[1]}</div><div class="d">${s[2]}</div></div>`).join("")}</div>
      <p class="meta">Full trial run on 18 October 2026: 1,203 events, 38 sources, 448 kept, 27 minutes, no errors.</p></div>`,
    script: `const g = document.getElementById("cb"); const cy = x => 46 - x * .03;
      line(g, 0, cy(0), 1200, cy(1200), 6);
      const col = (1048 - 4 * 22) / 5; [0,1,2,3,4].forEach(i => { const x = 76 + i * (col + 22) + 18; line(g, x, cy(x), x, cy(x) + 30, 5); bubble(g, x, cy(x) + 30 + 16, 16, 5); });` });

  // 3. One example post, with the board's English translation.
  job("devpost", "3-post" + sfx, 1200, 800, { font, css: DEV + `
    .ph { position: absolute; left: 76px; top: 64px; }
    .r { position: absolute; left: 520px; right: 76px; top: 92px; }
    h1 { font-size: 52px; margin: 18px 0 20px; }
    .p { font-size: 21px; }
    .en { margin-top: 30px; background: #F4F4F6; color: #121212; border-radius: 20px; padding: 18px 22px; font: 14.5px/1.42 'Inter', 'Noto Color Emoji', sans-serif; white-space: pre-wrap; }
    .en .h { display: block; font: 600 13px/1 var(--f); color: #5a5c66; margin-bottom: 10px; letter-spacing: .01em; }`,
    body: `<div class="ph">${phone("c3")}</div><div class="r"><span class="k">What is not obvious</span>
      <h1>Announced while you can still book.</h1>
      <p class="p">Agendas list a date range. grnbl posts the slot to book and the deadline, and drops what is already full. That timing is a code rule, not AI.</p>
      <div class="en"><span class="h">English translation (not posted)</span><span id="en"></span></div></div>`,
    script: `${chatInto("c3", post("gratuit-a-reserver"))} document.getElementById("en").innerHTML = wa(${JSON.stringify(K.POST_EN)});` });

  // 4. The numbers, one tile each.
  job("devpost", "4-numbers" + sfx, 1200, 800, { font, css: DEV + `
    .w { position: absolute; inset: 76px 76px 70px; display: flex; flex-direction: column; }
    h1 { font-size: 56px; margin: 18px 0 40px; }
    .tiles { flex: 1; display: grid; grid-template-columns: 1fr 1.3fr 1fr; gap: 16px; }
    .tile { border-radius: 30px; padding: 30px 30px 28px; display: flex; flex-direction: column; }
    .tile .n { font-size: 112px; font-weight: 700; letter-spacing: -.055em; line-height: .9; }
    .tile .t { font-size: 24px; font-weight: 600; line-height: 1.22; letter-spacing: -.015em; margin-top: 18px; }
    .tile .s { margin-top: auto; font-size: 16px; font-weight: 500; opacity: .7; }
    .tile .n { white-space: nowrap; font-size: 104px; } .b .n { font-size: 90px; }
    .a { background: #C6FF3D; color: #121212; } .b { background: #F4F4F6; color: #121212; } .c { background: #121212; color: #F4F4F6; }
    .c .n { color: #C6FF3D; }`,
    body: `<div class="w"><span class="k">The proof</span><h1>One week of Grenoble, in numbers.</h1><div class="tiles">
      <div class="tile a"><span class="n">45</span><span class="t">free outings worth going to near Grenoble, this week</span><span class="s">Week of 21 October 2026</span></div>
      <div class="tile b"><span class="n">15–17&thinsp;€</span><span class="t">between the cheapest and the dearest full tank in the metro area</span><span class="s">Official prices, 17 October 2026</span></div>
      <div class="tile c"><span class="n">1,203</span><span class="t">events from 38 public sources, read in 27 minutes</span><span class="s">Trial run, 18 October 2026</span></div></div></div>` });

  // 5. The review board (a reconstruction of the Publish screen of grnbl/admin.html, same labels).
  const ap = post("gratuit-a-reserver"), wk = post("gratuit-cette-semaine");
  const titles = t => [...t.matchAll(/^🆓 \*([^*]+)\* · ([^·\n]+)/gm)].map(m => [m[1], m[2].trim()]);
  const rowsB = titles(ap.text), rowsW = titles(wk.text);
  const cand = ([t, d], on = true) => `<div class="cd ${on ? "on" : ""}"><span class="bx">${on ? "✓" : ""}</span><div><div class="ct">${t}${on ? ' <span class="ok">approved</span>' : ""}</div><div class="cm2">${d} · free</div></div></div>`;
  job("devpost", "5-board" + sfx, 1200, 800, { font, css: DEV + `
    .hd { position: absolute; left: 76px; right: 76px; top: 64px; }
    h1 { font-size: 46px; margin: 14px 0 0; }
    .board { position: absolute; left: 76px; right: 76px; top: 222px; bottom: 0; border-radius: 22px 22px 0 0; background: #fbfbfd; color: #1d1d1f;
      font: 14px/1.45 'Inter', 'Noto Color Emoji', sans-serif; display: grid; grid-template-columns: 1fr 380px; overflow: hidden; box-shadow: 0 30px 80px rgba(8,14,60,.35); }
    .top { grid-column: 1 / -1; height: 48px; display: flex; align-items: center; gap: 14px; padding: 0 18px; border-bottom: 1px solid rgba(0,0,0,.08); }
    .top b { font-weight: 650; font-size: 15px; } .top .d { color: #86868b; }
    .seg { display: flex; background: #f2f2f5; border-radius: 8px; padding: 2px; gap: 2px; }
    .seg span { padding: 3px 11px; border-radius: 6px; font-size: 12.5px; color: #515154; }
    .seg span.on { background: #fff; color: #1d1d1f; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
    .notes { padding: 14px 18px; border-right: 1px solid rgba(0,0,0,.08); overflow: hidden; }
    .notes .seg { margin-bottom: 12px; width: fit-content; }
    .sum { display: flex; align-items: center; justify-content: space-between; background: #fff; border-radius: 12px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.06); margin-bottom: 12px; }
    .sum small { display: block; color: #86868b; font-size: 12px; }
    .btn { background: #1a7f37; color: #fff; border-radius: 8px; padding: 7px 14px; font-weight: 600; font-size: 13px; }
    h2 { font-size: 13px; font-weight: 650; margin: 10px 0 4px; display: flex; gap: 8px; } h2 span { color: #86868b; font-weight: 500; }
    .cd { display: grid; grid-template-columns: 20px 1fr; gap: 10px; padding: 6px 4px; border-radius: 8px; }
    .bx { width: 18px; height: 18px; border-radius: 5px; border: 1.5px solid #c7c7cc; display: grid; place-items: center; font-size: 11px; color: #fff; margin-top: 2px; }
    .cd.on .bx { background: #0071e3; border-color: #0071e3; }
    .ct { font-weight: 600; font-size: 13.5px; } .cm2 { color: #86868b; font-size: 12px; }
    .ok { font-size: 10.5px; font-weight: 600; color: #1a7f37; background: rgba(26,127,55,.1); padding: 1px 6px; border-radius: 99px; margin-left: 4px; }
    .more { color: #0071e3; font-size: 12.5px; padding: 2px 4px 0 34px; }
    .pv { background: #efeae2; padding: 0; display: flex; flex-direction: column; }
    .pv .chan { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #f6f5f4; border-bottom: 1px solid rgba(0,0,0,.08); }
    .pv .chan b { display: block; font-size: 13.5px; } .pv .chan small { color: #667781; font-size: 11.5px; }
    .pv .wa-msg { margin: 12px 12px 6px; font: 12.5px/1.38 'Inter', 'Noto Color Emoji', sans-serif; }
    .pv .en { margin: 0 12px; color: #54656f; font: 12px/1.38 'Inter', 'Noto Color Emoji', sans-serif; white-space: pre-wrap; }
    .pv .en b { color: #3b4a54; }
    .pv .en .h { display: block; font-weight: 600; color: #667781; margin-bottom: 4px; }`,
    body: `<div class="hd"><span class="k">The review board</span><h1>A human checks about 11 lines, not 1,203 events.</h1></div>
      <div class="board"><div class="top"><b>grnbl</b><span class="d">Edition of Wednesday 21 October</span><div class="seg"><span class="on">Publish</span><span>Browse</span></div></div>
      <div class="notes"><div class="seg"><span class="on">🆓 Gratuit</span><span>🎭 Sorties</span><span>👨‍👩‍👧 Famille</span><span>🛍️ Bons plans</span><span>🏔️ Nature</span><span>⛽ Carburant</span></div>
        <div class="sum"><div><b>${rowsB.length + rowsW.length} lines ticked</b><small>Tick what should go out, then approve: sending is scheduled.</small></div><span class="btn">All good</span></div>
        <h2>Book now <span>${rowsB.length} ticked</span></h2>${rowsB.map(r => cand(r)).join("")}<div class="more">Show 4 other options</div>
        <h2>This week <span>${rowsW.length} ticked</span></h2>${rowsW.map(r => cand(r)).join("")}<div class="more">Show 6 other options</div></div>
      <div class="pv"><div class="chan"><span id="pav"></span><div><b>grnbl · Gratuit</b><small>Group · preview before posting</small></div></div>
        <div class="wa-msg"><div class="wa-txt" id="pt"></div><span class="wa-time">12:00</span></div>
        <div class="en"><span class="h">English translation (not posted)</span><span id="pe"></span></div></div></div>`,
    script: `avatar(document.getElementById("pav"), "gratuit", 30);
      document.getElementById("pt").innerHTML = wa(${JSON.stringify(ap.text)});
      document.getElementById("pe").innerHTML = wa(${JSON.stringify(K.POST_EN.split("\n").slice(0, 6).join("\n"))});` });

  // 6. The community and its groups.
  const SIGNS = K.GROUPS.filter(g => g.id !== "community");
  job("devpost", "6-community" + sfx, 1200, 800, { font, css: DEV + `
    .ph { position: absolute; left: 76px; top: 64px; }
    .r { position: absolute; left: 520px; right: 76px; top: 92px; }
    h1 { font-size: 52px; margin: 18px 0 20px; }
    .p { font-size: 21px; }
    .signs { margin-top: 34px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px 24px; }
    .sg { display: flex; align-items: center; gap: 14px; font-size: 19px; font-weight: 600; letter-spacing: -.01em; }
    .sg small { display: block; font-size: 15px; font-weight: 500; color: rgba(244,244,246,.66); }`,
    body: `<div class="ph">${phone("c6", communityBody)}</div><div class="r"><span class="k">The product</span>
      <h1>One community, one group per topic.</h1>
      <p class="p">Join only what you care about. Nothing to install: it is WhatsApp. Red is kept for the rare alerts.</p>
      <div class="signs">${SIGNS.map(g => `<div class="sg"><span data-s="${g.id}"></span><span>${g.label}</span></div>`).join("")}</div></div>`,
    script: `${communityScript} document.querySelectorAll("[data-s]").forEach(n => avatar(n, n.dataset.s, 56));` });

  // ---------- Video, 1920 x 1080 ----------
  const VID = `
    .k { color: #C6FF3D; font-size: 34px; font-weight: 600; }
    h1 { font-weight: 700; letter-spacing: -.04em; line-height: .98; }
    .sub { color: rgba(244,244,246,.8); font-size: 50px; line-height: 1.2; letter-spacing: -.02em; font-weight: 500; }`;
  job("video", "00-title" + sfx, 1920, 1080, { font, css: VID + `
    .c { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .logo { width: 760px; }
    .sub { margin-top: 56px; font-size: 64px; color: #F4F4F6; }
    .c { padding-bottom: 60px; }
    .k { position: absolute; bottom: 86px; left: 0; right: 0; text-align: center; font-size: 30px; }`,
    body: `<div class="c"><svg class="logo"></svg><p class="sub">${K.TAGLINE}</p></div><p class="k">Neighborhood Hacks 2026 · Grenoble</p>`,
    script: `drawLogo(document.querySelector(".logo"));` });

  K.PARTS.forEach((part, i) => {
    job("video", `${String(i + 1).padStart(2, "0")}-${part.title.toLowerCase().replace(/[^a-z]+/g, "-").replace(/-$/, "")}` + sfx, 1920, 1080, { font, css: VID + `
      .cable { position: absolute; left: 0; top: 0; width: 1920px; height: 400px; }
      .t { position: absolute; left: 160px; right: 160px; top: 520px; }
      .k { display: block; margin-bottom: 26px; font-variant-numeric: tabular-nums; }
      h1 { font-size: 168px; }
      .sub { margin-top: 34px; max-width: 1400px; }`,
      body: `<svg class="cable" viewBox="0 0 1920 400"><g id="cb"></g></svg>
        <div class="t"><span class="k">${part.n} / 08</span><h1>${part.title}</h1><p class="sub">${part.sub}</p></div>`,
      script: `const g = document.getElementById("cb"), cy = x => 236 - x * .07; line(g, -20, cy(-20), 1940, cy(1940), 7);
        spread(250, 1670, 8).forEach((x, k) => { const cur = k === ${i}, r = cur ? 44 : 22, stem = cur ? 26 : 22;
          line(g, x, cy(x), x, cy(x) + stem + 2, 6);
          el("circle", { cx: x, cy: cy(x) + stem + r, r, fill: k <= ${i} ? C.lime : C.blue, stroke: C.ink, "stroke-width": 6 }, g);
          if (cur) { const t = el("text", { x, y: cy(x) + stem + r + 13, "text-anchor": "middle", style: "font: 700 36px var(--f); fill: #121212" }, g); t.textContent = ${JSON.stringify(part.n)}; } });` });
  });

  job("video", "99-end" + sfx, 1920, 1080, { font, css: VID + `
    .top { position: absolute; left: 160px; top: 120px; }
    .logo { width: 520px; display: block; margin-left: -12px; }
    .tag { font-size: 92px; margin-top: 40px; }
    .links { position: absolute; left: 160px; right: 160px; bottom: 140px; display: grid; grid-template-columns: 240px 1fr; row-gap: 22px; font-size: 40px; letter-spacing: -.015em; }
    .links dt { color: #C6FF3D; font-weight: 600; } .links dd { font-weight: 500; }`,
    body: `<div class="top"><svg class="logo"></svg><h1 class="tag">${K.TAGLINE}</h1></div>
      <dl class="links"><dt>Code</dt><dd>${K.REPO}</dd><dt>Built with</dt><dd>Python, Claude (Haiku, Sonnet), Claude Code, WhatsApp</dd><dt>Made by</dt><dd>Elior, in Grenoble, for Neighborhood Hacks 2026</dd></dl>`,
    script: `drawLogo(document.querySelector(".logo"));` });

  for (const lt of K.LOWER_THIRDS) {
    job("video", "lower-third-" + lt.file + sfx, 1920, 1080, { font, css: `
      .lt { position: absolute; left: 96px; bottom: 96px; display: flex; align-items: center; gap: 22px; padding: 18px 40px 18px 18px; border-radius: 30px; background: #2F4BFF; box-shadow: 0 10px 40px rgba(0,0,0,.28); }
      .lt b { display: block; font-size: 46px; font-weight: 700; letter-spacing: -.025em; line-height: 1.1; color: #F4F4F6; }
      .lt span.s { display: block; font-size: 30px; font-weight: 500; color: rgba(244,244,246,.8); letter-spacing: -.01em; margin-top: 2px; }`,
      body: `<div class="lt"><span id="a"></span><div><b>${lt.title}</b><span class="s">${lt.sub}</span></div></div>`,
      script: `avatar(document.getElementById("a"), "community", 96);` }, { transparent: true });
  }
}

// ---------- Run ----------
const only = process.argv.slice(2);
const todo = jobs.filter(j => !only.length || only.includes(j.family));
fs.mkdirSync(BUILD, { recursive: true });
const browser = await chromium.launch();
let bad = 0;
for (const j of todo) {
  const ctx = await browser.newContext({ viewport: { width: j.w, height: j.h }, deviceScaleFactor: j.scale });
  const page = await ctx.newPage();
  const src = path.join(BUILD, `${j.family}-${j.name}.html`);
  fs.writeFileSync(src, j.html);
  page.on("pageerror", e => { console.error(`  ! ${j.name}: ${e.message}`); bad++; });
  await page.goto(pathToFileURL(src).href);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 20000 });
  const fonts = await page.evaluate(() => window.__fonts);
  const missing = fonts.filter(f => !f[1]).map(f => f[0]);
  if (missing.length) { console.error(`  ! ${j.name}: fonts not loaded: ${missing.join(", ")}`); bad++; }
  const out = path.join(EXPORT, j.family, j.name + ".png");
  fs.mkdirSync(path.dirname(out), { recursive: true });
  await page.screenshot({ path: out, omitBackground: j.transparent });
  console.log(`${path.relative(BRAND, out)}  ${j.w * j.scale}x${j.h * j.scale}`);
  await ctx.close();
}
await browser.close();
if (bad) { console.error(`${bad} problem(s)`); process.exit(1); }
