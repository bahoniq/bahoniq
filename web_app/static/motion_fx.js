/* ==========================================================================
   BAHONIQ NEURAL UNIVERSE — 5-Layer Scene + Local Neural Halo + 1.5° 3D Tilt
   ========================================================================== */
(() => {
  const prefersReduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isFinePointer =
    window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  const isLowPower =
    (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) ||
    (navigator.deviceMemory && navigator.deviceMemory <= 4) ||
    window.innerWidth < 760;

  function initNeuralUniverse() {
    if (prefersReduced || isLowPower) return;
    if (document.getElementById("bahoniqUniverse")) return;

    const wrap = document.createElement("div");
    wrap.id = "bahoniqUniverse";
    wrap.setAttribute("aria-hidden", "true");

    const canvas = document.createElement("canvas");
    canvas.id = "bahoniqUniverseCanvas";
    const grain = document.createElement("div");
    grain.className = "bahoniq-grain";

    wrap.appendChild(canvas);
    wrap.appendChild(grain);
    document.body.prepend(wrap);

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = isLowPower ? 1 : Math.min(window.devicePixelRatio || 1, 1.5);
    let w = 1280;
    let h = 800;

    function resize() {
      w = window.innerWidth || document.documentElement.clientWidth || 1280;
      h = window.innerHeight || document.documentElement.clientHeight || 800;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    window.addEventListener("resize", resize);
    resize();

    // Курсор и сглаженный параллакс (3px, 7px, 10px)
    const mouse = { x: -999, y: -999, nx: 0.5, ny: 0.5, sx: 0.5, sy: 0.5 };
    let scrollMorph = 0;

    window.addEventListener("mousemove", (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.nx = e.clientX / Math.max(1, w);
      mouse.ny = e.clientY / Math.max(1, h);
    });

    window.addEventListener("mouseleave", () => {
      mouse.x = -999;
      mouse.y = -999;
    });

    const scrollTarget = document.querySelector(".content-body") || window;
    scrollTarget.addEventListener(
      "scroll",
      () => {
        const top =
          scrollTarget === window ? window.scrollY : scrollTarget.scrollTop;
        scrollMorph = top * 0.0015;
      },
      { passive: true }
    );

    // 1. Liquid Aurora облака с несовпадающими циклами 18s, 27s, 36s
    const auroraClouds = [
      { bx: 0.22, by: 0.26, rx: 0.14, ry: 0.11, period: 18000, phase: 0.4, size: 0.48, color: "0, 245, 212" },
      { bx: 0.78, by: 0.24, rx: 0.16, ry: 0.12, period: 27000, phase: 2.2, size: 0.52, color: "0, 184, 255" },
      { bx: 0.52, by: 0.76, rx: 0.15, ry: 0.13, period: 36000, phase: 4.1, size: 0.50, color: "83, 109, 254" },
      { bx: 0.82, by: 0.78, rx: 0.12, ry: 0.10, period: 27000, phase: 5.3, size: 0.44, color: "155, 92, 255" },
    ];

    // 2. Локальные нейронные узлы (вдвое слабее)
    const neuralNodes = [];
    const NODE_COUNT = isLowPower ? 14 : 24;
    for (let i = 0; i < NODE_COUNT; i++) {
      neuralNodes.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.2,
        vy: (Math.random() - 0.5) * 0.2,
        glow: 0,
      });
    }

    // 5. Digital Dust (сокращено на треть)
    const dust = [];
    const DUST_COUNT = isLowPower ? 14 : 26;
    for (let i = 0; i < DUST_COUNT; i++) {
      dust.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: 0.7 + Math.random() * 1.4,
        vy: 0.12 + Math.random() * 0.26,
        alpha: 0.15 + Math.random() * 0.35,
        violet: Math.random() > 0.55,
      });
    }

    const startTime = performance.now();
    let activePlanet = null;
    let nextPlanetAt = startTime + 2500;
    const comets = [];
    let nextCometAt = startTime + 2000;
    const rainDrops = [];
    const rainRipples = [];
    let nextRainAt = startTime + 4500;
    const dashboardView = document.getElementById("dashboardView");

    function scheduleNextComet(now) {
      nextCometAt = now + 10000 + Math.random() * 6000; // каждые 10–16 секунд
    }

    function spawnComet(now) {
      const fromRight = Math.random() > 0.35;
      const startX = fromRight ? w * (0.45 + Math.random() * 0.5) : w * (0.05 + Math.random() * 0.45);
      const startY = -20;
      const travelX = (fromRight ? -1 : 1) * (260 + Math.random() * 220);
      const travelY = h * (0.45 + Math.random() * 0.35);
      comets.push({
        startX,
        startY,
        travelX,
        travelY,
        tailLen: 150 + Math.random() * 90,
        born: now,
        duration: 1150 + Math.random() * 350,
      });
      scheduleNextComet(now);
    }

    function scheduleNextRain(now) {
      nextRainAt = now + 12000 + Math.random() * 6000; // каждые 12–18 секунд
    }

    function spawnRain(now) {
      const dropCount = isLowPower ? 4 : 6 + Math.floor(Math.random() * 4);
      for (let i = 0; i < dropCount; i++) {
        rainDrops.push({
          startX: w * (0.08 + Math.random() * 0.84),
          targetY: h * (0.18 + Math.random() * 0.68),
          slant: 10 + Math.random() * 14,
          born: now + i * (90 + Math.random() * 90),
          duration: 520 + Math.random() * 220,
        });
      }
      scheduleNextRain(now);
    }

    function renderFrame(now) {
      // Во внутренних модулях фон остаётся на месте, но тяжёлая отрисовка
      // приостанавливается: рабочие операции получают максимум ресурсов.
      const dashboardVisible = dashboardView && !dashboardView.classList.contains("hidden");
      if (!document.hidden && dashboardVisible) {
        const elapsed = now - startTime;
        const intro = Math.min(1, elapsed / 1800);
        const introEase = 1 - Math.pow(1 - intro, 3);

        mouse.sx += (mouse.nx - mouse.sx) * 0.05;
        mouse.sy += (mouse.ny - mouse.sy) * 0.05;

        const px3x = (mouse.sx - 0.5) * 6;
        const px3y = (mouse.sy - 0.5) * 6;
        const px7x = (mouse.sx - 0.5) * 14;
        const px7y = (mouse.sy - 0.5) * 14;
        const px10x = (mouse.sx - 0.5) * 20;
        const px10y = (mouse.sy - 0.5) * 20;

        ctx.clearRect(0, 0, w, h);
        const maxDim = Math.max(w, h);
        const isViolet = document.body.classList.contains("theme-day");

        // Слой 3: Приглушённое ядро (-30%)
        const corePulse = 0.5 + 0.5 * Math.sin(now * 0.0009);
        const coreX = w * 0.55 + px3x;
        const coreY = h * 0.48 + px3y;
        const coreGrad = ctx.createRadialGradient(coreX, coreY, 0, coreX, coreY, maxDim * 0.36);
        const coreRgb = isViolet ? "139, 92, 246" : "0, 184, 255";
        coreGrad.addColorStop(0, `rgba(${coreRgb}, ${(0.038 + corePulse * 0.02) * introEase})`);
        coreGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = coreGrad;
        ctx.fillRect(0, 0, w, h);

        // Слой 1: Приглушённые облака (-30%, Violet остаётся тёмным)
        auroraClouds.forEach((cloud, idx) => {
          const angle = (now / cloud.period) * Math.PI * 2 + cloud.phase + scrollMorph;
          const targetX = (cloud.bx + Math.sin(angle) * cloud.rx) * w + px7x;
          const targetY = (cloud.by + Math.cos(angle * 0.85) * cloud.ry) * h + px7y;
          const cx = w * 0.5 + (targetX - w * 0.5) * introEase;
          const cy = h * 0.5 + (targetY - h * 0.5) * introEase;
          const rad = maxDim * cloud.size * (0.4 + 0.6 * introEase);

          const rgb = isViolet ? (idx % 2 === 0 ? "139, 92, 246" : "83, 109, 254") : cloud.color;
          const intensity = isViolet ? 0.055 : 0.075;
          const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
          g.addColorStop(0, `rgba(${rgb}, ${intensity * introEase})`);
          g.addColorStop(0.5, `rgba(${rgb}, ${(intensity * 0.32) * introEase})`);
          g.addColorStop(1, `rgba(${rgb}, 0)`);

          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(cx, cy, rad, 0, Math.PI * 2);
          ctx.fill();
        });

        // Сетка почти скрыта (0.014)
        if (!isLowPower) {
          const step = 84;
          ctx.strokeStyle = `rgba(${isViolet ? "139, 92, 246" : "0, 184, 255"}, 0.014)`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          for (let x = -step; x < w + step; x += step) {
            const warp = Math.sin(x * 0.004 + now * 0.0004) * 5;
            ctx.moveTo(x + px10x, 0);
            ctx.quadraticCurveTo(x + px10x + warp, h * 0.5, x + px10x, h);
          }
          for (let y = -step; y < h + step; y += step) {
            ctx.moveTo(0, y + px10y);
            ctx.lineTo(w, y + px10y);
          }
          ctx.stroke();
        }

        // Фирменная пасхалка: полупрозрачная планета с тонким кольцом (сразу при старте, далее 3–5 мин, вне зоны заголовка)
        if (!prefersReduced && !activePlanet && now >= nextPlanetAt && w >= 640) {
          activePlanet = {
            startX: -50,
            endX: w + 60,
            y: Math.max(76, h * 0.11),
            r: 26 + Math.random() * 6, // 52–64 px диаметр
            born: now,
            duration: 24000,
          };
          nextPlanetAt = now + 180000 + Math.random() * 120000;
        }
        if (activePlanet) {
          const pp = (now - activePlanet.born) / activePlanet.duration;
          if (pp >= 1) {
            activePlanet = null;
          } else {
            const px = activePlanet.startX + (activePlanet.endX - activePlanet.startX) * pp;
            const pa = Math.sin(Math.PI * pp) * 0.14;
            const prgb = isViolet ? "167, 139, 250" : "0, 229, 255";
            const pg = ctx.createRadialGradient(
              px - activePlanet.r * 0.3,
              activePlanet.y - activePlanet.r * 0.3,
              1.5,
              px,
              activePlanet.y,
              activePlanet.r
            );
            pg.addColorStop(0, `rgba(240, 248, 255, ${pa.toFixed(3)})`);
            pg.addColorStop(0.7, `rgba(${prgb}, ${(pa * 0.72).toFixed(3)})`);
            pg.addColorStop(1, "rgba(0, 0, 0, 0)");
            ctx.fillStyle = pg;
            ctx.beginPath();
            ctx.arc(px, activePlanet.y, activePlanet.r, 0, Math.PI * 2);
            ctx.fill();

            ctx.save();
            ctx.translate(px, activePlanet.y);
            ctx.rotate(-0.26);
            ctx.scale(1, 0.28);
            ctx.beginPath();
            ctx.arc(0, 0, activePlanet.r * 1.65, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(${prgb}, ${(pa * 0.75).toFixed(3)})`;
            ctx.lineWidth = 1.3;
            ctx.stroke();
            ctx.restore();
          }
        }

        // Атмосферный дождь с мягкой рябью
        if (!prefersReduced && now >= nextRainAt) spawnRain(now);

        for (let i = rainDrops.length - 1; i >= 0; i--) {
          const drop = rainDrops[i];
          if (now < drop.born) continue;
          const p = Math.min(1, (now - drop.born) / drop.duration);
          const eased = p * p;
          const x = drop.startX + drop.slant * eased;
          const y = -24 + (drop.targetY + 24) * eased;
          const rainRgb = isViolet ? "217, 112, 255" : "75, 226, 255";

          ctx.beginPath();
          ctx.moveTo(x - 4, y - 16);
          ctx.lineTo(x, y);
          ctx.strokeStyle = `rgba(${rainRgb}, ${Math.sin(Math.PI * p) * 0.34})`;
          ctx.lineWidth = 1.1;
          ctx.stroke();

          if (p >= 1) {
            rainRipples.push({ x, y: drop.targetY, born: now, life: 1550 });
            rainDrops.splice(i, 1);
          }
        }

        for (let i = rainRipples.length - 1; i >= 0; i--) {
          const ripple = rainRipples[i];
          const p = (now - ripple.born) / ripple.life;
          if (p >= 1) {
            rainRipples.splice(i, 1);
            continue;
          }
          const easeOut = 1 - Math.pow(1 - p, 3);
          const radius = 4 + easeOut * 44;
          const rippleRgb = isViolet ? "217, 112, 255" : "0, 224, 255";
          ctx.save();
          ctx.translate(ripple.x, ripple.y);
          ctx.scale(1, 0.52);
          ctx.beginPath();
          ctx.arc(0, 0, radius, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${rippleRgb}, ${(1 - p) * 0.34})`;
          ctx.lineWidth = 1.15;
          ctx.stroke();
          ctx.restore();
        }

        // Редкая космическая комета
        if (!prefersReduced && now >= nextCometAt) spawnComet(now);

        for (let i = comets.length - 1; i >= 0; i--) {
          const c = comets[i];
          const p = (now - c.born) / c.duration;
          if (p >= 1) {
            comets.splice(i, 1);
            continue;
          }

          const eased = 1 - Math.pow(1 - p, 2);
          const hx = c.startX + c.travelX * eased;
          const hy = c.startY + c.travelY * eased;
          const len = Math.hypot(c.travelX, c.travelY) || 1;
          const ux = c.travelX / len;
          const uy = c.travelY / len;
          const tail = c.tailLen * Math.sin(Math.PI * p);
          const tx = hx - ux * tail;
          const ty = hy - uy * tail;
          const alpha = Math.sin(Math.PI * p);

          const headRgb = isViolet ? "232, 160, 255" : "180, 255, 245";
          const tailRgb = isViolet ? "155, 92, 255" : "0, 210, 255";

          const grad = ctx.createLinearGradient(tx, ty, hx, hy);
          grad.addColorStop(0, `rgba(${tailRgb}, 0)`);
          grad.addColorStop(0.65, `rgba(${tailRgb}, ${(alpha * 0.35).toFixed(3)})`);
          grad.addColorStop(1, `rgba(${headRgb}, ${(alpha * 0.85).toFixed(3)})`);

          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.6;
          ctx.lineCap = "round";
          ctx.beginPath();
          ctx.moveTo(tx, ty);
          ctx.lineTo(hx, hy);
          ctx.stroke();

          ctx.save();
          ctx.shadowColor = `rgba(${headRgb}, 0.95)`;
          ctx.shadowBlur = 11;
          ctx.beginPath();
          ctx.arc(hx, hy, 2.1, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${headRgb}, ${(alpha * 0.95).toFixed(3)})`;
          ctx.fill();
          ctx.restore();
        }

        // Слой 2: Локальный Neural Constellation вокруг курсора (радиус 320px, затухание 1.2s)
        if (mouse.x > 0) {
          const halo = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, 320);
          halo.addColorStop(0, `rgba(${isViolet ? "155, 92, 255" : "0, 245, 212"}, 0.08)`);
          halo.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = halo;
          ctx.beginPath();
          ctx.arc(mouse.x, mouse.y, 320, 0, Math.PI * 2);
          ctx.fill();
        }

        for (let i = 0; i < neuralNodes.length; i++) {
          const n = neuralNodes[i];
          n.x += n.vx;
          n.y += n.vy;
          if (n.x < 0 || n.x > w) n.vx *= -1;
          if (n.y < 0 || n.y > h) n.vy *= -1;

          const distCursor = mouse.x > 0 ? Math.hypot(mouse.x - n.x, mouse.y - n.y) : 9999;
          if (distCursor < 320) {
            n.glow = Math.min(1, n.glow + 0.08);
          } else {
            n.glow = Math.max(0, n.glow - 0.014); // затухание ~1.2с
          }

          if (n.glow > 0.02) {
            for (let j = i + 1; j < neuralNodes.length; j++) {
              const m = neuralNodes[j];
              if (m.glow <= 0.02) continue;
              const d = Math.hypot(n.x - m.x, n.y - m.y);
              if (d < 170) {
                const a = Math.min(n.glow, m.glow) * (1 - d / 170) * 0.16;
                ctx.beginPath();
                ctx.moveTo(n.x, n.y);
                ctx.lineTo(m.x, m.y);
                ctx.strokeStyle = `rgba(${isViolet ? "155, 92, 255" : "0, 245, 212"}, ${a.toFixed(3)})`;
                ctx.lineWidth = 0.85;
                ctx.stroke();
              }
            }

            ctx.beginPath();
            ctx.arc(n.x, n.y, 1.5, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${isViolet ? "217, 70, 239" : "0, 245, 212"}, ${(n.glow * 0.36).toFixed(3)})`;
            ctx.fill();
          }
        }

        // Светящийся центр реакции: пользователь всегда видит, где именно
        // фон «чувствует» курсор. Это часть сцены, а не замена системного указателя.
        if (mouse.x > 0 && isFinePointer) {
          const cursorPulse = 0.5 + 0.5 * Math.sin(now * 0.006);
          const cursorRgb = isViolet ? "217, 112, 255" : "0, 245, 212";

          ctx.save();
          ctx.shadowColor = `rgba(${cursorRgb}, 0.95)`;
          ctx.shadowBlur = 9 + cursorPulse * 3;
          ctx.beginPath();
          ctx.arc(mouse.x, mouse.y, 2.2 + cursorPulse * 0.4, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${cursorRgb}, ${0.86 + cursorPulse * 0.10})`;
          ctx.fill();
          ctx.restore();
        }

        // Слой 5: Digital Dust (микрочастицы, медленно поднимающиеся вверх)
        for (let i = 0; i < dust.length; i++) {
          const d = dust[i];
          d.y -= d.vy;
          if (d.y < -4) {
            d.y = h + 4;
            d.x = Math.random() * w;
          }
          ctx.beginPath();
          ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
          const dc = d.violet ? "155, 92, 255" : "0, 245, 212";
          ctx.fillStyle = `rgba(${dc}, ${d.alpha})`;
          ctx.fill();
        }
      }

      if (!prefersReduced && document.body.classList.contains("universe-fx-on")) {
        requestAnimationFrame(renderFrame);
      }
    }

    requestAnimationFrame(renderFrame);
  }

  // Плавный 3D-наклон (макс 1.5°) + подъём 6px + световое пятно
  function initCardTilt() {
    if (!isFinePointer || prefersReduced) return;
    document.querySelectorAll("#dashboardView .tool-tile").forEach((tile) => {
      tile.addEventListener("mousemove", (e) => {
        const rect = tile.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        tile.style.setProperty("--mx", `${x}px`);
        tile.style.setProperty("--my", `${y}px`);
        tile.style.setProperty("--mouse-x", `${x}px`);
        tile.style.setProperty("--mouse-y", `${y}px`);

        const rotY = (x / rect.width - 0.5) * 4.0;
        const rotX = -(y / rect.height - 0.5) * 4.0;
        tile.style.transition = "transform 0.06s linear, border-color 0.22s ease, box-shadow 0.28s ease";
        tile.style.transform = `perspective(1000px) translateY(-6px) rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg)`;
      });

      tile.addEventListener("mouseleave", () => {
        tile.style.transition = "";
        tile.style.transform = "";
      });
    });
  }

  // Каскад карточек 50мс после splash и при возврате на главную
  function runCascade() {
    if (prefersReduced) return;
    const tiles = document.querySelectorAll("#dashboardView .tool-tile");
    tiles.forEach((tile) => tile.classList.remove("fx-cascade"));
    void document.body.offsetWidth;
    tiles.forEach((tile, idx) => {
      tile.style.animationDelay = `${idx * 50}ms`;
      tile.classList.add("fx-cascade");
    });
  }

  function initCascade() {
    if (prefersReduced) return;
    const splash = document.getElementById("webSplash");
    if (splash && !splash.classList.contains("hidden")) {
      const splashObs = new MutationObserver(() => {
        if (splash.classList.contains("hidden") || getComputedStyle(splash).opacity === "0") {
          splashObs.disconnect();
          runCascade();
        }
      });
      splashObs.observe(splash, { attributes: true, attributeFilter: ["class", "style"] });
      setTimeout(runCascade, 750);
    } else {
      runCascade();
    }

    const dash = document.getElementById("dashboardView");
    if (dash) {
      let wasHidden = dash.classList.contains("hidden");
      const dashObs = new MutationObserver(() => {
        const isHidden = dash.classList.contains("hidden");
        if (wasHidden && !isHidden) runCascade();
        wasHidden = isHidden;
      });
      dashObs.observe(dash, { attributes: true, attributeFilter: ["class"] });
    }
  }

  function enableUniverseMode() {
    document.body.classList.add("universe-fx-on");
    initNeuralUniverse();
  }

  function disableUniverseMode() {
    document.body.classList.remove("universe-fx-on");
    const u = document.getElementById("bahoniqUniverse");
    if (u) u.remove();
  }

  function boot() {
    localStorage.removeItem("bahoniq_universe_fx");
    enableUniverseMode();
  }

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
