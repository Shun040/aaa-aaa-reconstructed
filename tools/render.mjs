// node render.mjs U|M t0 t1 out.raw  — offline render of one voice following the score
import fs from 'fs';
await import('./core.js'); await import('./driver.js');
const [who, t0s, t1s, out] = process.argv.slice(2); const t0=+t0s, t1=+t1s;
const fs_ = 48000;
const { instance } = await WebAssembly.instantiate(fs.readFileSync('chimera.wasm'), {});
const cat = JSON.parse(fs.readFileSync('cat-min.json')); const score = JSON.parse(fs.readFileSync('score.json'));
const intro = JSON.parse(fs.readFileSync('intro_plan.json'));
const body = new OneBreath.Body(instance.exports, fs_, who === 'M' ? 1 : 0);
const vowels = cat.vowels[who === 'M' ? 'female' : 'male'];
const N = Math.round((t1 - t0) * fs_), buf = new Float32Array(N);
const blk = 128, ctrlEvery = 4; // control every 4 blocks ≈ 10.7 ms
// pre-roll so the voice settles
let speaking = false;
if (who === 'M' && t0 < AAA.INTRO_END) {
  speaking = true;
  body.schedule(intro.gestures.filter((g) => g.t1 > t0).map((g) => ({ ...g, t0: g.t0 - t0, t1: g.t1 - t0 })), 0, true);
}
for (let i = 0, k = 0; i < N; i += blk, k++) {
  const tt = t0 + i / fs_;
  if (speaking && tt >= AAA.INTRO_END) { body.stopSpeech(); speaking = false; }
  if (k % ctrlEvery === 0 && !speaking) {
    const c = AAA.controls(score, who, t0 + i / fs_, vowels);
    body.artic(c.artic, cat.articKeys); body.source(c.source); body.gate(c.gate);
  }
  const n = Math.min(blk, N - i);
  buf.set(body.render(n), i);
}
fs.writeFileSync(out, Buffer.from(buf.buffer));
console.log(who, t0, t1, 'done');
