// One CHIMERA body per AudioContext (each context gets its own audio thread).
// Needs core.js loaded into the same worklet scope first (OneBreath.Body).
// Built on CHIMERA by Jameson Hodge (MIT).

class BodyProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { module, female } = options.processorOptions;
    const x = new WebAssembly.Instance(module, {}).exports;
    this.body = new OneBreath.Body(x, sampleRate, female);
    this.blocks = 0;
    this.load = 0;
    this.failed = false;
    this.port.onmessage = (e) => {
      const m = e.data;
      if (this.failed) return;
      try {
        if (m.stopSpeech) this.body.stopSpeech();
        if (m.schedule) this.body.schedule(m.schedule, m.lead ?? 0.05, true);
        if (m.artic) this.body.artic(m.artic, m.keys);
        if (m.source) this.body.source(m.source);
        if (m.gate !== undefined) this.body.gate(m.gate);
      } catch (err) {
        this.fail(err);
      }
    };
    this.port.postMessage({ type: "ready", sampleRate });
  }

  fail(err) {
    this.failed = true;
    this.port.postMessage({ type: "error", message: String(err) });
  }

  process(_in, outputs) {
    const ch = outputs[0] && outputs[0][0];
    if (!ch) return true;
    if (this.failed) {
      ch.fill(0);
      return true;
    }
    const t0 = Date.now();
    try {
      ch.set(this.body.render(ch.length));
    } catch (err) {
      ch.fill(0);
      this.fail(err);
      return true;
    }
    const budget = (ch.length / sampleRate) * 1000;
    this.load += 0.05 * ((Date.now() - t0) / budget - this.load);
    if (++this.blocks % 6 === 0) {
      try {
        this.port.postMessage(this.telemetry());
      } catch (err) {
        this.fail(err);
      }
    }
    return true;
  }

  /** the same telemetry message CHIMERA's own processor posts, so its renderer can read it */
  telemetry() {
    const x = this.body.x, h = this.body.h, mem = x.memory.buffer;
    const p = x.engine_telemetry(h);
    const head = new Float64Array(mem, p, 16);
    const [phLen, orLen, velumPort, f0, voicing, pLung, outRms, noiseLevel, noiseNode, gate, clock, nArtic, nPh, nOr, nScope] = head;
    const all = new Float64Array(mem, p, 16 + nArtic + 3 * (nPh + nOr) + 2 * nScope);
    let o = 16;
    const take = (n) => Float32Array.from(all.subarray(o, (o += n)));
    const artic = take(nArtic), phAreas = take(nPh), orAreas = take(nOr), pressureRms = take(nPh + nOr), flow = take(nPh + nOr), glottalArea = take(nScope), glottalFlow = take(nScope);
    return {
      type: "telemetry",
      t: { artic, phAreas, orAreas, phLen, orLen, pressureRms, flow, velumPort, glottalArea, glottalFlow, f0, voicing, pLung, outRms, noiseLevel, noiseNode, gate, clock, active: [] },
      load: this.load,
      body: { female: x.engine_body_female(h), child: x.engine_body_child(h) },
      nPh,
      nOr,
      beatStep: -1,
    };
  }
}

registerProcessor("chimera-body", BodyProcessor);
