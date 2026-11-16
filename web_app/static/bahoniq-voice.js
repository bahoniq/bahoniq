// ============================================================================
// BahonIQ Voice v1 — Unified Client-Side Voice System (Web Speech API)
// Provides Speech Synthesis (ru-RU), Speech Recognition (ru-RU), Text Cleaner,
// Auto-Speak Management, and UI Controller Bindings across all BahonIQ modules.
// ============================================================================
(() => {
  'use strict';

  // --- Voice State ---
  let cachedRussianVoice = null;
  let voicesLoaded = false;
  let currentUtterance = null;
  let currentController = null;
  let activeRecognition = null;
  let currentState = 'stopped'; // 'stopped' | 'loading' | 'playing' | 'paused' | 'error'

  // --- Support Checks ---
  const isSpeechSupported = () => {
    return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  };

  const isRecognitionSupported = () => {
    return typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);
  };

  // --- Voice Initialization ---
  function initVoices() {
    if (!isSpeechSupported()) return;
    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return;

    // Prefer high quality Russian voices
    const ruVoices = voices.filter(v => v.lang && (v.lang.toLowerCase() === 'ru-ru' || v.lang.toLowerCase().startsWith('ru')));
    if (ruVoices.length > 0) {
      // Prioritize natural / cloud / local modern voices
      const preferred = ruVoices.find(v => /google|natural|yandex|irina|pavel|dmitry/i.test(v.name)) || ruVoices[0];
      cachedRussianVoice = preferred;
    } else {
      cachedRussianVoice = voices.find(v => v.default) || voices[0];
    }
    voicesLoaded = true;
  }

  if (isSpeechSupported()) {
    initVoices();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = initVoices;
    }
  }

  // --- Text Preparation / Sanitization Engine ---
  function prepareText(text, module = 'general') {
    if (!text) return '';
    let s = String(text);

    // 1. Module-specific preprocessing
    if (module === 'code') {
      // Replace code blocks with spoken note
      s = s.replace(/```[\s\S]*?```/g, ' Пример кода показан на экране. ');
      s = s.replace(/`([^`]+)`/g, '$1');
    } else if (module === 'ticket') {
      // Strip ticket service metadata lines
      s = s.replace(/^(ТЕМА|ОПИСАНИЕ|ПРИОРИТЕТ|СИСТЕМА|МОДУЛЬ):\s*/gim, '');
    } else if (module === 'wiki') {
      // Strip markdown link URLs, keep anchor text
      s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
      s = s.replace(/https?:\/\/\S+/g, '');
    } else if (module === 'excel' || module === 'excel_ai') {
      // Keep formulas and functions, but avoid reading raw huge tables row-by-row
      s = s.replace(/https?:\/\/\S+/g, '');
      s = s.replace(/\|[^\n]+\|/g, ' '); // remove markdown table lines
    } else if (module === 'design') {
      // Strip internal coordinate IDs
      s = s.replace(/\[obj_\w+\]/g, '');
      s = s.replace(/x=\d+,\s*y=\d+/gi, '');
    }

    // 2. Universal Markdown & HTML cleaning
    s = s.replace(/<[^>]+>/g, ' '); // strip HTML tags
    s = s.replace(/```[\s\S]*?```/g, ' '); // any remaining code blocks
    s = s.replace(/`([^`]+)`/g, '$1'); // inline backticks
    s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // links
    s = s.replace(/https?:\/\/\S+/g, ''); // bare URLs
    s = s.replace(/[*_~#>]+/g, ' '); // markdown header/bold/italic chars

    // 3. Technical symbols sanitization (preserve mathematical symbols for excel)
    if (module !== 'excel' && module !== 'excel_ai') {
      s = s.replace(/[{}\[\]\\\/^=<>|~]/g, ' ');
    } else {
      s = s.replace(/[{}\[\]\\\/^|~]/g, ' ');
    }

    // 4. Whitespace normalization
    s = s.replace(/\s+/g, ' ').trim();

    // 5. Reasonable length limit per run (approx 1200 characters)
    if (s.length > 1200) {
      s = s.slice(0, 1200) + '... Текст сокращен для удобства прослушивания.';
    }

    return s;
  }

  // --- Speech Synthesis API ---
  function stop() {
    if (!isSpeechSupported()) return;
    try {
      window.speechSynthesis.cancel();
    } catch (e) {
      console.warn('Speech cancel error:', e);
    }
    currentState = 'stopped';
    currentUtterance = null;
    if (currentController && typeof currentController.onStateChange === 'function') {
      currentController.onStateChange('stopped');
    }
    currentController = null;
  }

  function pause() {
    if (!isSpeechSupported()) return;
    if (currentState === 'playing') {
      try {
        window.speechSynthesis.pause();
        currentState = 'paused';
        if (currentController && typeof currentController.onStateChange === 'function') {
          currentController.onStateChange('paused');
        }
      } catch (e) {
        console.warn('Speech pause error:', e);
      }
    }
  }

  function resume() {
    if (!isSpeechSupported()) return;
    if (currentState === 'paused') {
      try {
        window.speechSynthesis.resume();
        currentState = 'playing';
        if (currentController && typeof currentController.onStateChange === 'function') {
          currentController.onStateChange('playing');
        }
      } catch (e) {
        console.warn('Speech resume error:', e);
      }
    }
  }

  function speak(rawText, options = {}) {
    if (!isSpeechSupported()) {
      if (options.onError) options.onError('Синтез речи не поддерживается в этом браузере.');
      return false;
    }

    // Always stop previous speech before starting new
    stop();

    const textToSpeak = prepareText(rawText, options.module || 'general');
    if (!textToSpeak) {
      return false;
    }

    initVoices();

    const u = new SpeechSynthesisUtterance(textToSpeak);
    u.lang = 'ru-RU';
    if (cachedRussianVoice) {
      u.voice = cachedRussianVoice;
    }
    u.rate = options.rate || 1.0;
    u.pitch = options.pitch || 1.0;

    currentUtterance = u;
    currentController = options.controller || null;
    currentState = 'loading';
    if (currentController && typeof currentController.onStateChange === 'function') {
      currentController.onStateChange('loading');
    }

    u.onstart = () => {
      currentState = 'playing';
      if (currentController && typeof currentController.onStateChange === 'function') {
        currentController.onStateChange('playing');
      }
      if (options.onStart) options.onStart();
    };

    u.onpause = () => {
      currentState = 'paused';
      if (currentController && typeof currentController.onStateChange === 'function') {
        currentController.onStateChange('paused');
      }
      if (options.onPause) options.onPause();
    };

    u.onresume = () => {
      currentState = 'playing';
      if (currentController && typeof currentController.onStateChange === 'function') {
        currentController.onStateChange('playing');
      }
      if (options.onResume) options.onResume();
    };

    u.onend = () => {
      currentState = 'stopped';
      currentUtterance = null;
      if (currentController && typeof currentController.onStateChange === 'function') {
        currentController.onStateChange('stopped');
      }
      currentController = null;
      if (options.onEnd) options.onEnd();
    };

    u.onerror = (err) => {
      currentState = 'error';
      currentUtterance = null;
      if (currentController && typeof currentController.onStateChange === 'function') {
        currentController.onStateChange('error');
      }
      currentController = null;
      if (options.onError) options.onError(err);
    };

    try {
      window.speechSynthesis.speak(u);
      return true;
    } catch (e) {
      console.error('SpeechSynthesis error:', e);
      currentState = 'error';
      if (options.onError) options.onError(e);
      return false;
    }
  }

  // --- Speech Recognition (Voice Input) ---
  function startRecognition(options = {}) {
    if (!isRecognitionSupported()) {
      if (options.onError) options.onError('Распознавание речи не поддерживается браузером.');
      return null;
    }

    stopRecognition();

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SpeechRec();
    rec.lang = 'ru-RU';
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = false; // user speaks sentence, recognition completes

    activeRecognition = rec;

    rec.onstart = () => {
      if (options.onStart) options.onStart();
    };

    rec.onresult = (e) => {
      let finalTranscript = '';
      let interimTranscript = '';
      for (let i = e.resultIndex; i < e.results.length; ++i) {
        if (e.results[i].isFinal) {
          finalTranscript += e.results[i][0].transcript;
        } else {
          interimTranscript += e.results[i][0].transcript;
        }
      }
      const text = finalTranscript || interimTranscript;
      if (options.onResult) options.onResult(text, Boolean(finalTranscript));
    };

    rec.onerror = (e) => {
      activeRecognition = null;
      if (options.onError) options.onError(e.error || 'Ошибка распознавания');
    };

    rec.onend = () => {
      activeRecognition = null;
      if (options.onEnd) options.onEnd();
    };

    try {
      rec.start();
      return rec;
    } catch (e) {
      activeRecognition = null;
      if (options.onError) options.onError(e.message || 'Не удалось запустить микрофон');
      return null;
    }
  }

  function stopRecognition() {
    if (activeRecognition) {
      try {
        activeRecognition.stop();
      } catch (e) {
        // ignore
      }
      activeRecognition = null;
    }
  }

  // --- Auto-Speak Preferences ---
  const AUTO_SPEAK_KEY = 'bahoniq_voice_auto_';

  function isAutoSpeakEnabled(moduleId) {
    if (!moduleId) return false;
    return localStorage.getItem(AUTO_SPEAK_KEY + moduleId) === 'true';
  }

  function setAutoSpeakEnabled(moduleId, boolVal) {
    if (!moduleId) return;
    localStorage.setItem(AUTO_SPEAK_KEY + moduleId, boolVal ? 'true' : 'false');
  }

  function autoSpeakIfEnabled(text, moduleId, options = {}) {
    if (!isAutoSpeakEnabled(moduleId)) return false;
    if (!text || text.length > 800) return false; // don't auto-read massive dumps
    return speak(text, { ...options, module: moduleId });
  }

  // --- UI Component Controller & Factory ---
  function createVoiceBar(config = {}) {
    // config: { container, moduleId, getText, inputEl, showAutoSpeak, labelText }
    const container = typeof config.container === 'string' ? document.querySelector(config.container) : config.container;
    if (!container) return null;

    const bar = document.createElement('div');
    bar.className = 'bahoniq-voice-bar';
    bar.setAttribute('role', 'toolbar');
    bar.setAttribute('aria-label', 'Голосовое управление');

    // Controller state
    const controller = {
      state: 'stopped',
      onStateChange: (newState) => {
        controller.state = newState;
        updateUI();
      }
    };

    // 1. Speak / Pause Button
    const btnSpeak = document.createElement('button');
    btnSpeak.type = 'button';
    btnSpeak.className = 'bv-btn bv-btn-speak';
    btnSpeak.setAttribute('aria-label', 'Озвучить текст голосом');
    btnSpeak.title = 'Озвучить текст голосом';

    // 2. Stop Button
    const btnStop = document.createElement('button');
    btnStop.type = 'button';
    btnStop.className = 'bv-btn bv-btn-stop';
    btnStop.setAttribute('aria-label', 'Остановить воспроизведение');
    btnStop.title = 'Остановить воспроизведение';
    btnStop.innerHTML = '<span>⏹ Стоп</span>';
    btnStop.disabled = true;

    function updateUI() {
      btnSpeak.className = 'bv-btn bv-btn-speak ' + controller.state;
      if (controller.state === 'playing') {
        btnSpeak.innerHTML = '<span>⏸ Пауза</span>';
        btnStop.disabled = false;
      } else if (controller.state === 'paused') {
        btnSpeak.innerHTML = '<span>▶ Продолжить</span>';
        btnStop.disabled = false;
      } else if (controller.state === 'loading') {
        btnSpeak.innerHTML = '<span>⏳ Загрузка...</span>';
        btnStop.disabled = false;
      } else {
        btnSpeak.innerHTML = `<span>🔊 ${config.labelText || 'Озвучить'}</span>`;
        btnStop.disabled = true;
      }
    }

    updateUI();

    btnSpeak.onclick = () => {
      if (controller.state === 'playing') {
        pause();
      } else if (controller.state === 'paused') {
        resume();
      } else {
        const text = typeof config.getText === 'function' ? config.getText() : '';
        if (text) {
          speak(text, {
            module: config.moduleId || 'general',
            controller: controller
          });
        }
      }
    };

    btnStop.onclick = () => {
      stop();
    };

    bar.appendChild(btnSpeak);
    bar.appendChild(btnStop);

    // 3. Microphone Button (if input element provided)
    if (config.inputEl) {
      const input = typeof config.inputEl === 'string' ? document.querySelector(config.inputEl) : config.inputEl;
      if (input && isRecognitionSupported()) {
        const btnMic = document.createElement('button');
        btnMic.type = 'button';
        btnMic.className = 'bv-btn bv-btn-mic';
        btnMic.setAttribute('aria-label', 'Голосовой ввод (микрофон)');
        btnMic.title = 'Нажмите для голосового ввода на русском языке';
        btnMic.innerHTML = '<span>🎙 Голос</span>';

        let isListening = false;

        btnMic.onclick = () => {
          if (isListening) {
            stopRecognition();
            isListening = false;
            btnMic.classList.remove('listening');
            btnMic.innerHTML = '<span>🎙 Голос</span>';
          } else {
            // Stop any playing speech before listening to avoid echo
            stop();
            btnMic.classList.add('listening');
            btnMic.innerHTML = '<span>🎙 Слушаю...</span>';
            isListening = true;

            const originalVal = input.value || '';
            startRecognition({
              onStart: () => {
                isListening = true;
              },
              onResult: (transcript, isFinal) => {
                const space = (originalVal && !originalVal.endsWith(' ')) ? ' ' : '';
                input.value = originalVal ? (originalVal + space + transcript) : transcript;
                input.dispatchEvent(new Event('input', { bubbles: true }));
              },
              onEnd: () => {
                isListening = false;
                btnMic.classList.remove('listening');
                btnMic.innerHTML = '<span>🎙 Голос</span>';
              },
              onError: (err) => {
                isListening = false;
                btnMic.classList.remove('listening');
                btnMic.innerHTML = '<span>🎙 Голос</span>';
                if (err !== 'no-speech') {
                  alert('Микрофон: ' + (err.message || err));
                }
              }
            });
          }
        };

        bar.appendChild(btnMic);
      }
    }

    // 4. Auto-speak Toggle
    if (config.showAutoSpeak && config.moduleId) {
      const autoLabel = document.createElement('label');
      autoLabel.className = 'bv-auto-speak-wrap';
      autoLabel.title = 'Автоматически озвучивать ответы ИИ при их получении';

      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = isAutoSpeakEnabled(config.moduleId);
      chk.onchange = () => {
        setAutoSpeakEnabled(config.moduleId, chk.checked);
      };

      const txt = document.createElement('span');
      txt.textContent = 'Автоозвучка';

      autoLabel.appendChild(chk);
      autoLabel.appendChild(txt);
      bar.appendChild(autoLabel);
    }

    container.appendChild(bar);
    return { bar, controller };
  }

  // --- Auto-stop on Page Navigation & Tab Switches ---
  if (typeof window !== 'undefined') {
    window.addEventListener('hashchange', stop);
    window.addEventListener('beforeunload', stop);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop();
    });
  }

  // --- Public API Export ---
  window.BahonIQVoice = {
    speak,
    pause,
    resume,
    stop,
    getState: () => currentState,
    startRecognition,
    stopRecognition,
    isSpeechSupported,
    isRecognitionSupported,
    prepareText,
    isAutoSpeakEnabled,
    setAutoSpeakEnabled,
    autoSpeakIfEnabled,
    createVoiceBar
  };
})();
