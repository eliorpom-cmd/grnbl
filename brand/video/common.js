// Shared timeline for the video clips. Each clip defines DURATION (seconds) and frame(t), a pure
// function of the time: record.mjs calls seek(t) for every frame, a browser just plays it.
const C = { blue: "#2F4BFF", lime: "#C6FF3D", ink: "#121212", off: "#F4F4F6", mute: "rgba(244,244,246,.72)", red: "#FF3B30" };

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
// Progress of [start, start + dur] at time t, eased.
const span = (t, start, dur) => clamp((t - start) / dur);
const easeOut = k => 1 - Math.pow(1 - k, 3);
const easeInOut = k => (k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
// A spring-like pop: overshoots a little, settles at 1.
const pop = k => (k <= 0 ? 0 : k >= 1 ? 1 : 1 + 2.2 * Math.pow(k - 1, 3) + 1.2 * Math.pow(k - 1, 2));
const fmt = n => Math.round(n).toLocaleString("en-US");

// Font of the announcements, not chosen yet: ?font=host (default) or ?font=familjen.
const FONT = new URLSearchParams(location.search).get("font") === "familjen" ? "Familjen Grotesk" : "Host Grotesk";
document.documentElement.style.setProperty("--f", `'${FONT}'`);

function show(el, k, dy = 30) {
  el.style.opacity = k;
  el.style.transform = `translateY(${(1 - k) * dy}px)`;
}

window.seek = t => frame(Math.min(t, DURATION));
window.ready = document.fonts.ready.then(() => {
  const bad = [...document.fonts].filter(f => f.status === "error");
  if (bad.length) throw new Error("font failed: " + bad.map(f => f.family).join(", "));
  return true;
});

// Plays in a normal browser tab (loops); the recorder sets ?record and drives seek() itself.
if (!new URLSearchParams(location.search).has("record")) {
  window.ready.then(() => {
    const t0 = performance.now();
    const tick = now => { frame(((now - t0) / 1000) % (DURATION + 1)); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
}
