// 一份空气 / One Breath — two CHIMERA airways sharing one closed volume of air.
// Plain script (no imports): concatenated into the AudioWorklet and loaded by the Node test.
// Built on CHIMERA by Jameson Hodge (MIT).

globalThis.OneBreath = (function () {
  const SOURCE_KEYS = ["f0", "glide", "pressure", "breathiness", "tension", "fry", "roughness", "vibratoDepth", "vibratoRate", "drift", "voiced", "brightness"];
  const TELE_HEADER = 16;
  const CONTROL_KEYS = ["jaw", "tbX", "tbY", "ttX", "ttY", "ttCurl", "root", "lipAp", "lipProt", "lipWidth", "labiodental", "velum", "larynx", "epilarynx", "ventricular", "lateral", "dorsum", "abduction", "closure", "breath", "f0", "vibrato"];
  const O2_START = 0.21; // fraction of oxygen in fresh air
  const O2_FLOOR = 0.105; // modelled limit: below this nothing is left to speak with
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (t) => t * t * (3 - 2 * t);

  function blend(a, b, t, keys) {
    const o = {};
    for (const k of keys) {
      const x = a[k], y = b[k];
      if (x === undefined && y === undefined) continue;
      o[k] = lerp(x ?? y, y ?? x, t);
    }
    return o;
  }

  class Body {
    constructor(x, fs, female) {
      this.x = x;
      this.h = x.engine_new(fs);
      x.engine_set_body(this.h, female, 0);
    }
    values() {
      return new Float64Array(this.x.memory.buffer, this.x.engine_values(this.h), 32).fill(NaN);
    }
    source(s) {
      const v = this.values();
      for (const [k, val] of Object.entries(s)) {
        const i = SOURCE_KEYS.indexOf(k);
        if (i >= 0) v[i] = typeof val === "boolean" ? (val ? 1 : 0) : val;
      }
      this.x.engine_set_source(this.h);
    }
    artic(a, keys) {
      const v = this.values();
      keys.forEach((k, i) => {
        if (a[k] !== undefined) v[i] = a[k];
      });
      this.x.engine_set_artic(this.h, 2);
    }
    gate(g) {
      this.x.engine_set_gate(this.h, g);
    }
    /** schedule CHIMERA speech gestures (times relative to now + lead) — the engine's binary record layout v1 */
    schedule(gestures, lead, replace) {
      const x = this.x, REC = 272, MAX = 1024;
      const n = Math.min(gestures.length, MAX);
      const at = x.engine_records(this.h);
      const dv = new DataView(x.memory.buffer, at, n * REC);
      const bytes = new Uint8Array(x.memory.buffer, at, n * REC);
      for (let i = 0; i < n; i++) {
        const g = gestures[i], o = i * REC;
        const head = [g.t0, g.t1, g.rampIn, g.rampOut, g.strength, g.speed ?? NaN, g.releaseHold ?? NaN, g.tag ?? NaN];
        for (let j = 0; j < 8; j++) dv.setFloat64(o + j * 8, head[j], true);
        for (let k = 0; k < CONTROL_KEYS.length; k++) dv.setFloat64(o + 64 + k * 8, NaN, true);
        for (const [key, value] of Object.entries(g.targets)) {
          const k = CONTROL_KEYS.indexOf(key);
          if (k >= 0 && value !== undefined && value !== null) dv.setFloat64(o + 64 + k * 8, value, true);
        }
        bytes[o + 240] = 255; // no label
      }
      return x.engine_schedule(this.h, n, lead, replace ? 1 : 0);
    }
    stopSpeech() {
      this.x.engine_stop_speech(this.h);
    }
    render(n) {
      const p = this.x.engine_render(this.h, n);
      return new Float32Array(this.x.memory.buffer, p, n);
    }
    telemetry() {
      const x = this.x;
      const p = x.engine_telemetry(this.h);
      const head = new Float64Array(x.memory.buffer, p, TELE_HEADER);
      const [phLen, orLen, , f0, voicing, pLung, outRms, , , gate, , nArtic, nPh, nOr, nScope] = head;
      const all = new Float64Array(x.memory.buffer, p, TELE_HEADER + nArtic + 3 * (nPh + nOr) + 2 * nScope);
      let o = TELE_HEADER + nArtic;
      const take = (n) => Float32Array.from(all.subarray(o, (o += n)));
      const phAreas = take(nPh), orAreas = take(nOr), pressureRms = take(nPh + nOr), flow = take(nPh + nOr);
      return { phLen, orLen, f0, voicing, pLung, outRms, gate, phAreas, orAreas, pressureRms, flow };
    }
  }

  class Piece {
    /** a, b: anything with source(), artic(), gate() — a Body here, or a proxy to a worklet */
    constructor(a, b, catalog, fs) {
      this.fs = fs || 48000;
      this.keys = catalog.articKeys;
      this.vowelsF = catalog.vowels.female;
      this.vowelsM = catalog.vowels.male;
      this.a = a;
      this.b = b;
      a.f0 = 205;
      b.f0 = 112;
      this.minutes = 4; // how long the air lasts, untouched
      this.reset();
    }

    reset() {
      this.t = 0;
      this.o2 = O2_START;
      this.turn = 0; // 0: A breathes out into B; 1: B into A
      this.phase = 0; // 0..1 through the current turn
      this.turnLen = 3.4;
      this.breaths = 0;
      this.ended = false;
      this.running = false;
      this.ctrlAcc = 0;
      this.rescues = 0;
      for (const body of [this.a, this.b]) {
        body.gate(0);
        body.source({ pressure: 0, voiced: true, vibratoDepth: 0, glide: 0.12 });
      }
    }

    start() {
      if (this.ended) this.reset();
      this.running = true;
    }

    /** an outsider lets in a little fresh air */
    freshAir() {
      this.o2 = Math.min(O2_START, this.o2 + 0.025);
      this.rescues++;
      if (this.ended) {
        this.ended = false;
        this.running = true;
      }
    }

    get vitality() {
      return clamp((this.o2 - O2_FLOOR) / (O2_START - O2_FLOOR), 0, 1);
    }

    /** advance the shared air and the breath cycle, then set both bodies (control rate) */
    control(dt) {
      if (!this.running) return;
      this.t += dt;
      const v = this.vitality;

      // the closed air is used up; harder breathing uses it faster
      const perSec = (O2_START - O2_FLOOR) / (this.minutes * 60);
      this.o2 = Math.max(O2_FLOOR, this.o2 - perSec * dt * (0.75 + 0.5 * v));

      // turn length: calm, then air hunger (short, quick), then long failing gaps
      const target = v > 0.35 ? lerp(2.2, 3.4, (v - 0.35) / 0.65) : lerp(5.2, 2.2, v / 0.35);
      this.phase += dt / this.turnLen;
      if (this.phase >= 1) {
        this.phase -= 1;
        this.turn ^= 1;
        this.breaths++;
        this.turnLen = target * (0.92 + 0.16 * Math.random());
      }

      const out = this.turn === 0 ? this.a : this.b;
      const inn = this.turn === 0 ? this.b : this.a;
      const p = this.phase;
      // fraction of the turn that is actual breath; the rest is a pause that grows as they fail
      const active = lerp(0.62, 0.92, smooth(clamp(v * 1.6, 0, 1)));
      const q = clamp(p / active, 0, 1);
      const env = p > active ? 0 : smooth(clamp(q / 0.14, 0, 1)) * (1 - smooth(clamp((q - 0.78) / 0.22, 0, 1)));

      const u = 1 - v; // exhaustion
      // the one breaking out: a held open vowel that sags toward a slack, closing mouth
      const outV = out === this.a ? this.vowelsF : this.vowelsM;
      const mouth = u < 0.5 ? blend(outV["a"].artic, outV["ɑ"].artic, u * 2, this.keys) : blend(outV["ɑ"].artic, outV["ə"].artic, (u - 0.5) * 2, this.keys);
      out.artic(mouth, this.keys);
      const wobble = 1 + 0.03 * Math.sin(this.t * 0.7 + (out === this.a ? 0 : 2)) * u;
      out.source({
        f0: out.f0 * lerp(1.0, 0.8, u * u) * wobble,
        pressure: lerp(9, 4.6, Math.pow(u, 0.8)),
        breathiness: lerp(0.12, 0.85, Math.pow(u, 1.3)),
        tension: lerp(0.55, 0.2, u),
        roughness: lerp(0.08, 0.7, u * u),
        fry: u > 0.65 ? (u - 0.65) * 2.2 : 0,
        drift: lerp(4, 30, u),
        voiced: v > 0.06,
        brightness: lerp(0.3, 0.1, u),
      });
      out.gate(env * lerp(1, 0.85, u));

      // the other takes that same air in: the same flow, reversed (ingressive)
      const inV = inn === this.a ? this.vowelsF : this.vowelsM;
      inn.artic(blend(inV["ə"].artic, inV["a"].artic, 0.35 * v, this.keys), this.keys);
      const gasp = u > 0.55; // late on the inhale catches the folds
      inn.source({
        f0: inn.f0 * 1.1,
        pressure: -lerp(6, 4, u),
        breathiness: 0.95,
        tension: 0.3,
        roughness: 0.5,
        fry: 0,
        voiced: gasp,
        brightness: 0.1,
      });
      inn.gate(env * lerp(0.7, 0.9, u));

      this.flowDir = this.turn === 0 ? 1 : -1; // +1: A → B
      this.env = env;
      if (v <= 0 && !this.ended) {
        this.ended = true;
        this.running = false;
        this.a.gate(0);
        this.b.gate(0);
      }
    }

    /** offline only (both bodies are local Body objects): n frames, [left = A, right = B] */
    render(n, ctrlEvery) {
      this.ctrlAcc += n;
      if (this.ctrlAcc >= ctrlEvery) {
        this.control(this.ctrlAcc / this.fs);
        this.ctrlAcc = 0;
      }
      const l = Float32Array.from(this.a.render(n));
      const r = Float32Array.from(this.b.render(n));
      return [l, r];
    }

    state() {
      return {
        t: this.t,
        o2: this.o2,
        co2: 0.0004 + (O2_START - this.o2) * 0.85,
        vitality: this.vitality,
        turn: this.turn,
        phase: this.phase,
        env: this.env || 0,
        breaths: this.breaths,
        running: this.running,
        ended: this.ended,
        rescues: this.rescues,
        minutes: this.minutes,
      };
    }
  }

  return { Piece, Body };
})();
