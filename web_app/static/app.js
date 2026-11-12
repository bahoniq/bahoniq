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

// Управление темами: Ночь / День
function applyTheme(theme) {
  const body = document.body;
  const toggleBtn = $('#themeToggle');
  const icon = toggleBtn?.querySelector('.theme-icon');
  const label = toggleBtn?.querySelector('.theme-label');
  const sunSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>';
  const moonSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
  
  if (theme === 'day') {
    body.classList.remove('theme-night');
    body.classList.add('theme-day');
    if (icon) icon.innerHTML = sunSvg;
    if (label) label.textContent = 'День';
  } else {
    body.classList.remove('theme-day');
    body.classList.add('theme-night');
    if (icon) icon.innerHTML = moonSvg;
    if (label) label.textContent = 'Ночь';
  }
  localStorage.setItem('bahoniq_theme', theme);
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
  dashView.classList.add('hidden');
  $$('.module-page').forEach(p => p.classList.remove('active'));
  target.classList.add('active');
  modHost.classList.remove('hidden');
  modHost.classList.add('panorama-in');
  setTimeout(() => modHost.classList.remove('panorama-in'), 380);
  document.querySelector('.content-body')?.scrollTo({ top: 0, behavior: 'smooth' });
}

function returnToDashboard() {
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
  const name = tile.querySelector('.tool-name')?.textContent || '';
  openModule(modId, name);
});

// Кнопка "Открыть все системы"
$('#openAllSystems')?.addEventListener('click', () => {
  const urls = [
    "https://platonus.kaznmu.edu.kz/",
    "https://support.platonus.kz/",
    "https://web.telegram.org/",
    "https://web.whatsapp.com/",
    "https://mail.google.com/mail/u/0/#inbox",
    "https://salemoffice.kaznmu.edu.kz/sign-in"
  ];
  urls.forEach(u => window.open(u, '_blank'));
});

// Проверка прямого хэша в URL (например #tickets)
if (location.hash) {
  const hash = location.hash.slice(1);
  const matchedTile = document.querySelector(`[data-open="${hash}"]`);
  if (matchedTile) {
    const name = matchedTile.querySelector('.tool-name')?.textContent || '';
    openModule(hash, name);
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

// ----------------- EXCEL AI -----------------
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
  fd.append('problem', $('#ticketProblem').value);
  setBusy(b, true, 'BahonIQ AI структурирует заявку…');
  try {
    const data = await api('/api/tickets/generate', { method: 'POST', body: fd });
    $('#ticketTitle').value = data.title || '';
    $('#ticketDescription').value = data.description || '';
    showResult($('#ticketResult'), 'Заявка сформирована BahonIQ AI без лишних слов.');
  } catch (err) {
    showResult($('#ticketResult'), esc(err.message), true);
  } finally {
    setBusy(b, false);
  }
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
  fd.append('contact_id', $('#contactId').value || '0');
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
  setBusy(button, true, 'Думаю…');
  try {
    const fd = new FormData();
    fd.append('question', question);
    fd.append('mode', $('#academyMentorMode')?.value || 'hint');
    fd.append('code', $('#' + activeKind + 'Code')?.value || '');
    fd.append('chapter', item?.title || 'Code Academy');
    const data = await api('/api/academy/ask', { method: 'POST', body: fd });
    answer.textContent = data.answer || 'Ответ не получен.';
    answer.classList.remove('hidden');
    const prov = $('#academyMentorProvider');
    if (prov && data.provider_label) prov.textContent = data.provider_label;
  } catch (e) {
    answer.textContent = e.message;
    answer.classList.remove('hidden');
  } finally { setBusy(button, false); }
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
