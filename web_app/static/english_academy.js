/* ==========================================================================
   BAHONIQ — ENGLISH ACADEMY STUDIO (A0 -> B2)
   Лаконичный 3-колоночный интерфейс в едином стиле с Code Academy:
   [Слева: Уроки уровня] — [Центр: Теория -> Упражнения -> Итог] — [Справа: ИИ-наставник]
   ========================================================================== */
(() => {
  const LOCAL_BACKUP_KEY = 'bahoniq_english_academy_backup_v2';
  const OFFLINE_MODE_KEY = 'bahoniq_ea_force_offline';
  const PROFILE_ID_KEY = 'bahoniq_profile_id';

  function getProfileId() {
    try {
      let pid = localStorage.getItem(PROFILE_ID_KEY);
      if (pid && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(pid)) {
        return pid.toLowerCase();
      }
      if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        pid = window.crypto.randomUUID();
      } else {
        pid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
          const r = (Math.random() * 16) | 0;
          const v = c === 'x' ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        });
      }
      localStorage.setItem(PROFILE_ID_KEY, pid);
      return pid;
    } catch {
      return '';
    }
  }

  const SKILL_LABELS = {
    reading: 'Чтение',
    writing: 'Письмо',
    listening: 'Аудирование',
    vocabulary: 'Словарь',
    grammar: 'Грамматика',
    speaking: 'Речь',
  };

  const STAGE_NAMES = {
    A0: 'Абсолютный ноль',
    A1: 'Базовый',
    A2: 'Общение',
    B1: 'Средний',
    B2: 'Уверенный',
  };

  const store = {
    view: 'studio', // 'studio' | 'hub' | 'settings'
    hubTab: 'vocab', // 'vocab' | 'mistakes' | 'dialogues' | 'practice' | 'progress'
    sideTab: 'tutor', // 'tutor' | 'dict'
    sideDictQuery: '',
    sideDictLetter: '',
    forceOffline: (() => {
      try {
        return localStorage.getItem(OFFLINE_MODE_KEY) === '1';
      } catch {
        return false;
      }
    })(),
    selectedLevel: 'A0',
    lessonFilter: '',
    curriculum: { levels: [], dialogues: [] },
    state: null,
    progress: null,
    vocabulary: [],
    currentLesson: null,
    lessonStep: 'theory', // 'theory' | 'practice' | 'summary'
    exIndex: 0,
    exAttempts: {},
    exResults: {},
    lessonStartedAt: 0,
    vocabFilter: { mode: 'all', level: '', q: '' },
    srsSession: null,
    activeDialogueId: null,
    dlgTurnIdx: 0,
    mediaRecorder: null,
    recordedUrl: null,
  };

  const el = (id) => document.getElementById(id);

  function esc(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderTutorMarkdown(text) {
    const safe = esc(text || '');
    return safe
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^\*])\*([^\*\n]+?)\*/g, '$1<em>$2</em>')
      .replace(/`([^`\n]+?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  function updateTutorModeBadge() {
    const badge = el('eaTutorModeBadge');
    if (!badge) return;
    if (store.forceOffline) {
      badge.textContent = '⚪ Автономный наставник';
      badge.classList.add('offline');
    } else {
      badge.textContent = '🟢 ИИ подключён';
      badge.classList.remove('offline');
    }
  }

  async function apiCall(path, options = {}) {
    const pid = getProfileId();
    const res = await fetch(`/api/english-academy${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(pid ? { 'X-Profile-Id': pid } : {}),
        ...(options.headers || {}),
      },
      ...options,
    });
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const d = await res.json();
        if (d.detail) msg = d.detail;
      } catch {}
      throw new Error(msg);
    }
    return await res.json();
  }

  function saveSnapshot() {
    try {
      if (store.state && store.progress) {
        localStorage.setItem(
          LOCAL_BACKUP_KEY,
          JSON.stringify({
            curriculum: store.curriculum,
            state: store.state,
            progress: store.progress,
            vocabulary: store.vocabulary,
          })
        );
      }
    } catch {}
  }

  function showNotice(text) {
    const box = el('eaNoticeBanner');
    if (!box) return;
    if (!text) {
      box.classList.add('hidden');
      box.textContent = '';
      return;
    }
    box.textContent = text;
    box.classList.remove('hidden');
  }

  function speakEnglish(text, customRate = null) {
    if (!text || !('speechSynthesis' in window)) {
      showNotice('Озвучка недоступна в этом окне, ориентируйтесь на транскрипцию.');
      return;
    }
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text));
      u.lang = 'en-US';
      u.rate = customRate !== null ? customRate : Number(store.state?.settings?.speech_rate || 0.85);
      const voices = window.speechSynthesis.getVoices();
      const en = voices.find((v) => /^en(-|_)/i.test(v.lang));
      if (en) u.voice = en;
      window.speechSynthesis.speak(u);
    } catch {}
  }

  let _eaActiveAudio = null;
  function playAudioOrSpeech(text, opts = {}) {
    const { audioUrl = '', slowAudioUrl = '', slow = false } = opts || {};
    const targetUrl = slow && slowAudioUrl ? slowAudioUrl : (!slow && audioUrl ? audioUrl : (slow && audioUrl ? audioUrl : ''));
    if (targetUrl) {
      try {
        if (_eaActiveAudio) {
          _eaActiveAudio.pause();
          _eaActiveAudio = null;
        }
        const a = new Audio(targetUrl);
        if (slow && !slowAudioUrl) a.playbackRate = 0.78;
        _eaActiveAudio = a;
        a.play().catch(() => speakEnglish(text, slow ? 0.62 : null));
        return;
      } catch {}
    }
    speakEnglish(text, slow ? 0.62 : null);
  }

  function findLesson(lessonId) {
    for (const lvl of store.curriculum.levels || []) {
      for (const sec of lvl.sections || []) {
        for (const les of sec.lessons || []) {
          if (les.id === lessonId) return { ...les, level: lvl.code, section_title: sec.title };
        }
      }
    }
    return null;
  }

  /* -------------------- ЗАГРУЗКА И КАРКАС -------------------- */
  async function loadEnglishAcademy() {
    const host = el('englishAcademy');
    if (!host) return;
    buildShellIfNeeded(host);
    if (!store.progress && el('eaCenterBody')) {
      el('eaCenterBody').innerHTML = `<div class="ea-skeleton-box">Загрузка курса и прогресса...</div>`;
    }

    try {
      const data = await apiCall('/bootstrap');
      store.curriculum = data.curriculum;
      store.state = data.state;
      store.progress = data.progress;
      store.vocabulary = data.vocabulary || [];
      store.selectedLevel = data.progress.current_level || 'A0';
      if (!store.currentLesson) {
        store.currentLesson = findLesson(data.progress.next_step.lesson_id) || findLesson('a0-l1');
        store.lessonStep = store.currentLesson?.kind === 'lesson' ? 'theory' : 'practice';
        store.lessonStartedAt = Date.now();
      }
      saveSnapshot();
      showNotice('');
    } catch {
      try {
        const cached = JSON.parse(localStorage.getItem(LOCAL_BACKUP_KEY) || 'null');
        if (cached && cached.curriculum) {
          store.curriculum = cached.curriculum;
          store.state = cached.state;
          store.progress = cached.progress;
          store.vocabulary = cached.vocabulary || [];
          if (!store.currentLesson) store.currentLesson = findLesson('a0-l1');
          showNotice('Автономный режим: используется локальная копия курса и прогресса.');
        }
      } catch {}
    }

    renderAll();
  }

  function buildShellIfNeeded(host) {
    if (host.querySelector('.acad-top-header')) return;
    host.innerHTML = `
      <!-- Шапка 1-в-1 как в Code Academy -->
      <div class="acad-top-header card">
        <div class="acad-top-title-group">
          <h1>English Academy</h1>
          <p>Пошаговый курс английского от полного нуля (A0) до уверенного уровня (B2): чтение, речь, словарь и ИИ-наставник.</p>
        </div>

        <div class="acad-top-right" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          <div class="ea-view-switch" role="tablist" aria-label="Режим English Academy">
            <button class="ea-view-btn active" data-ea-view="studio" type="button">Обучение</button>
            <button class="ea-view-btn" data-ea-view="hub" type="button">
              Словарь и Ошибки <span id="eaHubBadge" class="ea-badge-count ea-hidden">0</span>
            </button>
            <button id="eaPlacementBtn" class="ea-view-btn" type="button">Определить уровень</button>
            <button class="ea-view-btn" data-ea-view="settings" type="button">Настройки</button>
          </div>

          <div class="acad-progress-widget">
            <div class="acad-progress-labels">
              <span>Общий путь A0–B2</span>
              <strong id="eaOverallText">0 / 21 (0%)</strong>
            </div>
            <div class="acad-progress-bar-bg">
              <div id="eaOverallFill" class="acad-progress-bar-fill" style="width:0%"></div>
            </div>
          </div>
        </div>
      </div>

      <div id="eaNoticeBanner" class="ea-notice hidden" role="status"></div>

      <!-- Вид 1: Основная 3-колоночная студия (как Code Academy) -->
      <div id="eaStudioView">
        <div id="eaStagesNav" class="ea-stages-5"></div>

        <div class="acad-workspace-grid with-chat">
          <!-- Левая колонка: Уроки выбранного уровня -->
          <aside class="card acad-lessons-sidebar">
            <div class="acad-sidebar-head">
              <span id="eaStageLabel">УРОВЕНЬ A0</span>
              <span id="eaStageCount" class="acad-badge-pill">0/7</span>
            </div>
            <input id="eaLessonSearch" type="search" class="acad-lesson-search" placeholder="Поиск темы урока...">
            <div id="eaLessonsList" class="acad-lessons-list"></div>
          </aside>

          <!-- Центр: Текущий урок / Упражнения -->
          <div class="card acad-trainer-card">
            <div class="acad-trainer-header">
              <div class="acad-trainer-meta">
                <div class="acad-badges-row">
                  <span id="eaLessonLevelBadge" class="acad-stage-badge">A0</span>
                  <span id="eaLessonStatusBadge" class="acad-status-badge">Текущий шаг</span>
                  <button id="eaContinueBtn" class="acad-regen-btn" type="button">▶ Продолжить обучение</button>
                </div>
                <h2 id="eaLessonTitle" class="acad-lesson-title">Загрузка...</h2>
                <p id="eaLessonSummary" class="acad-lesson-summary"></p>
              </div>

              <div class="acad-step-tracker">
                <div id="eaStepPill1" class="acad-step-pill active" style="cursor:pointer;">
                  <span class="acad-step-num">1</span>
                  <span class="acad-step-text">Объяснение</span>
                </div>
                <div class="acad-step-line"></div>
                <div id="eaStepPill2" class="acad-step-pill" style="cursor:pointer;">
                  <span class="acad-step-num">2</span>
                  <span class="acad-step-text">Упражнения</span>
                </div>
                <div class="acad-step-line"></div>
                <div id="eaStepPill3" class="acad-step-pill">
                  <span class="acad-step-num">3</span>
                  <span class="acad-step-text">Итог</span>
                </div>
              </div>
            </div>

            <div id="eaCenterBody" class="acad-trainer-feed" style="padding:16px 18px;"></div>
          </div>

          <!-- Правая колонка: ИИ-наставник и закреплённый Словарь A–Z -->
          <aside class="card acad-mentor-chat">
            <div class="acad-chat-header">
              <div class="ea-side-tabs" role="tablist" aria-label="Панель помощника">
                <button type="button" class="ea-side-tab active" data-ea-side-tab="tutor" role="tab" aria-selected="true">Наставник</button>
                <button type="button" class="ea-side-tab" data-ea-side-tab="dict" role="tab" aria-selected="false">Словарь A–Z</button>
              </div>
              <div id="eaTutorHeaderMeta" class="acad-chat-title-group">
                <div class="acad-chat-title">
                  <div>
                    <h3>ИИ-наставник</h3>
                    <small id="eaTutorHint">Контекст урока подключён</small>
                  </div>
                </div>
                <span id="eaTutorModeBadge" class="ea-tutor-status-pill">${store.forceOffline ? '⚪ Автономный наставник' : '🟢 ИИ подключён'}</span>
              </div>
            </div>

            <div id="eaSideTutorPane" class="ea-side-pane">
              <div class="acad-chat-quick">
                <button type="button" class="acad-quick-q" data-ea-qmode="explain" data-ea-q="Объясни текущую тему ещё проще на жизненном примере.">Проще на примере</button>
                <button type="button" class="acad-quick-q" data-ea-qmode="hint" data-ea-q="Дай короткую подсказку к текущему заданию, не раскрывая ответ.">Подсказка</button>
                <button type="button" class="acad-quick-q" data-ea-qmode="check_writing" data-ea-q="">Проверь фразу</button>
                <button type="button" class="acad-quick-q" data-ea-qmode="dialogue" data-ea-q="Начни короткий тренировочный диалог по моему уровню.">Диалог</button>
              </div>

              <div id="eaChatMessages" class="acad-chat-messages">
                <div class="acad-msg acad-msg-ai">
                  Этот диалог относится к текущему уроку. Спросите правило или напишите фразу на английском для проверки.
                </div>
              </div>

              <div class="acad-chat-input-row">
                <textarea id="eaChatInput" class="acad-chat-textarea" rows="2" placeholder="Спросите правило или напишите фразу на английском..."></textarea>
                <div class="acad-chat-btn-subrow">
                  <small class="acad-chat-key-hint">Enter — отправить</small>
                  <button id="eaChatSendBtn" class="button primary acad-chat-send-btn" type="button">
                    <span>Спросить</span>
                  </button>
                </div>
              </div>
            </div>

            <div id="eaSideDictPane" class="ea-side-pane ea-hidden">
              <div class="ea-side-dict-controls">
                <input id="eaSideDictSearch" class="ea-input ea-side-dict-input" type="search" placeholder="Поиск слова или перевода..." />
                <div id="eaSideDictAZ" class="ea-side-az" aria-label="Алфавитный указатель"></div>
              </div>
              <div id="eaSideDictCount" class="ea-side-dict-count"></div>
              <div id="eaSideDictList" class="ea-side-dict-list"></div>
            </div>
          </aside>
        </div>
      </div>

      <!-- Вид 2: Словарь, Ошибки, Диалоги, Произношение и Прогресс -->
      <div id="eaHubView" class="card ea-hidden" style="padding:18px 20px;"></div>

      <!-- Вид 3: Настройки и переносимость -->
      <div id="eaSettingsView" class="card ea-hidden" style="padding:18px 20px;"></div>
    `;

    host.querySelectorAll('[data-ea-view]').forEach((btn) => {
      btn.addEventListener('click', () => {
        store.view = btn.dataset.eaView;
        host.querySelectorAll('[data-ea-view]').forEach((b) => b.classList.toggle('active', b === btn));
        el('eaStudioView')?.classList.toggle('ea-hidden', store.view !== 'studio');
        el('eaHubView')?.classList.toggle('ea-hidden', store.view !== 'hub');
        el('eaSettingsView')?.classList.toggle('ea-hidden', store.view !== 'settings');
        renderAll();
      });
    });

    el('eaPlacementBtn')?.addEventListener('click', () => openPlacementTest());

    el('eaLessonSearch')?.addEventListener('input', (e) => {
      store.lessonFilter = e.target.value.trim().toLowerCase();
      renderLessonsSidebar();
    });

    el('eaContinueBtn')?.addEventListener('click', () => {
      const nextId = store.progress?.next_step?.lesson_id || 'a0-l1';
      openLesson(nextId);
    });

    el('eaStepPill1')?.addEventListener('click', () => {
      if (store.currentLesson?.kind === 'lesson') {
        store.lessonStep = 'theory';
        renderCenterBody();
      }
    });
    el('eaStepPill2')?.addEventListener('click', () => {
      store.lessonStep = 'practice';
      renderCenterBody();
    });

    // Чат ИИ-наставника
    const sendTutor = async (mode = 'chat', presetText = null) => {
      const inp = el('eaChatInput');
      const feed = el('eaChatMessages');
      const text = presetText !== null ? presetText : (inp?.value || '').trim();
      if (!text && mode === 'chat') return;
      if (presetText === null && inp) inp.value = '';

      if (text) {
        const u = document.createElement('div');
        u.className = 'acad-msg acad-msg-user';
        u.textContent = text;
        feed?.appendChild(u);
      }

      const aiMsg = document.createElement('div');
      aiMsg.className = 'acad-msg acad-msg-ai';
      aiMsg.textContent = 'Думаю…';
      feed?.appendChild(aiMsg);
      if (feed) feed.scrollTop = feed.scrollHeight;

      try {
        const res = await apiCall('/tutor', {
          method: 'POST',
          body: JSON.stringify({
            mode,
            message: text,
            lesson_id: store.currentLesson?.id || 'a0-l1',
            force_offline: Boolean(store.forceOffline),
          }),
        });
        aiMsg.innerHTML = renderTutorMarkdown(res.answer);
        if (res.notice) showNotice(res.notice);
      } catch {
        aiMsg.textContent = 'Автономная подсказка: сверьтесь с правилом текущего урока и порядком слов.';
      }
      if (feed) feed.scrollTop = feed.scrollHeight;
    };

    host.querySelectorAll('[data-ea-qmode]').forEach((b) => {
      b.addEventListener('click', () => {
        const mode = b.dataset.eaQmode;
        const q = b.dataset.eaQ || el('eaChatInput')?.value?.trim() || 'Проверь, пожалуйста, этот пример.';
        sendTutor(mode, q);
      });
    });

    el('eaChatSendBtn')?.addEventListener('click', () => sendTutor('chat'));
    el('eaChatInput')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendTutor('chat');
      }
    });

    // Переключатель правой панели: ИИ-наставник / Закреплённый словарь A–Z
    host.querySelectorAll('[data-ea-side-tab]').forEach((btn) => {
      btn.addEventListener('click', () => {
        store.sideTab = btn.dataset.eaSideTab;
        host.querySelectorAll('[data-ea-side-tab]').forEach((b) => {
          const active = b === btn;
          b.classList.toggle('active', active);
          b.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        el('eaSideTutorPane')?.classList.toggle('ea-hidden', store.sideTab !== 'tutor');
        el('eaTutorHeaderMeta')?.classList.toggle('ea-hidden', store.sideTab !== 'tutor');
        el('eaSideDictPane')?.classList.toggle('ea-hidden', store.sideTab !== 'dict');
        if (store.sideTab === 'dict') renderSideDictionary();
      });
    });

    el('eaSideDictSearch')?.addEventListener('input', (e) => {
      store.sideDictQuery = e.target.value.trim().toLowerCase();
      renderSideDictionary();
    });
  }

  function openLesson(lessonId) {
    const les = findLesson(lessonId);
    if (!les) return;
    if (!store.progress?.unlock_map?.[lessonId]) {
      showNotice('Этот урок пока закрыт — завершите предыдущий шаг (≥ 75%, экзамен ≥ 80%).');
      return;
    }
    store.selectedLevel = les.level;
    store.currentLesson = les;
    store.lessonStep = les.kind === 'lesson' ? 'theory' : 'practice';
    store.exIndex = 0;
    store.exAttempts = {};
    store.exResults = {};
    store.lessonStartedAt = Date.now();
    showNotice('');
    renderAll();
  }

  function renderAll() {
    if (!store.progress) return;
    renderTopProgress();
    if (store.view === 'studio') {
      renderStagesStrip();
      renderLessonsSidebar();
      renderCenterBody();
      if (store.sideTab === 'dict') renderSideDictionary();
    } else if (store.view === 'hub') {
      renderHubView();
    } else {
      renderSettingsView();
    }
  }

  function renderTopProgress() {
    const p = store.progress;
    if (el('eaOverallText')) el('eaOverallText').textContent = `${p.completed_lessons} / ${p.total_lessons} (${p.overall_percent}%)`;
    if (el('eaOverallFill')) el('eaOverallFill').style.width = `${p.overall_percent}%`;

    const totalAttention = (p.unresolved_mistakes_count || 0) + (p.vocab_summary?.due_today || 0);
    const badge = el('eaHubBadge');
    if (badge) {
      badge.textContent = String(totalAttention);
      badge.classList.toggle('ea-hidden', totalAttention === 0);
    }
  }

  function renderSideDictionary() {
    const azBox = el('eaSideDictAZ');
    const listBox = el('eaSideDictList');
    const countBox = el('eaSideDictCount');
    if (!azBox || !listBox) return;

    const allItems = Array.isArray(store.vocabulary) ? store.vocabulary : [];
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    azBox.innerHTML =
      `<button type="button" class="ea-az-btn ${!store.sideDictLetter ? 'active' : ''}" data-ea-az="">Все</button>` +
      letters
        .map(
          (ch) =>
            `<button type="button" class="ea-az-btn ${store.sideDictLetter === ch ? 'active' : ''}" data-ea-az="${ch}">${ch}</button>`
        )
        .join('');

    azBox.querySelectorAll('[data-ea-az]').forEach((btn) => {
      btn.addEventListener('click', () => {
        store.sideDictLetter = btn.dataset.eaAz || '';
        renderSideDictionary();
      });
    });

    const q = store.sideDictQuery || '';
    const letter = store.sideDictLetter || '';
    const filtered = allItems.filter((item) => {
      const w = String(item.word || '').toLowerCase();
      if (letter && !w.startsWith(letter.toLowerCase())) return false;
      if (!q) return true;
      return (
        w.includes(q) ||
        String(item.ru || '').toLowerCase().includes(q) ||
        String(item.topic || '').toLowerCase().includes(q) ||
        String(item.ru_hint || '').toLowerCase().includes(q)
      );
    });

    if (countBox) {
      countBox.textContent = `Найдено слов: ${filtered.length} из ${allItems.length}`;
    }

    if (!filtered.length) {
      listBox.innerHTML = `<div class="acad-muted" style="font-size:12.5px;padding:12px 2px;">Ничего не найдено. Попробуйте другую букву или запрос.</div>`;
      return;
    }

    listBox.innerHTML = filtered
      .slice(0, 120)
      .map(
        (v) => `
      <div class="ea-side-dict-card">
        <div class="ea-side-dict-head">
          <span class="ea-side-dict-word">${esc(v.word)}</span>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="ea-stage-badge" style="font-size:10px;padding:1px 6px;">${esc(v.level || 'A0')}</span>
            <button type="button" class="ea-speak-btn" style="width:26px;height:26px;font-size:12px;" data-ea-side-speak="${esc(v.word)}" title="Озвучить">🔊</button>
          </div>
        </div>
        <div class="ea-side-dict-ipa">${esc(v.ipa || '')}${v.ru_hint ? ` · [${esc(v.ru_hint)}]` : ''}</div>
        <div class="ea-side-dict-ru">${esc(v.ru || '')}</div>
        ${v.example ? `<div class="ea-side-dict-ex">${esc(v.example)}</div>` : ''}
      </div>
    `
      )
      .join('');

    listBox.querySelectorAll('[data-ea-side-speak]').forEach((btn) => {
      btn.addEventListener('click', () => speakEnglish(btn.dataset.eaSideSpeak));
    });
  }

  function renderStagesStrip() {
    const nav = el('eaStagesNav');
    const p = store.progress;
    if (!nav || !p) return;

    nav.innerHTML = p.levels
      .map(
        (lvl) => `
      <button class="ea-stage-card ${lvl.code === store.selectedLevel ? 'active' : ''} ${lvl.unlocked ? '' : 'locked'}" data-lvl="${lvl.code}" type="button">
        <div class="ea-stage-head">
          <span>${esc(lvl.code)} · ${esc(STAGE_NAMES[lvl.code] || '')}</span>
          <span>${lvl.unlocked ? `${lvl.percent}%` : '🔒'}</span>
        </div>
        <div class="ea-stage-sub">${lvl.completed} из ${lvl.total} уроков</div>
        <div class="ea-bar-track"><div class="ea-bar-fill" style="width:${lvl.percent}%"></div></div>
      </button>
    `
      )
      .join('');

    nav.querySelectorAll('[data-lvl]').forEach((b) => {
      b.addEventListener('click', () => {
        store.selectedLevel = b.dataset.lvl;
        renderStagesStrip();
        renderLessonsSidebar();
      });
    });
  }

  function renderLessonsSidebar() {
    const listEl = el('eaLessonsList');
    const p = store.progress;
    if (!listEl || !p) return;
    const lvlObj = (store.curriculum.levels || []).find((l) => l.code === store.selectedLevel);
    if (!lvlObj) return;

    const lvlStat = p.levels.find((x) => x.code === store.selectedLevel);
    if (el('eaStageLabel')) el('eaStageLabel').textContent = `УРОВЕНЬ ${lvlObj.code}: ${STAGE_NAMES[lvlObj.code] || ''}`.toUpperCase();
    if (el('eaStageCount') && lvlStat) el('eaStageCount').textContent = `${lvlStat.completed}/${lvlStat.total}`;

    const q = store.lessonFilter;
    listEl.innerHTML = (lvlObj.sections || [])
      .map((sec) => {
        const filtered = sec.lessons.filter((les) => !q || les.title.toLowerCase().includes(q));
        if (!filtered.length) return '';
        return `
          <div class="ea-sec-label">${esc(sec.title)}</div>
          ${filtered
            .map((les) => {
              const unlocked = Boolean(p.unlock_map[les.id]);
              const rec = store.state?.lessons?.[les.id];
              const active = store.currentLesson?.id === les.id;
              const badge = rec?.passed ? `✅ ${rec.score}%` : unlocked ? '▶' : '🔒';
              const prefix = les.kind === 'exam' ? '🏆 ' : les.kind === 'checkpoint' ? '🧪 ' : '';
              return `
                <button class="ea-lesson-btn ${active ? 'active' : ''}" data-les="${les.id}" ${unlocked ? '' : 'disabled'} type="button">
                  <span>${prefix}${esc(les.title)}</span>
                  <strong style="white-space:nowrap;">${badge}</strong>
                </button>
              `;
            })
            .join('')}
        `;
      })
      .join('');

    listEl.querySelectorAll('[data-les]').forEach((b) => {
      b.addEventListener('click', () => openLesson(b.dataset.les));
    });
  }

  function renderCenterBody() {
    const body = el('eaCenterBody');
    const les = store.currentLesson;
    if (!body || !les) return;

    if (el('eaLessonLevelBadge')) el('eaLessonLevelBadge').textContent = `Уровень ${les.level}`;
    const rec = store.state?.lessons?.[les.id];
    if (el('eaLessonStatusBadge')) el('eaLessonStatusBadge').textContent = rec?.passed ? `Освоено (${rec.score}%)` : 'В процессе';
    if (el('eaLessonTitle')) el('eaLessonTitle').textContent = les.title;
    if (el('eaLessonSummary')) el('eaLessonSummary').textContent = les.section_title || '';
    if (el('eaTutorHint')) el('eaTutorHint').textContent = `Урок: ${les.level} · ${les.title}`;

    el('eaStepPill1')?.classList.toggle('active', store.lessonStep === 'theory');
    el('eaStepPill2')?.classList.toggle('active', store.lessonStep === 'practice');
    el('eaStepPill3')?.classList.toggle('active', store.lessonStep === 'summary');

    if (store.lessonStep === 'theory' && les.kind === 'lesson') {
      const showHint = Boolean(store.state?.settings?.show_ru_hint ?? true);
      body.innerHTML = `
        ${
          (les.showcase || []).length
            ? `<div class="ea-sec-label">Показ в речи</div>
               <div class="ea-examples-list">
                 ${les.showcase
                   .map(
                     (s) => `
                   <div class="ea-ex-card">
                     <div>
                       <div style="font-weight:700;font-size:14px;">${esc(s.en)}</div>
                       <div style="font-size:12.5px;color:var(--ea-muted);margin-top:3px;">${esc(s.ru)}</div>
                     </div>
                     <button class="ea-speak-btn" data-speak="${esc(s.speak || s.en)}" type="button">🔊</button>
                   </div>`
                   )
                   .join('')}
               </div>`
            : ''
        }

        <div class="ea-sec-label">Объяснение простым языком</div>
        <div class="ea-theory-card">${esc(les.simple_explanation)}</div>
        <div class="ea-rule-line">📌 ${esc(les.rule_name)}</div>

        ${
          (les.examples || []).length
            ? `<div class="ea-sec-label">Примеры со звуком</div>
               <div class="ea-examples-list">
                 ${les.examples
                   .map(
                     (ex) => `
                   <div class="ea-ex-card">
                     <div>
                       <div style="font-weight:700;font-size:14.5px;">${esc(ex.en)}</div>
                       <div style="font-size:12px;color:var(--ea-accent);">${esc(ex.ipa || '')}${showHint && ex.ru_hint ? ` · [${esc(ex.ru_hint)}]` : ''}</div>
                       <div style="font-size:12.5px;color:var(--ea-muted);margin-top:2px;">${esc(ex.ru)}</div>
                     </div>
                     <div style="display:flex;flex-direction:column;gap:4px;">
                       <button class="ea-speak-btn" data-speak="${esc(ex.en)}" type="button">🔊</button>
                       <button class="ea-speak-btn" data-slow="${esc(ex.en)}" type="button" title="Медленно" style="font-size:11px;">🐢</button>
                     </div>
                   </div>`
                   )
                   .join('')}
               </div>`
            : ''
        }

        <div style="display:flex;justify-content:flex-end;margin-top:8px;">
          <button id="eaStartExBtn" class="button primary" type="button">Перейти к упражнениям (${(les.exercises || []).length}) →</button>
        </div>
      `;

      body.querySelectorAll('[data-speak]').forEach((b) => b.addEventListener('click', () => speakEnglish(b.dataset.speak)));
      body.querySelectorAll('[data-slow]').forEach((b) => b.addEventListener('click', () => speakEnglish(b.dataset.slow, 0.62)));
      el('eaStartExBtn')?.addEventListener('click', () => {
        store.lessonStep = 'practice';
        store.exIndex = 0;
        renderCenterBody();
      });
      return;
    }

    if (store.lessonStep === 'summary') {
      renderSummary(body, les);
      return;
    }

    const exercises = les.exercises || [];
    const ex = exercises[store.exIndex];
    if (!ex) {
      store.lessonStep = 'summary';
      renderSummary(body, les);
      return;
    }
    renderExercise(body, les, ex, exercises.length);
  }

  function renderExercise(body, lesson, ex, total) {
    let selectedVal = null;
    let assembled = [];

    let media = '';
    if (ex.type === 'reading_qa' && ex.passage) {
      media = `<div class="ea-theory-card" style="margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <strong style="font-size:12px;color:var(--ea-accent);">Текст</strong>
          <button class="ea-speak-btn" id="eaExSpeakPassage" type="button">🔊</button>
        </div>
        ${esc(ex.passage)}
      </div>`;
    } else if ((ex.type === 'listening_qa' || ex.type === 'dictation') && ex.audio_text) {
      media = `<div class="ea-theory-card" style="margin-bottom:10px;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
          <button class="button secondary" id="eaExAudioNorm" type="button">🔊 Слушать</button>
          <button class="button secondary" id="eaExAudioSlow" type="button">🐢 Медленно</button>
          ${ex.type === 'listening_qa' ? `<button class="button secondary" id="eaExToggleText" type="button">👁 Текст</button>` : ''}
        </div>
        <div id="eaExHiddenText" class="ea-hidden" style="margin-top:8px;color:var(--ea-muted);font-size:13px;">${esc(ex.audio_text)}</div>
      </div>`;
    } else if (ex.type === 'mini_dialogue') {
      media = `<div class="ea-theory-card" style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
        <div>
          <div style="font-size:11.5px;color:var(--ea-muted);">${esc(ex.context || '')}</div>
          <strong>${esc(ex.speaker_line)}</strong>
          <div style="font-size:12.5px;color:var(--ea-muted);">${esc(ex.speaker_ru || '')}</div>
        </div>
        <button class="ea-speak-btn" id="eaExSpeakLine" type="button">🔊</button>
      </div>`;
    }

    let inputHtml = '';
    if (ex.options) {
      inputHtml = (ex.options || [])
        .map((o, i) => `<button class="ea-choice-btn" data-opt="${i}" type="button">${esc(o)}</button>`)
        .join('');
    } else if (ex.type === 'match') {
      const rights = [...(ex.pairs || []).map((p) => p.right)].sort();
      inputHtml = (ex.pairs || [])
        .map(
          (p) => `
        <div class="ea-match-row">
          <div style="padding:9px 12px;border-radius:9px;background:rgba(255,255,255,0.03);border:1px solid var(--ea-border);font-weight:700;">${esc(p.left)}</div>
          <select class="ea-select" data-mleft="${esc(p.left)}">
            <option value="">— Выберите —</option>
            ${rights.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('')}
          </select>
        </div>`
        )
        .join('');
    } else if (ex.type === 'word_order') {
      inputHtml = `
        <div style="font-size:12px;color:var(--ea-muted);margin-top:6px;">Соберите предложение:</div>
        <div id="eaWordTarget" class="ea-word-zone"></div>
        <div id="eaWordBank" class="ea-word-zone"></div>
      `;
    } else if (ex.type === 'guided_writing' || ex.type === 'free_writing') {
      inputHtml = `
        ${ex.sample ? `<div style="font-size:12px;color:var(--ea-muted);margin:6px 0;">Образец: <em>${esc(ex.sample)}</em></div>` : ''}
        <textarea id="eaExText" class="ea-textarea" rows="3" placeholder="Напишите ответ по-английски..."></textarea>
      `;
    } else {
      inputHtml = `<input id="eaExText" class="ea-input" type="text" autocomplete="off" placeholder="Введите ответ по-английски..." style="margin-top:10px;" />`;
    }

    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--ea-muted);margin-bottom:8px;">
        <span>Задание ${store.exIndex + 1} из ${total} · ${esc(SKILL_LABELS[ex.skill] || ex.skill)}</span>
      </div>
      ${media}
      <div style="font-size:15.5px;font-weight:700;margin-bottom:12px;">${esc(ex.prompt)}</div>
      ${inputHtml}
      <div id="eaExFb" class="ea-feedback ea-hidden"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;">
        <button id="eaCheckBtn" class="button primary" type="button">Проверить</button>
        <button id="eaHintBtn" class="button secondary" type="button">Подсказка</button>
        <button id="eaNextBtn" class="button secondary ea-hidden" type="button">
          ${store.exIndex + 1 < total ? 'Дальше →' : 'Завершить →'}
        </button>
      </div>
    `;

    el('eaExSpeakPassage')?.addEventListener('click', () => speakEnglish(ex.passage));
    el('eaExAudioNorm')?.addEventListener('click', () => playAudioOrSpeech(ex.audio_text, { audioUrl: ex.audio_url, slowAudioUrl: ex.slow_audio_url, slow: false }));
    el('eaExAudioSlow')?.addEventListener('click', () => playAudioOrSpeech(ex.audio_text, { audioUrl: ex.audio_url, slowAudioUrl: ex.slow_audio_url, slow: true }));
    el('eaExSpeakLine')?.addEventListener('click', () => speakEnglish(ex.speaker_line));
    el('eaExToggleText')?.addEventListener('click', () => el('eaExHiddenText')?.classList.toggle('ea-hidden'));

    if (ex.options) {
      body.querySelectorAll('[data-opt]').forEach((b) => {
        b.addEventListener('click', () => {
          body.querySelectorAll('[data-opt]').forEach((x) => x.classList.remove('selected'));
          b.classList.add('selected');
          selectedVal = ex.options[Number(b.dataset.opt)];
        });
      });
    }

    if (ex.type === 'word_order') {
      const bank = (ex.words || []).map((w, i) => ({ id: i, w }));
      const paint = () => {
        const tEl = el('eaWordTarget');
        const bEl = el('eaWordBank');
        if (!tEl || !bEl) return;
        tEl.innerHTML = assembled.map((x) => `<button type="button" class="ea-word-chip" data-rem="${x.id}">${esc(x.w)}</button>`).join('');
        const used = new Set(assembled.map((x) => x.id));
        bEl.innerHTML = bank
          .filter((x) => !used.has(x.id))
          .map((x) => `<button type="button" class="ea-word-chip" data-add="${x.id}">${esc(x.w)}</button>`)
          .join('');
        tEl.querySelectorAll('[data-rem]').forEach((b) => {
          b.addEventListener('click', () => {
            assembled = assembled.filter((x) => x.id !== Number(b.dataset.rem));
            paint();
          });
        });
        bEl.querySelectorAll('[data-add]').forEach((b) => {
          b.addEventListener('click', () => {
            const f = bank.find((x) => x.id === Number(b.dataset.add));
            if (f) assembled.push(f);
            paint();
          });
        });
      };
      paint();
    }

    const fb = el('eaExFb');
    const nextBtn = el('eaNextBtn');

    el('eaHintBtn')?.addEventListener('click', () => {
      if (!fb) return;
      fb.className = 'ea-feedback err';
      fb.textContent = `💡 ${ex.hint || 'Сверьтесь с правилом текущего урока.'}`;
      fb.classList.remove('ea-hidden');
    });

    const submit = async () => {
      let ans = '';
      if (ex.type === 'match') {
        ans = {};
        body.querySelectorAll('[data-mleft]').forEach((s) => {
          if (s.value) ans[s.dataset.mleft] = s.value;
        });
      } else if (ex.type === 'word_order') {
        ans = assembled.map((x) => x.w);
      } else if (ex.options) {
        ans = selectedVal || '';
      } else {
        ans = el('eaExText')?.value || '';
      }

      const attempt = (store.exAttempts[ex.id] || 0) + 1;
      store.exAttempts[ex.id] = attempt;

      try {
        const resp = await apiCall('/exercise/check', {
          method: 'POST',
          body: JSON.stringify({ lesson_id: lesson.id, exercise_id: ex.id, answer: ans, attempt }),
        });
        store.progress = resp.progress;
        if (store.state) store.state.mistakes = resp.mistakes;
        saveSnapshot();
        renderTopProgress();

        const r = resp.result;
        if (fb) {
          fb.className = `ea-feedback ${r.correct ? 'ok' : 'err'}`;
          let rubricHtml = '';
          if (r.rubric) {
            const rb = r.rubric;
            rubricHtml = `<div class="ea-rubric-grid">
              <span>Задача: <strong>${rb.task_completion}/20</strong></span>
              <span>Грамматика: <strong>${rb.grammar}/20</strong></span>
              <span>Словарь: <strong>${rb.vocabulary}/20</strong></span>
              <span>Структура: <strong>${rb.structure}/20</strong></span>
              <span>Связность: <strong>${rb.coherence}/20</strong></span>
              <span>Итого: <strong>${rb.total_score}/100</strong></span>
            </div>`;
          }
          fb.innerHTML = `<div>${esc(r.feedback)}</div>${rubricHtml}`;
          fb.classList.remove('ea-hidden');
        }
        if (r.correct) {
          if (store.exResults[ex.id] === undefined) store.exResults[ex.id] = attempt <= 2;
          nextBtn?.classList.remove('ea-hidden');
        } else if (r.revealed) {
          if (store.exResults[ex.id] === undefined) store.exResults[ex.id] = false;
          nextBtn?.classList.remove('ea-hidden');
        }
      } catch {
        const exp = String(ex.answer || '').trim().toLowerCase();
        const given = Array.isArray(ans) ? ans.join(' ').trim().toLowerCase() : String(ans || '').trim().toLowerCase();
        const ok = Boolean(given) && given.replace(/[.!?]+$/, '') === exp.replace(/[.!?]+$/, '');
        store.exResults[ex.id] = ok;
        if (fb) {
          fb.className = `ea-feedback ${ok ? 'ok' : 'err'}`;
          fb.textContent = ok ? `Верно! ${ex.explanation || ''}` : `Подсказка: ${ex.hint || ex.explanation || ''}`;
          fb.classList.remove('ea-hidden');
        }
        if (ok || attempt >= 2) nextBtn?.classList.remove('ea-hidden');
      }
    };

    el('eaCheckBtn')?.addEventListener('click', submit);
    el('eaExText')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && ex.type !== 'guided_writing' && ex.type !== 'free_writing') {
        e.preventDefault();
        submit();
      }
    });
    nextBtn?.addEventListener('click', () => {
      store.exIndex += 1;
      renderCenterBody();
    });
  }

  async function renderSummary(body, les) {
    const spent = Math.max(45, Math.round((Date.now() - (store.lessonStartedAt || Date.now())) / 1000));
    body.innerHTML = `<p style="color:var(--ea-muted);">Сохраняем результат…</p>`;
    try {
      const resp = await apiCall('/lesson/complete', {
        method: 'POST',
        body: JSON.stringify({ lesson_id: les.id, exercise_results: store.exResults, spent_seconds: spent }),
      });
      store.state = resp.state;
      store.progress = resp.progress;
      store.vocabulary = resp.vocabulary || store.vocabulary;
      saveSnapshot();
      renderTopProgress();
      renderStagesStrip();
      renderLessonsSidebar();

      const out = resp.outcome;
      body.innerHTML = `
        <h3 style="margin:0 0 8px;">${out.passed ? '✅ Тема освоена!' : '⚠️ Порог не набран'}</h3>
        <p style="font-size:14px;color:var(--ea-muted);line-height:1.5;">
          Результат: <strong>${out.score}%</strong> (нужно от ${out.threshold}%).
          ${out.passed ? 'Слова урока добавлены в словарь повторения, следующий шаг открыт.' : 'Пройдите упражнения ещё раз, чтобы закрепить тему.'}
        </p>
        <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;">
          ${
            out.passed && out.next_lesson_id !== les.id
              ? `<button id="eaSumNext" class="button primary" type="button">Следующая тема →</button>`
              : `<button id="eaSumRetry" class="button primary" type="button">Повторить урок</button>`
          }
        </div>
      `;
      el('eaSumNext')?.addEventListener('click', () => openLesson(out.next_lesson_id));
      el('eaSumRetry')?.addEventListener('click', () => openLesson(les.id));
    } catch (e) {
      body.innerHTML = `<p style="color:#fde68a;">Ошибка сохранения (${esc(e.message)}).</p>`;
    }
  }

  /* -------------------- ВТОРИЧНЫЙ ХАБ: СЛОВАРЬ, ОШИБКИ, ДИАЛОГИ, ПРОГРЕСС -------------------- */
  async function renderHubView() {
    const hub = el('eaHubView');
    if (!hub) return;
    const p = store.progress;
    const tabs = [
      ['vocab', `Словарь (${p.vocab_summary.learned}/${p.vocab_summary.total_in_course})`],
      ['mistakes', `Ошибки (${p.unresolved_mistakes_count})`],
      ['dialogues', 'Диалоги'],
      ['practice', 'Произношение'],
      ['progress', 'Прогресс навыков'],
    ];

    hub.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:14px;">
        <div class="ea-view-switch">
          ${tabs.map(([k, lbl]) => `<button class="ea-view-btn ${store.hubTab === k ? 'active' : ''}" data-htab="${k}" type="button">${esc(lbl)}</button>`).join('')}
        </div>
        <button id="eaHubBackBtn" class="button secondary" type="button">← Вернуться к уроку</button>
      </div>
      <div id="eaHubContent"></div>
    `;

    hub.querySelectorAll('[data-htab]').forEach((b) => {
      b.addEventListener('click', () => {
        store.hubTab = b.dataset.htab;
        renderHubView();
      });
    });
    el('eaHubBackBtn')?.addEventListener('click', () => {
      document.querySelector('[data-ea-view="studio"]')?.click();
    });

    const content = el('eaHubContent');
    if (!content) return;

    if (store.hubTab === 'vocab') {
      await renderVocabSection(content);
    } else if (store.hubTab === 'mistakes') {
      renderMistakesSection(content);
    } else if (store.hubTab === 'dialogues') {
      renderDialoguesSection(content);
    } else if (store.hubTab === 'practice') {
      renderPronunciationSection(content);
    } else {
      renderProgressSection(content);
    }
  }

  async function renderVocabSection(box) {
    const f = store.vocabFilter;
    try {
      const res = await apiCall(`/vocabulary?mode=${encodeURIComponent(f.mode)}&level=${encodeURIComponent(f.level)}&q=${encodeURIComponent(f.q)}`);
      store.vocabulary = res.items || [];
    } catch {}

    if (store.srsSession && store.srsSession.queue.length > 0) {
      const card = store.srsSession.queue[0];
      box.innerHTML = `
        <div class="ea-sub-card" style="max-width:520px;margin:0 auto;text-align:center;padding:22px;">
          <div style="font-size:12px;color:var(--ea-accent);">Карточки SRS · осталось ${store.srsSession.queue.length}</div>
          <h2 style="font-size:28px;margin:12px 0 4px;">${esc(card.word)}</h2>
          <div style="color:var(--ea-muted);font-size:13px;margin-bottom:12px;">${esc(card.ipa)} · [${esc(card.ru_hint)}]
            <button class="ea-speak-btn" id="eaSrsPlay" style="display:inline-grid;margin-left:6px;" type="button">🔊</button>
          </div>
          ${
            store.srsSession.revealed
              ? `<div class="ea-theory-card"><strong>${esc(card.ru)}</strong><br/><small>${esc(card.example)}</small></div>
                 <div style="display:flex;gap:8px;justify-content:center;">
                   <button id="eaSrsNo" class="button secondary" type="button">Повторить сегодня</button>
                   <button id="eaSrsYes" class="button primary" type="button">Помню ✓</button>
                 </div>`
              : `<button id="eaSrsShow" class="button primary" type="button">Показать перевод</button>`
          }
          <button id="eaSrsStop" class="button secondary" style="margin-top:12px;align-self:center;" type="button">Выйти</button>
        </div>
      `;
      el('eaSrsPlay')?.addEventListener('click', () => speakEnglish(card.word));
      el('eaSrsShow')?.addEventListener('click', () => {
        store.srsSession.revealed = true;
        renderVocabSection(box);
      });
      const stepSrs = async (knew) => {
        try {
          const r = await apiCall('/vocabulary/review', { method: 'POST', body: JSON.stringify({ word_id: card.id, knew_it: knew }) });
          store.progress = r.progress;
          renderTopProgress();
        } catch {}
        store.srsSession.queue.shift();
        store.srsSession.revealed = false;
        if (!store.srsSession.queue.length) store.srsSession = null;
        renderVocabSection(box);
      };
      el('eaSrsNo')?.addEventListener('click', () => stepSrs(false));
      el('eaSrsYes')?.addEventListener('click', () => stepSrs(true));
      el('eaSrsStop')?.addEventListener('click', () => {
        store.srsSession = null;
        renderVocabSection(box);
      });
      return;
    }

    box.innerHTML = `
      <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:space-between;align-items:center;">
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          ${[
            ['all', 'Все'],
            ['new', 'Новые'],
            ['due', 'Повтор'],
            ['hard', 'Трудные ★'],
            ['mastered', 'Изученные'],
          ]
            .map(([m, l]) => `<button class="ea-view-btn ${f.mode === m ? 'active' : ''}" data-vm="${m}" type="button">${l}</button>`)
            .join('')}
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <input id="eaVQ" class="ea-input" style="width:200px;" placeholder="Поиск..." value="${esc(f.q)}">
          <select id="eaVL" class="ea-select" style="width:120px;">
            <option value="">Все уровни</option>
            ${['A0', 'A1', 'A2', 'B1', 'B2'].map((l) => `<option value="${l}" ${f.level === l ? 'selected' : ''}>${l}</option>`).join('')}
          </select>
          <button id="eaStartCards" class="button primary" type="button" ${store.vocabulary.length ? '' : 'disabled'}>Карточки (${store.vocabulary.length})</button>
        </div>
      </div>

      <div class="ea-sub-grid">
        ${store.vocabulary
          .map(
            (w) => `
          <div class="ea-sub-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:11px;color:var(--ea-accent);font-weight:700;">${esc(w.level)} · ${esc(w.topic)}</span>
              <div style="display:flex;gap:4px;">
                <button class="ea-speak-btn" data-vs="${esc(w.word)}" type="button">🔊</button>
                <button class="ea-speak-btn" data-vh="${w.id}" type="button" style="color:${w.is_hard ? '#fbbf24' : 'var(--ea-muted)'};">★</button>
              </div>
            </div>
            <strong style="font-size:17px;">${esc(w.word)}</strong>
            <div style="font-size:12px;color:var(--ea-accent);">${esc(w.ipa)} · [${esc(w.ru_hint)}]</div>
            <div style="font-size:13.5px;">${esc(w.ru)}</div>
            <div style="font-size:12px;color:var(--ea-muted);">${esc(w.example)}</div>
          </div>
        `
          )
          .join('')}
      </div>
    `;

    box.querySelectorAll('[data-vm]').forEach((b) =>
      b.addEventListener('click', () => {
        f.mode = b.dataset.vm;
        renderVocabSection(box);
      })
    );
    el('eaVQ')?.addEventListener('change', (e) => {
      f.q = e.target.value;
      renderVocabSection(box);
    });
    el('eaVL')?.addEventListener('change', (e) => {
      f.level = e.target.value;
      renderVocabSection(box);
    });
    box.querySelectorAll('[data-vs]').forEach((b) => b.addEventListener('click', () => speakEnglish(b.dataset.vs)));
    box.querySelectorAll('[data-vh]').forEach((b) =>
      b.addEventListener('click', async () => {
        await apiCall('/vocabulary/hard', { method: 'POST', body: JSON.stringify({ word_id: b.dataset.vh }) });
        renderVocabSection(box);
      })
    );
    el('eaStartCards')?.addEventListener('click', () => {
      store.srsSession = { queue: [...store.vocabulary.slice(0, 15)], revealed: false };
      renderVocabSection(box);
    });
  }

  function renderMistakesSection(box) {
    const active = (store.state?.mistakes || []).filter((m) => !m.resolved);
    if (!active.length) {
      box.innerHTML = `<p style="color:var(--ea-muted);">Активных ошибок нет — отличный темп!</p>`;
      return;
    }
    box.innerHTML = active
      .map(
        (m) => `
      <div class="ea-sub-card" style="margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--ea-accent);">
          <span>${esc(SKILL_LABELS[m.skill] || m.skill)} · Ошибок: ${m.count}</span>
          <button class="button secondary" data-mles="${esc(m.lesson_id)}" style="padding:3px 9px;font-size:11.5px;" type="button">К уроку</button>
        </div>
        <strong>${esc(m.prompt)}</strong>
        <div style="font-size:12.5px;color:#fca5a5;">Ваш ответ: ${esc(m.user_answer)}</div>
        <div style="font-size:12.5px;color:var(--ea-muted);">${esc(m.explanation)}</div>
        <div style="display:flex;gap:8px;margin-top:6px;">
          <input class="ea-input" style="max-width:340px;" data-minp="${esc(m.id)}" placeholder="Исправьте ответ...">
          <button class="button primary" data-mfix="${esc(m.id)}" type="button">Закрыть ошибку</button>
        </div>
      </div>
    `
      )
      .join('');

    box.querySelectorAll('[data-mles]').forEach((b) =>
      b.addEventListener('click', () => {
        document.querySelector('[data-ea-view="studio"]')?.click();
        openLesson(b.dataset.mles);
      })
    );
    box.querySelectorAll('[data-mfix]').forEach((b) =>
      b.addEventListener('click', async () => {
        const id = b.dataset.mfix;
        const val = box.querySelector(`[data-minp="${CSS.escape(id)}"]`)?.value || '';
        const r = await apiCall('/mistakes/resolve', { method: 'POST', body: JSON.stringify({ mistake_id: id, answer: val }) });
        if (store.state) store.state.mistakes = r.mistakes;
        store.progress = r.progress;
        renderTopProgress();
        renderMistakesSection(box);
      })
    );
  }

  function renderDialoguesSection(box) {
    const dlgs = store.curriculum.dialogues || [];
    if (!store.activeDialogueId && dlgs.length) store.activeDialogueId = dlgs[0].id;
    const active = dlgs.find((d) => d.id === store.activeDialogueId) || dlgs[0];
    const turn = active?.turns?.[store.dlgTurnIdx];
    const dlgMode = store.dlgMode || 'guided'; // 'guided' | 'free'

    const freeTopics = [
      { id: 'intro', level: 'A0', title: 'Знакомство и работа', prompt: 'Hello! Nice to meet you. What is your name and what do you do?' },
      { id: 'shop', level: 'A1', title: 'В магазине', prompt: 'Good afternoon! Can I help you find something?' },
      { id: 'travel', level: 'A1', title: 'Поездка и отель', prompt: 'Welcome to the hotel! Do you have a reservation?' },
      { id: 'office', level: 'A2', title: 'Офис и задачи', prompt: 'Hi! Are we ready for the morning update? What are you working on today?' },
      { id: 'call', level: 'A2', title: 'Рабочий звонок', prompt: 'Hello, this is Dana from support speaking. How can I assist you?' },
      { id: 'meeting', level: 'B1', title: 'Созвон / Встреча', prompt: "Let's start the meeting. What is your opinion on the new timeline?" },
      { id: 'negotiation', level: 'B2', title: 'Переговоры', prompt: 'We would like a 15% discount on the annual plan. What can you offer?' },
    ];
    if (!store.freeTopicId) store.freeTopicId = 'intro';
    const activeFree = freeTopics.find((t) => t.id === store.freeTopicId) || freeTopics[0];

    const modeTabs = `
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <button type="button" class="button ${dlgMode === 'guided' ? 'primary' : 'secondary'}" data-ea-dmode="guided">Сценарии (выбор реплики)</button>
        <button type="button" class="button ${dlgMode === 'free' ? 'primary' : 'secondary'}" data-ea-dmode="free">Свободный диалог (текстом)</button>
      </div>
    `;

    if (dlgMode === 'free') {
      box.innerHTML = `
        ${modeTabs}
        <div class="ea-two-col">
          <div>
            ${freeTopics.map((t) => `<button class="ea-lesson-btn ${t.id === activeFree.id ? 'active' : ''}" data-ftid="${t.id}" type="button"><span><strong>${esc(t.level)}</strong> · ${esc(t.title)}</span><span>💬</span></button>`).join('')}
          </div>
          <div class="ea-sub-card">
            <div style="font-size:12px;color:var(--ea-accent);">${esc(activeFree.level)} · Свободный диалог: ${esc(activeFree.title)}</div>
            <div class="ea-theory-card" style="display:flex;justify-content:space-between;align-items:center;">
              <div><strong>${esc(store.freeNextPrompt || activeFree.prompt)}</strong></div>
              <button class="ea-speak-btn" id="eaFreeSpk" type="button">🔊</button>
            </div>
            <textarea id="eaFreeInput" class="ea-textarea" rows="3" placeholder="Напишите свой ответ на английском..."></textarea>
            <div style="display:flex;gap:8px;margin-top:6px;">
              <button id="eaFreeSend" class="button primary" type="button">Ответить</button>
              <button id="eaFreeReset" class="button secondary" type="button">Сначала</button>
            </div>
            <div id="eaFreeFb" class="ea-feedback ea-hidden"></div>
          </div>
        </div>
      `;
      box.querySelectorAll('[data-ea-dmode]').forEach((b) => b.addEventListener('click', () => { store.dlgMode = b.dataset.eaDmode; renderDialoguesSection(box); }));
      box.querySelectorAll('[data-ftid]').forEach((b) => b.addEventListener('click', () => { store.freeTopicId = b.dataset.ftid; store.freeNextPrompt = ''; renderDialoguesSection(box); }));
      el('eaFreeSpk')?.addEventListener('click', () => speakEnglish(store.freeNextPrompt || activeFree.prompt));
      el('eaFreeReset')?.addEventListener('click', () => { store.freeNextPrompt = ''; renderDialoguesSection(box); });
      el('eaFreeSend')?.addEventListener('click', async () => {
        const text = el('eaFreeInput')?.value || '';
        const fb = el('eaFreeFb');
        try {
          const r = await apiCall('/free-dialogue/turn', { method: 'POST', body: JSON.stringify({ topic_id: activeFree.id, user_text: text }) });
          if (store.state) store.state.mistakes = r.mistakes;
          store.progress = r.progress;
          renderTopProgress();
          if (fb) {
            fb.className = `ea-feedback ${r.result.passed ? 'ok' : 'err'}`;
            fb.textContent = r.result.feedback;
            fb.classList.remove('ea-hidden');
          }
          if (r.result.passed && r.result.next_prompt) {
            store.freeNextPrompt = r.result.next_prompt;
          }
        } catch {
          if (fb) {
            fb.className = 'ea-feedback err';
            fb.textContent = 'Не удалось проверить ответ — проверьте соединение.';
            fb.classList.remove('ea-hidden');
          }
        }
      });
      return;
    }

    box.innerHTML = `
      ${modeTabs}
      <div class="ea-two-col">
        <div>
          ${dlgs
            .map(
              (d) => `<button class="ea-lesson-btn ${d.id === active?.id ? 'active' : ''}" data-did="${d.id}" type="button">
                <span><strong>${esc(d.level)}</strong> · ${esc(d.title)}</span><span>💬</span>
              </button>`
            )
            .join('')}
        </div>
        <div class="ea-sub-card">
          ${
            turn
              ? `<div style="font-size:12px;color:var(--ea-accent);">${esc(active.level)} · Реплика ${store.dlgTurnIdx + 1}/${active.turns.length}</div>
                 <div class="ea-theory-card" style="display:flex;justify-content:space-between;align-items:center;">
                   <div><strong>${esc(turn.en)}</strong><div style="font-size:12.5px;color:var(--ea-muted);">${esc(turn.ru)}</div></div>
                   <button class="ea-speak-btn" id="eaDSpk" type="button">🔊</button>
                 </div>
                 ${turn.options.map((o, i) => `<button class="ea-choice-btn" data-dopt="${i}" type="button">${esc(o.en)}</button>`).join('')}
                 <div id="eaDFb" class="ea-feedback ea-hidden"></div>
                 <button id="eaDNxt" class="button primary ea-hidden" type="button">Дальше →</button>`
              : `<strong>✅ Диалог пройден!</strong>
                 <button id="eaDRst" class="button secondary" type="button" style="align-self:flex-start;">Повторить</button>`
          }
        </div>
      </div>
    `;
    box.querySelectorAll('[data-ea-dmode]').forEach((b) => b.addEventListener('click', () => { store.dlgMode = b.dataset.eaDmode; renderDialoguesSection(box); }));

    box.querySelectorAll('[data-did]').forEach((b) =>
      b.addEventListener('click', () => {
        store.activeDialogueId = b.dataset.did;
        store.dlgTurnIdx = 0;
        renderDialoguesSection(box);
      })
    );
    el('eaDSpk')?.addEventListener('click', () => speakEnglish(turn.en));
    box.querySelectorAll('[data-dopt]').forEach((b) =>
      b.addEventListener('click', () => {
        const opt = turn.options[Number(b.dataset.dopt)];
        const fb = el('eaDFb');
        if (fb) {
          fb.className = `ea-feedback ${opt.correct ? 'ok' : 'err'}`;
          fb.textContent = opt.feedback;
          fb.classList.remove('ea-hidden');
        }
        if (opt.correct) {
          speakEnglish(opt.en);
          el('eaDNxt')?.classList.remove('ea-hidden');
        }
      })
    );
    el('eaDNxt')?.addEventListener('click', async () => {
      store.dlgTurnIdx += 1;
      if (store.dlgTurnIdx >= active.turns.length) {
        try {
          const r = await apiCall('/dialogue/complete', { method: 'POST', body: JSON.stringify({ dialogue_id: active.id }) });
          store.progress = r.progress;
          renderTopProgress();
        } catch {}
      }
      renderDialoguesSection(box);
    });
    el('eaDRst')?.addEventListener('click', () => {
      store.dlgTurnIdx = 0;
      renderDialoguesSection(box);
    });
  }

  function renderPronunciationSection(box) {
    const hasRec = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition || (navigator.mediaDevices && window.MediaRecorder));
    box.innerHTML = `
      <div class="ea-sub-card" style="max-width:640px;">
        <strong>Тренировка произношения и аудирования</strong>
        <select id="eaPSel" class="ea-select">
          <option value="Hello! My name is Anna. Nice to meet you.">A0: Hello! My name is Anna. Nice to meet you.</option>
          <option value="Do you speak English? Can you help me, please?">A1: Do you speak English? Can you help me, please?</option>
          <option value="Tomorrow I am going to work from home.">A2: Tomorrow I am going to work from home.</option>
          <option value="I have already sent the updated report.">B1: I have already sent the updated report.</option>
          <option value="Let us carry out a pilot test before the release.">B2: Let us carry out a pilot test before the release.</option>
        </select>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button id="eaPPlay" class="button primary" type="button">🔊 Слушать</button>
          <button id="eaPSlow" class="button secondary" type="button">🐢 Медленно (0.65x)</button>
          <button id="eaPRec" class="button secondary" type="button">🎙 Запись / Сверка</button>
        </div>
        <div id="eaPSt" class="ea-theory-card" style="margin:6px 0 0;font-size:13px;">
          ${hasRec ? 'Нажмите «Запись / Сверка» только при готовности говорить — микрофон запрашивается по кнопке.' : 'Микрофон недоступен: слушайте диктора и повторяйте вслух.'}
        </div>
        <audio id="eaPAudio" controls class="ea-hidden" style="width:100%;"></audio>
      </div>
    `;
    const sel = el('eaPSel');
    el('eaPPlay')?.addEventListener('click', () => speakEnglish(sel.value));
    el('eaPSlow')?.addEventListener('click', () => speakEnglish(sel.value, 0.62));
    el('eaPRec')?.addEventListener('click', async () => {
      const st = el('eaPSt');
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SR) {
        try {
          const r = new SR();
          r.lang = 'en-US';
          st.textContent = '🎙 Говорите...';
          r.onresult = async (ev) => {
            const heard = ev.results?.[0]?.[0]?.transcript || '';
            try {
              const cmp = await apiCall('/pronunciation/compare', {
                method: 'POST',
                body: JSON.stringify({ reference: sel.value, recognized: heard }),
              });
              const miss = (cmp.missing_words || []).length
                ? ` · Пропущено: ${cmp.missing_words.join(', ')}`
                : '';
              st.innerHTML = `<div>Распознано: «${esc(heard)}»</div>
                <div>Совпадение по словам: <strong>${cmp.match_percent}%</strong>${esc(miss)}</div>
                <small style="color:var(--ea-muted);">${esc(cmp.disclaimer)}</small>`;
            } catch {
              st.textContent = `Распознано: «${heard}». Сверьте с фразой выше.`;
            }
          };
          r.onerror = () => {
            st.textContent = 'Не удалось распознать речь — используйте сравнение на слух.';
          };
          r.start();
          return;
        } catch {}
      }
      if (navigator.mediaDevices && window.MediaRecorder) {
        if (store.mediaRecorder && store.mediaRecorder.state === 'recording') {
          store.mediaRecorder.stop();
          return;
        }
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const ch = [];
          const mr = new MediaRecorder(stream);
          store.mediaRecorder = mr;
          st.textContent = '🔴 Идёт запись... Нажмите ещё раз для остановки.';
          mr.ondataavailable = (e) => ch.push(e.data);
          mr.onstop = () => {
            stream.getTracks().forEach((t) => t.stop());
            if (store.recordedUrl) {
              try { URL.revokeObjectURL(store.recordedUrl); } catch {}
              store.recordedUrl = null;
            }
            const url = URL.createObjectURL(new Blob(ch, { type: 'audio/webm' }));
            store.recordedUrl = url;
            const a = el('eaPAudio');
            if (a) {
              a.src = url;
              a.classList.remove('ea-hidden');
            }
            st.textContent = 'Запись готова — прослушайте и сравните с эталоном.';
          };
          mr.start();
        } catch {
          st.textContent = 'Доступ к микрофону не выдан.';
        }
      }
    });
  }

  function renderProgressSection(box) {
    const p = store.progress;
    box.innerHTML = `
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px;font-size:13px;color:var(--ea-muted);">
        <span>🔥 Серия: <strong>${p.streak_days} дн.</strong></span>
        <span>⏱ Время: <strong>${p.study_minutes} мин</strong></span>
        <span>📚 Выучено слов: <strong>${p.vocab_summary.learned} / ${p.vocab_summary.total_in_course}</strong></span>
      </div>
      <div class="ea-sub-grid">
        ${Object.entries(p.skills)
          .map(
            ([k, st]) => `
          <div class="ea-sub-card">
            <div style="display:flex;justify-content:space-between;"><strong>${esc(SKILL_LABELS[k] || k)}</strong><span>${st.percent}%</span></div>
            <div class="ea-bar-track"><div class="ea-bar-fill" style="width:${st.percent}%"></div></div>
            <small style="color:var(--ea-muted);">Точность: ${st.accuracy}% (${st.correct}/${st.total})</small>
          </div>
        `
          )
          .join('')}
      </div>
    `;
  }

  /* -------------------- НАСТРОЙКИ И ЭКСПОРТ/ИМПОРТ -------------------- */
  function renderSettingsView() {
    const box = el('eaSettingsView');
    if (!box) return;
    const s = store.state?.settings || { speech_rate: 0.85, show_ru_hint: true, daily_goal_minutes: 15 };
    box.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <h3 style="margin:0;">Настройки и переносимость прогресса</h3>
        <button id="eaSetBackBtn" class="button secondary" type="button">← Вернуться к уроку</button>
      </div>
      <div class="ea-two-col">
        <div class="ea-sub-card">
          <label>Скорость озвучки:
            <select id="eaSRate" class="ea-select" style="margin-top:6px;">
              <option value="0.7" ${Number(s.speech_rate) <= 0.72 ? 'selected' : ''}>0.7x (медленно)</option>
              <option value="0.85" ${Number(s.speech_rate) > 0.72 && Number(s.speech_rate) < 0.95 ? 'selected' : ''}>0.85x (учебная)</option>
              <option value="1" ${Number(s.speech_rate) >= 0.95 ? 'selected' : ''}>1.0x (обычная)</option>
            </select>
          </label>
          <label style="display:flex;gap:8px;align-items:center;margin-top:8px;">
            <input type="checkbox" id="eaSRu" ${s.show_ru_hint ? 'checked' : ''} /> Показывать русскую фонетическую подсказку
          </label>
          <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--ea-border);">
            <label style="display:flex;gap:8px;align-items:center;cursor:pointer;">
              <input type="checkbox" id="eaSettingsOfflineToggle" ${store.forceOffline ? 'checked' : ''} />
              <span>Автономный режим наставника (без облачного ИИ)</span>
            </label>
            <div id="eaSettingsOfflineHint" style="font-size:12px;color:var(--ea-muted);margin-top:6px;${store.forceOffline ? '' : 'display:none;'}">
              Облачный ИИ будет отключён. Наставник продолжит работать по материалам текущего урока.
            </div>
          </div>
          <button id="eaSSave" class="button primary" style="align-self:flex-start;margin-top:10px;" type="button">Сохранить</button>
        </div>

        <div class="ea-sub-card">
          <p style="font-size:13px;color:var(--ea-muted);margin:0;">Схема хранения v2. Вы можете экспортировать, импортировать или сбросить прогресс.</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
            <button id="eaExp" class="button primary" type="button">⬇ Экспорт (.json)</button>
            <label class="button secondary" style="cursor:pointer;">⬆ Импорт (.json)<input id="eaImp" type="file" accept=".json" style="display:none;"></label>
            <button id="eaSettingsPlacementBtn" class="button secondary" type="button">Пройти тест уровня заново</button>
            <button id="eaRst" class="button secondary" type="button">Сбросить</button>
          </div>
        </div>
      </div>
    `;

    el('eaSetBackBtn')?.addEventListener('click', () => document.querySelector('[data-ea-view="studio"]')?.click());
    el('eaSettingsPlacementBtn')?.addEventListener('click', () => openPlacementTest());
    el('eaSettingsOfflineToggle')?.addEventListener('change', (e) => {
      const checked = Boolean(e.target.checked);
      store.forceOffline = checked;
      try {
        localStorage.setItem(OFFLINE_MODE_KEY, checked ? '1' : '0');
      } catch {}
      const hintEl = el('eaSettingsOfflineHint');
      if (hintEl) hintEl.style.display = checked ? 'block' : 'none';
      updateTutorModeBadge();
      if (checked) {
        showNotice('Облачный ИИ будет отключён. Наставник продолжит работать по материалам текущего урока.');
      } else {
        showNotice('Облачный ИИ-наставник снова подключён.');
      }
    });
    el('eaSSave')?.addEventListener('click', async () => {
      const r = await apiCall('/settings', {
        method: 'POST',
        body: JSON.stringify({ speech_rate: Number(el('eaSRate').value), show_ru_hint: Boolean(el('eaSRu').checked) }),
      });
      if (store.state) store.state.settings = r.settings;
      showNotice('Настройки сохранены.');
    });
    el('eaExp')?.addEventListener('click', async () => {
      const b = await apiCall('/export');
      const url = URL.createObjectURL(new Blob([JSON.stringify(b, null, 2)], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `bahoniq_english_progress.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
    el('eaImp')?.addEventListener('change', async (e) => {
      const f = e.target.files?.[0];
      if (!f) return;
      const r = await apiCall('/import', { method: 'POST', body: await f.text() });
      store.state = r.state;
      store.progress = r.progress;
      store.vocabulary = r.vocabulary || [];
      renderAll();
      showNotice('Прогресс импортирован.');
    });
    el('eaRst')?.addEventListener('click', async () => {
      if (!window.confirm('Сбросить прогресс English Academy?')) return;
      const r = await apiCall('/reset', { method: 'POST' });
      store.state = r.state;
      store.progress = r.progress;
      store.vocabulary = r.vocabulary || [];
      store.currentLesson = findLesson('a0-l1');
      store.lessonStep = 'theory';
      renderAll();
    });
  }

  async function openPlacementTest() {
    store.view = 'hub';
    el('eaStudioView')?.classList.add('ea-hidden');
    el('eaSettingsView')?.classList.add('ea-hidden');
    const box = el('eaHubView');
    if (!box) return;
    box.classList.remove('ea-hidden');
    box.innerHTML = `<div class="ea-skeleton-box">Загрузка входного теста...</div>`;

    try {
      const data = await apiCall('/placement');
      const qs = data.questions || [];
      const answers = {};
      box.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:8px;">
          <div>
            <h3 style="margin:0;">Входное тестирование (A0–B2)</h3>
            <small style="color:var(--ea-muted);">Ответьте на вопросы, чтобы определить комфортный старт. Можно отказаться и начать с A0.</small>
          </div>
          <button id="eaPlCancel" class="button secondary" type="button">Отказаться и начать с A0</button>
        </div>
        <div id="eaPlBody" style="display:flex;flex-direction:column;gap:12px;">
          ${qs
            .map(
              (q, i) => `
            <div class="ea-sub-card">
              <div style="font-size:12px;color:var(--ea-accent);">${esc(q.level)} · Вопрос ${i + 1} из ${qs.length}</div>
              ${q.passage ? `<div class="ea-theory-card" style="font-size:14px;">${esc(q.passage)}</div>` : ''}
              ${q.audio_text ? `<button type="button" class="button secondary" style="align-self:flex-start;" data-pl-audio="${esc(q.audio_text)}">🔊 Прослушать фразу</button>` : ''}
              <strong>${esc(q.prompt)}</strong>
              <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:6px;margin-top:4px;">
                ${(q.options || [])
                  .map(
                    (o) => `<button type="button" class="ea-choice-btn" style="margin:0;" data-pl-q="${esc(q.id)}" data-pl-val="${esc(o)}">${esc(o)}</button>`
                  )
                  .join('')}
              </div>
            </div>
          `
            )
            .join('')}
        </div>
        <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;">
          <button id="eaPlSubmit" class="button primary" type="button">Завершить и определить уровень</button>
        </div>
        <div id="eaPlResult" class="ea-hidden" style="margin-top:14px;"></div>
      `;

      box.querySelectorAll('[data-pl-audio]').forEach((b) => b.addEventListener('click', () => speakEnglish(b.dataset.plAudio)));
      box.querySelectorAll('[data-pl-q]').forEach((b) => {
        b.addEventListener('click', () => {
          const qid = b.dataset.plQ;
          answers[qid] = b.dataset.plVal;
          box.querySelectorAll(`[data-pl-q="${CSS.escape(qid)}"]`).forEach((x) => x.classList.toggle('selected', x === b));
        });
      });

      el('eaPlCancel')?.addEventListener('click', async () => {
        await apiCall('/placement/apply', { method: 'POST', body: JSON.stringify({ level: 'A0' }) });
        document.querySelector('[data-ea-view="studio"]')?.click();
        await loadEnglishAcademy();
      });

      el('eaPlSubmit')?.addEventListener('click', async () => {
        const res = await apiCall('/placement/submit', { method: 'POST', body: JSON.stringify({ answers }) });
        const r = res.result;
        const rBox = el('eaPlResult');
        if (!rBox) return;
        rBox.classList.remove('ea-hidden');
        rBox.innerHTML = `
          <div class="ea-theory-card">
            <div style="font-size:15px;margin-bottom:6px;">Рекомендуемый уровень: <strong>${esc(r.recommended_level)}</strong> (${r.score} из ${r.total})</div>
            <div style="color:var(--ea-muted);margin-bottom:10px;">${esc(r.explanation)}</div>
            <div style="display:flex;gap:10px;flex-wrap:wrap;">
              <button id="eaPlUseRec" class="button primary" type="button">Начать с уровня ${esc(r.recommended_level)}</button>
              <button id="eaPlUseA0" class="button secondary" type="button">Пройти всё с A0</button>
            </div>
          </div>
        `;
        el('eaPlUseRec')?.addEventListener('click', async () => {
          await apiCall('/placement/apply', { method: 'POST', body: JSON.stringify({ level: r.recommended_level }) });
          store.currentLesson = null;
          document.querySelector('[data-ea-view="studio"]')?.click();
          await loadEnglishAcademy();
        });
        el('eaPlUseA0')?.addEventListener('click', async () => {
          await apiCall('/placement/apply', { method: 'POST', body: JSON.stringify({ level: 'A0' }) });
          store.currentLesson = null;
          document.querySelector('[data-ea-view="studio"]')?.click();
          await loadEnglishAcademy();
        });
      });
    } catch {
      box.innerHTML = `<div class="ea-feedback err">Не удалось загрузить входной тест. Попробуйте позже.</div>`;
    }
  }

  window.loadEnglishAcademy = loadEnglishAcademy;
})();
