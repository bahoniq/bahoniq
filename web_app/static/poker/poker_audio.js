/* Звуки и мягкая фоновая клубная музыка Poker Club (Web Audio API, полностью офлайн). */
window.PokerAudio = (function () {
  let ctx = null, master = null, musicGain = null, noiseBuf = null;
  let enabled = true, musicEnabled = false, musicTimer = null, chordStep = 0, voices = 0;
  const lastPlayed = {};

  // Мягкая джазовая прогрессия (Dm9 -> G13 -> Cmaj9 -> A7alt)
  const CHORDS = [
    [146.83, 261.63, 329.63, 349.23, 440.00],
    [98.00,  246.94, 293.66, 329.63, 440.00],
    [130.81, 246.94, 293.66, 329.63, 392.00],
    [110.00, 207.65, 261.63, 329.63, 392.00],
  ];

  function ensure() {
    if (!ctx) {
      try {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        master = ctx.createGain();
        master.gain.value = 0.55;
        master.connect(ctx.destination);

        musicGain = ctx.createGain();
        musicGain.gain.value = 0.38;
        musicGain.connect(ctx.destination);

        noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
        const d = noiseBuf.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      } catch (e) { ctx = null; }
    }
    if (ctx && ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function playLoungeBar() {
    if (!musicEnabled || !ensure() || !musicGain) return;
    const notes = CHORDS[chordStep % CHORDS.length];
    chordStep++;
    const now = ctx.currentTime;

    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const filt = ctx.createBiquadFilter();
      const g = ctx.createGain();
      osc.type = idx === 0 ? 'triangle' : 'sine';
      osc.frequency.value = freq;

      filt.type = 'lowpass';
      filt.frequency.value = idx === 0 ? 320 : 950;

      const t0 = now + idx * 0.06;
      const peak = idx === 0 ? 0.24 : 0.085;
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.linearRampToValueAtTime(peak, t0 + 0.18);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 3.6);

      osc.connect(filt); filt.connect(g); g.connect(musicGain);
      osc.start(t0);
      osc.stop(t0 + 3.7);
    });
  }

  function startMusicLoop() {
    if (musicTimer) return;
    playLoungeBar();
    musicTimer = setInterval(playLoungeBar, 3800);
  }

  function stopMusicLoop() {
    if (musicTimer) {
      clearInterval(musicTimer);
      musicTimer = null;
    }
  }

  function env(g, t, peak, dur, attack) {
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(peak, t + (attack || 0.004));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  }

  function noise(when, dur, freq, q, peak, type) {
    const t = ctx.currentTime + when;
    const src = ctx.createBufferSource(); src.buffer = noiseBuf; src.loop = true;
    const f = ctx.createBiquadFilter(); f.type = type || 'bandpass'; f.frequency.value = freq; f.Q.value = q;
    const g = ctx.createGain(); env(g, t, peak, dur);
    src.connect(f); f.connect(g); g.connect(master);
    voices++; src.onended = () => { voices--; };
    src.start(t, Math.random() * 0.5); src.stop(t + dur + 0.02);
  }

  function tone(when, freq, dur, peak, type) {
    const t = ctx.currentTime + when;
    const o = ctx.createOscillator(); o.type = type || 'sine'; o.frequency.value = freq;
    const g = ctx.createGain(); env(g, t, peak, dur, 0.006);
    o.connect(g); g.connect(master);
    voices++; o.onended = () => { voices--; };
    o.start(t); o.stop(t + dur + 0.02);
  }

  const SOUNDS = {
    deal() { noise(0, 0.09, 3400, 0.9, 0.34); noise(0.02, 0.05, 6200, 1.2, 0.12); },
    chips() { for (let i = 0; i < 3; i++) { tone(i * 0.045, 2300 + i * 260, 0.07, 0.07, 'triangle'); noise(i * 0.045, 0.05, 4200, 2, 0.16); } },
    check() { tone(0, 170, 0.11, 0.30, 'sine'); tone(0.11, 150, 0.12, 0.26, 'sine'); },
    fold() { noise(0, 0.18, 1500, 0.7, 0.20, 'bandpass'); noise(0.04, 0.14, 700, 0.8, 0.12, 'lowpass'); },
    win() { [392, 494, 587, 784].forEach((f, i) => tone(i * 0.09, f, 0.45, 0.10, 'triangle')); },
    click() { tone(0, 900, 0.04, 0.08, 'square'); },
  };

  return {
    setEnabled(v) { enabled = !!v; },
    isEnabled() { return enabled; },
    setMusicEnabled(v) {
      musicEnabled = !!v;
      if (musicEnabled) {
        const c = ensure();
        if (c && c.state === 'suspended') c.resume().then(() => { if (musicEnabled) startMusicLoop(); });
        else startMusicLoop();
      } else {
        stopMusicLoop();
      }
    },
    isMusicEnabled() { return musicEnabled; },
    unlock() {
      ensure();
      if (musicEnabled && !musicTimer) startMusicLoop();
    },
    play(name) {
      if (!enabled || !SOUNDS[name]) return;
      const now = performance.now();
      if (lastPlayed[name] && now - lastPlayed[name] < 55) return;
      if (voices > 14) return;
      lastPlayed[name] = now;
      if (!ensure()) return;
      try { SOUNDS[name](); } catch (e) {}
    },
  };
})();
