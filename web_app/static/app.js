const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let analyticsSession=null, excelSession=null, operationHistory=[];

// Web Splash Screen Fade-Out
window.addEventListener('DOMContentLoaded', () => {
  const splash = $('#webSplash');
  if (splash) {
    if (location.search.includes('no_splash') || navigator.webdriver) {
      splash.remove();
    } else {
      setTimeout(() => {
        splash.classList.add('fade-out');
        setTimeout(() => splash.remove(), 600);
      }, 1800);
    }
  }

  // Часы реального времени
  const clock = $('#liveClock');
  if (clock) {
    const updateTime = () => {
      const d = new Date();
      clock.textContent = d.toTimeString().split(' ')[0];
    };
    updateTime();
    setInterval(updateTime, 1000);
  }
});

// Управление темами: Aqua / Violet.
// Внутренние значения night/day сохранены для совместимости с уже
// записанными настройками пользователей.
function applyTheme(theme) {
  const body = document.body;
  const toggleBtn = $('#themeToggle');
  const icon = toggleBtn?.querySelector('.theme-icon');
  const label = toggleBtn?.querySelector('.theme-label');
  const aquaSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.7 5.8 9.6a8 8 0 1 0 12.4 0L12 2.7Z"/><path d="M8.8 15.2c.7 1.5 1.8 2.2 3.4 2.2"/></svg>';
  const violetSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/><path d="m18 3 .5 1.5L20 5l-1.5.5L18 7l-.5-1.5L16 5l1.5-.5L18 3Z"/></svg>';
  
  const isDay = (theme === 'day' || theme === 'light');
  if (isDay) {
    body.classList.remove('theme-night');
    body.classList.add('theme-day');
    if (icon) icon.innerHTML = aquaSvg;
    if (label) label.textContent = 'Aqua';
    if (toggleBtn) {
      toggleBtn.title = 'Переключить на тему Aqua';
      toggleBtn.setAttribute('aria-label', 'Переключить на тему Aqua');
    }
  } else {
    body.classList.remove('theme-day');
    body.classList.add('theme-night');
    if (icon) icon.innerHTML = violetSvg;
    if (label) label.textContent = 'Violet';
    if (toggleBtn) {
      toggleBtn.title = 'Переключить на тему Violet';
      toggleBtn.setAttribute('aria-label', 'Переключить на тему Violet');
    }
  }
  localStorage.setItem('bahoniq_theme', isDay ? 'day' : 'night');
}

const savedTheme = localStorage.getItem('bahoniq_theme') || 'night';
applyTheme(savedTheme);

$('#themeToggle')?.addEventListener('click', () => {
  const isNight = document.body.classList.contains('theme-night');
  applyTheme(isNight ? 'day' : 'night');
});

// Навигация между Дашбордом и Модулями (PowerPoint-style плавные панорамные переходы)
const dashView = $('#dashboardView');
const modHost = $('#moduleHost');
const currentLabel = $('#currentModuleLabel');
let isTransitioning = false;

function openModule(modId, label) {
  const target = $('#' + modId);
  if (!target) return;
  if (currentLabel) currentLabel.textContent = label || modId.toUpperCase();
  location.hash = modId;
  if (modId === 'notes') loadNotes();
  if (modId === 'academy') loadAcademy();
  if (modId === 'sports' && typeof window.loadSportsHub === 'function') window.loadSportsHub();
  if (modId === 'designAcademy') {
    if (typeof window.loadDesignAcademy === 'function') {
      window.loadDesignAcademy();
    } else {
      const dasTimer = setInterval(() => {
        if (typeof window.loadDesignAcademy === 'function') {
          clearInterval(dasTimer);
          window.loadDesignAcademy();
        }
      }, 50);
      setTimeout(() => clearInterval(dasTimer), 4000);
    }
  }
  if (modId === 'platonus' && typeof window.loadPlatonusWiki === 'function') window.loadPlatonusWiki();
  dashView.classList.add('hidden');
  $$('.module-page').forEach(p => p.classList.remove('active'));
  target.classList.add('active');
  modHost.classList.remove('hidden');
  modHost.classList.add('panorama-in');
  setTimeout(() => modHost.classList.remove('panorama-in'), 380);
  document.querySelector('.content-body')?.scrollTo({ top: 0, behavior: 'smooth' });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function returnToDashboard() {
  if (typeof window.unloadSportsHub === 'function') window.unloadSportsHub();
  modHost.classList.add('hidden');
  modHost.classList.remove('panorama-in', 'panorama-out');
  $$('.module-page').forEach(p => p.classList.remove('active'));
  dashView.classList.remove('hidden');
  dashView.classList.add('panorama-in');
  window.history.replaceState(null, '', location.pathname + location.search);
  setTimeout(() => dashView.classList.remove('panorama-in'), 380);
}

$('#backToDash')?.addEventListener('click', returnToDashboard);

// Всплывающее окно для инструментов рабочего стола (Очистка, Дубликаты, AnyDesk)
const desktopModal = $('#desktopModal');
const modalTitle = $('#modalToolTitle');
const modalDesc = $('#modalToolDesc');

function showDesktopModal(title, desc) {
  if (modalTitle) modalTitle.textContent = title;
  if (modalDesc) modalDesc.textContent = desc;
  desktopModal?.classList.remove('hidden');
}

$('#closeDesktopModal')?.addEventListener('click', () => {
  desktopModal?.classList.add('hidden');
});

desktopModal?.addEventListener('click', (e) => {
  if (e.target === desktopModal) {
    desktopModal.classList.add('hidden');
  }
});

// Делегирование делает переходы устойчивыми даже после динамического обновления DOM.
document.addEventListener('mousemove', (e) => {
  const tile = e.target.closest('.tool-tile');
  if (tile) {
    const rect = tile.getBoundingClientRect();
    tile.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
    tile.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
  }
});

document.addEventListener('click', (e) => {
  const tile = e.target.closest('.tool-tile');
  if (!tile) return;
  if (tile.dataset.desktopOnly === 'true') {
    const title = tile.dataset.title || tile.querySelector('.tool-name')?.textContent || '';
    const desc = tile.dataset.desc || tile.querySelector('.tool-desc')?.textContent || '';
    showDesktopModal(title, desc);
    return;
  }
  const modId = tile.dataset.open;
  if (!modId) return;
  if (modId === 'reconcile') {
    openModule('excel', 'Excel AI — Сверка студентов');
    const recTab = document.querySelector('[data-tab="excelReconcile"]');
    if (recTab) recTab.click();
    return;
  }
  const name = tile.querySelector('.tool-name')?.textContent || '';
  openModule(modId, name);
});

// Модальное окно при блокировке браузером множественного открытия вкладок
function showPopupNoticeModal(systems) {
  let modal = document.getElementById('popupNoticeModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'popupNoticeModal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.72);display:flex;align-items:center;justify-content:center;z-index:999999;backdrop-filter:blur(5px);padding:16px;';
    modal.innerHTML = `
      <div style="background:#0F1D33;border:1px solid #1E3352;border-radius:14px;max-width:520px;width:100%;padding:24px;color:#F8FAFC;box-shadow:0 20px 40px rgba(0,0,0,0.5);font-family:sans-serif;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h3 style="margin:0;font-size:16px;font-weight:700;display:flex;align-items:center;gap:8px;">
            <span style="color:#F59E0B;font-size:18px;">⚡</span> Запуск всех систем в браузере
          </h3>
          <button id="closePopupNoticeBtn" style="background:transparent;border:none;color:#A9BDD3;font-size:18px;cursor:pointer;padding:4px 8px;">✕</button>
        </div>
        <div style="background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.35);border-radius:8px;padding:12px 14px;font-size:13px;line-height:1.5;color:#F8FAFC;margin-bottom:14px;">
          <strong>Браузер заблокировал открытие остальных вкладок!</strong><br/>
          Защита Chrome и Edge по умолчанию открывает только 1 вкладку за клик (поэтому открылся только Platonus).
        </div>
        <div style="font-size:13px;color:#CBD5E1;margin-bottom:14px;line-height:1.55;">
          <strong style="color:#00E5FF;">Как включить открытие всех 6 вкладок в 1 клик:</strong><br/>
          1. Посмотрите в адресную строку браузера (справа) — там появился значок <strong>🚫 «Всплывающие окна заблокированы»</strong>.<br/>
          2. Кликните по нему и выберите <strong>«Всегда разрешать всплывающие окна для bahoniq.onrender.com»</strong> ➔ нажмите <strong>«Готово»</strong>.<br/>
          3. Нажмите кнопку «Открыть все системы» снова — откроются <strong>все 6 систем одновременно</strong>!
        </div>
        <div style="font-size:11.5px;font-weight:800;text-transform:uppercase;color:#647D96;letter-spacing:0.05em;margin-bottom:8px;">Или откройте нужные системы прямо сейчас:</div>
        <div id="popupSystemsGrid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;"></div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('#closePopupNoticeBtn').onclick = () => modal.remove();
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
  }

  const grid = modal.querySelector('#popupSystemsGrid');
  grid.innerHTML = systems.map(s => `
    <a href="${s.url}" target="_blank" rel="noopener" style="display:flex;align-items:center;gap:8px;background:#13233E;border:1px solid #1E3352;padding:9px 12px;border-radius:8px;color:#F8FAFC;text-decoration:none;font-size:12.5px;font-weight:600;transition:background 0.15s;" onmouseover="this.style.background='#163B5C'" onmouseout="this.style.background='#13233E'">
      <span>${s.icon}</span>
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${s.name}</span>
    </a>
  `).join('');

  modal.style.display = 'flex';
}

// Кнопка "Открыть все системы"
$('#openAllSystems')?.addEventListener('click', () => {
  const systems = [
    { name: "Platonus", icon: "🎓", url: "https://platonus.kaznmu.edu.kz/" },
    { name: "Поддержка Platonus", icon: "🛡", url: "https://support.platonus.kz/" },
    { name: "Telegram Web", icon: "✈️", url: "https://web.telegram.org/" },
    { name: "WhatsApp Web", icon: "💬", url: "https://web.whatsapp.com/" },
    { name: "Gmail", icon: "✉️", url: "https://mail.google.com/mail/u/0/#inbox" },
    { name: "Salem Office", icon: "🏢", url: "https://salemoffice.kaznmu.edu.kz/sign-in" }
  ];

  let blockedCount = 0;
  systems.forEach((s) => {
    try {
      const w = window.open(s.url, '_blank');
      if (!w || w.closed || typeof w.closed === 'undefined') {
        blockedCount++;
      }
    } catch (e) {
      blockedCount++;
    }
  });

  if (blockedCount > 0) {
    showPopupNoticeModal(systems);
  }
});

// Проверка прямого хэша в URL (например #tickets или #reconcile)
if (location.hash) {
  const hash = location.hash.slice(1);
  if (hash === 'reconcile') {
    openModule('excel', 'Excel AI — Сверка студентов');
    const recTab = document.querySelector('[data-tab="excelReconcile"]');
    if (recTab) recTab.click();
  } else {
    const matchedTile = document.querySelector(`[data-open="${hash}"]`);
    if (matchedTile) {
      const name = matchedTile.querySelector('.tool-name')?.textContent || '';
      openModule(hash, name);
    }
  }
}

// Табы внутри модулей
$$('.tab').forEach(b => b.onclick = () => {
  const scope = b.closest('.module-page');
  scope.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  scope.querySelectorAll('.tab-page').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  $('#' + b.dataset.tab).classList.add('active');
});

const pdfOps = {
  pdf_word: ["PDF → Word", "Преобразование PDF в редактируемый DOCX", ".pdf"],
  word_pdf: ["Word → PDF", "Экспорт Word в PDF через Microsoft Word", ".doc,.docx"],
  pdf_png: ["PDF → PNG", "Каждая страница сохраняется отдельным PNG", ".pdf"],
  pdf_jpg: ["PDF → JPG", "Каждая страница сохраняется отдельным JPG", ".pdf"],
  images_pdf: ["Изображения → PDF", "Изображения объединяются в один PDF", ".jpg,.jpeg,.png,.bmp,.tif,.tiff,.webp"],
  merge_pdf: ["Объединить PDF", "PDF объединяются в указанном порядке", ".pdf"],
  split_pdf: ["Разделить PDF", "Каждая страница становится отдельным PDF", ".pdf"],
  compress_pdf: ["Оптимизировать PDF", "Очистка структуры и сжатие потоков", ".pdf"],
  pdf_txt: ["PDF → TXT", "Извлечение текстового слоя документа", ".pdf"]
};
let pdfOperation = "pdf_word";

// Потоковое чтение SSE (Server-Sent Events)
async function consumeSSE(url, formData, onChunk, onDone, onError) {
  try {
    const res = await fetch(url, { credentials: 'same-origin', method: 'POST', body: formData });
    if (!res.ok) {
      const errText = await res.text();
      let msg = res.statusText;
      try { const j = JSON.parse(errText); if (j.detail) msg = j.detail; } catch (_) { msg = errText || msg; }
      throw new Error(msg);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let doneEventReceived = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data:')) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;
        try {
          const payload = JSON.parse(jsonStr);
          if (payload.type === 'chunk' && payload.text) {
            if (onChunk) onChunk(payload.text);
          } else if (payload.type === 'done') {
            doneEventReceived = true;
            if (onDone) onDone(payload);
          } else if (payload.type === 'error') {
            throw new Error(payload.error || 'Ошибка генерации');
          }
        } catch (parseErr) {
          if (parseErr.message && !parseErr.message.includes('JSON')) {
            throw parseErr;
          }
        }
      }
    }
    if (!doneEventReceived && onDone) {
      onDone({});
    }
  } catch (err) {
    if (onError) onError(err);
  }
}

async function api(url, options = {}) {
  const r = await fetch(url, options);
  let data = {};
  try { data = await r.json(); } catch {}
  if (!r.ok) throw new Error(data.detail || "Ошибка сервера");
  return data;
}

function showResult(node, html, error = false) {
  node.classList.remove("hidden");
  node.classList.toggle("error", error);
  node.innerHTML = html;
}

function setBusy(button, busy, text = "Выполняется…") {
  if (!button) return;
  button.disabled = busy;
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.textContent = busy ? text : button.dataset.label;
}

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function formatBytes(n) {
  if (n < 1024) return n + ' Б';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' КБ';
  return (n / 1048576).toFixed(1) + ' МБ';
}

// ----------------- ANALYTICS AI -----------------
$('#analyticsFile')?.addEventListener('change', e => {
  $('#analyticsFileName').textContent = e.target.files[0]?.name || '.xls, .xlsx или .xlsm';
});

$('#inspectButton')?.addEventListener('click', async () => {
  const file = $('#analyticsFile').files[0];
  if (!file) return alert('Выберите Excel-файл.');
  const b = $('#inspectButton');
  setBusy(b, true, 'Чтение файла…');
  const fd = new FormData();
  fd.append('workbook', file);
  try {
    const data = await api('/api/analytics/inspect', { method: 'POST', body: fd });
    analyticsSession = data.session_id;
    const select = $('#sheetName');
    select.innerHTML = data.sheets.map((s, i) => `<option value="${esc(s.name)}" data-index="${i}">${esc(s.name)} · ${s.rows} строк</option>`).join('');
    select._sheets = data.sheets;
    select.onchange = renderPreview;
    renderPreview();
  } catch (e) {
    alert(e.message);
  } finally {
    setBusy(b, false);
  }
});

function renderPreview() {
  const select = $('#sheetName'), sheet = select._sheets?.[select.selectedIndex];
  if (!sheet) return;
  $('#previewMeta').textContent = `${sheet.rows} записей · ${sheet.columns} столбцов`;
  const heads = sheet.headers || [], rows = sheet.preview || [];
  $('#previewTable').innerHTML = `<thead><tr>${heads.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody>`;
}

$('#analyticsForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  if (!analyticsSession) return alert('Сначала загрузите и просмотрите Excel-файл.');
  const button = e.submitter, pPanel = $('#analyticsProgress');
  pPanel.classList.remove('hidden');
  setBusy(button, true);
  let p = 12;
  $('#progressLabel').textContent = 'Подготовка данных и структуры';
  $('#progressBar').style.width = p + '%';
  $('#progressPercent').textContent = p + '%';

  const timer = setInterval(() => {
    p = Math.min(94, p + Math.max(1, Math.round((96 - p) / 10)));
    $('#progressLabel').textContent = p < 45 ? 'Анализ разрезов таблицы' : p < 75 ? 'BahonIQ AI формирует стратегические выводы' : 'Верстка отчёта';
    $('#progressBar').style.width = p + '%';
    $('#progressPercent').textContent = p + '%';
  }, 900);

  const format = $('#outputFormat').value;
  const fd = new FormData();
  [
    ['session_id', analyticsSession],
    ['sheet_name', $('#sheetName').value],
    ['title', $('#reportTitle').value],
    ['description', $('#analyticsTask').value],
    ['pdf', format !== 'pptx'],
    ['pptx', format !== 'pdf'],
    ['include_source_table', $('#includeSource').checked],
    ['report_profile', $('#reportProfile').value],
    ['report_depth', $('#reportDepth').value]
  ].forEach(([k, v]) => fd.append(k, v));

  try {
    const data = await api('/api/analytics/generate', { method: 'POST', body: fd });
    p = 100;
    $('#progressBar').style.width = '100%';
    $('#progressPercent').textContent = '100%';
    $('#progressLabel').textContent = 'Отчёт готов';
    const links = Object.entries(data.downloads).map(([k, u]) => `<a class="button primary" href="${u}" style="margin-right:8px">Скачать ${k.toUpperCase()}</a>`).join('');
    showResult($('#analyticsResult'), `<b>Аналитический отчёт успешно сформирован BahonIQ AI.</b><div style="margin-top:12px">${links}</div>${data.warnings?.length ? `<small style="display:block;margin-top:8px">${esc(data.warnings.join(' · '))}</small>` : ''}`);
  } catch (err) {
    showResult($('#analyticsResult'), esc(err.message), true);
  } finally {
    clearInterval(timer);
    setBusy(button, false);
  }
});

// ----------------- EXCEL AI ШАБЛОНЫ -----------------
const EXCEL_TEMPLATES = {
  dedup: {
    title: "Удалить дубликаты",
    prompt: "Найди и удали полные дубликаты строк. Если нужно сравнивать записи по конкретному идентификатору, используй выбранный мной столбец. Исходный лист не изменяй: сохрани очищенный результат на новом листе «Очищенные данные».",
    preview: "Создаст очищенную копию данных без повторяющихся записей.", tag: "Универсальная очистка"
  },
  clean_fio: {
    title: "Очистить текст",
    prompt: "Нормализуй текст в выбранных столбцах: удали пробелы по краям, замени повторяющиеся пробелы одним и приведи регистр к единому формату. Исходный лист сохрани без изменений.",
    preview: "Устранит лишние пробелы и неодинаковый регистр в выбранных текстовых полях.", tag: "Текстовая нормализация"
  },
  validate_iin: {
    title: "Проверить формат",
    prompt: "Проверь выбранный столбец по указанным мной правилам длины и допустимых символов. Ошибочные и пустые значения вынеси на отдельный лист «Ошибки проверки».",
    preview: "Сформирует отдельный список значений, не прошедших заданные правила.", tag: "Контроль качества"
  },
  split_faculty: {
    title: "Разделить по листам",
    prompt: "Раздели таблицу на отдельные листы по уникальным значениям выбранного мной столбца. На каждом листе сохрани исходную структуру таблицы.",
    preview: "Разобьёт единую базу на вкладки по категориям.", tag: "Структурирование"
  },
  merge_fio: {
    title: "Объединить столбцы",
    prompt: "Объедини выбранные столбцы через один пробел в новый столбец. Пустые значения пропускай без лишних пробелов, исходные столбцы не удаляй.",
    preview: "Сформирует один итоговый столбец из нескольких исходных.", tag: "Объединение полей"
  },
  filter_grant: {
    title: "Отфильтровать строки",
    prompt: "Отфильтруй строки по указанным мной условиям и сохрани результат на новом листе «Отбор». Исходные данные не изменяй.",
    preview: "Создаст отдельный лист только со строками, соответствующими условиям.", tag: "Фильтрация"
  },
  pivot_courses: {
    title: "Создать сводку",
    prompt: "Создай сводную таблицу по выбранным категориальным столбцам: покажи количество записей, итоги и процентную долю каждой категории.",
    preview: "Сформирует компактную сводку по выбранным категориям.", tag: "Сводная таблица"
  },
  audit_blanks: {
    title: "Найти пропуски",
    prompt: "Найди строки с пустыми значениями в выбранных мной столбцах. Сформируй отдельный лист «Требуют заполнения» и укажи, какие поля отсутствуют.",
    preview: "Создаст список неполных записей для последующего исправления.", tag: "Аудит пропусков"
  },
  chart_distribution: {
    title: "Диаграмма распределения",
    prompt: "Посчитай распределение записей по выбранной категории, создай сводную таблицу и подходящую диаграмму с подписями значений и долей.",
    preview: "Сформирует сводную таблицу и диаграмму распределения.", tag: "Визуальная сводка"
  }
};

document.addEventListener('click', e => {
  const chip = e.target.closest('.template-chip');
  if (chip && chip.dataset.template) {
    const key = chip.dataset.template;
    const tpl = EXCEL_TEMPLATES[key];
    if (tpl) {
      document.querySelectorAll('.template-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      const textarea = document.getElementById('excelInstruction');
      if (textarea) {
        textarea.value = tpl.prompt;
        textarea.focus();
      }
      const previewCard = document.getElementById('excelTemplatePreviewCard');
      const desc = document.getElementById('excelTemplateDesc');
      const tag = document.getElementById('excelTemplateTag');
      if (previewCard && desc && tag) {
        desc.textContent = tpl.preview;
        tag.textContent = tpl.tag;
        previewCard.classList.remove('hidden');
      }
    }
  }
});

// ----------------- EXCEL AI -----------------
$('#excelFile')?.addEventListener('change', async e => {
  const file = e.target.files?.[0], panel = $('#excelFilePreview');
  if (!file || !panel) return;
  panel.classList.remove('hidden');
  panel.innerHTML = `<b>${esc(file.name)}</b><span>${formatBytes(file.size)} · читаю структуру…</span>`;
  const fd = new FormData(); fd.append('workbook', file);
  try {
    const data = await api('/api/excel/inspect', {method:'POST', body:fd});
    panel.innerHTML = `<div class="excel-preview-head"><b>${esc(file.name)}</b><span>${formatBytes(file.size)}</span></div>` +
      (data.sheets || []).map(s => `<div class="excel-preview-sheet"><strong>${esc(s.name)}</strong><span>${s.rows} строк · ${s.columns} столбцов</span><small>${(s.headers || []).map(esc).join(' · ')}</small></div>`).join('');
  } catch (err) {
    panel.innerHTML = `<b>${esc(file.name)}</b><span class="error-text">${esc(err.message)}</span>`;
  }
});

$('#excelForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const button = e.submitter, fd = new FormData();
  fd.append('workbook', $('#excelFile').files[0]);
  fd.append('instruction', $('#excelInstruction').value);
  setBusy(button, true, 'BahonIQ AI готовит план…');
  try {
    const data = await api('/api/excel/plan', { method: 'POST', body: fd });
    if (data.status === 'questions') {
      showPlan(`<h2>Нужно уточнение</h2><ul>${data.questions.map(q => `<li>${esc(q)}</li>`).join('')}</ul>`);
    } else {
      excelSession = data.session_id;
      showPlan(`<h2>План изменений</h2><p>${esc(data.explanation || 'План подготовлен.')}</p><ol class="plan-list">${(data.operations || []).map(o => `<li><b>${esc(o.type || 'Операция')}</b> ${esc(JSON.stringify(o))}</li>`).join('')}</ol><button id="executePlan" class="button primary" style="margin-top:14px">Подтвердить и выполнить</button>`);
      $('#executePlan').onclick = executeExcel;
    }
  } catch (err) {
    showPlan(`<div class="result-panel error">${esc(err.message)}</div>`);
  } finally {
    setBusy(button, false);
  }
});

function showPlan(html) {
  $('#planContent').className = '';
  $('#planContent').innerHTML = html;
  document.querySelector('[data-tab="excelPlan"]').click();
}

async function executeExcel() {
  const b = $('#executePlan'), fd = new FormData();
  fd.append('session_id', excelSession);
  fd.append('confirmed', 'true');
  setBusy(b, true);
  try {
    const data = await api('/api/excel/execute', { method: 'POST', body: fd });
    const item = { time: new Date().toLocaleTimeString(), text: $('#excelInstruction').value };
    operationHistory.unshift(item);
    showPlan(`<h2>Готово</h2><p>Изменения выполнены после подтверждения.</p><ul>${(data.changes || []).map(x => `<li>${esc(typeof x === 'string' ? x : JSON.stringify(x))}</li>`).join('')}</ul><a class="button primary" style="display:inline-block;margin-top:12px" href="${data.download_url}">Скачать готовый Excel</a>`);
    renderHistory();
  } catch (e) {
    showResult($('#planContent'), esc(e.message), true);
  } finally {
    setBusy(b, false);
  }
}

function renderHistory() {
  $('#historyContent').className = '';
  $('#historyContent').innerHTML = operationHistory.map(x => `<div class="queue-item" style="padding:10px;border-bottom:1px solid var(--border)"><b>${esc(x.text)}</b><small style="display:block;color:var(--text-sub)">${x.time}</small></div>`).join('');
}

// ----------------- PDF CENTER -----------------
const toolList = $('#pdfTools');
if (toolList) {
  Object.entries(pdfOps).forEach(([key, v]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'button secondary' + (key === pdfOperation ? ' active' : '');
    b.style.margin = '0 6px 6px 0';
    b.textContent = v[0];
    b.onclick = () => selectPdf(key);
    toolList.appendChild(b);
  });
}

let pdfQueueFiles = [];

function pdfAcceptList() {
  return (pdfOps[pdfOperation][2] || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
}

function selectPdf(key) {
  pdfOperation = key;
  $$('#pdfTools button').forEach((b, i) => b.classList.toggle('active', Object.keys(pdfOps)[i] === key));
  const v = pdfOps[key];
  $('#pdfTitle').textContent = v[0];
  $('#pdfHint').textContent = v[1];
  $('#pdfFiles').accept = v[2];
  $('#pdfFiles').value = '';
  pdfQueueFiles = [];
  renderQueue();
  $('#pdfResult').classList.add('hidden');
}

function addPdfFiles(list) {
  const allowed = pdfAcceptList();
  const rejected = [];
  [...list].forEach(f => {
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (allowed.length && !allowed.includes(ext)) { rejected.push(f.name); return; }
    if (!pdfQueueFiles.some(x => x.name === f.name && x.size === f.size && x.lastModified === f.lastModified)) pdfQueueFiles.push(f);
  });
  renderQueue(rejected.length ? `Пропущено (неподходящий формат ${allowed.join(', ')}): ${rejected.join(', ')}` : '');
}

if ($('#pdfFiles')) selectPdf(pdfOperation);

$('#pdfFiles')?.addEventListener('change', e => {
  addPdfFiles(e.target.files);
  e.target.value = '';   // позволяет выбирать файлы повторно и накапливать список
});

const pdfDrop = document.querySelector('#pdfForm .file-drop');
if (pdfDrop) {
  ['dragenter', 'dragover'].forEach(n => pdfDrop.addEventListener(n, e => { e.preventDefault(); pdfDrop.classList.add('dragover'); }));
  ['dragleave', 'drop'].forEach(n => pdfDrop.addEventListener(n, e => { e.preventDefault(); pdfDrop.classList.remove('dragover'); }));
  pdfDrop.addEventListener('drop', e => addPdfFiles(e.dataTransfer.files));
}

$('#pdfQueue')?.addEventListener('click', e => {
  const btn = e.target.closest('[data-q]');
  if (!btn) return;
  const i = Number(btn.dataset.i), act = btn.dataset.q;
  if (act === 'del') pdfQueueFiles.splice(i, 1);
  if (act === 'up' && i > 0) [pdfQueueFiles[i - 1], pdfQueueFiles[i]] = [pdfQueueFiles[i], pdfQueueFiles[i - 1]];
  if (act === 'down' && i < pdfQueueFiles.length - 1) [pdfQueueFiles[i + 1], pdfQueueFiles[i]] = [pdfQueueFiles[i], pdfQueueFiles[i + 1]];
  if (act === 'clear') pdfQueueFiles = [];
  renderQueue();
});

function renderQueue(note = '') {
  const files = pdfQueueFiles;
  const orderMatters = ['merge_pdf', 'images_pdf'].includes(pdfOperation);
  $('#pdfFileNames').textContent = files.length
    ? `${files.length} файл(ов) выбрано · нажмите, чтобы добавить ещё, или перетащите сюда`
    : 'Выберите несколько файлов или перетащите их сюда · ' + pdfAcceptList().join(', ');
  const rows = files.map((f, i) => `<div class="queue-item pdf-queue-row"><span class="pdf-queue-name"><b>${String(i + 1).padStart(2, '0')}. ${esc(f.name)}</b> <small style="color:var(--text-sub)">(${formatBytes(f.size)})</small></span><span class="pdf-queue-actions">${orderMatters ? `<button type="button" data-q="up" data-i="${i}" title="Выше" ${i === 0 ? 'disabled' : ''}>↑</button><button type="button" data-q="down" data-i="${i}" title="Ниже" ${i === files.length - 1 ? 'disabled' : ''}>↓</button>` : ''}<button type="button" data-q="del" data-i="${i}" title="Убрать">✕</button></span></div>`).join('');
  const clear = files.length > 1 ? `<div style="padding:6px 0"><button type="button" class="pdf-queue-clear" data-q="clear" data-i="0">Очистить список</button></div>` : '';
  const warn = note ? `<div style="color:var(--yellow);font-size:12px;padding:4px 0">${esc(note)}</div>` : '';
  $('#pdfQueue').innerHTML = (files.length ? rows + clear : '<span>Файлы не выбраны</span>') + warn;
}

$('#pdfForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const files = [...pdfQueueFiles];
  if (!files.length) return alert('Добавьте файлы.');
  const button = e.submitter, fd = new FormData();
  fd.append('operation', pdfOperation);
  files.forEach(f => fd.append('files', f));
  setBusy(button, true);
  try {
    const data = await api('/api/pdf/process', { method: 'POST', body: fd });
    showResult($('#pdfResult'), `<b>Операция завершена.</b><div style="margin-top:10px"><a class="button primary" href="${data.download_url}">Скачать ${esc(data.filename)}</a></div>`);
  } catch (err) {
    showResult($('#pdfResult'), esc(err.message), true);
  } finally {
    setBusy(button, false);
  }
});

// ----------------- TICKET WRITER AI -----------------
$('#ticketForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const b = e.submitter, fd = new FormData();
  const problemVal = $('#ticketProblem').value.trim();
  if (!problemVal) return;
  fd.append('problem', problemVal);
  setBusy(b, true, 'Формирование заявки…');

  const titleInput = $('#ticketTitle');
  const descInput = $('#ticketDescription');
  const resPanel = $('#ticketResult');
  titleInput.value = '';
  descInput.value = '';
  showResult(resPanel, 'Формирование заявки…');

  let streamText = '';
  await consumeSSE(
    '/api/tickets/generate_stream',
    fd,
    (chunk) => {
      streamText += chunk;
      descInput.value = streamText;
      descInput.scrollTop = descInput.scrollHeight;
    },
    (doneData) => {
      setBusy(b, false);
      if (doneData.title) titleInput.value = doneData.title;
      if (doneData.description) descInput.value = doneData.description;
      showResult(resPanel, 'Заявка сформирована');
    },
    async () => {
      try {
        const data = await api('/api/tickets/generate', { method: 'POST', body: fd });
        titleInput.value = data.title || '';
        descInput.value = data.description || '';
        showResult(resPanel, 'Заявка сформирована');
      } catch (fbErr) {
        const cleanMsg = (fbErr && fbErr.message && !/ollama|gemini|http|traceback/i.test(fbErr.message))
          ? fbErr.message
          : 'Не удалось сформировать заявку. Проверьте текст обращения и повторите попытку.';
        showResult(resPanel, esc(cleanMsg), true);
      } finally {
        setBusy(b, false);
      }
    }
  );
});

$('#copyTicket')?.addEventListener('click', async () => {
  const text = `${$('#ticketTitle').value}\n\n${$('#ticketDescription').value}`.trim();
  if (text) {
    await navigator.clipboard.writeText(text);
    alert('Заявка скопирована в буфер обмена!');
  }
});

// ----------------- PHONEBOOK -----------------
let contacts = [];
async function loadPhonebook() {
  const input = $('#phoneSearch');
  if (!input) return;
  const data = await api('/api/phonebook?q=' + encodeURIComponent(input.value));
  contacts = data.contacts;
  $('#phoneCount').textContent = `${data.shown} ИЗ ${data.total}`;
  $('#phoneRows').innerHTML = contacts.map(c => `<tr><td>${esc(c.department)}</td><td>${esc(c.position)}</td><td><b>${esc(c.name)}</b></td><td>${esc(c.location)}</td><td>${esc(c.city_phone)}</td><td>${esc(c.extension)}</td><td>${esc(c.mobile)}</td><td>${c.email ? `<a href="mailto:${esc(c.email)}" style="color:var(--green-neon)">${esc(c.email)}</a>` : ''}</td><td><button class="button secondary" style="padding:4px 8px;font-size:11px" data-edit="${c.id}">Изменить</button></td></tr>`).join('');
  $$('[data-edit]').forEach(b => b.onclick = () => openContact(Number(b.dataset.edit)));
}

let phoneTimer = null;
$('#phoneSearch')?.addEventListener('input', () => {
  clearTimeout(phoneTimer);
  phoneTimer = setTimeout(loadPhonebook, 250);
});

function openContact(id = 0) {
  const c = contacts.find(x => x.id === id) || {};
  $('#contactHeading').textContent = id ? 'Изменение контакта' : 'Новый контакт';
  $('#contactId').value = id;
  ['department', 'position', 'name', 'location', 'city_phone', 'extension', 'mobile', 'email'].forEach(k => $('#contactForm').elements[k].value = c[k] || '');
  $('#contactDialog').showModal();
}

$('#newContact')?.addEventListener('click', () => openContact());
$('#contactForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  if (e.submitter?.value === 'cancel') {
    $('#contactDialog').close();
    return;
  }
  const fd = new FormData(e.currentTarget);
  const cid = $('#contactId')?.value || '0';
  fd.set('contact_id', cid);
  try {
    await api('/api/phonebook/save', { method: 'POST', body: fd });
    $('#contactDialog').close();
    await loadPhonebook();
  } catch (err) {
    alert(err.message);
  }
});

// ----------------- CODE ACADEMY -----------------
let academy = { python: [], sql: [], book: [], builder_files: [] };
let academyLoaded = false;
const academySelection = { python: 0, sql: 0 };
const academyCompleted = new Set(JSON.parse(localStorage.getItem('bahoniq_academy_completed') || '[]'));

async function loadAcademy() {
  if (typeof window.loadBahonIQAcademy === 'function') {
    return window.loadBahonIQAcademy();
  }
  if (academyLoaded) return;
  try {
    academy = await api('/api/academy/catalog');
    academyLoaded = true;
    renderLessons('python');
    renderLessons('sql');
    renderBook();
    renderBuilder();
    selectLesson('python', 0);
    selectLesson('sql', 0);
    if (academy.book.length) openBook(0);
    if (academy.builder_files.length) openBuilder(academy.builder_files[0]);
    updateAcademyProgress();
  } catch (e) {
    const stage = document.querySelector('.academy-stage');
    if (stage) stage.innerHTML = `<div class="card"><b>Code Academy не загрузилась.</b><p class="helper">${esc(e.message)}</p></div>`;
  }
}

function renderLessons(kind) {
  const query = (document.querySelector(`.academy-search[data-kind="${kind}"]`)?.value || '').toLowerCase();
  const target = $('#' + kind + 'Lessons');
  if (!target) return;
  target.innerHTML = academy[kind].map((x, i) => ({ x, i })).filter(o => !query || (`${o.x.title} ${o.x.theory}`).toLowerCase().includes(query)).map(o => {
    const active = academySelection[kind] === o.i ? ' active' : '';
    const done = academyCompleted.has(`${kind}:${o.x.slug}`) ? ' done' : '';
    return `<button class="academy-lesson-btn${active}${done}" type="button" data-lesson="${kind}:${o.i}">${esc(o.x.title)}</button>`;
  }).join('');
  target.querySelectorAll('button').forEach(b => b.onclick = () => {
    const [k, i] = b.dataset.lesson.split(':');
    selectLesson(k, Number(i));
  });
}

function selectLesson(kind, index) {
  const item = academy[kind][index];
  if (!item) return;
  academySelection[kind] = index;
  renderLessons(kind);
  $('#' + kind + 'Title').textContent = item.title;
  $('#' + kind + 'Theory').textContent = item.theory;
  $('#' + kind + 'Walkthrough').textContent = item.walkthrough;
  $('#' + kind + 'Code').value = item.code;
  $('#' + kind + 'Challenge').textContent = item.challenge;
  $('#' + kind + 'Hint').textContent = item.hint;
  $('#' + kind + 'Level').textContent = `УРОВЕНЬ ${item.level} · ${kind === 'python' ? 'PYTHON' : 'SQL'}`;
  const complete = document.querySelector(`.academy-complete[data-language="${kind}"]`);
  const done = academyCompleted.has(`${kind}:${item.slug}`);
  complete?.classList.toggle('done', done);
  if (complete) complete.textContent = done ? '✓ Урок пройден' : 'Отметить пройденным';
  showAcademyPhase(kind, 'theory');
}

$$('.academy-search').forEach(i => i.oninput = () => renderLessons(i.dataset.kind));
$$('.academy-run').forEach(b => b.onclick = async () => {
  const lang = b.dataset.language, fd = new FormData();
  fd.append('language', lang);
  fd.append('code', $('#' + lang + 'Code').value);
  if (lang === 'python') fd.append('stdin', $('#pythonStdin')?.value || '');
  setBusy(b, true);
  try {
    const data = await api('/api/academy/run', { method: 'POST', body: fd });
    $('#' + lang + 'Output').textContent = (Array.isArray(data.output) ? data.output.join('\n') : data.output || '') + (data.error ? '\n' + data.error : '');
  } catch (e) {
    $('#' + lang + 'Output').textContent = e.message;
  } finally {
    setBusy(b, false);
  }
});

function showAcademyPhase(kind, phase) {
  const view = $('#' + (kind === 'python' ? 'academyPython' : 'academySql'));
  if (!view) return;
  view.querySelectorAll('.academy-phase-tabs button').forEach(b => b.classList.toggle('active', b.dataset.phase === phase));
  const ids = ['Theory', 'Walkthrough', 'Challenge', 'Hint'];
  ids.forEach(s => $('#' + kind + s)?.classList.add('hidden'));
  const phaseMap = { theory: 'Theory', walkthrough: 'Walkthrough', practice: 'Challenge', check: 'Challenge', reinforce: 'Hint' };
  $('#' + kind + phaseMap[phase])?.classList.remove('hidden');
  const labels = { theory: 'ТЕОРИЯ', walkthrough: 'РАЗБОР ПРИМЕРА', practice: 'ПРАКТИЧЕСКОЕ ЗАДАНИЕ', check: 'ПРОВЕРЬ РЕШЕНИЕ ЗАПУСКОМ', reinforce: 'ЗАКРЕПЛЕНИЕ И ПОДСКАЗКА' };
  $('#' + kind + 'PhaseLabel').textContent = labels[phase];
}

$$('.academy-phase-tabs').forEach(tabs => tabs.addEventListener('click', e => {
  const button = e.target.closest('button[data-phase]');
  if (!button) return;
  const view = button.closest('.academy-view');
  showAcademyPhase(view.id === 'academyPython' ? 'python' : 'sql', button.dataset.phase);
}));

$$('[data-academy-view]').forEach(button => button.addEventListener('click', () => {
  $$('.academy-route-btn').forEach(b => b.classList.remove('active'));
  button.classList.add('active');
  $$('.academy-view').forEach(v => v.classList.remove('active'));
  $('#' + button.dataset.academyView)?.classList.add('active');
}));

$$('.academy-reset').forEach(button => button.addEventListener('click', () => {
  const kind = button.dataset.language;
  const item = academy[kind][academySelection[kind]];
  if (item) $('#' + kind + 'Code').value = item.code;
}));

$$('.academy-hint').forEach(button => button.addEventListener('click', () => showAcademyPhase(button.dataset.language, 'reinforce')));
$$('.academy-next').forEach(button => button.addEventListener('click', () => {
  const kind = button.dataset.language;
  const next = Math.min(academySelection[kind] + 1, academy[kind].length - 1);
  selectLesson(kind, next);
  $('#' + kind + 'Lessons')?.querySelector('.academy-lesson-btn.active')?.scrollIntoView({ block: 'nearest' });
}));

$$('.academy-complete').forEach(button => button.addEventListener('click', () => {
  const kind = button.dataset.language;
  const item = academy[kind][academySelection[kind]];
  if (!item) return;
  const key = `${kind}:${item.slug}`;
  if (academyCompleted.has(key)) academyCompleted.delete(key); else academyCompleted.add(key);
  localStorage.setItem('bahoniq_academy_completed', JSON.stringify([...academyCompleted]));
  selectLesson(kind, academySelection[kind]);
  updateAcademyProgress();
}));

function updateAcademyProgress() {
  const total = (academy.python?.length || 48) + (academy.sql?.length || 35);
  const node = $('#academyProgress');
  if (node) node.textContent = `${academyCompleted.size} / ${total} пройдено`;
}

function renderBook() {
  const q = ($('#bookSearch')?.value || '').toLowerCase();
  const container = $('#bookChapters');
  if (!container) return;
  container.innerHTML = academy.book.filter(x => !q || (`${x.section} ${x.title} ${x.file}`).toLowerCase().includes(q)).map(x => `<button class="academy-lesson-btn" type="button" data-chapter="${x.index}">${esc(x.section)} · ${esc(x.title)}</button>`).join('');
  $$('[data-chapter]').forEach(b => b.onclick = () => openBook(Number(b.dataset.chapter)));
}

$('#bookSearch')?.addEventListener('input', renderBook);
async function openBook(index) {
  const data = await api('/api/academy/book/' + index);
  $('#bookTitle').textContent = data.title;
  $('#bookReading').textContent = data.reading;
  $('#bookSource').value = data.source || '';
}

function renderBuilder() {
  const container = $('#builderFiles');
  if (!container) return;
  container.innerHTML = academy.builder_files.map(name => `<button class="academy-lesson-btn" type="button" data-builder="${esc(name)}">${esc(name)}</button>`).join('');
  $$('[data-builder]').forEach(b => b.onclick = () => openBuilder(b.dataset.builder));
}

async function openBuilder(name) {
  const data = await api('/api/academy/builder?name=' + encodeURIComponent(name));
  $('#builderTitle').textContent = data.name;
  $('#builderSource').value = data.source;
}

$('#copyBuilder')?.addEventListener('click', () => navigator.clipboard.writeText($('#builderSource').value));

const mentorDialog = $('#academyMentorDialog');
$('#academyMentorOpen')?.addEventListener('click', () => mentorDialog?.showModal());
$('#academyMentorAsk')?.addEventListener('click', async () => {
  const question = $('#academyMentorQuestion').value.trim();
  if (!question) return;
  const activeKind = $('#academySql')?.classList.contains('active') ? 'sql' : 'python';
  const item = academy[activeKind]?.[academySelection[activeKind]];
  const button = $('#academyMentorAsk');
  const answer = $('#academyMentorAnswer');
  setBusy(button, true, '⚡ Наставник печатает…');
  answer.textContent = '';
  answer.classList.remove('hidden');

  const fd = new FormData();
  fd.append('question', question);
  fd.append('mode', $('#academyMentorMode')?.value || 'hint');
  fd.append('code', $('#' + activeKind + 'Code')?.value || '');
  fd.append('chapter', item?.title || 'Code Academy');

  let streamAns = '';
  await consumeSSE(
    '/api/academy/ask_stream',
    fd,
    (chunk) => {
      streamAns += chunk;
      answer.textContent = streamAns;
      answer.scrollTop = answer.scrollHeight;
    },
    (doneData) => {
      setBusy(button, false);
      if (doneData.answer) answer.textContent = doneData.answer;
      const prov = $('#academyMentorProvider');
      if (prov && doneData.provider_label) prov.textContent = doneData.provider_label;
    },
    async (err) => {
      try {
        const data = await api('/api/academy/ask', { method: 'POST', body: fd });
        answer.textContent = data.answer || 'Ответ не получен.';
        const prov = $('#academyMentorProvider');
        if (prov && data.provider_label) prov.textContent = data.provider_label;
      } catch (fbErr) {
        answer.textContent = fbErr.message || err.message;
      } finally {
        setBusy(button, false);
      }
    }
  );
});

loadPhonebook();

// ----------------- ЗАМЕТКИ (NOTES) -----------------
const notesEditor = $('#notesEditor');
const notesStatusDot = $('#notesStatusDot');
const notesStatusText = $('#notesStatusText');
const notesWordCount = $('#notesWordCount');
const notesCharCount = $('#notesCharCount');
let notesSaveTimeout = null;

function updateNotesCounters(text) {
  const chars = text.length;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  if (notesWordCount) {
    notesWordCount.textContent = `${words} ${words === 1 ? 'слово' : (words >= 2 && words <= 4 ? 'слова' : 'слов')}`;
  }
  if (notesCharCount) {
    notesCharCount.textContent = `${chars} символов`;
  }
}

async function loadNotes() {
  try {
    const res = await api('/api/notes');
    if (notesEditor) {
      notesEditor.value = res.text || '';
      updateNotesCounters(notesEditor.value);
    }
    setNotesStatus('saved');
  } catch (e) {
    console.error('Ошибка загрузки заметок:', e);
  }
}

function setNotesStatus(state) {
  if (!notesStatusDot || !notesStatusText) return;
  if (state === 'saving') {
    notesStatusDot.className = 'status-dot-saving';
    notesStatusText.textContent = 'Сохранение...';
  } else {
    notesStatusDot.className = 'status-dot-saved';
    notesStatusText.textContent = 'Синхронизировано';
  }
}

notesEditor?.addEventListener('input', () => {
  const text = notesEditor.value;
  updateNotesCounters(text);
  setNotesStatus('saving');
  clearTimeout(notesSaveTimeout);
  notesSaveTimeout = setTimeout(async () => {
    try {
      const fd = new FormData();
      fd.append('text', text);
      await api('/api/notes', { method: 'POST', body: fd });
      setNotesStatus('saved');
    } catch (e) {
      console.error('Ошибка сохранения заметок:', e);
    }
  }, 600);
});

$('#copyNotesBtn')?.addEventListener('click', async () => {
  if (!notesEditor) return;
  await navigator.clipboard.writeText(notesEditor.value);
  const btn = $('#copyNotesBtn');
  const originalText = btn.textContent;
  btn.textContent = '✓ Скопировано!';
  setTimeout(() => { btn.textContent = originalText; }, 1800);
});

$('#clearNotesBtn')?.addEventListener('click', async () => {
  if (!notesEditor) return;
  if (confirm('Очистить текст всех заметок?')) {
    notesEditor.value = '';
    updateNotesCounters('');
    setNotesStatus('saving');
    try {
      const fd = new FormData();
      fd.append('text', '');
      await api('/api/notes', { method: 'POST', body: fd });
      setNotesStatus('saved');
    } catch (e) {
      console.error('Ошибка очистки заметок:', e);
    }
  }
});

// ----------------- СВЕРКА СТУДЕНТОВ (RECONCILE) -----------------
const recFile1 = $('#reconcileFile1');
const recFile2 = $('#reconcileFile2');
const recName1 = $('#reconcileFileName1');
const recName2 = $('#reconcileFileName2');
const recForm = $('#reconcileForm');
const recProgress = $('#reconcileProgress');
const recResult = $('#reconcileResult');
const recBtn = $('#reconcileSubmitBtn');

recFile1?.addEventListener('change', e => {
  const f = e.target.files[0];
  if (recName1) recName1.textContent = f ? `${f.name} (${formatBytes(f.size)})` : '.xls, .xlsx или .xlsm, до 50 МБ';
});

recFile2?.addEventListener('change', e => {
  const f = e.target.files[0];
  if (recName2) recName2.textContent = f ? `${f.name} (${formatBytes(f.size)})` : '.xls, .xlsx или .xlsm, до 50 МБ';
});

recForm?.addEventListener('submit', async e => {
  e.preventDefault();
  const f1 = recFile1?.files[0];
  const f2 = recFile2?.files[0];

  if (!f1 || !f2) {
    alert('Пожалуйста, выберите оба файла для сверки.');
    return;
  }

  setBusy(recBtn, true, 'Сверка баз студентов…');
  if (recProgress) recProgress.classList.remove('hidden');
  if (recResult) recResult.classList.add('hidden');

  const fd = new FormData();
  fd.append('file1', f1);
  fd.append('file2', f2);

  try {
    const data = await api('/api/excel/reconcile', { method: 'POST', body: fd });
    const c = data.counts || {};

    let html = `
      <div style="background:rgba(20,200,193,0.08);border:1px solid rgba(20,200,193,0.3);border-radius:12px;padding:20px;margin-bottom:20px;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px;">
          <div>
            <h2 style="font-size:18px;margin:0 0 4px 0;color:var(--text-main);">Сверка успешно завершена!</h2>
            <div style="font-size:13px;color:var(--text-muted);">
              Сравнение файлов: <b>${esc(data.file1_name)}</b> и <b>${esc(data.file2_name)}</b>
            </div>
          </div>
          <a class="button primary" style="padding:10px 20px;font-size:14px;text-decoration:none;display:inline-flex;align-items:center;gap:8px;" href="${data.download_url}" download>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Скачать отчёт сверки (.xlsx)
          </a>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px;margin-bottom:16px;">
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:var(--text-sub);text-transform:uppercase;">Файл 1 (всего)</div>
            <div style="font-size:24px;font-weight:700;color:var(--text-main);margin-top:4px;">${c.total1?.toLocaleString() || 0}</div>
          </div>
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:var(--text-sub);text-transform:uppercase;">Файл 2 (всего)</div>
            <div style="font-size:24px;font-weight:700;color:var(--text-main);margin-top:4px;">${c.total2?.toLocaleString() || 0}</div>
          </div>
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:var(--text-sub);text-transform:uppercase;">Совпали в обоих</div>
            <div style="font-size:24px;font-weight:700;color:var(--green-neon);margin-top:4px;">${c.matched?.toLocaleString() || 0}</div>
          </div>
          <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:var(--yellow);text-transform:uppercase;font-weight:600;">НЕ повторяются (всего)</div>
            <div style="font-size:24px;font-weight:700;color:var(--yellow);margin-top:4px;">${c.unique_total?.toLocaleString() || 0}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">(Файл 1: ${c.only1} | Файл 2: ${c.only2})</div>
          </div>
        </div>

        <p style="font-size:13px;color:var(--text-sub);margin:0;">
          Готовый файл Excel содержит 5 вкладок: <b>Сводка сверки</b>, <b>Все_неповторяющиеся</b> (${c.unique_total}), <b>Только_в_Файле_1</b> (${c.only1}), <b>Только_в_Файле_2</b> (${c.only2}) и <b>Совпавшие_студенты</b> (${c.matched}).
        </p>
      </div>
    `;

    if (data.samples_only2 && data.samples_only2.length > 0) {
      html += `
        <div style="margin-bottom:20px;">
          <h3 style="font-size:15px;margin-bottom:8px;color:var(--text-main);">Студенты, найденные только во втором файле (${data.samples_only2.length} чел.):</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>№</th>
                  <th>ФИО</th>
                  <th>ИИН</th>
                  <th>Курс</th>
                  <th>Специальность</th>
                  <th>Общежитие / Комната</th>
                </tr>
              </thead>
              <tbody>
                ${data.samples_only2.map(s => `
                  <tr>
                    <td>${s.num}</td>
                    <td><b>${esc(s.fio)}</b></td>
                    <td><code>${esc(s.iin || '-')}</code></td>
                    <td>${esc(s.kurs || '-')}</td>
                    <td>${esc(s.fac_spec || '-')}</td>
                    <td>${esc(s.dorm || '')} ${esc(s.room ? 'комн. ' + s.room : '')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    if (data.samples_only1 && data.samples_only1.length > 0) {
      html += `
        <div>
          <h3 style="font-size:15px;margin-bottom:8px;color:var(--text-main);">Образец студентов, которые есть только в первом файле (показаны первые 20 из ${c.only1}):</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>№</th>
                  <th>ФИО</th>
                  <th>ИИН</th>
                  <th>Курс</th>
                  <th>Факультет</th>
                  <th>Регион</th>
                </tr>
              </thead>
              <tbody>
                ${data.samples_only1.map(s => `
                  <tr>
                    <td>${s.num}</td>
                    <td><b>${esc(s.fio)}</b></td>
                    <td><code>${esc(s.iin || '-')}</code></td>
                    <td>${esc(s.kurs || '-')}</td>
                    <td>${esc(s.fac_spec || '-')}</td>
                    <td>${esc(s.reg || '-')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          <small style="display:block;margin-top:6px;color:var(--text-sub);">Полный реестр всех ${c.only1} студентов доступен в скачиваемом Excel-файле.</small>
        </div>
      `;
    }

    if (recResult) {
      recResult.innerHTML = html;
      recResult.classList.remove('hidden');
    }
  } catch (err) {
    if (recResult) {
      showResult(recResult, `<b>Ошибка сверки:</b> ${esc(err.message)}`, true);
    } else {
      alert('Ошибка сверки: ' + err.message);
    }
  } finally {
    setBusy(recBtn, false);
    if (recProgress) recProgress.classList.add('hidden');
  }
});

// Конвертер XLS в XLSX
const convertForm = $('#convertXlsForm');
const convertInput = $('#convertXlsInput');
const convertBtn = $('#convertXlsBtn');
const convertResult = $('#convertXlsResult');

convertForm?.addEventListener('submit', async e => {
  e.preventDefault();
  const file = convertInput?.files[0];
  if (!file) {
    alert('Пожалуйста, выберите файл .xls');
    return;
  }
  setBusy(convertBtn, true, 'Конвертация в XLSX…');
  if (convertResult) convertResult.classList.add('hidden');

  const fd = new FormData();
  fd.append('workbook', file);

  try {
    const data = await api('/api/excel/convert-xls', { method: 'POST', body: fd });
    if (convertResult) {
      convertResult.className = 'result-panel';
      convertResult.innerHTML = `
        <div style="background:rgba(0,230,118,0.08);border:1px solid rgba(0,230,118,0.3);border-radius:10px;padding:16px;">
          <h3 style="margin:0 0 8px;color:var(--green-neon);font-size:16px;">✓ Файл успешно сконвертирован!</h3>
          <p style="margin:0 0 12px;font-size:13px;color:var(--text-main);">
            Файл <b>${esc(data.filename)}</b> готов в современном формате XLSX со всеми листами и данными.
          </p>
          <a class="button primary" href="${data.download_url}" style="display:inline-block;padding:8px 18px;text-decoration:none;">Скачать ${esc(data.filename)}</a>
        </div>
      `;
      convertResult.classList.remove('hidden');
    }
  } catch (err) {
    if (convertResult) {
      convertResult.className = 'result-panel error';
      convertResult.textContent = err.message;
      convertResult.classList.remove('hidden');
    }
  } finally {
    setBusy(convertBtn, false);
  }
});


// Выдвижное меню систем (мобильная версия)
(function () {
  const sb = $('.sidebar'), btn = $('#sidebarToggle'), bd = $('#sidebarBackdrop');
  if (!sb || !btn) return;
  const setOpen = open => {
    sb.classList.toggle('open', open);
    bd?.classList.toggle('show', open);
    btn.setAttribute('aria-expanded', String(open));
  };
  btn.addEventListener('click', () => setOpen(!sb.classList.contains('open')));
  bd?.addEventListener('click', () => setOpen(false));
  sb.addEventListener('click', e => { if (e.target.closest('a.system-item')) setOpen(false); });
  window.addEventListener('resize', () => { if (window.innerWidth > 768) setOpen(false); });
})();


// Обработка горизонтальной прокрутки таблицы кнопками и пальцем
(function initTableScrollHelper() {
  function scrollWrap(wrap, delta) {
    if (!wrap) return;
    try {
      wrap.scrollBy({ left: delta, behavior: 'smooth' });
    } catch (e) {
      wrap.scrollLeft += delta;
    }
  }

  function handleScrollBtn(target) {
    const btn = target.closest('.btn-scroll-left, .btn-scroll-right');
    if (!btn) return false;
    const isLeft = btn.classList.contains('btn-scroll-left');
    const delta = isLeft ? -280 : 280;
    const wrap = btn.closest('.preview-card, #analytics, .tab-page, .module-page')?.querySelector('.table-wrap') || document.querySelector('.table-wrap');
    if (wrap) {
      scrollWrap(wrap, delta);
    }
    return true;
  }

  // Клик по кнопкам Влево / Вправо
  document.addEventListener('click', (e) => {
    handleScrollBtn(e.target);
  });

  // Сенсорное перетаскивание таблицы пальцем (touch drag)
  function bindTouch(wrap) {
    if (!wrap || wrap._touchReady) return;
    wrap._touchReady = true;

    let startX = 0, startY = 0, startScroll = 0, isDragging = false, isHorizontal = false;

    wrap.addEventListener('touchstart', (e) => {
      if (e.touches.length !== 1) return;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      startScroll = wrap.scrollLeft;
      isDragging = true;
      isHorizontal = false;
    }, { passive: true });

    wrap.addEventListener('touchmove', (e) => {
      if (!isDragging || e.touches.length !== 1) return;
      const x = e.touches[0].clientX;
      const y = e.touches[0].clientY;
      const diffX = startX - x;
      const diffY = startY - y;

      if (!isHorizontal) {
        if (Math.abs(diffX) > 6 && Math.abs(diffX) > Math.abs(diffY)) {
          isHorizontal = true;
        } else if (Math.abs(diffY) > 8) {
          isDragging = false;
          return;
        }
      }

      if (isHorizontal) {
        wrap.scrollLeft = startScroll + diffX;
        if (e.cancelable) e.preventDefault();
      }
    }, { passive: false });

    const endDrag = () => { isDragging = false; isHorizontal = false; };
    wrap.addEventListener('touchend', endDrag, { passive: true });
    wrap.addEventListener('touchcancel', endDrag, { passive: true });

    // Индикатор прокрутки
    wrap.addEventListener('scroll', () => {
      const max = wrap.scrollWidth - wrap.clientWidth;
      const ind = wrap.parentElement?.querySelector('.scroll-status');
      if (ind && max > 0) {
        const pct = Math.round((wrap.scrollLeft / max) * 100);
        ind.textContent = `↔ Прокрутка: ${pct}% ${pct >= 95 ? '(конец)' : pct <= 5 ? '(начало)' : ''}`;
      }
    }, { passive: true });
  }

  function rebind() {
    document.querySelectorAll('.table-wrap').forEach(bindTouch);
  }
  rebind();
  setInterval(rebind, 1200);
})();

// Гарантированная поддержка Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X на ЛЮБОЙ раскладке (русской, английской, казахской)
(function initClipboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    const code = e.code; // Всегда физическая клавиша: KeyA, KeyC, KeyV, KeyX независимо от языка
    const active = document.activeElement;
    const isInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable);

    // Ctrl + A (Выделить всё)
    if (code === 'KeyA') {
      if (isInput) {
        active.select?.();
        e.preventDefault();
      } else {
        const sel = window.getSelection();
        const range = document.createRange();
        const container = active?.closest('.card, .preview-card, .tab-page, .module-page, table') || document.querySelector('.module-page.active') || document.body;
        range.selectNodeContents(container);
        sel.removeAllRanges();
        sel.addRange(range);
        e.preventDefault();
      }
    }

    // Ctrl + C (Копировать)
    if (code === 'KeyC') {
      const sel = window.getSelection();
      const selectedText = sel ? sel.toString() : '';
      if (selectedText) {
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(selectedText);
          }
        } catch (err) {}
      }
    }

    // Ctrl + V (Вставить)
    // Браузер выполняет нативную вставку автоматически на всех раскладках клавиатуры.
    // Не вызываем программный readText/setRangeText, чтобы исключить двойную вставку контента.
  });
})();

// ============================================================================
// МОДУЛЬ: PLATONUS WIKI AI (Единая серверная база знаний SQLite + Gemini Flash)
// ============================================================================
(function initPlatonusWikiModule() {
  const treeContainer = $('#wikiTopicsTree');
  const treeSearchInput = $('#wikiTreeSearchInput');
  const totalStatsText = $('#wikiTotalStatsText');

  const askPanel = $('#wikiAskPanel');
  const questionInput = $('#wikiQuestionInput');
  const askBtn = $('#wikiAskBtn');
  const answerBox = $('#wikiAnswerBox');
  const answerContent = $('#wikiAnswerContent');
  const answerProviderLabel = $('#wikiAnswerProviderLabel');
  const copyAnswerBtn = $('#wikiCopyAnswerBtn');
  const sourcesWrap = $('#wikiSourcesWrap');
  const sourcesList = $('#wikiSourcesList');

  const articleCard = $('#wikiArticleCard');
  const backToSearchBtn = $('#wikiBackToSearchBtn');
  const copyArticleBtn = $('#wikiCopyArticleBtn');
  const editArticleBtn = $('#wikiEditArticleBtn');
  const deleteArticleBtn = $('#wikiDeleteArticleBtn');

  const articleViewMode = $('#wikiArticleViewMode');
  const articleTopicBadge = $('#wikiArticleTopicBadge');
  const articleSourceFile = $('#wikiArticleSourceFile');
  const articleTitleEl = $('#wikiArticleTitle');
  const articleBodyEl = $('#wikiArticleBody');

  const articleEditMode = $('#wikiArticleEditMode');
  const editFormHeading = $('#wikiEditFormHeading');
  const editTopicInput = $('#wikiEditTopicInput');
  const editTitleInput = $('#wikiEditTitleInput');
  const editContentInput = $('#wikiEditContentInput');
  const cancelEditBtn = $('#wikiCancelEditBtn');
  const saveArticleBtn = $('#wikiSaveArticleBtn');
  const addManualBtn = $('#wikiAddManualBtn');

  const uploadModal = $('#wikiUploadModal');
  const openUploadModalBtn = $('#wikiOpenUploadModalBtn');
  const closeUploadModalBtn = $('#wikiCloseUploadModalBtn');
  const cancelUploadBtn = $('#wikiCancelUploadBtn');
  const dropZone = $('#wikiDropZone');
  const filesInput = $('#wikiFilesInput');
  const selectedFilesBox = $('#wikiSelectedFilesBox');
  const uploadProgressWrap = $('#wikiUploadProgressWrap');
  const uploadProgressBar = $('#wikiUploadProgressBar');
  const uploadStatusText = $('#wikiUploadStatusText');
  const uploadResultBox = $('#wikiUploadResultBox');
  const startUploadBtn = $('#wikiStartUploadBtn');

  let cachedTree = { total_topics: 0, total_articles: 0, topics: [] };
  let activeArticle = null;
  let isCreatingNewArticle = false;
  let lastRawAnswer = '';
  let pendingUploadFiles = [];

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatRichText(text) {
    let safe = escapeHtml(text || '');
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
    return safe;
  }

  async function copyText(text, btn, doneText = '✓ Скопировано') {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
    }
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = doneText;
      setTimeout(() => { btn.textContent = orig; }, 1800);
    }
  }

  // 1. Загрузка и отрисовка дерева разделов и инструкций
  async function fetchWikiTree() {
    try {
      const res = await fetch('/api/wiki/tree');
      if (!res.ok) throw new Error('Ошибка загрузки дерева базы знаний');
      cachedTree = await res.json();
      if (totalStatsText) {
        totalStatsText.textContent = `Разделов: ${cachedTree.total_topics} • Инструкций: ${cachedTree.total_articles}`;
      }
      renderWikiTree(treeSearchInput?.value || '');
    } catch (err) {
      if (treeContainer) {
        treeContainer.innerHTML = `<div style="padding:12px;color:var(--text-sub);font-size:12.5px;">Не удалось загрузить список инструкций.</div>`;
      }
    }
  }

  function renderWikiTree(filterQuery = '') {
    if (!treeContainer) return;
    const q = (filterQuery || '').trim().toLowerCase();
    const topics = cachedTree.topics || [];

    if (!topics.length) {
      treeContainer.innerHTML = `<div style="padding:14px;color:var(--text-sub);font-size:12.5px;">База пуста. Нажмите «+ Загрузить инструкции», чтобы добавить файлы.</div>`;
      return;
    }

    let html = '';
    topics.forEach((topic) => {
      const matchedArticles = (topic.articles || []).filter(a => {
        if (!q) return true;
        return a.title.toLowerCase().includes(q) || topic.name.toLowerCase().includes(q);
      });
      if (!matchedArticles.length) return;

      const hasActive = activeArticle && matchedArticles.some(a => a.id === activeArticle.id);
      const isCollapsed = (!q && !hasActive) ? 'collapsed' : '';

      const articlesHtml = matchedArticles.map(art => {
        const isActive = activeArticle && activeArticle.id === art.id ? 'active' : '';
        return `<button type="button" class="wiki-article-item ${isActive}" data-article-id="${art.id}">${escapeHtml(art.title)}</button>`;
      }).join('');

      html += `
        <div class="wiki-topic-block ${isCollapsed}" data-topic-id="${topic.id}">
          <button type="button" class="wiki-topic-header">
            <span>${escapeHtml(topic.name)}</span>
            <span class="wiki-topic-count">${matchedArticles.length}</span>
          </button>
          <div class="wiki-topic-articles">
            ${articlesHtml}
          </div>
        </div>
      `;
    });

    treeContainer.innerHTML = html || `<div style="padding:12px;color:var(--text-sub);font-size:12.5px;">По запросу «${escapeHtml(filterQuery)}» статей не найдено.</div>`;
  }

  treeContainer?.addEventListener('click', (e) => {
    const header = e.target.closest('.wiki-topic-header');
    if (header) {
      const block = header.closest('.wiki-topic-block');
      block?.classList.toggle('collapsed');
      return;
    }
    const artBtn = e.target.closest('.wiki-article-item');
    if (artBtn) {
      const id = Number(artBtn.dataset.articleId);
      if (id) openArticleById(id);
    }
  });

  treeSearchInput?.addEventListener('input', () => {
    renderWikiTree(treeSearchInput.value);
  });

  // 2. Просмотр, редактирование, создание и удаление статьи
  async function openArticleById(articleId) {
    try {
      const res = await fetch(`/api/wiki/articles/${articleId}`);
      if (!res.ok) throw new Error('Статья не найдена');
      const art = await res.json();
      activeArticle = art;
      isCreatingNewArticle = false;

      if (articleTopicBadge) articleTopicBadge.textContent = art.topic_name || 'Раздел';
      if (articleSourceFile) {
        articleSourceFile.textContent = art.source_filename ? `Источник: ${art.source_filename}` : '';
      }
      if (articleTitleEl) articleTitleEl.textContent = art.title || '';
      if (articleBodyEl) articleBodyEl.innerHTML = formatRichText(art.content || '');

      articleViewMode?.classList.remove('hidden');
      articleEditMode?.classList.add('hidden');
      askPanel?.classList.add('hidden');
      articleCard?.classList.remove('hidden');

      renderWikiTree(treeSearchInput?.value || '');
    } catch (err) {
      alert(err.message || 'Ошибка открытия инструкции');
    }
  }

  function showSearchWorkspace() {
    activeArticle = null;
    isCreatingNewArticle = false;
    articleCard?.classList.add('hidden');
    askPanel?.classList.remove('hidden');
    renderWikiTree(treeSearchInput?.value || '');
  }

  backToSearchBtn?.addEventListener('click', showSearchWorkspace);

  copyArticleBtn?.addEventListener('click', () => {
    if (!activeArticle) return;
    copyText(`${activeArticle.title}\n\n${activeArticle.content}`, copyArticleBtn);
  });

  editArticleBtn?.addEventListener('click', () => {
    if (!activeArticle) return;
    isCreatingNewArticle = false;
    if (editFormHeading) editFormHeading.textContent = 'Редактирование инструкции';
    if (editTopicInput) editTopicInput.value = activeArticle.topic_name || '';
    if (editTitleInput) editTitleInput.value = activeArticle.title || '';
    if (editContentInput) editContentInput.value = activeArticle.content || '';
    articleViewMode?.classList.add('hidden');
    articleEditMode?.classList.remove('hidden');
  });

  addManualBtn?.addEventListener('click', () => {
    activeArticle = null;
    isCreatingNewArticle = true;
    if (editFormHeading) editFormHeading.textContent = 'Новая текстовая инструкция';
    if (editTopicInput) {
      editTopicInput.value = cachedTree.topics?.[0]?.name || 'Раздел 3: Журнал, оценки и Рубежный контроль (РК)';
    }
    if (editTitleInput) editTitleInput.value = '';
    if (editContentInput) editContentInput.value = '';
    askPanel?.classList.add('hidden');
    articleCard?.classList.remove('hidden');
    articleViewMode?.classList.add('hidden');
    articleEditMode?.classList.remove('hidden');
  });

  cancelEditBtn?.addEventListener('click', () => {
    if (isCreatingNewArticle) {
      showSearchWorkspace();
    } else {
      articleEditMode?.classList.add('hidden');
      articleViewMode?.classList.remove('hidden');
    }
  });

  saveArticleBtn?.addEventListener('click', async () => {
    const topicName = (editTopicInput?.value || '').trim();
    const title = (editTitleInput?.value || '').trim();
    const content = (editContentInput?.value || '').trim();
    if (!title || !content) {
      alert('Заполните заголовок и текст инструкции.');
      return;
    }

    saveArticleBtn.disabled = true;
    try {
      const url = isCreatingNewArticle
        ? '/api/wiki/articles'
        : `/api/wiki/articles/${activeArticle.id}`;
      const method = isCreatingNewArticle ? 'POST' : 'PUT';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_name: topicName, title, content }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Ошибка сохранения');
      await fetchWikiTree();
      await openArticleById(data.id);
    } catch (err) {
      alert(err.message || 'Не удалось сохранить инструкцию');
    } finally {
      saveArticleBtn.disabled = false;
    }
  });

  deleteArticleBtn?.addEventListener('click', async () => {
    if (!activeArticle) return;
    if (!confirm(`Удалить инструкцию «${activeArticle.title}» из базы знаний?`)) return;
    try {
      const res = await fetch(`/api/wiki/articles/${activeArticle.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Не удалось удалить статью');
      await fetchWikiTree();
      showSearchWorkspace();
    } catch (err) {
      alert(err.message || 'Ошибка удаления');
    }
  });

  // 3. AI-поиск и генерация ответа по базе знаний
  async function runWikiAsk(customQuery) {
    const q = (customQuery ?? questionInput?.value ?? '').trim();
    if (!q) {
      questionInput?.focus();
      return;
    }
    if (questionInput && customQuery) {
      questionInput.value = customQuery;
    }

    showSearchWorkspace();
    if (askBtn) {
      askBtn.disabled = true;
      askBtn.textContent = 'ИИ ищет в базе...';
    }
    answerBox?.classList.remove('hidden');
    if (answerContent) {
      answerContent.innerHTML = '⏳ Поиск релевантных инструкций в базе знаний и подготовка пошагового ответа...';
    }
    sourcesWrap?.classList.add('hidden');

    try {
      const res = await fetch('/api/wiki/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Ошибка получения ответа');

      lastRawAnswer = data.answer || '';
      if (answerProviderLabel) {
        answerProviderLabel.textContent = data.provider === 'gemini'
          ? 'Ответ эксперта ИИ (BahonIQ AI • строго по базе знаний)'
          : 'Ответ по базе инструкций Platonus';
      }
      if (answerContent) {
        answerContent.innerHTML = formatRichText(lastRawAnswer);
      }

      const sources = data.sources || [];
      if (sources.length && sourcesList && sourcesWrap) {
        sourcesList.innerHTML = sources.map(s => `
          <button type="button" class="wiki-source-link" data-source-id="${s.id}">
            <span>📄 ${escapeHtml(s.title)}</span>
          </button>
        `).join('');
        sourcesWrap.classList.remove('hidden');
      } else {
        sourcesWrap?.classList.add('hidden');
      }
    } catch (err) {
      if (answerContent) {
        answerContent.textContent = `Ошибка: ${err.message || 'Не удалось выполнить поиск'}`;
      }
    } finally {
      if (askBtn) {
        askBtn.disabled = false;
        askBtn.textContent = 'Получить ответ';
      }
    }
  }

  askBtn?.addEventListener('click', () => runWikiAsk());

  questionInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      runWikiAsk();
    }
  });

  document.querySelectorAll('.wiki-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.q;
      if (q) runWikiAsk(q);
    });
  });

  copyAnswerBtn?.addEventListener('click', () => {
    copyText(lastRawAnswer, copyAnswerBtn);
  });

  sourcesList?.addEventListener('click', (e) => {
    const btn = e.target.closest('.wiki-source-link');
    if (btn) {
      const id = Number(btn.dataset.sourceId);
      if (id) openArticleById(id);
    }
  });

  // 4. Пакетная загрузка файлов (.pdf, .docx, .txt) с авто-каталогизацией ИИ
  function openUploadModal() {
    pendingUploadFiles = [];
    if (filesInput) filesInput.value = '';
    selectedFilesBox?.classList.add('hidden');
    uploadProgressWrap?.classList.add('hidden');
    uploadResultBox?.classList.add('hidden');
    if (startUploadBtn) startUploadBtn.disabled = true;
    uploadModal?.classList.remove('hidden');
  }

  function closeUploadModal() {
    uploadModal?.classList.add('hidden');
  }

  openUploadModalBtn?.addEventListener('click', openUploadModal);
  closeUploadModalBtn?.addEventListener('click', closeUploadModal);
  cancelUploadBtn?.addEventListener('click', closeUploadModal);
  uploadModal?.addEventListener('click', (e) => {
    if (e.target === uploadModal) closeUploadModal();
  });

  function updatePendingFilesList(fileList) {
    pendingUploadFiles = Array.from(fileList || []).filter(f => {
      const low = f.name.toLowerCase();
      return low.endsWith('.pdf') || low.endsWith('.docx') || low.endsWith('.doc') || low.endsWith('.txt') || low.endsWith('.md');
    });

    if (!pendingUploadFiles.length) {
      selectedFilesBox?.classList.add('hidden');
      if (startUploadBtn) startUploadBtn.disabled = true;
      return;
    }

    if (selectedFilesBox) {
      selectedFilesBox.innerHTML = `
        <div style="font-weight:700;color:var(--text-main);margin-bottom:6px;">Выбрано файлов: ${pendingUploadFiles.length}</div>
        ${pendingUploadFiles.map(f => `<div>• ${escapeHtml(f.name)} <span style="opacity:.65">(${(f.size / 1024).toFixed(1)} КБ)</span></div>`).join('')}
      `;
      selectedFilesBox.classList.remove('hidden');
    }
    if (startUploadBtn) startUploadBtn.disabled = false;
  }

  filesInput?.addEventListener('change', () => {
    updatePendingFilesList(filesInput.files);
  });

  dropZone?.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone?.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });
  dropZone?.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer?.files?.length) {
      updatePendingFilesList(e.dataTransfer.files);
    }
  });

  startUploadBtn?.addEventListener('click', async () => {
    if (!pendingUploadFiles.length) return;
    startUploadBtn.disabled = true;
    uploadResultBox?.classList.add('hidden');
    uploadProgressWrap?.classList.remove('hidden');
    if (uploadProgressBar) uploadProgressBar.style.width = '35%';
    if (uploadStatusText) {
      uploadStatusText.textContent = `Обработка файлов (${pendingUploadFiles.length} шт.)... ИИ извлекает текст и распределяет инструкции по темам`;
    }

    try {
      const fd = new FormData();
      pendingUploadFiles.forEach(f => fd.append('files', f));

      if (uploadProgressBar) uploadProgressBar.style.width = '70%';
      const res = await fetch('/api/wiki/upload', {
        method: 'POST',
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки файлов');

      if (uploadProgressBar) uploadProgressBar.style.width = '100%';
      if (uploadStatusText) {
        uploadStatusText.textContent = `✓ Готово! Обработано файлов: ${data.files_processed}, сохранено инструкций: ${(data.articles_created || []).length}`;
      }

      if (uploadResultBox) {
        const createdList = (data.articles_created || [])
          .map(a => `<div>• <b>${escapeHtml(a.title)}</b> <span style="opacity:.75">(${escapeHtml(a.topic)})</span></div>`)
          .join('');
        uploadResultBox.innerHTML = `
          <div style="font-weight:700;margin-bottom:6px;">Инструкции успешно сохранены в базу Work Center:</div>
          ${createdList || '<div>Файлы обработаны.</div>'}
        `;
        uploadResultBox.classList.remove('hidden');
      }

      await fetchWikiTree();
    } catch (err) {
      if (uploadStatusText) {
        uploadStatusText.textContent = `Ошибка: ${err.message || 'Не удалось обработать файлы'}`;
      }
    }
  });

  window.loadPlatonusWiki = fetchWikiTree;
  fetchWikiTree();
})();

// ============================================================================
// ============================================================================
// МОДУЛЬ: BAHONIQ AI ACADEMY (60 УРОКОВ + ЖИВОЙ ИИ-ТРЕНЕР + МИКРОШАГИ + ТЕСТЫ + PDF)
// ============================================================================
(function initBahonIQAcademyModule() {
  const overallText = document.getElementById('acadOverallText');
  const overallFill = document.getElementById('acadOverallFill');
  const exportPdfBtn = document.getElementById('acadExportPdfBtn');
  const stagesNav = document.getElementById('acadStagesNav');

  const currentStageLabel = document.getElementById('acadCurrentStageLabel');
  const stageLessonsCount = document.getElementById('acadStageLessonsCount');
  const lessonFilter = document.getElementById('acadLessonFilter');
  const lessonsList = document.getElementById('acadLessonsList');

  const lessonStageBadge = document.getElementById('acadLessonStageBadge');
  const lessonStatusBadge = document.getElementById('acadLessonStatusBadge');
  const lessonTitle = document.getElementById('acadLessonTitle');
  const lessonSummary = document.getElementById('acadLessonSummary');

  const stepPill1 = document.getElementById('acadStepPill1');
  const stepPill2 = document.getElementById('acadStepPill2');
  const stepPill3 = document.getElementById('acadStepPill3');
  const regenAiBtn = document.getElementById('acadRegenAiBtn');

  const trainerFeed = document.getElementById('acadTrainerFeed');
  const repoFileBox = null;
  const repoFileName = null;
  const repoFileCode = null;

  // Доки ответов
  const step1Dock = document.getElementById('acadStep1Dock');
  const step1Input = document.getElementById('acadStep1Input');
  const submitStep1Btn = document.getElementById('acadSubmitStep1Btn');

  const step2Dock = document.getElementById('acadStep2Dock');
  const codeEditor = document.getElementById('acadCodeEditor');
  const editorLangTag = document.getElementById('acadEditorLangTag');
  const resetCodeBtn = document.getElementById('acadResetCodeBtn');
  const runCodeBtn = document.getElementById('acadRunCodeBtn');
  const submitStep2Btn = document.getElementById('acadSubmitStep2Btn');
  const consoleOutput = document.getElementById('acadConsoleOutput');

  const step3Dock = document.getElementById('acadStep3Dock');
  const quizQuestionsContainer = document.getElementById('acadQuizQuestionsContainer');
  const submitQuizBtn = document.getElementById('acadSubmitQuizBtn');
  const nextLessonBtn = document.getElementById('acadNextLessonBtn');
  const restoreProgressBtn = document.getElementById('acadRestoreProgressBtn');
  const markPassedBtn = document.getElementById('acadMarkPassedBtn');

  const clearChatBtn = document.getElementById('acadClearChatBtn');
  const chatLessonHint = document.getElementById('acadChatLessonHint');
  const chatMessages = document.getElementById('acadChatMessages');
  const chatInput = document.getElementById('acadChatInput');
  const chatSendBtn = document.getElementById('acadChatSendBtn');
  const CHAT_STORAGE_PREFIX = 'code_academy_chat_lesson_';

  // Канонические ключи LocalStorage и множество завершённых уроков (ID + stable_id)
  const ACADEMY_STORAGE_KEY = 'bahoniq_academy_progress_v2';
  const ACADEMY_LAST_LESSON_KEY = 'bahoniq_academy_last_lesson_id';
  const completedLessonsSet = new Set();

  let roadmapData = null;
  let currentStageId = 1;
  let currentLesson = null;
  let userQuizAnswers = {};

  function migrateAndLoadAcademyProgress() {
    // Дефолтный прогресс: Урок 1 и Урок 2 всегда завершены (2/18)
    completedLessonsSet.add('1');
    completedLessonsSet.add('2');
    completedLessonsSet.add('python_01_environment');
    completedLessonsSet.add('python_02_variables');

    // Безопасная миграция старых форматов без сброса и потерь
    const oldKeys = ['bahoniq_academy_completed', 'academy_progress', 'code_academy_progress', ACADEMY_STORAGE_KEY];
    oldKeys.forEach(key => {
      try {
        const raw = localStorage.getItem(key);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) {
            parsed.forEach(id => completedLessonsSet.add(String(id)));
          } else if (typeof parsed === 'object' && parsed !== null) {
            Object.keys(parsed).forEach(id => {
              if (parsed[id]) completedLessonsSet.add(String(id));
            });
          }
        }
      } catch {}
    });

    try {
      localStorage.setItem(ACADEMY_STORAGE_KEY, JSON.stringify([...completedLessonsSet]));
    } catch {}

    // Фоновая синхронизация с сервером
    fetch('/api/academy/progress/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ completed_ids: [...completedLessonsSet] }),
    }).then(r => r.json()).then(data => {
      if (data && data.roadmap) {
        roadmapData = data.roadmap;
        renderRoadmapUI();
      }
    }).catch(() => {});
  }

  function isLessonCompleted(les) {
    if (!les) return false;
    if (les.completed) return true;
    if (completedLessonsSet.has(String(les.id))) return true;
    if (les.stable_id && completedLessonsSet.has(les.stable_id)) return true;
    return false;
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatText(raw) {
    let s = escapeHtml(raw || '');
    s = s.replace(/```([a-zA-Z]*)\r?\n([\s\S]*?)```/g, '<pre class="acad-trap-code">$2</pre>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\n/g, '<br/>');
    return s;
  }

  // 1. Отрисовка дорожной карты и прогресса
  function renderRoadmapUI() {
    if (!roadmapData) return;

    let overallDone = 0;
    (roadmapData.stages || []).forEach(st => {
      let stDone = 0;
      (st.lessons || []).forEach(les => {
        if (isLessonCompleted(les)) {
          les.completed = true;
          stDone++;
        }
      });
      st.completed_lessons = Math.max(st.completed_lessons || 0, stDone);
      st.percent = st.total_lessons ? Math.round((st.completed_lessons / st.total_lessons) * 100) : 0;
      overallDone += st.completed_lessons;
    });

    roadmapData.completed_lessons = Math.max(roadmapData.completed_lessons || 0, overallDone);
    roadmapData.overall_percent = roadmapData.total_lessons
      ? Math.round((roadmapData.completed_lessons / roadmapData.total_lessons) * 100)
      : 0;

    if (overallText) {
      overallText.textContent = `${roadmapData.completed_lessons} / ${roadmapData.total_lessons} (${roadmapData.overall_percent}%)`;
    }
    if (overallFill) {
      overallFill.style.width = `${roadmapData.overall_percent}%`;
    }

    if (stagesNav) {
      stagesNav.innerHTML = (roadmapData.stages || []).map(st => {
        const isActive = st.id === currentStageId ? 'active' : '';
        return `
          <button type="button" class="acad-stage-tab ${isActive}" data-stage-id="${st.id}">
            <div class="acad-stage-tab-top">
              <span class="acad-stage-num">ЭТАП ${st.order_index}</span>
              <span class="acad-stage-count">${st.completed_lessons} / ${st.total_lessons}</span>
            </div>
            <div class="acad-stage-tab-title">${escapeHtml(st.title.replace(/^Этап \d+:\s*/i, ''))}</div>
            <div class="acad-stage-tab-sub">${escapeHtml(st.subtitle)}</div>
          </button>
        `;
      }).join('');

      stagesNav.querySelectorAll('.acad-stage-tab').forEach(btn => {
        btn.addEventListener('click', () => {
          const sid = parseInt(btn.dataset.stageId, 10);
          switchStage(sid);
        });
      });
    }

    renderLessonsSidebar();
  }

  function switchStage(stageId) {
    currentStageId = stageId;
    renderRoadmapUI();
    const st = roadmapData?.stages?.find(s => s.id === stageId);
    if (st && st.lessons?.length) {
      const savedLastId = Number(localStorage.getItem(ACADEMY_LAST_LESSON_KEY));
      const savedInStage = savedLastId ? st.lessons.find(l => l.id === savedLastId) : null;
      if (savedInStage) {
        openLesson(savedInStage.id);
      } else {
        const firstIncomplete = st.lessons.find(l => !isLessonCompleted(l)) || st.lessons[0];
        openLesson(firstIncomplete.id);
      }
    }
  }

  function renderLessonsSidebar() {
    if (!roadmapData || !lessonsList) return;
    const st = roadmapData.stages?.find(s => s.id === currentStageId);
    if (!st) return;

    if (currentStageLabel) {
      currentStageLabel.textContent = st.title.toUpperCase();
    }
    if (stageLessonsCount) {
      stageLessonsCount.textContent = `${st.completed_lessons}/${st.total_lessons} пройдено`;
    }

    const q = (lessonFilter?.value || '').trim().toLowerCase();
    const filtered = (st.lessons || []).filter(l => {
      if (!q) return true;
      return l.title.toLowerCase().includes(q) || (l.summary || '').toLowerCase().includes(q);
    });

    lessonsList.innerHTML = filtered.map(les => {
      const isCur = currentLesson && currentLesson.id === les.id ? 'active' : '';
      const done = isLessonCompleted(les);
      const isDone = done ? 'completed' : '';
      const icon = done
        ? '<span class="acad-lesson-status-icon done">✔</span>'
        : `<span class="acad-lesson-status-icon pending">${les.order_index}</span>`;

      return `
        <button type="button" class="acad-lesson-item ${isCur} ${isDone}" data-lesson-id="${les.id}">
          ${icon}
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(les.title)}</span>
        </button>
      `;
    }).join('');

    lessonsList.querySelectorAll('.acad-lesson-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const lid = parseInt(btn.dataset.lessonId, 10);
        localStorage.setItem(ACADEMY_LAST_LESSON_KEY, lid);
        openLesson(lid);
      });
    });
  }

  // 2. Открытие конкретного урока (генерация уникального микроурока через Gemini Flash в реальном времени)
  async function openLesson(lessonId, forceRefresh = false) {
    try {
      localStorage.setItem(ACADEMY_LAST_LESSON_KEY, lessonId);
      if (lessonTitle) lessonTitle.textContent = 'ИИ формирует урок под тему...';
      if (lessonSummary) lessonSummary.textContent = 'ИИ-тренер подготавливает уникальные микрошаги и задачу...';
      if (trainerFeed) {
        trainerFeed.innerHTML = `
          <div class="acad-msg-bubble acad-msg-trainer">
            <div class="acad-msg-author">🤖 ИИ-тренер</div>
            <div>Секунду! Подготавливаю эксклюзивный интерактивный материал строго по этой теме...</div>
          </div>
        `;
      }

      let stageMeta = null;
      let lessonMeta = null;
      if (roadmapData && roadmapData.stages) {
        for (const st of roadmapData.stages) {
          const found = (st.lessons || []).find(l => l.id === lessonId);
          if (found) {
            stageMeta = st;
            lessonMeta = found;
            break;
          }
        }
      }

      const payload = {
        lesson_id: lessonId,
        stage_id: stageMeta ? stageMeta.id : 1,
        stage_title: stageMeta ? stageMeta.title : '',
        lesson_title: lessonMeta ? lessonMeta.title : '',
        lesson_summary: lessonMeta ? lessonMeta.summary : '',
        force_refresh: Boolean(forceRefresh),
      };

      const res = await fetch('/api/academy/start-lesson', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error('Не удалось запустить урок');
      currentLesson = await res.json();
      if (isLessonCompleted(currentLesson)) {
        currentLesson.completed = true;
      }
      currentStageId = currentLesson.stage_id;
      userQuizAnswers = {};

      renderRoadmapUI();
      renderCurrentLessonWorkspace();
    } catch (err) {
      console.error('Ошибка открытия урока:', err);
      try {
        const fallbackRes = await fetch(`/api/academy/lesson/${lessonId}`);
        if (fallbackRes.ok) {
          currentLesson = await fallbackRes.json();
          if (isLessonCompleted(currentLesson)) {
            currentLesson.completed = true;
          }
          currentStageId = currentLesson.stage_id;
          userQuizAnswers = {};
          renderRoadmapUI();
          renderCurrentLessonWorkspace();
        }
      } catch (e) {
        console.error('Критическая ошибка загрузки урока:', e);
      }
    }
  }

  function renderCurrentLessonWorkspace() {
    if (!currentLesson) return;

    // Шапка темы
    if (lessonStageBadge) {
      lessonStageBadge.textContent = currentLesson.stage_title || `Этап ${currentLesson.stage_id}`;
    }
    if (lessonStatusBadge) {
      if (currentLesson.completed) {
        lessonStatusBadge.textContent = '✔ Тема пройдена';
        lessonStatusBadge.className = 'acad-status-badge done';
      } else {
        lessonStatusBadge.textContent = 'В процессе';
        lessonStatusBadge.className = 'acad-status-badge';
      }
    }
    if (lessonTitle) lessonTitle.textContent = currentLesson.title;
    if (lessonSummary) lessonSummary.textContent = currentLesson.summary;

    if (editorLangTag) {
      editorLangTag.textContent = currentLesson.language === 'sql' ? 'SQL (SQLite)' : 'PYTHON 3.14';
    }

    // Блок файла проекта репозитория (для Этапа 3)
    if (repoFileBox && repoFileName && repoFileCode) {
      if (currentLesson.file_path && currentLesson.repo_source_preview) {
        repoFileName.textContent = currentLesson.file_path;
        repoFileCode.textContent = currentLesson.repo_source_preview;
        repoFileBox.classList.remove('hidden');
      } else {
        repoFileBox.classList.add('hidden');
      }
    }

    // Редактор кода стартовый шаблон
    if (codeEditor) {
      codeEditor.value = currentLesson.user_code || currentLesson.step2_starter_code || currentLesson.starter_code || '';
    }
    if (consoleOutput) {
      consoleOutput.textContent = 'Нажмите «Запустить» или «Отправить код тренеру».';
    }

    // Определяем текущий шаг урока
    updateStepTrackerUI();
    renderTrainerDialogueFeed();
    renderChatForLesson(currentLesson);
  }

  function updateStepTrackerUI() {
    if (!currentLesson) return;
    const isStep1Done = Boolean(currentLesson.step1_passed);
    const isStep2Done = Boolean(currentLesson.step2_passed);
    const isCompleted = Boolean(currentLesson.completed);

    // Сброс классов
    stepPill1.className = 'acad-step-pill';
    stepPill2.className = 'acad-step-pill';
    stepPill3.className = 'acad-step-pill';

    if (isStep1Done) stepPill1.classList.add('passed');
    if (isStep2Done) stepPill2.classList.add('passed');
    if (isCompleted) stepPill3.classList.add('passed');

    // Прячем все доки
    step1Dock.classList.add('hidden');
    step2Dock.classList.add('hidden');
    step3Dock.classList.add('hidden');

    if (!isStep1Done) {
      stepPill1.classList.add('active');
      step1Dock.classList.remove('hidden');
    } else if (!isStep2Done) {
      stepPill2.classList.add('active');
      step2Dock.classList.remove('hidden');
    } else {
      stepPill3.classList.add('active');
      step3Dock.classList.remove('hidden');
      renderQuizUI();
    }
  }

  // 3. Формирование живого диалога в потоке
  function renderTrainerDialogueFeed() {
    if (!currentLesson || !trainerFeed) return;
    let html = '';

    // Реплика 1: Тренер объясняет механику шага 1
    const concept1 = currentLesson.step1_concept || currentLesson.ai_theory;
    html += `
      <div class="acad-msg-bubble acad-msg-trainer">
        <div class="acad-msg-author">🤖 ИИ-тренер • Шаг 1: Чтение кода</div>
        <div>${formatText(concept1)}</div>
        <div class="acad-trap-card">
          <div class="acad-trap-header">🔍 «Поймай ловушку» (Внимательно прочитай 3 строчки кода)</div>
          <pre class="acad-trap-code">${escapeHtml(currentLesson.step1_trap_code || '')}</pre>
          <div class="acad-trap-q">Вопрос тренера: ${escapeHtml(currentLesson.step1_trap_question || 'Что выведет этот код на экран и почему?')}</div>
        </div>
      </div>
    `;

    // Если ученик уже отвечал на шаг 1
    if (currentLesson.step1_answer) {
      html += `
        <div class="acad-msg-bubble acad-msg-user">
          <div class="acad-msg-author">Вы • Ответ на ловушку</div>
          <div>${escapeHtml(currentLesson.step1_answer)}</div>
        </div>
      `;
    }

    // Если шаг 1 пройден — вердикт + правило тренера + переход к шагу 2
    if (currentLesson.step1_passed) {
      html += `
        <div class="acad-msg-bubble acad-msg-trainer">
          <div class="acad-msg-author">🤖 ИИ-тренер • Разбор под микроскопом</div>
          <div>Отлично подмечено! Ловушка успешно пройдена.</div>
          <div class="acad-trainer-rule">
            <span class="acad-rule-icon">📌</span>
            <div><strong>Главное правило тренера:</strong> ${escapeHtml(currentLesson.step1_rule || 'Внимательно следите за кавычками и типами данных.')}</div>
          </div>
        </div>
      `;

      // Шаг 2: Написание кода
      const concept2 = currentLesson.step2_concept || 'Теперь закрепим эту механику на практике написанием собственного кода.';
      const task2 = currentLesson.step2_task_prompt || currentLesson.task_prompt;
      html += `
        <div class="acad-msg-bubble acad-msg-trainer">
          <div class="acad-msg-author">🤖 ИИ-тренер • Шаг 2: Практика в редакторе</div>
          <div>${formatText(concept2)}</div>
          <div style="margin-top:10px;padding:12px;background:rgba(0,229,255,0.06);border-radius:8px;border-left:3px solid var(--cyan-neon);">
            <strong>Практическая задача:</strong> ${formatText(task2)}
          </div>
        </div>
      `;

      if (currentLesson.step2_code) {
        html += `
          <div class="acad-msg-bubble acad-msg-user">
            <div class="acad-msg-author">Вы • Отправленный код</div>
            <pre class="acad-trap-code">${escapeHtml(currentLesson.step2_code)}</pre>
          </div>
        `;
      }

      if (currentLesson.step2_passed) {
        html += `
          <div class="acad-msg-bubble acad-msg-trainer">
            <div class="acad-msg-author">🤖 ИИ-тренер • Вердикт по коду</div>
            <div>${formatText(currentLesson.mentor_feedback || 'Код написан чисто и выполнился без ошибок!')}</div>
            <div class="acad-trainer-rule">
              <span class="acad-rule-icon">📌</span>
              <div><strong>Главное правило тренера:</strong> ${escapeHtml(currentLesson.step2_rule || 'Решение работает надёжно и эффективно.')}</div>
            </div>
          </div>
        `;
      } else if (currentLesson.step2_code && currentLesson.mentor_feedback) {
        html += `
          <div class="acad-msg-bubble acad-msg-trainer" style="border-color: rgba(255, 82, 82, 0.45); background: rgba(255, 82, 82, 0.05);">
            <div class="acad-msg-author" style="color: #ff5252;">🤖 ИИ-тренер • Разбор решения под микроскопом</div>
            <div>${formatText(currentLesson.mentor_feedback)}</div>
          </div>
        `;
      }
    } else if (currentLesson.step1_answer && currentLesson.step1_feedback) {
      html += `
        <div class="acad-msg-bubble acad-msg-trainer" style="border-color: rgba(255, 171, 0, 0.45); background: rgba(255, 171, 0, 0.05);">
          <div class="acad-msg-author" style="color: #ffab00;">🤖 ИИ-тренер • Разбор ответа под микроскопом</div>
          <div>${formatText(currentLesson.step1_feedback)}</div>
        </div>
      `;
    }

    if (currentLesson.completed) {
      html += `
        <div class="acad-msg-bubble acad-msg-trainer" style="border-color:rgba(0,230,118,0.4);background:rgba(0,230,118,0.07);">
          <div class="acad-msg-author" style="color:var(--green-neon);">🎉 Тема успешно освоена!</div>
          <div>Поздравляю! Ты прошел микрошаг чтения, решил практическую задачу и справился с тестом по теме. Можешь двигаться дальше!</div>
        </div>
      `;
    }

    trainerFeed.innerHTML = html;
    trainerFeed.scrollTop = trainerFeed.scrollHeight;
  }

  // Кнопка регенерации примера от ИИ
  if (regenAiBtn) {
    regenAiBtn.addEventListener('click', async () => {
      if (!currentLesson) return;
      regenAiBtn.disabled = true;
      regenAiBtn.innerHTML = '<span class="acad-regen-icon">⏳</span> Генерирую...';
      try {
        await openLesson(currentLesson.id, true);
      } finally {
        regenAiBtn.disabled = false;
        regenAiBtn.innerHTML = '<span class="acad-regen-icon">🔄</span> Новый пример от ИИ';
      }
    });
  }

  // 4. Отправка ответа на Шаг 1
  if (submitStep1Btn && step1Input) {
    submitStep1Btn.addEventListener('click', async () => {
      const answer = (step1Input.value || '').trim();
      if (!answer) {
        alert('Пожалуйста, напишите ваш ответ на вопрос тренера.');
        return;
      }
      submitStep1Btn.disabled = true;
      submitStep1Btn.innerHTML = '<span>Проверка ИИ...</span>';

      try {
        const res = await fetch('/api/academy/step1/evaluate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lesson_id: currentLesson.id,
            answer: answer,
          }),
        });
        if (!res.ok) throw new Error('Ошибка сервера при проверке');
        const data = await res.json();

        currentLesson.step1_answer = answer;
        currentLesson.step1_passed = data.passed;
        currentLesson.step1_feedback = data.feedback;
        if (data.roadmap) roadmapData = data.roadmap;

        step1Input.value = '';
        renderRoadmapUI();
        updateStepTrackerUI();
        renderTrainerDialogueFeed();
      } catch (err) {
        alert('Не удалось отправить ответ: ' + err.message);
      } finally {
        submitStep1Btn.disabled = false;
        submitStep1Btn.innerHTML = '<span>Отправить ответ ➔</span>';
      }
    });
  }

  // 5. Запуск кода Шага 2 (песочница)
  if (runCodeBtn && codeEditor) {
    runCodeBtn.addEventListener('click', async () => {
      const code = codeEditor.value;
      runCodeBtn.disabled = true;
      runCodeBtn.textContent = 'Запуск...';
      try {
        const res = await fetch('/api/academy/step2/evaluate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lesson_id: currentLesson.id,
            code: code,
          }),
        });
        const data = await res.json();
        if (consoleOutput) {
          consoleOutput.textContent = data.stderr
            ? `Ошибка:\n${data.stderr}`
            : (data.stdout || '(программа ничего не вывела)');
        }
      } catch (err) {
        if (consoleOutput) consoleOutput.textContent = 'Ошибка выполнения: ' + err.message;
      } finally {
        runCodeBtn.disabled = false;
        runCodeBtn.textContent = '▶ Запустить (проверить вывод)';
      }
    });
  }

  // 6. Отправка кода на проверку тренеру (Шаг 2)
  if (submitStep2Btn && codeEditor) {
    submitStep2Btn.addEventListener('click', async () => {
      const code = codeEditor.value;
      submitStep2Btn.disabled = true;
      submitStep2Btn.innerHTML = '<span>ИИ проверяет код...</span>';

      try {
        const res = await fetch('/api/academy/step2/evaluate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lesson_id: currentLesson.id,
            code: code,
          }),
        });
        if (!res.ok) throw new Error('Ошибка сервера при проверке кода');
        const data = await res.json();

        currentLesson.step2_code = code;
        currentLesson.step2_passed = data.passed;
        currentLesson.mentor_feedback = data.feedback;
        if (data.roadmap) roadmapData = data.roadmap;

        if (consoleOutput) {
          consoleOutput.textContent = data.stderr
            ? `Ошибка:\n${data.stderr}`
            : (data.stdout || '(код выполнился без вывода)');
        }

        renderRoadmapUI();
        updateStepTrackerUI();
        renderTrainerDialogueFeed();
      } catch (err) {
        alert('Ошибка при отправке: ' + err.message);
      } finally {
        submitStep2Btn.disabled = false;
        submitStep2Btn.innerHTML = '🚀 Отправить код тренеру';
      }
    });
  }

  // 7. Отрисовка интерактивного теста (Шаг 3: 5 вопросов)
  function renderQuizUI() {
    if (!currentLesson || !quizQuestionsContainer) return;
    const questions = currentLesson.quiz_data || [];
    if (!questions.length) {
      quizQuestionsContainer.innerHTML = '<div style="color:var(--text-muted);">Тест для этого урока формируется...</div>';
      return;
    }

    quizQuestionsContainer.innerHTML = questions.map((q, qIdx) => {
      const userChoice = userQuizAnswers[qIdx];
      const optsHtml = (q.options || []).map((opt, optIdx) => {
        const isSelected = userChoice === optIdx ? 'selected' : '';
        const letters = ['A', 'B', 'C', 'D'];
        return `
          <div class="acad-quiz-opt ${isSelected}" data-q="${qIdx}" data-opt="${optIdx}">
            <span class="acad-quiz-opt-letter">${letters[optIdx] || optIdx + 1}</span>
            <span>${escapeHtml(opt)}</span>
          </div>
        `;
      }).join('');

      return `
        <div class="acad-quiz-card" id="quizCard_${qIdx}">
          <div class="acad-quiz-q-title">${qIdx + 1}. ${escapeHtml(q.question)}</div>
          <div class="acad-quiz-options">${optsHtml}</div>
          <div id="quizExp_${qIdx}" class="acad-quiz-explanation hidden"></div>
        </div>
      `;
    }).join('');

    quizQuestionsContainer.querySelectorAll('.acad-quiz-opt').forEach(optEl => {
      optEl.addEventListener('click', () => {
        const qIdx = parseInt(optEl.dataset.q, 10);
        const optIdx = parseInt(optEl.dataset.opt, 10);
        userQuizAnswers[qIdx] = optIdx;

        const parent = optEl.closest('.acad-quiz-options');
        parent.querySelectorAll('.acad-quiz-opt').forEach(o => o.classList.remove('selected'));
        optEl.classList.add('selected');
      });
    });

    if (nextLessonBtn) {
      if (currentLesson.completed && currentLesson.next_lesson_id) {
        nextLessonBtn.classList.remove('hidden');
        nextLessonBtn.onclick = () => openLesson(currentLesson.next_lesson_id);
      } else {
        nextLessonBtn.classList.add('hidden');
      }
    }
  }

  // 8. Проверка ответов теста (Шаг 3)
  if (submitQuizBtn) {
    submitQuizBtn.addEventListener('click', async () => {
      const questions = currentLesson?.quiz_data || [];
      if (!questions.length) return;

      if (Object.keys(userQuizAnswers).length < questions.length) {
        alert('Пожалуйста, ответьте на все 5 вопросов теста перед отправкой.');
        return;
      }

      submitQuizBtn.disabled = true;
      submitQuizBtn.textContent = 'Проверка теста...';

      try {
        const res = await fetch('/api/academy/quiz/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lesson_id: currentLesson.id,
            answers: userQuizAnswers,
          }),
        });
        if (res.status === 401) {
          alert('Сессия авторизации истекла (сервер обновился). Пожалуйста, обновите страницу и войдите в систему.');
          window.location.reload();
          return;
        }
        if (!res.ok) {
          const errData = await res.json().catch(() => null);
          throw new Error(errData?.detail || errData?.error || `Сервер временно недоступен (${res.status} ${res.statusText || 'проверьте соединение'})`);
        }
        const result = await res.json();

        // Подсвечиваем результаты вопросов
        (result.detailed || []).forEach(d => {
          const card = document.getElementById(`quizCard_${d.question_index}`);
          const expBox = document.getElementById(`quizExp_${d.question_index}`);
          if (card) {
            const opts = card.querySelectorAll('.acad-quiz-opt');
            opts.forEach(opt => {
              const optIdx = parseInt(opt.dataset.opt, 10);
              if (optIdx === d.correct_index) {
                opt.classList.add('correct');
              } else if (optIdx === d.user_choice && !d.is_correct) {
                opt.classList.add('wrong');
              }
            });
          }
          if (expBox && d.explanation) {
            expBox.textContent = 'Пояснение: ' + d.explanation;
            expBox.classList.remove('hidden');
          }
        });

        if (result.roadmap) roadmapData = result.roadmap;
        currentLesson.completed = result.passed;

        renderRoadmapUI();
        renderTrainerDialogueFeed();

        if (result.passed) {
          completedLessonsSet.add(String(currentLesson.id));
          if (currentLesson.stable_id) completedLessonsSet.add(currentLesson.stable_id);
          if (result.stable_id) completedLessonsSet.add(result.stable_id);
          try {
            localStorage.setItem(ACADEMY_STORAGE_KEY, JSON.stringify([...completedLessonsSet]));
          } catch {}

          // Синхронизируем с сервером
          fetch('/api/academy/progress/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ completed_ids: [...completedLessonsSet] }),
          }).catch(() => {});

          currentLesson.completed = true;
          renderRoadmapUI();
          updateStepTrackerUI();
          renderCurrentLessonWorkspace();

          alert(`🎉 Поздравляем! Результат: ${result.score} из ${result.total}. Прогресс сохранён!`);
          if (nextLessonBtn && result.next_lesson_id) {
            nextLessonBtn.classList.remove('hidden');
            nextLessonBtn.onclick = () => {
              localStorage.setItem(ACADEMY_LAST_LESSON_KEY, result.next_lesson_id);
              openLesson(result.next_lesson_id);
            };
          }
        } else {
          alert(`Результат: ${result.score} из ${result.total}. Для зачёта темы требуется минимум 4 верных ответа. Попробуйте еще раз!`);
        }
      } catch (err) {
        alert('Ошибка при проверке теста: ' + err.message);
      } finally {
        submitQuizBtn.disabled = false;
        submitQuizBtn.textContent = 'Завершить тест и проверить ответы';
      }
    });
  }

  // 9. Сброс кода к стартовому
  if (resetCodeBtn && codeEditor) {
    resetCodeBtn.addEventListener('click', () => {
      if (currentLesson) {
        codeEditor.value = currentLesson.step2_starter_code || currentLesson.starter_code || '';
      }
    });
  }

  // 10. Фильтрация списка уроков в сайдбаре
  if (lessonFilter) {
    lessonFilter.addEventListener('input', () => {
      renderLessonsSidebar();
    });
  }

  // 11. Скачивание персональной PDF-книги
  if (exportPdfBtn) {
    exportPdfBtn.addEventListener('click', async () => {
      const orig = exportPdfBtn.innerHTML;
      exportPdfBtn.disabled = true;
      exportPdfBtn.innerHTML = '<span>Сборка книги...</span>';
      try {
        const res = await fetch('/api/academy/export-pdf', { method: 'POST' });
        if (!res.ok) throw new Error('Ошибка сборки PDF');
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'BahonIQ_Architecture_Book_A_to_Z.pdf';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      } catch (err) {
        alert('Не удалось сгенерировать PDF-книгу: ' + err.message);
      } finally {
        exportPdfBtn.disabled = false;
        exportPdfBtn.innerHTML = orig;
      }
    });
  }

  // Кнопки ручного управления и восстановления прогресса
  if (restoreProgressBtn) {
    restoreProgressBtn.addEventListener('click', async () => {
      migrateAndLoadAcademyProgress();
      if (currentLesson) {
        completedLessonsSet.add(String(currentLesson.id));
        if (currentLesson.stable_id) completedLessonsSet.add(currentLesson.stable_id);
      }
      try {
        localStorage.setItem(ACADEMY_STORAGE_KEY, JSON.stringify([...completedLessonsSet]));
        const res = await fetch('/api/academy/progress/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ completed_ids: [...completedLessonsSet] }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.roadmap) roadmapData = data.roadmap;
          renderRoadmapUI();
          alert('⚡ Прогресс успешно восстановлен и синхронизирован с сервером!');
        }
      } catch (err) {
        alert('Ошибка синхронизации: ' + err.message);
      }
    });
  }

  if (markPassedBtn) {
    markPassedBtn.addEventListener('click', async () => {
      if (!currentLesson) return;
      completedLessonsSet.add(String(currentLesson.id));
      if (currentLesson.stable_id) completedLessonsSet.add(currentLesson.stable_id);
      try {
        localStorage.setItem(ACADEMY_STORAGE_KEY, JSON.stringify([...completedLessonsSet]));
        const res = await fetch('/api/academy/progress/mark', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lesson_id: currentLesson.id }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.roadmap) roadmapData = data.roadmap;
          currentLesson.completed = true;
          renderRoadmapUI();
          updateStepTrackerUI();
          renderCurrentLessonWorkspace();
          alert(`✔ Урок «${currentLesson.title}» отмечен завершённым! Прогресс сохранён.`);
        }
      } catch (err) {
        alert('Ошибка отметки урока: ' + err.message);
      }
    });
  }

  // ==========================================================================
  // СВОБОДНЫЙ ЧАТ «ИИ-ТРЕНЕР» (ВОПРОСЫ ПО PYTHON, SQL, АРХИТЕКТУРЕ И УРОКУ)
  // ==========================================================================
  function formatChatMarkdown(raw) {
    let s = escapeHtml(raw || '');
    s = s.replace(/```([a-zA-Z]*)\r?\n([\s\S]*?)```/g, '<pre class="acad-trap-code">$2</pre>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\n/g, '<br/>');
    return s;
  }

  function getLessonChatHistory(lessonId) {
    try {
      const raw = localStorage.getItem(CHAT_STORAGE_PREFIX + lessonId);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}
    return [];
  }

  function saveLessonChatHistory(lessonId, messages) {
    try {
      localStorage.setItem(CHAT_STORAGE_PREFIX + lessonId, JSON.stringify(messages));
    } catch (e) {}
  }

  function updateChatBadge(count) {
    const badgeEl = document.getElementById('acadChatCountBadge') || document.getElementById('chatCountBadge');
    if (!badgeEl) return;
    const chatClosed = typeof isChatOpen === 'function' ? !isChatOpen() : true;
    if (count > 0 && chatClosed) {
      badgeEl.textContent = count;
      badgeEl.classList.remove('hidden');
    } else {
      badgeEl.classList.add('hidden');
    }
  }

  function renderChatForLesson(lesson) {
    if (!chatMessages) return;
    if (chatLessonHint) {
      if (lesson) {
        const stageNum = lesson.stage_id || 1;
        chatLessonHint.textContent = `Контекст: Этап ${stageNum} • ${lesson.title || ''}`;
      } else {
        chatLessonHint.textContent = 'Контекст: Текущий урок';
      }
    }

    const history = lesson ? getLessonChatHistory(lesson.id) : [];
    if (!history || history.length === 0) {
      chatMessages.innerHTML = `
        <div class="acad-msg acad-msg-ai">
          Привет! Я твой персональный ИИ-тренер. Здесь ты можешь задать мне совершенно любой вопрос — по Python, SQL, архитектуре или текущему уроку. Разберём всё понятным языком и на простых примерах!
        </div>
      `;
    } else {
      chatMessages.innerHTML = history.map(m => {
        const cls = m.role === 'user' ? 'acad-msg-user' : 'acad-msg-ai';
        return `<div class="acad-msg ${cls}">${formatChatMarkdown(m.text)}</div>`;
      }).join('');
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
    updateChatBadge(history.length);
  }

  async function sendMentorQuestion(customQ) {
    const q = (customQ ?? chatInput?.value ?? '').trim();
    if (!q || !currentLesson) return;
    if (!customQ && chatInput) chatInput.value = '';

    const history = getLessonChatHistory(currentLesson.id);
    history.push({ role: 'user', text: q, time: Date.now() });
    saveLessonChatHistory(currentLesson.id, history);

    // Добавляем реплику пользователя
    const userDiv = document.createElement('div');
    userDiv.className = 'acad-msg acad-msg-user';
    userDiv.textContent = q;
    chatMessages.appendChild(userDiv);

    // Добавляем индикатор ответа ИИ
    const loadDiv = document.createElement('div');
    loadDiv.className = 'acad-msg acad-msg-ai';
    loadDiv.innerHTML = '⏳ <em>ИИ-тренер обдумывает ответ...</em>';
    chatMessages.appendChild(loadDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    if (chatSendBtn) {
      chatSendBtn.disabled = true;
      chatSendBtn.innerHTML = '<span>Думает...</span>';
    }

    try {
      const res = await fetch('/api/academy/mentor-ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lesson_id: currentLesson.id,
          question: q,
          code: codeEditor?.value || '',
          theory: currentLesson.step1_concept || currentLesson.ai_theory || '',
          trap_code: currentLesson.step1_trap_code || '',
          task_prompt: currentLesson.step2_task_prompt || currentLesson.task_prompt || '',
          output: consoleOutput?.textContent || '',
          history: history.slice(-6),
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Не удалось получить ответ ИИ-тренера');

      const answerText = data.answer || '';
      loadDiv.innerHTML = formatChatMarkdown(answerText);
      history.push({ role: 'ai', text: answerText, time: Date.now() });
      saveLessonChatHistory(currentLesson.id, history);
    } catch (err) {
      loadDiv.innerHTML = `<span style="color:#ff5252;">⚠️ Ошибка: ${escapeHtml(err.message)}</span>`;
    } finally {
      if (chatSendBtn) {
        chatSendBtn.disabled = false;
        chatSendBtn.innerHTML = '<span>Спросить</span>';
      }
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  if (clearChatBtn) {
    clearChatBtn.addEventListener('click', () => {
      if (!currentLesson) return;
      try {
        localStorage.removeItem(CHAT_STORAGE_PREFIX + currentLesson.id);
      } catch (e) {}
      renderChatForLesson(currentLesson);
    });
  }

  if (chatSendBtn) {
    chatSendBtn.addEventListener('click', () => sendMentorQuestion());
  }

  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMentorQuestion();
      }
    });
  }

  document.querySelectorAll('.acad-quick-q').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.q;
      if (q) sendMentorQuestion(q);
    });
  });

  // 12. Первичная инициализация с приоритетом ручного выбора
  async function initAcademyPlatform() {
    try {
      migrateAndLoadAcademyProgress();
      const res = await fetch('/api/academy/roadmap');
      if (!res.ok) throw new Error('Ошибка загрузки карты курса');
      roadmapData = await res.json();
      renderRoadmapUI();

      // Ручной выбор урока пользователем имеет наивысший приоритет
      const savedLessonId = Number(localStorage.getItem(ACADEMY_LAST_LESSON_KEY));
      let targetLessonId = null;

      if (savedLessonId && roadmapData.stages) {
        for (const st of roadmapData.stages) {
          const found = (st.lessons || []).find(l => l.id === savedLessonId);
          if (found) {
            targetLessonId = found.id;
            currentStageId = st.id;
            break;
          }
        }
      }

      // Только если пользователь никогда не выбирал урок, переходим к первому незавершенному
      if (!targetLessonId) {
        const firstStage = roadmapData.stages?.[0];
        if (firstStage && firstStage.lessons?.length) {
          const firstIncomplete = firstStage.lessons.find(l => !isLessonCompleted(l)) || firstStage.lessons[0];
          targetLessonId = firstIncomplete.id;
        }
      }

      if (targetLessonId) {
        await openLesson(targetLessonId);
      }
    } catch (err) {
      console.error('Academy init error:', err);
    }
  }

  window.loadBahonIQAcademy = initAcademyPlatform;
  initAcademyPlatform();
})();
