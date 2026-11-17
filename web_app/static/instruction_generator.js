(() => {
  const $ = s => document.querySelector(s);
  const steps = $('#igSteps');
  if (!steps) return;
  let result = null;

  const TARGET_W = 1299;
  const TARGET_H = 623;
  const TARGET_ASPECT = TARGET_W / TARGET_H; // ~2.085072

  const escapeHtml = s => String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[c]));

  const renumber = () => [...steps.children].forEach((card, i) => {
    const titleEl = card.querySelector('.ig-step-title');
    if (titleEl) titleEl.textContent = `Этап ${i + 1}`;
    card.dataset.stepIndex = String(i + 1);
    const updatePreviewCap = card._updateLivePreviewCaption;
    if (typeof updatePreviewCap === 'function') updatePreviewCap();
  });

  // Modal validation dialog for SalemHR Gold Standard
  function showValidationDialog(warnings, onProceed) {
    const existing = document.querySelector('.ig-modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'ig-modal-overlay';
    overlay.innerHTML = `
      <div class="ig-modal">
        <div class="ig-modal-head">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#facc15" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <h3>Проверка золотого стандарта SalemHR</h3>
        </div>
        <div class="ig-modal-desc">
          Обнаружены несоответствия стандарту оформления скриншотов (золотой стандарт: 1299 × 623 px, ~2.08:1):
        </div>
        <ul class="ig-modal-list">
          ${warnings.map(w => `<li><strong>Этап ${w.step}:</strong> ${escapeHtml(w.message)}</li>`).join('')}
        </ul>
        <div class="ig-modal-actions">
          <button type="button" class="button secondary ig-btn-fix">✏️ Исправить</button>
          <button type="button" class="button primary ig-btn-proceed">🚀 Всё равно продолжить</button>
        </div>
      </div>
    `;

    overlay.querySelector('.ig-btn-fix').onclick = () => {
      overlay.remove();
      if (warnings.length > 0 && warnings[0].card) {
        warnings[0].card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        warnings[0].card.classList.add('ig-step-highlight');
        setTimeout(() => warnings[0].card.classList.remove('ig-step-highlight'), 2000);
      }
    };

    overlay.querySelector('.ig-btn-proceed').onclick = () => {
      overlay.remove();
      onProceed();
    };

    document.body.appendChild(overlay);
  }

  function validateSalemStandard(onProceed) {
    const stepCards = [...steps.children];
    const warnings = [];

    stepCards.forEach((card, idx) => {
      const stepNum = idx + 1;
      const dataVal = card.querySelector('.ig-data')?.value || '';
      if (!dataVal) return;

      const mode = card.dataset.mode || 'standard';
      const cropW = Number(card.dataset.cropW) || 0;
      const cropH = Number(card.dataset.cropH) || 0;
      const isNarrow = card.dataset.isNarrow === 'true';

      if (mode === 'standard') {
        if (cropW > 0 && (cropW < TARGET_W || cropH < TARGET_H)) {
          warnings.push({
            step: stepNum,
            card,
            message: `Разрешение кадра (${cropW} × ${cropH} px) ниже стандарта (требуется от 1299 × 623 px). Рекомендуется увеличить масштаб или загрузить снимок более высокого разрешения.`
          });
        }
        if (isNarrow) {
          warnings.push({
            step: stepNum,
            card,
            message: `Скриншот имеет вертикальный/узкий формат. Рекомендуется загрузить снимок полного окна браузера или переключить в режим «Компактное окно».`
          });
        }
      }
    });

    if (warnings.length > 0) {
      showValidationDialog(warnings, onProceed);
    } else {
      onProceed();
    }
  }

  function addStep(data = {}) {
    const card = document.createElement('article');
    card.className = 'ig-step card';
    card.dataset.mode = 'standard';
    card.innerHTML = `
      <div class="ig-step-head">
        <strong class="ig-step-title">Этап</strong>
        <div class="ig-step-btns">
          <button type="button" class="button secondary ig-up" title="Переместить вверх">↑</button>
          <button type="button" class="button secondary ig-down" title="Переместить вниз">↓</button>
          <button type="button" class="button danger ig-delete" title="Удалить этап">Удалить</button>
        </div>
      </div>
      <label>
        Действие своими словами
        <textarea class="ig-text" rows="3" placeholder="Например: переходим во вкладку Заявки, выбираем нужного студента и нажимаем кнопку Подтвердить..."></textarea>
      </label>
      <label>
        Подпись к скриншоту
        <input class="ig-caption" placeholder="Например: Вкладка «Заявки» и выбор студента">
      </label>
      <label class="file-drop ig-drop">
        <input class="ig-image" type="file" accept="image/png,image/jpeg,image/webp">
        <span class="file-title">Прикрепите скриншот (или вставьте через Ctrl+V)</span>
        <small class="ig-file-name">Золотое правило: снимок полного рабочего окна браузера/программы (1299 × 623 px)</small>
      </label>
      <div class="ig-editor-zone"></div>
      <textarea class="ig-data hidden"></textarea>
    `;

    const textEl = card.querySelector('.ig-text');
    const captionEl = card.querySelector('.ig-caption');
    const dropEl = card.querySelector('.ig-drop');
    const fileInput = card.querySelector('.ig-image');
    const editorZone = card.querySelector('.ig-editor-zone');
    const dataEl = card.querySelector('.ig-data');

    textEl.value = data.text || '';
    captionEl.value = data.caption || '';

    let currentImg = null;
    let originalDataUrl = null;

    function getCaptionText() {
      const cap = captionEl.value.trim();
      if (cap) return cap;
      const txt = textEl.value.trim();
      if (txt) {
        const words = txt.split(/\s+/).slice(0, 5).join(' ');
        return words.charAt(0).toUpperCase() + words.slice(1);
      }
      const num = card.dataset.stepIndex || '1';
      return `Действие этапа ${num}`;
    }

    card._updateLivePreviewCaption = () => {
      const liveCap = card.querySelector('.ig-live-preview-caption');
      if (liveCap) {
        const num = card.dataset.stepIndex || '1';
        liveCap.innerHTML = `<b>Рисунок ${num}.</b> ${escapeHtml(getCaptionText())}`;
      }
    };

    captionEl.oninput = card._updateLivePreviewCaption;
    textEl.oninput = card._updateLivePreviewCaption;

    function setupEditor(imgSrc) {
      originalDataUrl = imgSrc;
      const img = new Image();
      img.onload = () => {
        currentImg = img;
        renderEditor();
      };
      img.src = imgSrc;
    }

    function renderEditor() {
      if (!currentImg) return;
      dropEl.classList.add('hidden');

      const origW = currentImg.naturalWidth;
      const origH = currentImg.naturalHeight;
      const srcAspect = origW / origH;
      const isNarrow = srcAspect < 1.4 || origH > origW;
      card.dataset.isNarrow = String(isNarrow);

      editorZone.innerHTML = `
        <div class="ig-cropper-card">
          <div class="ig-mode-bar">
            <div class="ig-mode-group">
              <button type="button" class="ig-mode-btn ig-mode-standard active" title="Стандартное соотношение 1299:623 (16,5 × 7,9 см в PDF)">💎 Золотой стандарт SalemHR (1299×623)</button>
              <button type="button" class="ig-mode-btn ig-mode-compact" title="Для небольших диалоговых окон">🪟 Компактное окно</button>
            </div>
            <div class="ig-tool-actions">
              <button type="button" class="button secondary ig-btn-replace" title="Загрузить другой снимок">🔄 Заменить скриншот</button>
            </div>
          </div>

          <div class="ig-badge-container"></div>

          <!-- Standard Cropper Viewport -->
          <div class="ig-viewport-wrap">
            <canvas class="ig-cropper-canvas"></canvas>
            <div class="ig-viewport-hint">Перетаскивайте кадр мышью</div>
          </div>

          <!-- Compact Viewport (hidden by default) -->
          <div class="ig-compact-wrap hidden">
            <img class="ig-compact-img" src="${originalDataUrl}" alt="Компактный скриншот">
          </div>

          <!-- Cropper Toolbar -->
          <div class="ig-toolbar">
            <div class="ig-zoom-group">
              <button type="button" class="ig-zoom-btn ig-zoom-out" title="Уменьшить">−</button>
              <input type="range" class="ig-zoom-slider" min="1.0" max="3.5" step="0.01" value="1.0">
              <button type="button" class="ig-zoom-btn ig-zoom-in" title="Увеличить">+</button>
              <span class="ig-zoom-val">100%</span>
            </div>
            <div class="ig-tool-actions">
              <button type="button" class="button secondary ig-btn-reset" title="Сбросить центрирование">↺ Центрировать</button>
            </div>
          </div>

          <!-- Live PDF Preview -->
          <div class="ig-live-preview-box">
            <div class="ig-live-preview-title">
              <span>Предпросмотр в PDF (16,5 × 7,9 см)</span>
              <span class="ig-live-preview-target">Стандарт SalemHR</span>
            </div>
            <div class="ig-live-preview-container">
              <div class="ig-live-preview-frame standard">
                <img class="ig-live-preview-img" alt="Предпросмотр">
              </div>
            </div>
            <div class="ig-live-preview-caption"><b>Рисунок ${card.dataset.stepIndex || 1}.</b> ${escapeHtml(getCaptionText())}</div>
          </div>
        </div>
      `;

      const btnStandard = editorZone.querySelector('.ig-mode-standard');
      const btnCompact = editorZone.querySelector('.ig-mode-compact');
      const btnReplace = editorZone.querySelector('.ig-btn-replace');
      const btnReset = editorZone.querySelector('.ig-btn-reset');
      const btnZoomOut = editorZone.querySelector('.ig-zoom-out');
      const btnZoomIn = editorZone.querySelector('.ig-zoom-in');
      const zoomSlider = editorZone.querySelector('.ig-zoom-slider');
      const zoomVal = editorZone.querySelector('.ig-zoom-val');
      const badgeContainer = editorZone.querySelector('.ig-badge-container');
      const viewportWrap = editorZone.querySelector('.ig-viewport-wrap');
      const compactWrap = editorZone.querySelector('.ig-compact-wrap');
      const toolbar = editorZone.querySelector('.ig-toolbar');
      const canvas = editorZone.querySelector('.ig-cropper-canvas');
      const ctx = canvas.getContext('2d');
      const liveFrame = editorZone.querySelector('.ig-live-preview-frame');
      const liveImg = editorZone.querySelector('.ig-live-preview-img');
      const liveTarget = editorZone.querySelector('.ig-live-preview-target');

      let mode = 'standard';
      let zoom = 1.0;
      let offsetX = 0;
      let offsetY = 0;
      let isDragging = false;
      let dragStartX = 0, dragStartY = 0;
      let initOffX = 0, initOffY = 0;

      // Sizing canvas display width
      const containerWidth = Math.min(540, card.clientWidth - 48 || 480);
      const cw = containerWidth;
      const ch = Math.round(cw / TARGET_ASPECT);
      canvas.width = cw;
      canvas.height = ch;

      // Base scale so image fills (cw, ch) completely at zoom=1.0 without blank borders
      const scaleX = cw / origW;
      const scaleY = ch / origH;
      const baseScale = Math.max(scaleX, scaleY);

      function centerOffsets(z) {
        const curScale = baseScale * z;
        const dw = origW * curScale;
        const dh = origH * curScale;
        offsetX = (cw - dw) / 2;
        offsetY = (ch - dh) / 2;
      }
      centerOffsets(zoom);

      function updateBadges(cropW, cropH) {
        let badgesHtml = '';
        if (mode === 'compact') {
          badgesHtml += `
            <div class="ig-badge ig-badge-compact">
              <span>⚠️ Отличается от золотого стандарта SalemHR (режим «Компактное окно»: отображается целиком без кадрирования)</span>
            </div>
          `;
        } else {
          if (isNarrow) {
            badgesHtml += `
              <div class="ig-badge ig-badge-warning">
                <span>⚠️ Скриншот не соответствует стандартному формату (соотношение значительно меньше 2.08:1). Рекомендуется загрузить снимок полного окна.</span>
              </div>
            `;
          }
          if (cropW < TARGET_W || cropH < TARGET_H) {
            badgesHtml += `
              <div class="ig-badge ig-badge-warning">
                <span>⚠️ Разрешение кадра: ${cropW} × ${cropH} px (ниже минимального стандарта 1299 × 623 px).</span>
              </div>
            `;
          } else {
            badgesHtml += `
              <div class="ig-badge ig-badge-success">
                <span>✓ Золотой стандарт SalemHR: ${cropW} × ${cropH} px (целевой формат 1299:623 выполнен)</span>
              </div>
            `;
          }
        }
        badgeContainer.innerHTML = badgesHtml;
      }

      function updateOutput() {
        if (mode === 'compact') {
          dataEl.value = originalDataUrl;
          card.dataset.mode = 'compact';
          card.dataset.cropW = String(origW);
          card.dataset.cropH = String(origH);
          liveFrame.className = 'ig-live-preview-frame compact';
          liveImg.src = originalDataUrl;
          liveTarget.textContent = 'Компактное окно';
          updateBadges(origW, origH);
          return;
        }

        // Standard SalemHR Mode:
        card.dataset.mode = 'standard';
        liveFrame.className = 'ig-live-preview-frame standard';
        liveTarget.textContent = 'Стандарт SalemHR';

        const curScale = baseScale * zoom;
        const dw = origW * curScale;
        const dh = origH * curScale;

        // Strictly bound offsets so NO background or whitespace is exposed
        const minX = cw - dw;
        const minY = ch - dh;
        offsetX = Math.min(0, Math.max(minX, offsetX));
        offsetY = Math.min(0, Math.max(minY, offsetY));

        // Draw in viewport canvas
        ctx.clearRect(0, 0, cw, ch);
        ctx.drawImage(currentImg, offsetX, offsetY, dw, dh);

        // Calculate source rectangle in original image coordinates
        const cropX = -offsetX / curScale;
        const cropY = -offsetY / curScale;
        const cropW = cw / curScale;
        const cropH = ch / curScale;

        const roundedCropW = Math.round(cropW);
        const roundedCropH = Math.round(cropH);
        card.dataset.cropW = String(roundedCropW);
        card.dataset.cropH = String(roundedCropH);

        // Generate full export canvas (at least 1299 x 623 px)
        const expW = Math.max(TARGET_W, roundedCropW);
        const expH = Math.round(expW / TARGET_ASPECT);

        const expCanvas = document.createElement('canvas');
        expCanvas.width = expW;
        expCanvas.height = expH;
        const expCtx = expCanvas.getContext('2d');
        expCtx.drawImage(currentImg, cropX, cropY, cropW, cropH, 0, 0, expW, expH);

        const expData = expCanvas.toDataURL('image/png');
        dataEl.value = expData;
        liveImg.src = expData;

        zoomSlider.value = zoom.toFixed(2);
        zoomVal.textContent = `${Math.round(zoom * 100)}%`;
        updateBadges(roundedCropW, roundedCropH);
      }

      function setZoom(newZoom, pivotClientX, pivotClientY) {
        newZoom = Math.min(3.5, Math.max(1.0, newZoom));
        if (Math.abs(newZoom - zoom) < 0.001) return;

        const rect = canvas.getBoundingClientRect();
        const pivotX = (pivotClientX !== undefined ? (pivotClientX - rect.left) : cw / 2);
        const pivotY = (pivotClientY !== undefined ? (pivotClientY - rect.top) : ch / 2);

        const oldScale = baseScale * zoom;
        const newScale = baseScale * newZoom;

        // Keep point under cursor stationary
        const imgX = (pivotX - offsetX) / oldScale;
        const imgY = (pivotY - offsetY) / oldScale;

        offsetX = pivotX - imgX * newScale;
        offsetY = pivotY - imgY * newScale;
        zoom = newZoom;

        updateOutput();
      }

      // Drag / Pan interaction
      canvas.addEventListener('mousedown', e => {
        isDragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        initOffX = offsetX;
        initOffY = offsetY;
        canvas.classList.add('grabbing');
      });

      window.addEventListener('mousemove', e => {
        if (!isDragging) return;
        offsetX = initOffX + (e.clientX - dragStartX);
        offsetY = initOffY + (e.clientY - dragStartY);
        updateOutput();
      });

      window.addEventListener('mouseup', () => {
        if (isDragging) {
          isDragging = false;
          canvas.classList.remove('grabbing');
        }
      });

      // Touch events for mobile/tablet
      canvas.addEventListener('touchstart', e => {
        if (e.touches.length === 1) {
          isDragging = true;
          dragStartX = e.touches[0].clientX;
          dragStartY = e.touches[0].clientY;
          initOffX = offsetX;
          initOffY = offsetY;
        }
      }, { passive: true });

      canvas.addEventListener('touchmove', e => {
        if (isDragging && e.touches.length === 1) {
          offsetX = initOffX + (e.touches[0].clientX - dragStartX);
          offsetY = initOffY + (e.touches[0].clientY - dragStartY);
          updateOutput();
        }
      }, { passive: true });

      canvas.addEventListener('touchend', () => {
        isDragging = false;
      });

      // Mouse wheel zoom
      canvas.addEventListener('wheel', e => {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 0.08 : -0.08;
        setZoom(zoom + delta, e.clientX, e.clientY);
      }, { passive: false });

      zoomSlider.oninput = () => {
        const val = parseFloat(zoomSlider.value);
        setZoom(val);
      };
      btnZoomIn.onclick = () => setZoom(zoom + 0.15);
      btnZoomOut.onclick = () => setZoom(zoom - 0.15);

      btnReset.onclick = () => {
        zoom = 1.0;
        centerOffsets(zoom);
        updateOutput();
      };

      // Switch to standard mode
      btnStandard.onclick = () => {
        mode = 'standard';
        btnStandard.classList.add('active');
        btnCompact.classList.remove('active');
        viewportWrap.classList.remove('hidden');
        toolbar.classList.remove('hidden');
        compactWrap.classList.add('hidden');
        updateOutput();
      };

      // Switch to compact mode
      btnCompact.onclick = () => {
        mode = 'compact';
        btnCompact.classList.add('active');
        btnStandard.classList.remove('active');
        viewportWrap.classList.add('hidden');
        toolbar.classList.add('hidden');
        compactWrap.classList.remove('hidden');
        updateOutput();
      };

      // Replace screenshot button
      btnReplace.onclick = () => {
        fileInput.value = '';
        fileInput.click();
      };

      updateOutput();
    }

    const setImage = (file) => {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        setupEditor(reader.result);
      };
      reader.readAsDataURL(file);
    };

    fileInput.onchange = e => {
      if (e.target.files && e.target.files[0]) {
        setImage(e.target.files[0]);
      }
    };

    card.addEventListener('paste', e => {
      const f = [...(e.clipboardData?.files || [])].find(x => x.type.startsWith('image/'));
      if (f) {
        e.preventDefault();
        e.stopPropagation();
        setImage(f);
      }
    });

    card.querySelector('.ig-delete').onclick = () => {
      if (steps.children.length > 1) card.remove();
      renumber();
    };
    card.querySelector('.ig-up').onclick = () => {
      if (card.previousElementSibling) steps.insertBefore(card, card.previousElementSibling);
      renumber();
    };
    card.querySelector('.ig-down').onclick = () => {
      if (card.nextElementSibling) steps.insertBefore(card.nextElementSibling, card);
      renumber();
    };

    steps.appendChild(card);
    renumber();

    if (data.image) {
      setupEditor(data.image);
    }
  }

  const payload = () => ({
    title: ($('#igTitle')?.value || '').trim() || 'Инструкция по работе с системой',
    audience: '',
    department: '',
    intro: '',
    steps: [...steps.children].map(c => ({
      text: c.querySelector('.ig-text').value.trim(),
      caption: c.querySelector('.ig-caption').value.trim(),
      image: c.querySelector('.ig-data').value,
      mode: c.dataset.mode || 'standard',
      width: Number(c.dataset.cropW) || null,
      height: Number(c.dataset.cropH) || null,
    }))
  });

  $('#igAdd').onclick = () => addStep();

  async function executeGenerate() {
    const btn = $('#igGenerate');
    const status = $('#igStatus');
    btn.disabled = true;
    status.textContent = 'ИИ анализирует этапы и составляет эталонную инструкцию…';

    try {
      const p = payload();
      const filledSteps = p.steps.filter(s => s.text || s.image);
      if (filledSteps.length === 0) {
        throw new Error('Пожалуйста, заполните хотя бы один этап (описание или скриншот)');
      }

      const r = await fetch('/api/instruction-generator/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(p)
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Ошибка генерации инструкции');

      result = d;
      render(d);
      status.textContent = `Готово · ${d.steps.length} этапов · Стандарт: SalemHR Gold Standard`;
    } catch (e) {
      status.textContent = '✕ Ошибка: ' + e.message;
    } finally {
      btn.disabled = false;
    }
  }

  $('#igGenerate').onclick = () => {
    validateSalemStandard(executeGenerate);
  };

  function render(d) {
    const preview = $('#igResult');
    const tocList = d.steps.map(s => `<li><span class="ig-toc-num">${s.number}.</span> <span class="ig-toc-cap">${escapeHtml(s.caption || ('Шаг ' + s.number))}</span></li>`).join('');

    const stepsHtml = d.steps.map(s => `
      <section class="ig-step-doc">
        <h2 class="ig-step-num-title">${s.number}. ${escapeHtml(s.caption || ('Шаг ' + s.number))}</h2>
        <p class="ig-step-body">${escapeHtml(s.text)}</p>
        ${s.note ? `<div class="ig-step-note"><b>Важно:</b> ${escapeHtml(s.note)}</div>` : ''}
        ${s.image ? `
          <div class="ig-screen-box">
            <img class="ig-screen-img ${s.mode === 'compact' ? 'compact-window' : 'salem-standard'}" src="${s.image}" alt="${escapeHtml(s.caption)}">
            <div class="ig-screen-caption"><b>Рисунок ${s.number}.</b> ${escapeHtml(s.caption)}</div>
          </div>
        ` : ''}
      </section>
    `).join('');

    preview.innerHTML = `
      <div class="ig-doc-inner">
        <div class="ig-doc-main-header">
          <div class="ig-doc-super">Инструкция</div>
          <h1 class="ig-doc-main-title">${escapeHtml(d.title)}</h1>
        </div>
        <div class="ig-doc-toc">
          <div class="ig-doc-toc-title">Содержание</div>
          <ol class="ig-doc-toc-items">${tocList}</ol>
        </div>
        <div class="ig-doc-divider"></div>
        <div class="ig-doc-steps">${stepsHtml}</div>
      </div>
    `;

    preview.classList.remove('hidden');
    $('#igExports').classList.remove('hidden');
  }

  document.querySelectorAll('[data-ig-export]').forEach(b => {
    b.onclick = () => {
      if (!result) return;
      validateSalemStandard(async () => {
        const kind = b.dataset.igExport;
        const r = await fetch(`/api/instruction-generator/export/${kind}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(result)
        });
        if (!r.ok) return;
        const blob = await r.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `instruction.${kind}`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      });
    };
  });

  addStep();
})();