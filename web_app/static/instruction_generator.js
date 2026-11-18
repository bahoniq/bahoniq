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

  // Modal validation dialog for screenshot quality check
  function showValidationDialog(warnings, onProceed) {
    const existing = document.querySelector('.ig-modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'ig-modal-overlay';
    overlay.innerHTML = `
      <div class="ig-modal">
        <div class="ig-modal-head">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#facc15" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <h3>Проверка скриншотов перед печатью</h3>
        </div>
        <div class="ig-modal-desc">
          Некоторые скриншоты могут быть мелкими или не полностью заполнять стандартный кадр:
        </div>
        <ul class="ig-modal-list">
          ${warnings.map(w => `<li><strong>Этап ${w.step}:</strong> ${escapeHtml(w.message)}</li>`).join('')}
        </ul>
        <div class="ig-modal-actions">
          <button type="button" class="button secondary ig-btn-fix">✏️ Проверить кадры</button>
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
        if (cropW > 0 && (cropW < TARGET_W * 0.7 || cropH < TARGET_H * 0.7)) {
          warnings.push({
            step: stepNum,
            card,
            message: `Разрешение кадра (${cropW} × ${cropH} px) невысокое. Рекомендуется снимок с более высоким разрешением для максимальной чёткости.`
          });
        }
        if (isNarrow) {
          warnings.push({
            step: stepNum,
            card,
            message: `Скриншот имеет вертикальный формат. При необходимости переключите в режим «Компактное окно».`
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

  // Detects red / highlighter marker annotations drawn by user (rectangles, circles, arrows)
  function detectMarkerRegion(img) {
    try {
      const scanW = Math.min(img.naturalWidth, 1000);
      const scanH = Math.round(scanW * (img.naturalHeight / img.naturalWidth));
      if (scanW <= 0 || scanH <= 0) return null;

      const c = document.createElement('canvas');
      c.width = scanW;
      c.height = scanH;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, scanW, scanH);
      const d = ctx.getImageData(0, 0, scanW, scanH).data;

      let minX = scanW, minY = scanH, maxX = 0, maxY = 0;
      let count = 0;

      for (let y = 0; y < scanH; y++) {
        for (let x = 0; x < scanW; x++) {
          const idx = (y * scanW + x) * 4;
          const r = d[idx], g = d[idx + 1], b = d[idx + 2];
          // User red pen / rectangle annotation: strong red contrast
          if (r > 150 && (r - g) > 42 && (r - b) > 42) {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
            count++;
          }
        }
      }

      // If red not found, check for yellow / orange highlighter
      if (count < 25) {
        minX = scanW; minY = scanH; maxX = 0; maxY = 0; count = 0;
        for (let y = 0; y < scanH; y++) {
          for (let x = 0; x < scanW; x++) {
            const idx = (y * scanW + x) * 4;
            const r = d[idx], g = d[idx + 1], b = d[idx + 2];
            if (r > 210 && g > 180 && b < 90) {
              if (x < minX) minX = x;
              if (x > maxX) maxX = x;
              if (y < minY) minY = y;
              if (y > maxY) maxY = y;
              count++;
            }
          }
        }
      }

      // Ensure annotation is localized (not the entire background)
      const totalPixels = scanW * scanH;
      if (count >= 25 && count <= totalPixels * 0.40 && maxX > minX && maxY > minY) {
        const scaleX = img.naturalWidth / scanW;
        const scaleY = img.naturalHeight / scanH;
        return {
          x: minX * scaleX,
          y: minY * scaleY,
          w: (maxX - minX) * scaleX,
          h: (maxY - minY) * scaleY,
          cx: ((minX + maxX) / 2) * scaleX,
          cy: ((minY + maxY) / 2) * scaleY,
          count
        };
      }
    } catch (e) {
      console.warn('Marker detection skipped:', e);
    }
    return null;
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
        <small class="ig-file-name">Подходит любой скриншот. Области с выделением/рамками автоматически увеличиваются в единый размер 16,5 × 7,9 см.</small>
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

      // Detect red / annotation marker box
      const marker = detectMarkerRegion(currentImg);

      editorZone.innerHTML = `
        <div class="ig-cropper-card">
          <div class="ig-mode-bar">
            <div class="ig-mode-group">
              <button type="button" class="ig-mode-btn ig-mode-standard active" title="Единый альбомный кадр 16,5 × 7,9 см в PDF">📐 Стандартный формат (16,5 × 7,9 см)</button>
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
              ${marker ? '<button type="button" class="button secondary ig-btn-focus" title="Вернуть фокус на выделенную область">🎯 К отметке</button>' : ''}
              <button type="button" class="button secondary ig-btn-reset" title="Показать весь скриншот">↺ Полный кадр</button>
            </div>
          </div>

          <!-- Live PDF Preview -->
          <div class="ig-live-preview-box">
            <div class="ig-live-preview-title">
              <span>Предпросмотр в PDF (16,5 × 7,9 см)</span>
              <span class="ig-live-preview-target">Стандартный формат</span>
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
      const btnFocus = editorZone.querySelector('.ig-btn-focus');
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

      function focusOnMarker(m) {
        if (!m) {
          zoom = 1.0;
          centerOffsets(zoom);
          return;
        }
        // Desired view box around marker with context
        let desiredViewW = Math.max(m.w * 2.8, origW * 0.42);
        let desiredViewH = Math.max(m.h * 2.8, origH * 0.42);

        if (desiredViewW / desiredViewH < TARGET_ASPECT) {
          desiredViewW = desiredViewH * TARGET_ASPECT;
        } else {
          desiredViewH = desiredViewW / TARGET_ASPECT;
        }

        desiredViewW = Math.min(origW, desiredViewW);
        desiredViewH = Math.min(origH, desiredViewH);

        const targetZoom = origW / desiredViewW;
        zoom = Math.min(2.5, Math.max(1.25, Math.round(targetZoom * 100) / 100));

        const curScale = baseScale * zoom;
        const dw = origW * curScale;
        const dh = origH * curScale;

        offsetX = (cw / 2) - (m.cx * curScale);
        offsetY = (ch / 2) - (m.cy * curScale);

        const minX = cw - dw;
        const minY = ch - dh;
        offsetX = Math.min(0, Math.max(minX, offsetX));
        offsetY = Math.min(0, Math.max(minY, offsetY));
      }

      // Initial focus: if marker detected, automatically zoom in on it!
      if (marker) {
        focusOnMarker(marker);
      } else {
        centerOffsets(zoom);
      }

      function updateBadges(cropW, cropH) {
        let badgesHtml = '';
        if (mode === 'compact') {
          badgesHtml += `
            <div class="ig-badge ig-badge-compact">
              <span>ℹ️ Режим «Компактное окно»: окно отображается целиком без кадрирования</span>
            </div>
          `;
        } else {
          if (marker) {
            badgesHtml += `
              <div class="ig-badge ig-badge-success">
                <span>🎯 Авто-фокус: область с отметкой увеличена для чёткости в PDF</span>
              </div>
            `;
          }
          if (isNarrow) {
            badgesHtml += `
              <div class="ig-badge ig-badge-warning">
                <span>ℹ️ Скриншот узкий — кадр выровнен по ширине</span>
              </div>
            `;
          }
          badgesHtml += `
            <div class="ig-badge ig-badge-success">
              <span>✓ Стандартный формат: 16,5 × 7,9 см (${cropW} × ${cropH} px)</span>
            </div>
          `;
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

        // Standard 16.5 x 7.9 cm Mode:
        card.dataset.mode = 'standard';
        liveFrame.className = 'ig-live-preview-frame standard';
        liveTarget.textContent = 'Стандартный формат';

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

        // Generate full export canvas (standard 1299 x 623 px for PDF)
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
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        setZoom(zoom + delta, e.clientX, e.clientY);
      }, { passive: false });

      // Slider and Zoom buttons
      zoomSlider.oninput = e => {
        setZoom(parseFloat(e.target.value));
      };

      btnZoomIn.onclick = () => setZoom(zoom + 0.15);
      btnZoomOut.onclick = () => setZoom(zoom - 0.15);

      btnReset.onclick = () => {
        zoom = 1.0;
        centerOffsets(zoom);
        updateOutput();
      };

      if (btnFocus && marker) {
        btnFocus.onclick = () => {
          focusOnMarker(marker);
          updateOutput();
        };
      }

      // Mode switching
      btnStandard.onclick = () => {
        mode = 'standard';
        btnStandard.classList.add('active');
        btnCompact.classList.remove('active');
        viewportWrap.classList.remove('hidden');
        toolbar.classList.remove('hidden');
        compactWrap.classList.add('hidden');
        updateOutput();
      };

      btnCompact.onclick = () => {
        mode = 'compact';
        btnCompact.classList.add('active');
        btnStandard.classList.remove('active');
        viewportWrap.classList.add('hidden');
        toolbar.classList.add('hidden');
        compactWrap.classList.remove('hidden');
        updateOutput();
      };

      btnReplace.onclick = () => {
        fileInput.value = '';
        fileInput.click();
      };

      updateOutput();
    }

    fileInput.onchange = e => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = ev => setupEditor(ev.target.result);
      reader.readAsDataURL(file);
    };

    dropEl.addEventListener('dragover', e => {
      e.preventDefault();
      dropEl.classList.add('dragover');
    });

    dropEl.addEventListener('dragleave', () => {
      dropEl.classList.remove('dragover');
    });

    dropEl.addEventListener('drop', e => {
      e.preventDefault();
      dropEl.classList.remove('dragover');
      const file = e.dataTransfer.files?.[0];
      if (!file || !file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = ev => setupEditor(ev.target.result);
      reader.readAsDataURL(file);
    });

    // Paste image from clipboard directly onto step card
    card.addEventListener('paste', e => {
      const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const file = item.getAsFile();
          const reader = new FileReader();
          reader.onload = ev => setupEditor(ev.target.result);
          reader.readAsDataURL(file);
          break;
        }
      }
    });

    card.querySelector('.ig-delete').onclick = () => {
      if (steps.children.length <= 1) {
        alert('В инструкции должен оставаться хотя бы один шаг.');
        return;
      }
      card.remove();
      renumber();
    };

    card.querySelector('.ig-up').onclick = () => {
      const prev = card.previousElementSibling;
      if (prev) {
        steps.insertBefore(card, prev);
        renumber();
      }
    };

    card.querySelector('.ig-down').onclick = () => {
      const next = card.nextElementSibling;
      if (next) {
        steps.insertBefore(next, card);
        renumber();
      }
    };

    card._setupEditor = setupEditor;
    if (data.image) {
      setupEditor(data.image);
    }

    steps.appendChild(card);
    renumber();
  }

  // Global paste handler on page to paste images into the active or last step
  window.addEventListener('paste', e => {
    const activeEl = document.activeElement;
    if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA') && !activeEl.classList.contains('ig-image')) {
      const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
      let hasImg = false;
      if (items) {
        for (const item of items) {
          if (item.type.startsWith('image/')) { hasImg = true; break; }
        }
      }
      if (!hasImg) return;
    }

    const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        const reader = new FileReader();
        reader.onload = ev => {
          const stepCards = [...steps.children];
          let targetCard = null;
          for (let i = stepCards.length - 1; i >= 0; i--) {
            if (!stepCards[i].querySelector('.ig-data').value) {
              targetCard = stepCards[i];
              break;
            }
          }
          if (!targetCard) {
            addStep();
            targetCard = steps.lastElementChild;
          }
          const fileInput = targetCard.querySelector('.ig-image');
          const dropEl = targetCard.querySelector('.ig-drop');
          const editorZone = targetCard.querySelector('.ig-editor-zone');
          const dataEl = targetCard.querySelector('.ig-data');
          const img = new Image();
          img.onload = () => {
            fileInput.dispatchEvent(new Event('change'));
          };
          targetCard.querySelector('.ig-drop').classList.add('hidden');
          const setup = () => {
            const tempImg = new Image();
            tempImg.onload = () => {
              const fakeEvent = { target: { result: ev.target.result } };
              const changeHandler = fileInput.onchange;
              const r = new FileReader();
              r.readAsDataURL(file);
            };
          };
          const dummyReader = new FileReader();
          dummyReader.onload = dev => {
            const evt = new CustomEvent('custom-img-load', { detail: dev.target.result });
            targetCard.dispatchEvent(evt);
          };
          dummyReader.readAsDataURL(file);
        };
        reader.readAsDataURL(file);
        break;
      }
    }
  });

  // Custom event listener on step cards for programmatic image load
  document.addEventListener('custom-img-load', e => {
    const card = e.target.closest('.ig-step');
    if (!card) return;
    const dropEl = card.querySelector('.ig-drop');
    const editorZone = card.querySelector('.ig-editor-zone');
    const dataEl = card.querySelector('.ig-data');
    const imgSrc = e.detail;
    dropEl.classList.add('hidden');
    const img = new Image();
    img.onload = () => {
      const setupFunc = card._setupEditor;
      if (typeof setupFunc === 'function') {
        setupFunc(imgSrc);
      } else {
        const fileInput = card.querySelector('.ig-image');
        fileInput.dispatchEvent(new Event('change'));
      }
    };
    img.src = imgSrc;
  });

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
      status.textContent = `Готово · ${d.steps.length} этапов · Альбомный формат 16,5 × 7,9 см`;
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
