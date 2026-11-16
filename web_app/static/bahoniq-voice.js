// ============================================================================
// BahonIQ Voice v2 — Unified Neural Text-to-Speech & Speech Recognition Engine
// Powered by Microsoft Edge Neural Voices (ru-RU-DmitryNeural, ru-RU-SvetlanaNeural)
// with HTML5 Audio Element streaming, In-Memory Client Cache, AbortController,
// Sequential Chunking for Long Texts (>4000 chars), and strictly user-confirmed
// Emergency Fallback to Web Speech API.
// ============================================================================
(() => {
  'use strict';

  // --- Storage Keys ---
  const VOICE_KEY = 'bahoniq_voice_selected_voice';
  const RATE_KEY = 'bahoniq_voice_selected_rate';

  // --- Voice State & Sequential Queue ---
  let currentAudio = null;
  let currentAudioUrl = null;
  let currentAbortController = null;
  let currentController = null;
  let activeRecognition = null;
  let currentState = 'stopped'; // 'stopped' | 'loading' | 'playing' | 'paused' | 'error'

  let activeQueue = [];
  let currentQueueIndex = 0;
  let isPlayingQueue = false;
  let currentQueueOptions = {};

  // --- In-Memory Client Blob Cache (Max 30 items) ---
  const clientBlobCache = new Map();
  const MAX_CLIENT_CACHE = 30;

  function getClientCachedBlob(cacheKey) {
    if (clientBlobCache.has(cacheKey)) {
      const blob = clientBlobCache.get(cacheKey);
      clientBlobCache.delete(cacheKey);
      clientBlobCache.set(cacheKey, blob);
      return blob;
    }
    return null;
  }

  function setClientCachedBlob(cacheKey, blob) {
    if (clientBlobCache.has(cacheKey)) {
      clientBlobCache.delete(cacheKey);
    }
    clientBlobCache.set(cacheKey, blob);
    if (clientBlobCache.size > MAX_CLIENT_CACHE) {
      const oldestKey = clientBlobCache.keys().next().value;
      clientBlobCache.delete(oldestKey);
    }
  }

  // --- Settings Getters & Setters ---
  function getSelectedVoice() {
    const val = localStorage.getItem(VOICE_KEY);
    return (val === 'ru-RU-SvetlanaNeural') ? 'ru-RU-SvetlanaNeural' : 'ru-RU-DmitryNeural';
  }

  function setSelectedVoice(voice) {
    const valid = (voice === 'ru-RU-SvetlanaNeural') ? 'ru-RU-SvetlanaNeural' : 'ru-RU-DmitryNeural';
    localStorage.setItem(VOICE_KEY, valid);
    document.querySelectorAll('.bv-voice-select').forEach(sel => {
      sel.value = valid;
    });
  }

  function getSelectedRate() {
    const val = localStorage.getItem(RATE_KEY);
    if (val === '0.9' || val === '1.1') return val;
    return '1.0';
  }

  function setSelectedRate(rate) {
    const valid = (rate === '0.9' || rate === '1.1') ? rate : '1.0';
    localStorage.setItem(RATE_KEY, valid);
    document.querySelectorAll('.bv-rate-select').forEach(sel => {
      sel.value = valid;
    });
  }

  function rateToPercent(rateStr) {
    if (rateStr === '0.9') return '-10%';
    if (rateStr === '1.1') return '+10%';
    return '+0%';
  }

  // --- Web Speech API Support Checks ---
  const isSpeechSupported = () => {
    return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  };

  const isRecognitionSupported = () => {
    return typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);
  };

  // --- Text Preparation / Sanitization Engine ---
  function prepareText(text, module = 'general') {
    if (!text) return '';
    let s = String(text);

    // 1. Module-specific preprocessing
    if (module === 'code') {
      s = s.replace(/```[\s\S]*?```/g, ' Пример кода показан на экране. ');
      s = s.replace(/`([^`]+)`/g, '$1');
    } else if (module === 'ticket') {
      s = s.replace(/^(ТЕМА|ОПИСАНИЕ|ПРИОРИТЕТ|СИСТЕМА|МОДУЛЬ):\s*/gim, '');
    } else if (module === 'wiki') {
      s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
      s = s.replace(/https?:\/\/\S+/g, '');
    } else if (module === 'excel' || module === 'excel_ai') {
      s = s.replace(/https?:\/\/\S+/g, '');
      s = s.replace(/\|[^\n]+\|/g, ' ');
    } else if (module === 'design') {
      s = s.replace(/\[obj_\w+\]/g, '');
      s = s.replace(/x=\d+,\s*y=\d+/gi, '');
    }

    // 2. Universal Markdown & HTML cleaning
    s = s.replace(/<[^>]+>/g, ' ');
    s = s.replace(/```[\s\S]*?```/g, ' ');
    s = s.replace(/`([^`]+)`/g, '$1');
    s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    s = s.replace(/https?:\/\/\S+/g, '');
    s = s.replace(/[*_~#>]+/g, ' ');

    // 3. Technical symbols sanitization
    if (module !== 'excel' && module !== 'excel_ai') {
      s = s.replace(/[{}\[\]\\\/^=<>|~]/g, ' ');
    } else {
      s = s.replace(/[{}\[\]\\\/^|~]/g, ' ');
    }

    // 4. Whitespace normalization
    s = s.replace(/\s+/g, ' ').trim();
    return s;
  }

  // --- Safe Text Chunking (>3500 chars) for Long Wiki Answers ---
  function splitIntoChunks(text, maxLen = 3200) {
    if (!text || text.length <= maxLen) return [text];
    const chunks = [];
    let remaining = text.trim();

    while (remaining.length > 0) {
      if (remaining.length <= maxLen) {
        chunks.push(remaining);
        break;
      }

      const slice = remaining.slice(0, maxLen);
      let splitIdx = -1;

      // Split on paragraph break
      const pIdx = slice.lastIndexOf('\n');
      if (pIdx > maxLen * 0.5) {
        splitIdx = pIdx + 1;
      } else {
        // Split on sentence boundary
        const lastPeriod = Math.max(slice.lastIndexOf('. '), slice.lastIndexOf('! '), slice.lastIndexOf('? '));
        if (lastPeriod > maxLen * 0.4) {
          splitIdx = lastPeriod + 2;
        }
      }

      // Fallback: split on space
      if (splitIdx === -1) {
        const spaceIdx = slice.lastIndexOf(' ');
        splitIdx = (spaceIdx > maxLen * 0.3) ? spaceIdx + 1 : maxLen;
      }

      const chunk = remaining.slice(0, splitIdx).trim();
      if (chunk) chunks.push(chunk);
      remaining = remaining.slice(splitIdx).trim();
    }

    return chunks;
  }

  // --- Audio Control API (Stop / Pause / Resume) ---
  function stop() {
    activeQueue = [];
    currentQueueIndex = 0;
    isPlayingQueue = false;

    // 1. Abort active network synthesis
    if (currentAbortController) {
      try {
        currentAbortController.abort();
      } catch (e) {}
      currentAbortController = null;
    }

    // 2. Stop HTMLAudioElement
    if (currentAudio) {
      try {
        currentAudio.pause();
        currentAudio.currentTime = 0;
      } catch (e) {}
      currentAudio = null;
    }

    // 3. Revoke Blob Object URL
    if (currentAudioUrl) {
      try {
        URL.revokeObjectURL(currentAudioUrl);
      } catch (e) {}
      currentAudioUrl = null;
    }

    // 4. Cancel browser fallback speech if active
    if (isSpeechSupported()) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {}
    }

    currentState = 'stopped';
    if (currentController && typeof currentController.onStateChange === 'function') {
      currentController.onStateChange('stopped');
    }
    currentController = null;
  }

  function pause() {
    if (currentState === 'playing' && currentAudio) {
      try {
        currentAudio.pause();
        currentState = 'paused';
        if (currentController && typeof currentController.onStateChange === 'function') {
          currentController.onStateChange('paused');
        }
      } catch (e) {
        console.warn('Audio pause error:', e);
      }
    } else if (currentState === 'playing' && isSpeechSupported()) {
      try {
        window.speechSynthesis.pause();
        currentState = 'paused';
        if (currentController && typeof currentController.onStateChange === 'function') {
          currentController.onStateChange('paused');
        }
      } catch (e) {}
    }
  }

  function resume() {
    if (currentState === 'paused' && currentAudio) {
      try {
        currentAudio.play().then(() => {
          currentState = 'playing';
          if (currentController && typeof currentController.onStateChange === 'function') {
            currentController.onStateChange('playing');
          }
        }).catch(err => {
          console.warn('Audio resume error:', err);
        });
      } catch (e) {
        console.warn('Audio resume exception:', e);
      }
    } else if (currentState === 'paused' && isSpeechSupported()) {
      try {
        window.speechSynthesis.resume();
        currentState = 'playing';
        if (currentController && typeof currentController.onStateChange === 'function') {
          currentController.onStateChange('playing');
        }
      } catch (e) {}
    }
  }

  // --- Fallback Browser Speech Synthesis (Only upon explicit user confirmation) ---
  function speakFallback(cleanText, options = {}) {
    if (!isSpeechSupported()) {
      alert('Синтез речи не поддерживается браузером.');
      stop();
      return;
    }

    const u = new SpeechSynthesisUtterance(cleanText);
    u.lang = 'ru-RU';
    u.rate = parseFloat(getSelectedRate()) || 1.0;

    const voices = window.speechSynthesis.getVoices() || [];
    const ruVoices = voices.filter(v => v.lang && v.lang.toLowerCase().startsWith('ru'));
    if (ruVoices.length > 0) {
      u.voice = ruVoices.find(v => /google|natural|yandex|irina|pavel|dmitry/i.test(v.name)) || ruVoices[0];
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
    };

    u.onresume = () => {
      currentState = 'playing';
      if (currentController && typeof currentController.onStateChange === 'function') {
        currentController.onStateChange('playing');
      }
    };

    u.onend = () => {
      stop();
      if (options.onEnd) options.onEnd();
    };

    u.onerror = (e) => {
      stop();
      if (options.onError) options.onError(e);
    };

    try {
      window.speechSynthesis.speak(u);
    } catch (err) {
      console.error('Fallback speech error:', err);
      stop();
    }
  }

  // --- Fetch & Play a Single Audio Chunk ---
  async function playSingleChunk(chunkText, options = {}, queueInfo = null) {
    if (!chunkText) return false;

    currentState = 'loading';
    if (currentController && typeof currentController.onStateChange === 'function') {
      currentController.onStateChange('loading', queueInfo);
    }

    const voice = options.voice || getSelectedVoice();
    const rateStr = getSelectedRate();
    const rateParam = rateToPercent(rateStr);

    const cacheKey = `${voice}|${rateParam}|${chunkText.length}|${chunkText.slice(0, 50)}`;
    let audioBlob = getClientCachedBlob(cacheKey);

    if (!audioBlob) {
      currentAbortController = new AbortController();
      const signal = currentAbortController.signal;

      try {
        const response = await fetch('/api/voice/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: chunkText,
            voice: voice,
            rate: rateParam,
            pitch: '+0Hz'
          }),
          signal: signal
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${response.status}`);
        }

        audioBlob = await response.blob();
        setClientCachedBlob(cacheKey, audioBlob);
      } catch (err) {
        if (err.name === 'AbortError') {
          return false;
        }

        console.warn('Neural TTS request failed:', err.message);
        currentState = 'stopped';
        if (currentController && typeof currentController.onStateChange === 'function') {
          currentController.onStateChange('stopped');
        }

        const confirmFallback = confirm(
          'Нейроголос недоступен. Использовать системный голос?'
        );

        if (confirmFallback) {
          speakFallback(chunkText, options);
          return true;
        } else {
          stop();
          if (options.onError) options.onError(err);
          return false;
        }
      } finally {
        currentAbortController = null;
      }
    }

    if (!audioBlob) return false;

    return new Promise((resolve) => {
      try {
        if (currentAudioUrl) {
          try { URL.revokeObjectURL(currentAudioUrl); } catch (e) {}
        }

        currentAudioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(currentAudioUrl);
        currentAudio = audio;

        audio.onplay = () => {
          currentState = 'playing';
          if (currentController && typeof currentController.onStateChange === 'function') {
            currentController.onStateChange('playing', queueInfo);
          }
          if (options.onStart) options.onStart();
        };

        audio.onpause = () => {
          if (currentState === 'playing') {
            currentState = 'paused';
            if (currentController && typeof currentController.onStateChange === 'function') {
              currentController.onStateChange('paused', queueInfo);
            }
            if (options.onPause) options.onPause();
          }
        };

        audio.onended = () => {
          if (currentAudioUrl) {
            try { URL.revokeObjectURL(currentAudioUrl); } catch (e) {}
            currentAudioUrl = null;
          }
          currentAudio = null;
          resolve(true);
        };

        audio.onerror = (e) => {
          console.warn('HTMLAudio error:', e);
          if (currentAudioUrl) {
            try { URL.revokeObjectURL(currentAudioUrl); } catch (e) {}
            currentAudioUrl = null;
          }
          currentAudio = null;
          resolve(false);
        };

        audio.play().catch(playErr => {
          if (playErr.name === 'AbortError') {
            resolve(false);
            return;
          }
          console.warn('Audio play rejection:', playErr);
          resolve(false);
        });
      } catch (err) {
        console.warn('Audio setup error:', err);
        resolve(false);
      }
    });
  }

  // --- Sequential Queue Runner for Long Texts ---
  async function runQueue() {
    isPlayingQueue = true;
    while (isPlayingQueue && currentQueueIndex < activeQueue.length) {
      const idx = currentQueueIndex;
      const chunk = activeQueue[idx];
      const queueInfo = activeQueue.length > 1 ? { current: idx + 1, total: activeQueue.length } : null;

      const success = await playSingleChunk(chunk, currentQueueOptions, queueInfo);
      if (!success || !isPlayingQueue) {
        break;
      }
      currentQueueIndex++;
    }

    if (isPlayingQueue && currentQueueIndex >= activeQueue.length) {
      stop();
      if (currentQueueOptions.onEnd) currentQueueOptions.onEnd();
    }
  }

  // --- Primary Neural TTS speak() Engine ---
  async function speak(rawText, options = {}) {
    stop();

    const textToSpeak = prepareText(rawText, options.module || 'general');
    if (!textToSpeak) return false;

    currentController = options.controller || null;
    currentQueueOptions = options;

    activeQueue = splitIntoChunks(textToSpeak, 3200);
    currentQueueIndex = 0;

    runQueue();
    return true;
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
    rec.continuous = false;

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
      } catch (e) {}
      activeRecognition = null;
    }
  }

  // --- UI Component Controller & Factory ---
  function createVoiceBar(config = {}) {
    const container = typeof config.container === 'string' ? document.querySelector(config.container) : config.container;
    if (!container) return null;

    const bar = document.createElement('div');
    bar.className = 'bahoniq-voice-bar';
    bar.setAttribute('role', 'toolbar');
    bar.setAttribute('aria-label', 'Голосовое управление');

    let currentQueueInfo = null;

    // Controller state
    const controller = {
      state: 'stopped',
      onStateChange: (newState, queueInfo = null) => {
        controller.state = newState;
        if (queueInfo) currentQueueInfo = queueInfo;
        updateUI();
      }
    };

    // 1. Speak / Pause Button
    const btnSpeak = document.createElement('button');
    btnSpeak.type = 'button';
    btnSpeak.className = 'bv-btn bv-btn-speak';
    btnSpeak.setAttribute('aria-label', 'Озвучить текст голосом');
    btnSpeak.title = 'Озвучить нейросетевым голосом';

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
      const partStr = currentQueueInfo && currentQueueInfo.total > 1 ? ` (${currentQueueInfo.current}/${currentQueueInfo.total})` : '';

      if (controller.state === 'playing') {
        btnSpeak.innerHTML = `<span>⏸ Пауза${partStr}</span>`;
        btnStop.disabled = false;
      } else if (controller.state === 'paused') {
        btnSpeak.innerHTML = `<span>▶ Продолжить${partStr}</span>`;
        btnStop.disabled = false;
      } else if (controller.state === 'loading') {
        btnSpeak.innerHTML = `<span>⏳ Готовлю голос…${partStr}</span>`;
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

    // 3. Compact Voice Selector (Дмитрий — основной, Светлана)
    const voiceSelect = document.createElement('select');
    voiceSelect.className = 'bv-select bv-voice-select';
    voiceSelect.setAttribute('aria-label', 'Выбор нейроголоса');
    voiceSelect.title = 'Выбор нейросетевого голоса';

    const optDmitry = document.createElement('option');
    optDmitry.value = 'ru-RU-DmitryNeural';
    optDmitry.textContent = '👨 Дмитрий';

    const optSvetlana = document.createElement('option');
    optSvetlana.value = 'ru-RU-SvetlanaNeural';
    optSvetlana.textContent = '👩 Светлана';

    voiceSelect.appendChild(optDmitry);
    voiceSelect.appendChild(optSvetlana);
    voiceSelect.value = getSelectedVoice();

    voiceSelect.onchange = () => {
      setSelectedVoice(voiceSelect.value);
    };

    bar.appendChild(voiceSelect);

    // 4. Compact Speed Selector (0.9x / 1.0x / 1.1x)
    const rateSelect = document.createElement('select');
    rateSelect.className = 'bv-select bv-rate-select';
    rateSelect.setAttribute('aria-label', 'Скорость речи');
    rateSelect.title = 'Скорость речи';

    const opt09 = document.createElement('option');
    opt09.value = '0.9';
    opt09.textContent = '0.9x';

    const opt10 = document.createElement('option');
    opt10.value = '1.0';
    opt10.textContent = '1.0x';

    const opt11 = document.createElement('option');
    opt11.value = '1.1';
    opt11.textContent = '1.1x';

    rateSelect.appendChild(opt09);
    rateSelect.appendChild(opt10);
    rateSelect.appendChild(opt11);
    rateSelect.value = getSelectedRate();

    rateSelect.onchange = () => {
      setSelectedRate(rateSelect.value);
    };

    bar.appendChild(rateSelect);

    // 5. Microphone Button (if input element provided)
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
    getSelectedVoice,
    setSelectedVoice,
    getSelectedRate,
    setSelectedRate,
    startRecognition,
    stopRecognition,
    isSpeechSupported,
    isRecognitionSupported,
    prepareText,
    autoSpeakIfEnabled: () => false, // Auto-speak permanently disabled as per user instruction
    createVoiceBar
  };
})();
