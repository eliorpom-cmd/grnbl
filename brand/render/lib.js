// Drawing helpers shared by every visual. Runs in the page (Chromium), not in Node.
// The logo and the icon are the exact geometry of brand/logo-7.html (logo 3, icon B).
const NS = "http://www.w3.org/2000/svg";
const C = {
  blue: "#2F4BFF", violet: "#6A35FF", lime: "#C6FF3D", ink: "#121212",
  off: "#F4F4F6", red: "#FF3B30", mute: "rgba(244,244,246,.72)",
};

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== undefined) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
function text(g, s, attrs = {}, x = 0, y = 0, size = 100) {
  const t = el("text", { x, y, style: `font-family:'Bagel Fat One';font-size:${size}px;font-feature-settings:'liga' 0`, ...attrs }, g);
  t.textContent = s; return t;
}
function stickerText(g, s, x = 0, y = 0, size = 100, w = 12) {
  text(g, s, { fill: C.ink, stroke: C.ink, "stroke-width": w + 4, "stroke-linejoin": "round" }, x + 6 * size / 100, y + 8 * size / 100, size);
  return text(g, s, { fill: "#fff", stroke: C.ink, "stroke-width": w, "stroke-linejoin": "round", "paint-order": "stroke" }, x, y, size);
}
function bubble(g, x, y, r, sw = 5, fill = C.lime) {
  el("circle", { cx: x + r * .27, cy: y + r * .33, r: r + sw / 2, fill: C.ink }, g);
  el("circle", { cx: x, cy: y, r, fill, stroke: C.ink, "stroke-width": sw }, g);
}
function line(g, x1, y1, x2, y2, w, color = C.ink) { el("line", { x1, y1, x2, y2, stroke: color, "stroke-width": w, "stroke-linecap": "round" }, g); }
function hang(g, xs, cy, r, stem, sw = 5) {
  xs.forEach(x => { line(g, x, cy(x), x, cy(x) + stem + 2, sw); bubble(g, x, cy(x) + stem + r, r, sw); });
}
const spread = (a, b, n) => n === 1 ? [(a + b) / 2] : [...Array(n)].map((_, i) => a + i * (b - a) / (n - 1));
function wordWidth(g) { const t = text(g, "grnbl", { fill: "none" }); const W = t.getComputedTextLength(); t.remove(); return W; }
function fit(svg, pad = 10) {
  const bb = svg.querySelector("g").getBBox();
  svg.setAttribute("viewBox", `${bb.x - pad} ${bb.y - pad} ${bb.width + pad * 2} ${bb.height + pad * 2}`);
}

// Logo 3 of logo-7.html: "Bulles plus grosses".
function drawLogo(svg, pad = 10) {
  const g = el("g", {}, svg);
  const W = wordWidth(g), cy = x => 50 - 18 * x / W;
  line(g, -12, cy(-12), W + 12, cy(W + 12), 8);
  hang(g, spread(W * .09, W * .91, 5), cy, 21, 8, 6);
  stickerText(g, "grnbl");
  fit(svg, pad);
  // Height from the viewBox, so the logo takes its real place in the layout.
  const vb = svg.viewBox.baseVal;
  svg.style.height = (svg.getBoundingClientRect().width * vb.height / vb.width) + "px";
}

// Icon B of logo-7.html: three bubbles under the cable, drawn in a 200 x 200 box centred on 0,0.
function drawIconB(g) {
  const cy = x => -24 - .27 * x;
  line(g, -120, cy(-120), 120, cy(120), 8);
  hang(g, spread(-54, 54, 3), cy, 20, 10, 5.5);
}

// A group photo: one big cabin on the cable, the group's Lucide sign inside it.
// `icon` is the inner markup of a 24 x 24 Lucide SVG.
function drawSign(g, icon, { fill = C.lime, stroke = C.ink } = {}) {
  const cy = x => -80 - .22 * x, r = 70, stem = 6, sw = 7;
  line(g, -120, cy(-120), 120, cy(120), 8);
  line(g, 0, cy(0), 0, cy(0) + stem + 2, sw);
  const y = cy(0) + stem + r;
  // Same sticker as the bubbles of the logo, with a shorter shadow so the big cabin stays light.
  el("circle", { cx: 7, cy: y + 9, r: r + sw / 2, fill: C.ink }, g);
  el("circle", { cx: 0, cy: y, r, fill, stroke: C.ink, "stroke-width": sw }, g);
  const s = 3.7, ic = el("g", { transform: `translate(${-12 * s} ${y - 12 * s}) scale(${s})`, fill: "none", stroke, "stroke-width": 2.6, "stroke-linecap": "round", "stroke-linejoin": "round" }, g);
  ic.innerHTML = icon;
}

// An avatar: a square div with the drawing in it. kind = "community" | group id.
function avatar(host, kind, size, radius = "50%") {
  const d = document.createElement("div");
  d.className = "av";
  d.style.cssText = `width:${size}px;height:${size}px;border-radius:${radius};background:${C.blue};position:relative;overflow:hidden;flex:none`;
  host.appendChild(d);
  const svg = el("svg", { viewBox: "-100 -100 200 200", style: "position:absolute;inset:0;width:100%;height:100%" }, d);
  const g = el("g", {}, svg);
  const grp = (window.GROUPS || []).find(x => x.id === kind);
  if (!grp || kind === "community") drawIconB(g);
  else drawSign(g, window.ICONS[grp.icon], grp.alert ? { fill: C.red, stroke: C.off } : {});
  return d;
}

// WhatsApp formatting: *bold*, _italic_, line breaks kept as written.
function wa(t) {
  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc(t).replace(/\*([^*\n]+)\*/g, "<b>$1</b>").replace(/(^|[\s(])_([^_\n]+)_(?=$|[\s).,])/gm, "$1<i>$2</i>");
}

// A WhatsApp group chat (iOS look), messages anchored to the bottom like a real conversation.
function chat(host, { group, title, sub = "Communauté grnbl", day = "Aujourd'hui", posts = [], time = "12:00" }) {
  const box = document.createElement("div");
  box.className = "wa";
  box.innerHTML = `<div class="wa-head"><span class="wa-back">‹</span><span class="wa-av"></span><div class="wa-t"><b>${title}</b><small>${sub}</small></div></div>
    <div class="wa-body"><div class="wa-flow"><span class="wa-day">${day}</span>${posts.map(p => `<div class="wa-msg"><span class="wa-from">grnbl</span><div class="wa-txt">${wa(p)}</div><span class="wa-time">${time}</span></div>`).join("")}</div></div>
    <div class="wa-foot">Seuls les admins peuvent envoyer des messages</div>`;
  host.appendChild(box);
  avatar(box.querySelector(".wa-av"), group, 36);
  return box;
}
