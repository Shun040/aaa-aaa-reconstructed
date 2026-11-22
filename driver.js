// AAA-AAA (1978) — model reconstruction. Maps the analysed score (score.json) to CHIMERA controls.
// Plain script: used by the Node renderer and the browser page alike.
// Sound engine: CHIMERA by Jameson Hodge (MIT).

globalThis.AAA = (function () {
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (x) => x * x * (3 - 2 * x);

  /** sample a 25 Hz score array at time t (s), linear */
  function at(arr, fps, t) {
    const x = t * fps;
    const i = Math.floor(x);
    if (i < 0) return arr[0];
    if (i >= arr.length - 1) return arr[arr.length - 1];
    const f = x - i;
    return arr[i] * (1 - f) + arr[i + 1] * f;
  }

  // tuning, fitted against the recording (see fit notes in README)
  const TUNE = {
    pressure: [11, 17, 5], // base, × effort, × progress (cmH2O)
    gateFloor: 0.55,
  };

  /**
   * Controls for one voice ("U" Ulay, "M" Marina) at time t.
   * vowels: catalog vowels for that body ({a, ɑ, ə}); keys: articulator key order.
   */
  function controls(score, who, t, vowels) {
    const fps = score.fps;
    const act = at(score.active, fps, t);
    const e = at(score.effort, fps, t);
    const v = at(score[who].voiced, fps, t);
    const f0 = at(score[who].f0, fps, t);
    const p = clamp((t - score.span[0]) / (score.span[1] - score.span[0]), 0, 1);
    const on = act > 0.5;
    // between cries the mouth shuts and the breath comes in through the nose.
    // c: how closed the mouth is, ramping ~0.15 s around each phrase edge (it opens just before the cry)
    let open = 0;
    for (const d of [-0.12, -0.06, 0, 0.06, 0.12, 0.18, 0.24]) open += at(score.active, fps, t + d) > 0.5 ? 1 : 0;
    const gapness = smooth(clamp(1 - open / 4, 0, 1));
    // from the film: in the first breaths they shut their mouths to breathe in; by ~1:50 they
    // gasp through the open mouth instead
    const shut = 1 - smooth(clamp((t - 55) / 55, 0, 1));
    const c = gapness * shut;
    const gasp = gapness * (1 - shut);

    const source = {
      f0,
      glide: 0.03,
      pressure: TUNE.pressure[0] + TUNE.pressure[1] * e + TUNE.pressure[2] * p,
      tension: who === "M" ? clamp(0.5 - 0.15 * e, 0, 1) : clamp(0.55 + 0.35 * e, 0, 1),
      breathiness: clamp(0.08 + 0.45 * (1 - v) + 0.15 * p, 0, 1),
      roughness: clamp(0.12 + 0.4 * p + 0.3 * (1 - v), 0, 1),
      fry: 0,
      vibratoDepth: 0,
      drift: 6 + 14 * p,
      voiced: v > 0.08,
      brightness: clamp(0.15 + 0.75 * e, 0, 1),
    };
    let gate = on ? TUNE.gateFloor + (1 - TUNE.gateFloor) * v : 0;
    if (!on) {
      // the in-breath: closed lips, open velum, air drawn in through the nose
      Object.assign(source, { pressure: -lerp(3, 6, p), voiced: false, breathiness: 1, roughness: 0.2, brightness: 0.1 });
      gate = t > score.span[0] - 1.2 && t < score.span[1] ? 0.22 * (c + gasp) : 0;
    }

    // the mouth: a wide open "a", opening further with effort and with time
    const base = vowels["a"].artic;
    const artic = Object.assign({}, base);
    artic.jaw = clamp((base.jaw ?? 1.5) + (who === "M" ? 0.15 : 0.5) * e + 0.35 * p, -0.2, 3);
    artic.lipAp = (base.lipAp ?? 2) + (who === "M" ? 0.2 : 0.6) * e;
    artic.lipWidth = (base.lipWidth ?? 1) + 0.3 * e;
    // close the mouth: jaw up, lips sealed, tongue at rest, velum lowered for nasal breathing
    if (c > 0) {
      const rest = vowels["ə"].artic;
      for (const k of Object.keys(rest)) if (artic[k] !== undefined) artic[k] = lerp(artic[k], rest[k], c);
      artic.jaw = lerp(artic.jaw, 0.12, c);
      artic.lipAp = lerp(artic.lipAp, -0.25, c);
      artic.lipProt = lerp(artic.lipProt ?? 0, 0.1, c);
      artic.velum = lerp(-0.15, 0.95, c);
    } else artic.velum = -0.15;
    // a gasp keeps the mouth open, a little less wide than the cry
    if (gasp > 0) artic.jaw = lerp(artic.jaw, artic.jaw * 0.6, gasp);
    return { source, gate, artic, on, closed: c, gasp };
  }

  /** where the two heads are: gap between the mouths (head-lengths) and camera zoom, from the video */
  // [time, gap between mouths (head-lengths), zoom]; zoom stays ≤ 1 so both heads are always whole
  const STAGING = [
    [0, 1.0, 0.8],
    [15, 1.0, 0.8],
    [85, 0.85, 0.8],
    [125, 0.6, 0.86],
    [150, 0.32, 0.93],
    [172, 0.06, 1.0],
    [573, 0.04, 1.0],
    [592, 0.04, 1.0],
  ];
  function staging(t) {
    let i = 0;
    while (i < STAGING.length - 2 && STAGING[i + 1][0] <= t) i++;
    const [t0, g0, z0] = STAGING[i], [t1, g1, z1] = STAGING[i + 1];
    const f = clamp((t - t0) / (t1 - t0), 0, 1);
    const s = f * f * (3 - 2 * f);
    return { gap: g0 + (g1 - g0) * s, zoom: z0 + (z1 - z0) * s };
  }

  // Marina reads the work's statement over the title card; her speech is CHIMERA's speech planner,
  // warped onto the word timings of the recording (intro_plan.json)
  const INTRO_END = 14.0;
  return { controls, staging, at, TUNE, INTRO_END };
})();
