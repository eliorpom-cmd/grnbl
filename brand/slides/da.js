// Timing helpers shared by the slides. Each slide defines window.frame(t); render.mjs captures it frame by frame.
const clamp = x => Math.max(0, Math.min(1, x));
const span = (t, a, d) => clamp((t - a) / d);
const out = x => 1 - Math.pow(1 - x, 3);
const inout = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const back = x => { const c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
// Fade and rise an element in from `a` over `d` seconds.
function rise(el, t, a, d = .6, dy = 24) { const v = out(span(t, a, d)); el.style.opacity = v; el.style.transform = `translateY(${(1 - v) * dy}px)`; return v; }
// A cabin hanging from the cable at x: stem + bubble, swinging by `deg` around the hook.
function cabin(g, x, y, { stem = 90, r = 62, deg = 0, fill = '#C6FF3D', sw = 8 } = {}) {
  const c = el('g', { transform: `rotate(${deg} ${x} ${y})` }, g);
  line(c, x, y, x, y + stem, sw); bubble(c, x, y + stem + r, r, sw, fill); return c;
}
// Damped swing after a cabin stops: big at arrival, settled after ~1.5 s.
const settle = (s, amp = 9) => s <= 0 ? 0 : amp * Math.exp(-2.6 * s) * Math.sin(s * 6.5);
