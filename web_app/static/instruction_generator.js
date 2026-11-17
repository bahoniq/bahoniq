(() => {
  const $ = s => document.querySelector(s);
  const steps = $('#igSteps');
  if (!steps) return;
  let result = null;

  const escapeHtml = s => String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[c]));

  const renumber = () => [...steps.children].forEach((card, i) => {
    const titleEl = card.querySelector('.ig-step-title');
    if (titleEl) titleEl.textContent = `Этап ${i + 1}`;
  });

  function addStep(data = {}) {
    const card = document.createElement('article');
    card.className = 'ig-step card';
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
        <small class="ig-file-name">PNG, JPG или WebP</small>
      </label>
      <img class="ig-preview hidden" alt="Предпросмотр скриншота">
      <textarea class="ig-data hidden"></textarea>
    `;

    card.querySelector('.ig-text').value = data.text || '';
    card.querySelector('.ig-caption').value = data.caption || '';

    const setImage = (file) => {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        card.querySelector('.ig-data').value = reader.result;
        const im = card.querySelector('.ig-preview');
        im.src = reader.result;
        im.classList.remove('hidden');
        card.querySelector('.ig-file-name').textContent = file.name || 'Скриншот прикреплен';
      };
      reader.readAsDataURL(file);
    };

    card.querySelector('.ig-image').onchange = e => setImage(e.target.files[0]);
    card.addEventListener('paste', e => {
      const f = [...(e.clipboardData?.files || [])].find(x => x.type.startsWith('image/'));
      if (f) {
        e.preventDefault();
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
  }

  const payload = () => ({
    title: ($('#igTitle')?.value || '').trim() || 'Инструкция по работе с системой',
    audience: '',
    department: '',
    intro: '',
    steps: [...steps.children].map(c => ({
      text: c.querySelector('.ig-text').value.trim(),
      caption: c.querySelector('.ig-caption').value.trim(),
      image: c.querySelector('.ig-data').value
    }))
  });

  $('#igAdd').onclick = () => addStep();

  $('#igGenerate').onclick = async () => {
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
      status.textContent = `Готово · ${d.steps.length} этапов · Стандарт: ${d.style || 'Золотой стандарт'}`;
    } catch (e) {
      status.textContent = '✕ Ошибка: ' + e.message;
    } finally {
      btn.disabled = false;
    }
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
            <div class="ig-screen-frame">
              <img src="${s.image}" alt="${escapeHtml(s.caption)}">
            </div>
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
    b.onclick = async () => {
      if (!result) return;
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
    };
  });

  addStep();
})();
