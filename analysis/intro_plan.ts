// Plan Marina's spoken intro with CHIMERA's planner, then warp it onto the recording's word timings.
import { readFileSync, writeFileSync } from "fs";
import { gunzipSync } from "zlib";
import { initChimera } from "../wasm/chimera.ts";
const wasm = readFileSync("target/wasm32-unknown-unknown/release/chimera_wasm.wasm");
await initChimera(wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength));
const { EnglishG2P, planPhrases, plannedCounts } = await import("../wasm/engine.ts");

const align: [string, number, number][] = JSON.parse(readFileSync(process.argv[2], "utf8"));
const words = align.filter(([w]) => w !== "<sil>").map(([w, a, b]) => ({ w: w.replace(/\(\d\)$/, ""), a, b }));

const g2p = new EnglishG2P();
g2p.setDictionaryText(gunzipSync(readFileSync("public/data/cmudict.txt.gz")).toString("utf8"));
const text = "We are facing each other, both producing a continuous vocal sound. We slowly build up the tension. Our faces coming closer together, until we are screaming into each other's open mouths.";
const phrases = g2p.toPhrases(text);
const body = { female: 1, child: 0 };
const plan = planPhrases(phrases, { body, t0: 0, rate: 1, f0: 190 });

// each planned word's span
const counts = plannedCounts(phrases.flatMap((p: any) => p.segments.map((s: any) => s.ipa)));
const spans: { t0: number; t1: number }[] = [];
let k = 0, j = 0;
for (const p of phrases as any[]) {
  let t0: number | null = null;
  p.segments.forEach((s: any, i: number) => {
    const n = counts[k++];
    const first = plan.segments[j], last = plan.segments[j + n - 1];
    j += n;
    if (!first || !last) return;
    t0 ??= first.t0;
    if (s.wordEnd || i === p.segments.length - 1) { spans.push({ t0, t1: last.t1 }); t0 = null; }
  });
}
if (spans.length !== words.length) throw new Error(`planned ${spans.length} words, aligned ${words.length}`);

// piecewise-linear warp: planned word edges → recorded word edges
const knots: [number, number][] = [[spans[0].t0 - 0.3, words[0].a - 0.3]];
spans.forEach((s, i) => { knots.push([s.t0, words[i].a]); knots.push([s.t1, Math.max(words[i].b, words[i].a + 0.04)]); });
knots.push([plan.end + 0.5, knots[knots.length - 1][1] + 0.5]);
for (let i = 1; i < knots.length; i++) if (knots[i][0] <= knots[i - 1][0]) knots[i][0] = knots[i - 1][0] + 1e-4;
function warp(t: number): number {
  let i = 0;
  while (i < knots.length - 2 && knots[i + 1][0] <= t) i++;
  const [x0, y0] = knots[i], [x1, y1] = knots[i + 1];
  return y0 + ((t - x0) / (x1 - x0)) * (y1 - y0);
}
const gestures = plan.gestures.map((g: any) => {
  const t0 = warp(g.t0), t1 = warp(g.t1);
  const s = (t1 - t0) / Math.max(1e-4, g.t1 - g.t0);
  return { ...g, t0, t1, rampIn: g.rampIn * Math.min(1.5, Math.max(0.5, s)), rampOut: g.rampOut * Math.min(1.5, Math.max(0.5, s)) };
});
const out = { text, words: words.map((w, i) => ({ w: w.w, t0: w.a, t1: w.b })), end: warp(plan.end), gestures };
writeFileSync(process.argv[3], JSON.stringify(out));
console.log("gestures", gestures.length, "planned dur", plan.end.toFixed(2), "→", out.end.toFixed(2));
