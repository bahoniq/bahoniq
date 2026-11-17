(() => {
  const $ = s => document.querySelector(s);
  const steps = $('#igSteps');
  if (!steps) return;
  let result = null;

  const renumber = () => [...steps.children].forEach((card, i) => {
    const titleEl = card.querySelector('.ig-step-title');
    if (titleEl) titleEl.textContent = `Шаг ${i + 1}`;
  });

  function addStep(data = {}) {
    const card = document.createElement('article');
    card.className = 'ig-step card';
    card.innerHTML = `
      <div class="ig-step-head">
        <strong class="ig-step-title"></strong>
        <div class="ig-step-nav-btns">
          <button type="button" class="button secondary ig-up" title="Поднять выше">↑</button>
          <button type="button" class="button secondary ig-down" title="Опустить ниже">↓</button>
          <button type="button" class="button danger ig-delete" title="Удалить шаг">Удалить</button>
        </div>
      </div>
      <label>Черновое описание действия
        <textarea class="ig-text" rows="3" placeholder="Например: заходим в Platonus, открываем раздел заявки и нажимаем согласовать..."></textarea>
      </label>
      <label>Подпись к скриншоту
        <input class="ig-caption" placeholder="Например: Раздел согласования заявок">
      </label>
      <label class="file-drop ig-drop">
        <input class="ig-image" type="file" accept="image/png,image/jpeg,image/webp">
        <span class="file-title">📸 Загрузите скриншот или нажмите Ctrl+V</span>
        <small class="ig-file-name">PNG, JPG или WebP (исходные пропорции сохраняются)</small>
      </label>
      <img class="ig-preview hidden" alt="Предпросмотр">
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
        card.querySelector('.ig-file-name').textContent = file.name;
      };
      reader.readAsDataURL(file);
    };

    card.querySelector('.ig-image').onchange = e => setImage(e.target.files[0]);
    card.addEventListener('paste', e => {
      const f = [...e.clipboardData.files].find(x => x.type.startsWith('image/'));
      if (f) {
        e.preventDefault();
        setImage(f);
      }
    });

    card.querySelector('.ig-delete').onclick = () => {
      if (steps.children.length > 1) {
        card.remove();
        renumber();
      }
    };
    card.querySelector('.ig-up').onclick = () => {
      if (card.previousElementSibling) {
        steps.insertBefore(card, card.previousElementSibling);
        renumber();
      }
    };
    card.querySelector('.ig-down').onclick = () => {
      if (card.nextElementSibling) {
        steps.insertBefore(card.nextElementSibling, card);
        renumber();
      }
    };

    steps.appendChild(card);
    renumber();
  }

  const payload = () => ({
    title: $('#igTitle').value,
    audience: $('#igAudience').value,
    department: $('#igDepartment').value,
    intro: $('#igIntro').value,
    steps: [...steps.children].map(c => ({
      text: c.querySelector('.ig-text').value,
      caption: c.querySelector('.ig-caption').value,
      image: c.querySelector('.ig-data').value
    }))
  });

  $('#igAdd').onclick = () => addStep();

  $('#igGenerate').onclick = async () => {
    const btn = $('#igGenerate');
    const status = $('#igStatus');
    btn.disabled = true;
    status.textContent = '⚡ ИИ обрабатывает черновик и приводит к эталонному стандарту...';

    try {
      const r = await fetch('/api/instruction-generator/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload())
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Ошибка генерации');
      result = d;
      render(d);
      status.textContent = `✓ Готово · ${d.steps.length} шагов оформлено · Стандарт: ${d.style || 'КазНМУ'}`;
    } catch (e) {
      status.textContent = '✕ Ошибка: ' + e.message;
    } finally {
      btn.disabled = false;
    }
  };

  const escapeHtml = s => String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[c]));

  function render(d) {
    const preview = $('#igResult');
    const metaStr = [d.department, d.audience ? ('Для кого: ' + d.audience) : ''].filter(Boolean).join(' · ');

    const tocHtml = `
      <div class="ig-toc">
        <div class="ig-toc-title">Содержание документа</div>
        <ol class="ig-toc-list">
          ${d.steps.map(s => `<li>${escapeHtml(s.caption || ('Шаг ' + s.number))}</li>`).join('')}
        </ol>
      </div>
    `;

    const stepsHtml = d.steps.map(s => `
      <section class="ig-preview-step">
        <h2 class="ig-step-heading">${s.number}. ${escapeHtml(s.caption || ('Шаг ' + s.number))}</h2>
        <p class="ig-step-desc">${escapeHtml(s.text)}</p>
        ${s.note ? `<aside class="ig-note"><b>Важно.</b> ${escapeHtml(s.note)}</aside>` : ''}
        ${s.image ? `
          <div class="ig-image-frame">
            <img src="${s.image}" alt="${escapeHtml(s.caption)}" class="ig-screen-img">
            <small class="ig-caption-text">Рисунок ${s.number}. ${escapeHtml(s.caption)}</small>
          </div>
        ` : ''}
      </section>
    `).join('');

    preview.innerHTML = `
      <div class="ig-doc-wrapper">
        <header class="ig-doc-header">
          <div class="ig-doc-univ">КАЗАХСКИЙ НАЦИОНАЛЬНЫЙ МЕДИЦИНСКИЙ УНИВЕРСИТЕТ</div>
          <div class="ig-doc-badge">ОФИЦИАЛЬНАЯ ИНСТРУКЦИЯ</div>
          <h1 class="ig-doc-title">${escapeHtml(d.title)}</h1>
          ${metaStr ? `<p class="ig-doc-meta">${escapeHtml(metaStr)}</p>` : ''}
        </header>

        ${d.intro ? `<div class="ig-doc-intro"><p>${escapeHtml(d.intro)}</p></div>` : ''}
        ${tocHtml}
        <div class="ig-steps-container">
          ${stepsHtml}
        </div>
      </div>
    `;

    preview.classList.remove('hidden');
    $('#igExports').classList.remove('hidden');
  }

  document.querySelectorAll('[data-ig-export]').forEach(b => b.onclick = async () => {
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
  });

  addStep();
})();
