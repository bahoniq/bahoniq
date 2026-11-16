// ============================================================================
// BahonIQ Excel Academy Studio — Professional Spreadsheet Simulator Engine
// Supports: Real Column Resizing, Autofill Drag Handle, Rich Formula Engine,
// Range Selection, Lesson Starter Tables, PWA Offline & Theme Support.
// ============================================================================
(() => {
  'use strict';

  const q = s => document.querySelector(s);
  const qa = s => [...document.querySelectorAll(s)];
  const KEY_PREFIX = 'bahoniq_excel_academy_office_it_v3_';
  const OLD_PROGRESS_KEY = 'bahoniq_excel_academy_done';
  const PROGRESS_KEY = 'bahoniq_excel_academy_progress_v3';
  const MIGRATION_FLAG_KEY = 'bahoniq_excel_academy_progress_reset_2026_11_16';

  // Одноразовая миграция: сброс только прогресса Excel Academy Studio
  (() => {
    try {
      if (!localStorage.getItem(MIGRATION_FLAG_KEY)) {
        localStorage.removeItem(OLD_PROGRESS_KEY);
        localStorage.removeItem('bahoniq_excel_academy_progress');
        localStorage.setItem(PROGRESS_KEY, '[]');
        localStorage.setItem(MIGRATION_FLAG_KEY, '1');
      }
    } catch (e) {
      console.warn('Excel Academy migration notice:', e);
    }
  })();

  function getSavedDone() {
    try {
      const raw = localStorage.getItem(PROGRESS_KEY);
      return new Set(raw ? JSON.parse(raw) : []);
    } catch {
      return new Set();
    }
  }

  // State
  const state = {
    loaded: false,
    course: null,
    stage: 1,
    lesson: null,
    active: 0,
    selected: 'A1',
    selection: { start: 'A1', end: 'A1' },
    isSelecting: false,
    isFilling: false,
    fillTarget: null,
    isResizingCol: false,
    resizingColName: null,
    resizeStartX: 0,
    resizeStartWidth: 96,
    book: null,
    done: getSavedDone(),
    history: [],
    future: []
  };

  const freshBook = () => ({
    name: 'Учебная книга',
    activeSheet: 0,
    sheets: [{ name: 'Лист1', cells: {} }],
    operations: [],
    charts: [],
    pivots: [],
    columnWidths: {}
  });

  state.book = freshBook();

  // API helper
  const api = async (url, opts = {}) => {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Ошибка ' + res.status);
    }
    return res.headers.get('content-type')?.includes('json') ? res.json() : res.blob();
  };

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  // Coordinate utilities
  const colNameToIdx = s => [...s.toUpperCase()].reduce((n, ch) => n * 26 + ch.charCodeAt(0) - 64, 0);
  const colIdxToName = n => {
    let s = '';
    for (; n > 0; n = Math.floor((n - 1) / 26)) {
      s = String.fromCharCode(65 + (n - 1) % 26) + s;
    }
    return s;
  };

  function parseCell(addr) {
    const m = String(addr).toUpperCase().match(/^([A-Z]+)(\d+)$/);
    if (!m) return { col: 'A', row: 1, c: 1, r: 1 };
    return { col: m[1], row: parseInt(m[2], 10), c: colNameToIdx(m[1]), r: parseInt(m[2], 10) };
  }

  function toCell(c, r) {
    return colIdxToName(c) + r;
  }

  function qualifiedRef(ref) {
    const clean = String(ref).trim().replace(/\$/g, '');
    const bang = clean.lastIndexOf('!');
    if (bang < 0) return { sheetIndex: state.active, addr: clean };
    const name = clean.slice(0, bang).replace(/^'|'$/g, '');
    const index = state.book.sheets.findIndex(s => s.name === name);
    return { sheetIndex: index >= 0 ? index : state.active, addr: clean.slice(bang + 1) };
  }

  function evaluateRef(ref, seen = new Set()) {
    const parsed = qualifiedRef(ref), previous = state.active;
    state.active = parsed.sheetIndex;
    try { return evaluateCell(parsed.addr, seen); }
    finally { state.active = previous; }
  }

  function getRangeBounds(cellA, cellB) {
    const p1 = parseCell(cellA);
    const p2 = parseCell(cellB);
    return {
      c1: Math.min(p1.c, p2.c),
      c2: Math.max(p1.c, p2.c),
      r1: Math.min(p1.r, p2.r),
      r2: Math.max(p1.r, p2.r)
    };
  }

  function isCellInRange(addr, start, end) {
    const p = parseCell(addr);
    const b = getRangeBounds(start, end);
    return p.c >= b.c1 && p.c <= b.c2 && p.r >= b.r1 && p.r <= b.r2;
  }

  // Workbook Accessors
  const currentSheet = () => {
    if (!state.book.sheets[state.active]) {
      state.book.sheets[state.active] = { name: 'Лист' + (state.active + 1), cells: {} };
    }
    return state.book.sheets[state.active];
  };

  const getCell = addr => {
    const s = currentSheet();
    s.cells[addr] = s.cells[addr] || { value: '', formula: '', style: {} };
    return s.cells[addr];
  };

  const getRaw = addr => {
    const c = getCell(addr);
    return c.formula || c.value;
  };

  function commit() {
    state.history.push(JSON.stringify(state.book));
    if (state.history.length > 50) state.history.shift();
    state.future = [];
  }

  function save() {
    if (!state.lesson) return;
    state.book.columnWidths = state.book.columnWidths || {};
    localStorage.setItem(KEY_PREFIX + state.lesson.id, JSON.stringify(state.book));
    const st = q('#eaStatus');
    if (st) st.textContent = 'Сохранено в ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function restore() {
    try {
      const rawData = localStorage.getItem(KEY_PREFIX + state.lesson.id);
      if (rawData) {
        state.book = JSON.parse(rawData);
      } else {
        state.book = freshBook();
        applyStarterData(state.lesson.id);
      }
    } catch {
      state.book = freshBook();
      applyStarterData(state.lesson.id);
    }
    state.book.columnWidths = state.book.columnWidths || {};
    state.active = state.book.activeSheet || 0;
    state.history = [JSON.stringify(state.book)];
    state.future = [];
  }

  // ==========================================================================
  // STARTER TEMPLATES FOR LESSONS
  // ==========================================================================
  function applyStarterData(lessonId) {
    const configured = state.lesson?.starter?.sheets;
    if (Array.isArray(configured) && configured.length) {
      state.book.sheets = configured.map(source => {
        const cells = {};
        (source.rows || []).forEach((row, r) => row.forEach((value, col) => {
          if (value === '' || value == null) return;
          cells[toCell(col + 1, r + 1)] = {
            value, formula: '', style: r === 0 ? { bold: true, background: '#123525' } : {}
          };
        }));
        return { name: source.name || 'Лист1', cells };
      });
      state.active = 0;
      state.book.activeSheet = 0;
      state.selected = 'A1';
      state.selection = { start: 'A1', end: 'A1' };
      return;
    }
    const s = currentSheet();
    const set = (addr, val, bold = false) => {
      s.cells[addr] = { value: val, formula: '', style: bold ? { bold: true } : {} };
    };

    switch (lessonId) {
      case '1-1':
        set('A1', 'Привет, Excel!');
        set('A2', 100);
        break;
      case '1-2':
        set('A1', 'Товар', true); set('B1', 'Кол-во', true); set('C1', 'Цена ₸', true);
        set('A2', 'Ноутбук'); set('B2', 5); set('C2', 350000);
        set('A3', 'Мышь'); set('B3', 20); set('C3', 4500);
        break;
      case '1-3':
        set('A1', 'Текст'); set('B1', 250.75); set('C1', '2026-11-16');
        break;
      case '1-6':
        // Автозаполнение: числа 1 и 2 в A1:A2 для протягивания до A5
        set('A1', 1);
        set('A2', 2);
        break;
      case '1-7':
        // Изменение ширины столбца A: длинный текст
        set('A1', 'ТОО «Международная IT Академия BahonIQ Казахстан»');
        set('B1', 1500000);
        break;
      case '2-1':
        set('A1', 150);
        set('A2', 250);
        break;
      case '2-2':
        // SUM
        set('A1', 'Филиал', true); set('B1', 'Выручка', true);
        set('A2', 'Алматы'); set('B2', 12500);
        set('A3', 'Астана'); set('B3', 18300);
        set('A4', 'Шымкент'); set('B4', 9400);
        set('A5', 'Актобе'); set('B5', 14200);
        set('A6', 'ИТОГО:', true);
        break;
      case '2-3':
        // AVERAGE
        set('A1', 'Студент', true); set('C1', 'Балл', true);
        set('A2', 'Азамат'); set('C2', 85);
        set('A3', 'Диана'); set('C3', 92);
        set('A4', 'Ерлан'); set('C4', 78);
        set('A5', 'Мадина'); set('C5', 95);
        set('A6', 'Средний балл:', true);
        break;
      case '2-4':
        // MIN / MAX
        set('C1', 'Товар', true); set('D1', 'Цена', true);
        set('C2', 'Монитор'); set('D2', 120000);
        set('C3', 'Клавиатура'); set('D3', 25000);
        set('C4', 'Мышь'); set('D4', 7500);
        set('C5', 'Ноутбук'); set('D5', 450000);
        set('C6', 'Экстремум:', true);
        break;
      case '2-5':
        // Относительные ссылки (цена * кол-во)
        set('A1', 'Товар', true); set('B1', 'Кол-во', true); set('C1', 'Цена', true); set('D1', 'Сумма', true);
        set('A2', 'Яблоки'); set('B2', 10); set('C2', 500);
        set('A3', 'Груши'); set('B3', 5); set('C3', 800);
        set('A4', 'Бананы'); set('B4', 8); set('C4', 700);
        break;
      case '2-6':
        // Абсолютная ссылка ($)
        set('D1', 'Курс USD', true); set('D2', 500);
        set('A1', 'Товар', true); set('B1', 'Цена $', true); set('C1', 'Цена KZT', true);
        set('A2', 'Книга'); set('B2', 15);
        set('A3', 'Флешка'); set('B3', 25);
        set('A4', 'Наушники'); set('B4', 60);
        break;
      case '2-7':
        // IF
        set('A1', 'Студент', true); set('B1', 'Балл', true); set('C1', 'Результат', true);
        set('A2', 'Асет'); set('B2', 75);
        set('A3', 'Берик'); set('B3', 45);
        set('A4', 'Гульназ'); set('B4', 90);
        set('A5', 'Дастан'); set('B5', 50);
        break;
      case '2-8':
        // COUNTIF
        set('A1', 'Город', true); set('B1', 'Сумма', true);
        set('A2', 'Алматы'); set('B2', 5000);
        set('A3', 'Астана'); set('B3', 7000);
        set('A4', 'Алматы'); set('B4', 3000);
        set('A5', 'Шымкент'); set('B5', 8000);
        set('A6', 'Алматы'); set('B6', 4000);
        break;
      case '2-9':
        // SUMIF
        set('A1', 'Категория', true); set('B1', 'Расход', true);
        set('A2', 'Питание'); set('B2', 4500);
        set('A3', 'Транспорт'); set('B3', 1200);
        set('A4', 'Питание'); set('B4', 6800);
        set('A5', 'Связь'); set('B5', 3000);
        break;
      case '2-10':
        // CONCAT / &
        set('A1', 'Имя', true); set('B1', 'Фамилия', true); set('C1', 'ФИО', true);
        set('A2', 'Арман'); set('B2', 'Абаев');
        set('A3', 'Алия'); set('B3', 'Ибраева');
        set('A4', 'Серик'); set('B4', 'Касымов');
        break;
      case '2-11':
        // LEFT, RIGHT, MID
        set('A1', 'Код документа', true);
        set('A2', 'KZ-ALA-101');
        set('A3', 'KZ-AST-202');
        set('A4', 'KZ-CIT-303');
        break;
      case '3-1':
        // Сортировка
        set('A1', 'Сотрудник', true); set('B1', 'Оклад', true);
        set('A2', 'Яковлев'); set('B2', 320000);
        set('A3', 'Алиев'); set('B3', 450000);
        set('A4', 'Болатов'); set('B4', 280000);
        set('A5', 'Васильев'); set('B5', 510000);
        break;
      case '3-5':
        // Удаление дубликатов
        set('A1', 'Клиент', true); set('B1', 'Телефон', true);
        set('A2', 'Иванов'); set('B2', '77011112233');
        set('A3', 'Петров'); set('B3', '77022223344');
        set('A4', 'Иванов'); set('B4', '77011112233');
        set('A5', 'Сидоров'); set('B5', '77033334455');
        break;
      default:
        break;
    }
  }

  // ==========================================================================
  // FORMULA ENGINE
  // ==========================================================================
  function evaluateCell(addr, seen = new Set()) {
    if (seen.has(addr)) return '#CYCLE!';
    seen.add(addr);

    const c = getCell(addr);
    const f = c.formula;
    if (!f) return c.value;
    if (!f.startsWith('=')) return f;

    try {
      return runFormula(f.slice(1).trim(), seen);
    } catch {
      return '#ERROR!';
    }
  }

  function getRangeValues(ref, seen) {
    const parts = ref.split(':');
    if (parts.length === 1) {
      const val = evaluateRef(parts[0].trim(), seen);
      return [val];
    }
    const first = qualifiedRef(parts[0]), second = qualifiedRef(parts[1]);
    const b = getRangeBounds(first.addr, second.addr);
    const prefix = state.book.sheets[first.sheetIndex]?.name + '!';
    const out = [];
    for (let r = b.r1; r <= b.r2; r++) {
      for (let c = b.c1; c <= b.c2; c++) {
        out.push(evaluateRef(prefix + toCell(c, r), new Set(seen)));
      }
    }
    return out;
  }

  function runFormula(expr, seen) {
    // 1. Check for Top-Level Functions
    const fnMatch = expr.match(/^([A-Z0-9_]+)\s*\((.*)\)$/is);
    if (fnMatch) {
      const name = fnMatch[1].toUpperCase();
      const rawArgs = splitFormulaArgs(fnMatch[2]);

      // SUM
      if (name === 'SUM') {
        const nums = rawArgs.flatMap(a => getRangeValues(a, seen)).map(Number).filter(Number.isFinite);
        return nums.reduce((a, b) => a + b, 0);
      }

      // AVERAGE
      if (name === 'AVERAGE') {
        const nums = rawArgs.flatMap(a => getRangeValues(a, seen)).map(Number).filter(Number.isFinite);
        return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0;
      }

      // MIN & MAX
      if (name === 'MIN') {
        const nums = rawArgs.flatMap(a => getRangeValues(a, seen)).map(Number).filter(Number.isFinite);
        return nums.length ? Math.min(...nums) : 0;
      }
      if (name === 'MAX') {
        const nums = rawArgs.flatMap(a => getRangeValues(a, seen)).map(Number).filter(Number.isFinite);
        return nums.length ? Math.max(...nums) : 0;
      }

      // COUNT & COUNTA
      if (name === 'COUNT') {
        return rawArgs.flatMap(a => getRangeValues(a, seen)).map(Number).filter(Number.isFinite).length;
      }
      if (name === 'COUNTA') {
        return rawArgs.flatMap(a => getRangeValues(a, seen)).filter(x => x !== '' && x != null).length;
      }

      // ROUND, ROUNDUP, ROUNDDOWN
      if (name === 'ROUND') {
        const n = Number(runFormula(rawArgs[0], seen)) || 0;
        const d = Number(rawArgs[1] != null ? runFormula(rawArgs[1], seen) : 0) || 0;
        return Number(n.toFixed(d));
      }

      // IF
      if (name === 'IF') {
        const cond = runFormula(rawArgs[0], seen);
        return cond ? runFormula(rawArgs[1], seen) : (rawArgs[2] != null ? runFormula(rawArgs[2], seen) : false);
      }

      // IFERROR
      if (name === 'IFERROR') {
        try {
          const val = runFormula(rawArgs[0], seen);
          if (String(val).startsWith('#')) return runFormula(rawArgs[1], seen);
          return val;
        } catch {
          return runFormula(rawArgs[1], seen);
        }
      }

      // COUNTIF(range, criteria)
      if (name === 'COUNTIF') {
        const vals = getRangeValues(rawArgs[0], seen);
        let crit = String(runFormula(rawArgs[1], seen)).trim().replace(/^"|"$/g, '');
        return countIfHelper(vals, crit);
      }

      if (name === 'COUNTIFS') {
        const ranges = [], criteria = [];
        for (let i = 0; i < rawArgs.length; i += 2) {
          ranges.push(getRangeValues(rawArgs[i], seen));
          criteria.push(String(runFormula(rawArgs[i + 1], seen)).trim().replace(/^"|"$/g, ''));
        }
        const length = Math.min(...ranges.map(x => x.length));
        let count = 0;
        for (let i = 0; i < length; i++) if (ranges.every((r, n) => matchesCriteria(r[i], criteria[n]))) count++;
        return count;
      }

      // SUMIF(range, criteria, [sum_range])
      if (name === 'SUMIF') {
        const critVals = getRangeValues(rawArgs[0], seen);
        let crit = String(runFormula(rawArgs[1], seen)).trim().replace(/^"|"$/g, '');
        const sumVals = rawArgs[2] ? getRangeValues(rawArgs[2], seen) : critVals;
        let sum = 0;
        for (let i = 0; i < critVals.length; i++) {
          if (matchesCriteria(critVals[i], crit)) {
            sum += Number(sumVals[i]) || 0;
          }
        }
        return sum;
      }

      if (name === 'SUMIFS') {
        const sumValues = getRangeValues(rawArgs[0], seen), ranges = [], criteria = [];
        for (let i = 1; i < rawArgs.length; i += 2) {
          ranges.push(getRangeValues(rawArgs[i], seen));
          criteria.push(String(runFormula(rawArgs[i + 1], seen)).trim().replace(/^"|"$/g, ''));
        }
        return sumValues.reduce((total, value, i) => total + (ranges.every((r, n) => matchesCriteria(r[i], criteria[n])) ? Number(value) || 0 : 0), 0);
      }

      // TEXT FUNCTIONS
      if (name === 'CONCAT' || name === 'CONCATENATE') {
        return rawArgs.map(a => {
          if (a.includes(':')) return getRangeValues(a, seen).join('');
          return runFormula(a, seen);
        }).join('');
      }

      if (name === 'LEFT') {
        const txt = String(runFormula(rawArgs[0], seen));
        const len = Number(rawArgs[1] ? runFormula(rawArgs[1], seen) : 1) || 1;
        return txt.slice(0, len);
      }
      if (name === 'RIGHT') {
        const txt = String(runFormula(rawArgs[0], seen));
        const len = Number(rawArgs[1] ? runFormula(rawArgs[1], seen) : 1) || 1;
        return txt.slice(-len);
      }
      if (name === 'MID') {
        const txt = String(runFormula(rawArgs[0], seen));
        const start = Math.max(1, Number(runFormula(rawArgs[1], seen)) || 1) - 1;
        const len = Number(runFormula(rawArgs[2], seen)) || 0;
        return txt.slice(start, start + len);
      }
      if (name === 'LEN') return String(runFormula(rawArgs[0], seen)).length;
      if (name === 'TRIM') return String(runFormula(rawArgs[0], seen)).trim();
      if (name === 'UPPER') return String(runFormula(rawArgs[0], seen)).toUpperCase();
      if (name === 'LOWER') return String(runFormula(rawArgs[0], seen)).toLowerCase();
      if (name === 'PROPER') {
        return String(runFormula(rawArgs[0], seen)).toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
      }

      // VLOOKUP(lookup_value, table_array, col_index, [range_lookup])
      if (name === 'VLOOKUP') {
        const lookup = String(runFormula(rawArgs[0], seen)).trim();
        const rangeParts = rawArgs[1].split(':');
        const first = qualifiedRef(rangeParts[0]), second = qualifiedRef(rangeParts[1]);
        const b = getRangeBounds(first.addr, second.addr);
        const prefix = state.book.sheets[first.sheetIndex]?.name + '!';
        const targetColIdx = (Number(runFormula(rawArgs[2], seen)) || 1) - 1;
        for (let r = b.r1; r <= b.r2; r++) {
          const firstVal = String(evaluateRef(prefix + toCell(b.c1, r), seen)).trim();
          if (firstVal.toLowerCase() === lookup.toLowerCase()) {
            return evaluateRef(prefix + toCell(b.c1 + targetColIdx, r), seen);
          }
        }
        return '#N/A';
      }

      if (name === 'XLOOKUP') {
        const lookup = String(runFormula(rawArgs[0], seen)).trim().toLowerCase();
        const lookupValues = getRangeValues(rawArgs[1], seen);
        const resultValues = getRangeValues(rawArgs[2], seen);
        const idx = lookupValues.findIndex(x => String(x).trim().toLowerCase() === lookup);
        return idx >= 0 ? resultValues[idx] : (rawArgs[3] ? runFormula(rawArgs[3], seen) : '#N/A');
      }

      if (name === 'MATCH') {
        const lookup = String(runFormula(rawArgs[0], seen)).trim().toLowerCase();
        const items = getRangeValues(rawArgs[1], seen);
        const idx = items.findIndex(x => String(x).trim().toLowerCase() === lookup);
        return idx >= 0 ? idx + 1 : '#N/A';
      }

      if (name === 'INDEX') {
        const items = getRangeValues(rawArgs[0], seen);
        const row = Number(runFormula(rawArgs[1], seen)) || 1;
        return items[row - 1] ?? '#N/A';
      }

      // SUBTOTAL & RANK
      if (name === 'SUBTOTAL') {
        const nums = getRangeValues(rawArgs[1], seen).map(Number).filter(Number.isFinite);
        return nums.reduce((a, b) => a + b, 0);
      }
      if (name === 'RANK') {
        const val = Number(runFormula(rawArgs[0], seen));
        const nums = getRangeValues(rawArgs[1], seen).map(Number).filter(Number.isFinite).sort((a, b) => b - a);
        const idx = nums.indexOf(val);
        return idx >= 0 ? idx + 1 : '#N/A';
      }
    }

    // 2. Handle & String Concatenation
    if (expr.includes('&')) {
      const parts = expr.split('&');
      return parts.map(p => runFormula(p.trim(), seen)).join('');
    }

    // 3. Math Expression with Cell References
    let safe = expr.replace(/\$?([A-Z]+)\$?(\d+)/g, (_, c, r) => {
      const v = evaluateCell(c + r, new Set(seen));
      return typeof v === 'number' ? v : JSON.stringify(v);
    });

    if (!/^[\d\s+\-*/().<>=!"']+$/.test(safe)) {
      return expr;
    }

    try {
      const sanitized = safe.replace(/([^!<>=])=([^=])/g, '$1==$2');
      return Function('"use strict"; return (' + sanitized + ')')();
    } catch {
      return expr;
    }
  }

  function splitFormulaArgs(str) {
    const args = [];
    let cur = '', depth = 0, inQuote = false;
    for (let i = 0; i < str.length; i++) {
      const ch = str[i];
      if (ch === '"' && str[i - 1] !== '\\') inQuote = !inQuote;
      if (!inQuote) {
        if (ch === '(') depth++;
        if (ch === ')') depth--;
        if (ch === ',' && depth === 0) {
          args.push(cur.trim());
          cur = '';
          continue;
        }
      }
      cur += ch;
    }
    if (cur.trim()) args.push(cur.trim());
    return args;
  }

  function matchesCriteria(val, crit) {
    if (crit.startsWith('>=')) return Number(val) >= Number(crit.slice(2));
    if (crit.startsWith('<=')) return Number(val) <= Number(crit.slice(2));
    if (crit.startsWith('<>')) return String(val).toLowerCase() !== crit.slice(2).trim().toLowerCase();
    if (crit.startsWith('>')) return Number(val) > Number(crit.slice(1));
    if (crit.startsWith('<')) return Number(val) < Number(crit.slice(1));
    if (crit.startsWith('=')) return String(val).toLowerCase() === crit.slice(1).trim().toLowerCase();
    return String(val).toLowerCase() === crit.toLowerCase();
  }

  function countIfHelper(vals, crit) {
    return vals.filter(v => matchesCriteria(v, crit)).length;
  }

  // ==========================================================================
  // FORMULA RELATIVE SHIFTER (For Real Autofill Dragging)
  // ==========================================================================
  function shiftFormula(formula, rowDelta, colDelta) {
    if (!formula.startsWith('=')) return formula;
    return '=' + formula.slice(1).replace(/(\$?)([A-Z]+)(\$?)([0-9]+)/g, (match, lockCol, colStr, lockRow, rowStr) => {
      let newCol = colStr;
      let newRow = rowStr;
      if (!lockCol && colDelta !== 0) {
        const cIdx = colNameToIdx(colStr) + colDelta;
        if (cIdx >= 1) newCol = colIdxToName(cIdx);
      }
      if (!lockRow && rowDelta !== 0) {
        const rIdx = parseInt(rowStr, 10) + rowDelta;
        if (rIdx >= 1) newRow = String(rIdx);
      }
      return (lockCol || '') + newCol + (lockRow || '') + newRow;
    });
  }

  // ==========================================================================
  // GRID RENDERING & RESIZING & AUTOFILL
  // ==========================================================================
  const COLS_COUNT = 14;
  const ROWS_COUNT = 40;

  function renderGrid() {
    const table = q('#eaGrid');
    if (!table) return;

    state.book.columnWidths = state.book.columnWidths || {};

    let html = '<colgroup><col style="width:42px">';
    for (let c = 1; c <= COLS_COUNT; c++) {
      const cName = colIdxToName(c);
      const w = state.book.columnWidths[cName] || 96;
      html += `<col class="ea-col-${cName}" style="width:${w}px">`;
    }
    html += '</colgroup>';

    // Thead
    html += '<thead><tr><th class="row-head"></th>';
    for (let c = 1; c <= COLS_COUNT; c++) {
      const cName = colIdxToName(c);
      html += `<th data-col="${cName}">${cName}<div class="ea-col-resizer" data-col="${cName}" title="Потяните для изменения ширины (двойной клик — автоподбор)"></div></th>`;
    }
    html += '</tr></thead><tbody>';

    // Tbody
    const b = getRangeBounds(state.selection.start, state.selection.end);

    for (let r = 1; r <= ROWS_COUNT; r++) {
      html += `<tr><th class="row-head">${r}</th>`;
      for (let c = 1; c <= COLS_COUNT; c++) {
        const addr = toCell(c, r);
        const cellData = getCell(addr);
        const st = cellData.style || {};
        const isSelected = (state.selected === addr);
        const inSelection = (c >= b.c1 && c <= b.c2 && r >= b.r1 && r <= b.r2);

        let styleStr = '';
        if (st.background) styleStr += `background:${st.background};`;
        if (st.color) styleStr += `color:${st.color};`;
        if (st.bold) styleStr += 'font-weight:700;';
        if (st.align) styleStr += `text-align:${st.align};`;

        let classes = [];
        if (isSelected) classes.push('selected');
        if (inSelection) classes.push('ea-in-selection');

        const disp = evaluateCell(addr);
        html += `<td contenteditable data-cell="${addr}" class="${classes.join(' ')}" style="${styleStr}">${esc(disp)}</td>`;
      }
      html += '</tr>';
    }
    table.innerHTML = html + '</tbody>';

    attachGridEvents();
    renderSheets();
    updateStatsBar();
  }

  function attachGridEvents() {
    const table = q('#eaGrid');
    if (!table) return;

    // Attach fill handle to active cell
    const selectedTd = table.querySelector(`[data-cell="${state.selected}"]`);
    if (selectedTd && !selectedTd.querySelector('.ea-fill-handle')) {
      const handle = document.createElement('div');
      handle.className = 'ea-fill-handle';
      handle.title = 'Потяните для автозаполнения (двойной клик — автозаполнение вниз)';
      handle.addEventListener('mousedown', e => {
        e.stopPropagation();
        e.preventDefault();
        startAutofill();
      });
      handle.addEventListener('dblclick', e => {
        e.stopPropagation();
        e.preventDefault();
        autofillDoubleDown();
      });
      selectedTd.appendChild(handle);
    }

    // Cell events
    qa('[data-cell]').forEach(td => {
      const addr = td.dataset.cell;

      td.onmousedown = e => {
        if (e.target.classList.contains('ea-fill-handle')) return;
        state.isSelecting = true;
        select(addr, addr);
      };

      td.onmouseenter = () => {
        if (state.isSelecting) {
          select(state.selection.start, addr);
        } else if (state.isFilling) {
          updateFillPreview(addr);
        }
      };

      td.onfocus = () => {
        select(addr, addr);
      };

      td.onblur = () => {
        const text = td.textContent.trim();
        edit(addr, text);
      };

      td.onkeydown = e => {
        if (e.key === 'Enter') {
          e.preventDefault();
          td.blur();
          const p = parseCell(addr);
          if (p.r < ROWS_COUNT) select(toCell(p.c, p.r + 1));
        } else if (e.key === 'Tab') {
          e.preventDefault();
          td.blur();
          const p = parseCell(addr);
          if (p.c < COLS_COUNT) select(toCell(p.c + 1, p.r));
        }
      };
    });

    // Column resizer events
    qa('.ea-col-resizer').forEach(resizer => {
      const colName = resizer.dataset.col;

      resizer.onmousedown = e => {
        e.stopPropagation();
        e.preventDefault();
        state.isResizingCol = true;
        state.resizingColName = colName;
        state.resizeStartX = e.clientX;
        const curCol = q(`.ea-col-${colName}`);
        state.resizeStartWidth = curCol ? parseInt(curCol.style.width, 10) || 96 : 96;
        resizer.classList.add('resizing');
      };

      resizer.ondblclick = e => {
        e.stopPropagation();
        e.preventDefault();
        autoFitColumn(colName);
      };
    });
  }

  // Global Mouse Handlers for Drag Selection, Resizing & Autofill
  window.addEventListener('mousemove', e => {
    if (state.isResizingCol && state.resizingColName) {
      const delta = e.clientX - state.resizeStartX;
      const newWidth = Math.max(48, Math.min(450, state.resizeStartWidth + delta));
      const curCol = q(`.ea-col-${state.resizingColName}`);
      if (curCol) curCol.style.width = newWidth + 'px';
      state.book.columnWidths[state.resizingColName] = newWidth;
    }
  });

  window.addEventListener('mouseup', () => {
    if (state.isResizingCol) {
      state.isResizingCol = false;
      qa('.ea-col-resizer').forEach(r => r.classList.remove('resizing'));
      if (!state.book.operations.includes('column_width')) state.book.operations.push('column_width');
      save();
      renderGrid();
    }
    if (state.isSelecting) {
      state.isSelecting = false;
    }
    if (state.isFilling) {
      commitAutofill();
      state.isFilling = false;
      state.fillTarget = null;
      qa('.ea-autofill-target').forEach(el => el.classList.remove('ea-autofill-target'));
    }
  });

  function autoFitColumn(colName) {
    const cIdx = colNameToIdx(colName);
    let maxLen = 4;
    for (let r = 1; r <= ROWS_COUNT; r++) {
      const val = evaluateCell(toCell(cIdx, r));
      if (val != null) {
        maxLen = Math.max(maxLen, String(val).length);
      }
    }
    const computed = Math.min(380, Math.max(64, maxLen * 8.5 + 24));
    state.book.columnWidths[colName] = Math.round(computed);
    if (!state.book.operations.includes('column_width')) state.book.operations.push('column_width');
    save();
    renderGrid();
  }

  // Selection
  function select(startAddr, endAddr = null) {
    endAddr = endAddr || startAddr;
    state.selected = startAddr;
    state.selection = { start: startAddr, end: endAddr };

    const nameBox = q('#eaNameBox');
    if (nameBox) {
      nameBox.textContent = (startAddr === endAddr) ? startAddr : `${startAddr}:${endAddr}`;
    }

    const formulaInput = q('#eaFormula');
    if (formulaInput) formulaInput.value = getRaw(startAddr);

    qa('[data-cell]').forEach(td => {
      const a = td.dataset.cell;
      const isLead = (a === startAddr);
      const inBox = isCellInRange(a, startAddr, endAddr);
      td.classList.toggle('selected', isLead);
      td.classList.toggle('ea-in-selection', inBox);
    });

    updateStatsBar();
  }

  function updateStatsBar() {
    const b = getRangeBounds(state.selection.start, state.selection.end);
    let count = 0, sum = 0, numCount = 0;

    for (let r = b.r1; r <= b.r2; r++) {
      for (let c = b.c1; c <= b.c2; c++) {
        count++;
        const val = evaluateCell(toCell(c, r));
        const num = Number(val);
        if (Number.isFinite(num) && val !== '' && val != null) {
          sum += num;
          numCount++;
        }
      }
    }

    const avg = numCount ? (sum / numCount).toFixed(2).replace(/\.00$/, '') : 0;
    const cEl = q('#eaStatCount'); if (cEl) cEl.textContent = count;
    const sEl = q('#eaStatSum'); if (sEl) sEl.textContent = sum;
    const aEl = q('#eaStatAvg'); if (aEl) aEl.textContent = avg;
  }

  function edit(addr, text) {
    commit();
    const c = getCell(addr);
    if (String(text).startsWith('=')) {
      c.formula = text;
      c.value = '';
    } else {
      c.value = /^-?\d+(\.\d+)?$/.test(text) ? Number(text) : text;
      c.formula = '';
    }
    save();
    renderGrid();
  }

  // ==========================================================================
  // SMART AUTOFILL ENGINE
  // ==========================================================================
  function startAutofill() {
    state.isFilling = true;
    state.fillTarget = state.selected;
  }

  function updateFillPreview(hoverAddr) {
    state.fillTarget = hoverAddr;
    qa('.ea-autofill-target').forEach(el => el.classList.remove('ea-autofill-target'));

    const b = getRangeBounds(state.selection.start, hoverAddr);
    qa('[data-cell]').forEach(td => {
      const a = td.dataset.cell;
      if (isCellInRange(a, toCell(b.c1, b.r1), toCell(b.c2, b.r2))) {
        td.classList.add('ea-autofill-target');
      }
    });
  }

  function commitAutofill() {
    if (!state.fillTarget) return;

    commit();
    const srcBounds = getRangeBounds(state.selection.start, state.selection.end);
    const tgtBounds = getRangeBounds(state.selection.start, state.fillTarget);

    // Vertical autofill down
    if (tgtBounds.r2 > srcBounds.r2) {
      for (let c = srcBounds.c1; c <= srcBounds.c2; c++) {
        const srcCells = [];
        for (let r = srcBounds.r1; r <= srcBounds.r2; r++) {
          srcCells.push({ addr: toCell(c, r), raw: getRaw(toCell(c, r)), val: evaluateCell(toCell(c, r)) });
        }

        const isAllNumbers = srcCells.every(x => typeof x.val === 'number' || /^-?\d+(\.\d+)?$/.test(x.val));
        let step = 1;
        if (isAllNumbers && srcCells.length >= 2) {
          step = (Number(srcCells.at(-1).val) - Number(srcCells[0].val)) / (srcCells.length - 1);
        }

        for (let r = srcBounds.r2 + 1; r <= tgtBounds.r2; r++) {
          const targetAddr = toCell(c, r);
          const targetCell = getCell(targetAddr);
          const idxOffset = r - srcBounds.r2;

          if (srcCells.length === 1 && String(srcCells[0].raw).startsWith('=')) {
            targetCell.formula = shiftFormula(srcCells[0].raw, idxOffset, 0);
            targetCell.value = '';
          } else if (isAllNumbers) {
            const baseVal = Number(srcCells.at(-1).val);
            targetCell.value = baseVal + step * idxOffset;
            targetCell.formula = '';
          } else {
            const srcItem = srcCells[(idxOffset - 1) % srcCells.length];
            if (String(srcItem.raw).startsWith('=')) {
              targetCell.formula = shiftFormula(srcItem.raw, idxOffset, 0);
              targetCell.value = '';
            } else {
              targetCell.value = srcItem.val;
              targetCell.formula = '';
            }
          }
        }
      }
    }

    // Horizontal autofill right
    if (tgtBounds.c2 > srcBounds.c2) {
      for (let r = srcBounds.r1; r <= srcBounds.r2; r++) {
        const srcCells = [];
        for (let c = srcBounds.c1; c <= srcBounds.c2; c++) {
          srcCells.push({ addr: toCell(c, r), raw: getRaw(toCell(c, r)), val: evaluateCell(toCell(c, r)) });
        }
        for (let c = srcBounds.c2 + 1; c <= tgtBounds.c2; c++) {
          const targetAddr = toCell(c, r);
          const targetCell = getCell(targetAddr);
          const colOffset = c - srcBounds.c2;
          const srcItem = srcCells[(colOffset - 1) % srcCells.length];
          if (String(srcItem.raw).startsWith('=')) {
            targetCell.formula = shiftFormula(srcItem.raw, 0, colOffset);
            targetCell.value = '';
          } else {
            targetCell.value = srcItem.val;
            targetCell.formula = '';
          }
        }
      }
    }

    if (!state.book.operations.includes('autofill')) state.book.operations.push('autofill');
    if (!state.book.operations.includes('sequence')) state.book.operations.push('sequence');
    select(toCell(tgtBounds.c1, tgtBounds.r1), toCell(tgtBounds.c2, tgtBounds.r2));
    save();
    renderGrid();
  }

  function autofillDoubleDown() {
    const curP = parseCell(state.selected);
    let leftC = curP.c > 1 ? curP.c - 1 : curP.c + 1;
    let maxRow = curP.r;
    for (let r = curP.r; r <= ROWS_COUNT; r++) {
      if (evaluateCell(toCell(leftC, r)) !== '' && evaluateCell(toCell(leftC, r)) != null) {
        maxRow = r;
      } else {
        break;
      }
    }
    if (maxRow > curP.r) {
      state.fillTarget = toCell(curP.c, maxRow);
      commitAutofill();
    }
  }

  // Sheets & Styles & Operations
  function renderSheets() {
    const cont = q('#eaSheetTabs');
    if (!cont) return;
    cont.innerHTML = state.book.sheets.map((s, i) =>
      `<button class="${i === state.active ? 'active' : ''}" data-sheet="${i}">${esc(s.name)}</button>`
    ).join('');

    qa('[data-sheet]').forEach(b => {
      b.onclick = () => {
        state.active = +b.dataset.sheet;
        state.book.activeSheet = state.active;
        renderGrid();
      };
      b.ondblclick = () => {
        const item = state.book.sheets[+b.dataset.sheet];
        const name = prompt('Название листа', item.name)?.trim();
        if (name && !state.book.sheets.some((s, i) => s.name === name && i !== +b.dataset.sheet)) {
          commit(); item.name = name.slice(0, 31); renderSheets(); save();
        }
      };
    });
  }

  function addSheet() {
    commit();
    const fallback = 'Лист' + (state.book.sheets.length + 1);
    const requested = prompt('Название нового листа', fallback)?.trim() || fallback;
    const name = state.book.sheets.some(s => s.name === requested) ? fallback : requested.slice(0, 31);
    state.book.sheets.push({ name, cells: {} });
    state.active = state.book.sheets.length - 1;
    state.book.activeSheet = state.active;
    renderGrid();
    save();
  }

  function applyStyle(key, value) {
    commit();
    const b = getRangeBounds(state.selection.start, state.selection.end);
    for (let r = b.r1; r <= b.r2; r++) {
      for (let c = b.c1; c <= b.c2; c++) {
        const cellData = getCell(toCell(c, r));
        cellData.style = { ...(cellData.style || {}), [key]: value };
      }
    }
    if (!state.book.operations.includes('format')) state.book.operations.push('format');
    renderGrid();
    save();
  }

  function runOperation(name) {
    commit();
    const s = currentSheet();
    const entries = Object.entries(s.cells);

    if (name === 'sort') {
      const used = entries.map(([a]) => parseCell(a));
      const maxRow = Math.max(1, ...used.map(x => x.r)), maxCol = Math.max(1, ...used.map(x => x.c));
      const rows = [];
      for (let r = 2; r <= maxRow; r++) rows.push(Array.from({ length: maxCol }, (_, i) => structuredClone(getCell(toCell(i + 1, r)))));
      rows.sort((a, b) => String(a[0].value).localeCompare(String(b[0].value), 'ru', { numeric: true }));
      rows.forEach((row, i) => row.forEach((value, j) => { s.cells[toCell(j + 1, i + 2)] = value; }));
      mentor('Строки таблицы отсортированы по первому столбцу; заголовок сохранён.');
    }
    if (name === 'deduplicate') {
      const used = entries.map(([a]) => parseCell(a));
      const maxRow = Math.max(1, ...used.map(x => x.r)), maxCol = Math.max(1, ...used.map(x => x.c));
      const seen = new Set(); let delCount = 0;
      for (let r = 2; r <= maxRow; r++) {
        const signature = Array.from({ length: maxCol }, (_, i) => String(getRaw(toCell(i + 1, r))).trim().toLowerCase()).join('\u241f');
        if (signature && seen.has(signature)) {
          for (let col = 1; col <= maxCol; col++) delete s.cells[toCell(col, r)];
          delCount++;
        } else if (signature) seen.add(signature);
      }
      mentor(`Удалено полностью повторяющихся строк: ${delCount}.`);
    }
    if (name === 'remove_blanks') {
      let delCount = 0;
      for (const [addr, c] of entries) {
        if (c.value === '' || c.value == null) {
          delete s.cells[addr];
          delCount++;
        }
      }
      mentor(`Очищено пустых ячеек: ${delCount}.`);
    }
    if (name === 'replace') {
      const from = prompt('Что заменить?');
      if (from != null) {
        const to = prompt('На что заменить?', '') || '';
        for (const c of Object.values(s.cells)) {
          c.value = String(c.value).replaceAll(from, to);
        }
        mentor(`Заменено: «${from}» → «${to}».`);
      }
    }
    if (name === 'filter') {
      q('#eaGrid')?.classList.toggle('filtered');
      mentor('Режим фильтра переключен.');
    }
    if (name === 'conditional') {
      const b = getRangeBounds(state.selection.start, state.selection.end);
      for (let r = b.r1; r <= b.r2; r++) for (let c = b.c1; c <= b.c2; c++) {
        const item = getCell(toCell(c, r));
        item.style = { ...(item.style || {}), background: item.value in { '': 1, null: 1 } ? '#7f1d1d' : '#14532d' };
      }
      mentor('Условное оформление применено к выбранному диапазону.');
    }

    if (!state.book.operations.includes(name)) state.book.operations.push(name);
    renderGrid();
    save();
  }

  function createChart(type) {
    const s = currentSheet();
    const values = Object.entries(s.cells)
      .filter(([, c]) => typeof c.value === 'number')
      .slice(0, 12)
      .map(([label, c]) => ({ label, value: c.value }));

    state.book.charts.push({
      type,
      title: 'Диаграмма ' + (state.book.charts.length + 1),
      data: values.length ? values : [{ label: 'A', value: 10 }, { label: 'B', value: 25 }, { label: 'C', value: 18 }]
    });

    if (!state.book.operations.includes('chart')) state.book.operations.push('chart');
    showChartModal(state.book.charts.at(-1));
    save();
  }

  function showChartModal(ch) {
    const modal = q('#eaChartModal');
    if (!modal) return;
    modal.classList.add('open');
    q('#eaChartTitle').textContent = ch.title;
    const max = Math.max(1, ...ch.data.map(x => Math.abs(x.value)));
    const view = q('#eaChartView');
    view.className = 'ea-chart-view ' + ch.type;
    view.innerHTML = ch.type === 'pie' ? '' : ch.data.map(x =>
      `<i title="${esc(x.label)}: ${x.value}" style="height:${Math.max(8, Math.abs(x.value) / max * 260)}px"></i>`
    ).join('');
  }

  function createPivot() {
    const vals = {};
    for (const [addr, c] of Object.entries(currentSheet().cells)) {
      const r = addr.match(/\d+/)[0];
      if (addr.startsWith('A') && c.value) {
        vals[c.value] = (vals[c.value] || 0) + (Number(getCell('B' + r).value) || 0);
      }
    }
    state.book.pivots.push({ fields: ['A', 'B'], values: vals });
    if (!state.book.operations.includes('pivot')) state.book.operations.push('pivot');
    mentor('Сводная таблица сформирована: ' + Object.entries(vals).map(x => x.join(' — ')).join(', '));
    save();
  }

  // Stages & Lessons UI
  function renderStages() {
    q('#eaStages').innerHTML = state.course.stages.map(s =>
      `<button class="ea-stage ${s.id === state.stage ? 'active' : ''}" data-stage="${s.id}">
        <small>ЭТАП ${s.id}</small>
        <b>${esc(s.title)}</b>
        <span>${esc(s.subtitle)} · ${s.lessons}</span>
      </button>`
    ).join('');

    qa('[data-stage]').forEach(b => {
      b.onclick = () => {
        state.stage = +b.dataset.stage;
        renderStages();
        renderLessons();
        const first = state.course.lessons.find(x => x.stage_id === state.stage);
        if (first) openLesson(first.id);
      };
    });
  }

  function renderLessons(filter = '') {
    const list = state.course.lessons.filter(x =>
      x.stage_id === state.stage && (!filter || x.title.toLowerCase().includes(filter.toLowerCase()))
    );

    q('#eaLessons').innerHTML = list.map(x =>
      `<button class="ea-lesson ${state.lesson?.id === x.id ? 'active' : ''} ${state.done.has(x.id) ? 'done' : ''}" data-lesson="${x.id}">
        <i>${state.done.has(x.id) ? '✓' : x.number}</i>
        ${esc(x.title)}
      </button>`
    ).join('');

    qa('[data-lesson]').forEach(b => b.onclick = () => openLesson(b.dataset.lesson));
    const st = state.course.stages.find(x => x.id === state.stage);
    q('#eaStageLabel').textContent = 'ЭТАП ' + state.stage;
    q('#eaStageCount').textContent = `${[...state.done].filter(x => x.startsWith(state.stage + '-')).length}/${st?.lessons || 12}`;
  }

  function openLesson(id) {
    state.lesson = state.course.lessons.find(x => x.id === id);
    if (!state.lesson) return;
    state.stage = state.lesson.stage_id;
    restore();

    q('#eaBadge').textContent = `ЭТАП ${state.stage} · УРОК ${state.lesson.number} · ${state.lesson.level || 'Практика'}`;
    q('#eaTitle').textContent = state.lesson.title;
    q('#eaSummary').textContent = state.lesson.summary;
    q('#eaTheory').textContent = state.lesson.theory;
    q('#eaTask').textContent = state.lesson.task;
    q('#eaSteps').innerHTML = state.lesson.steps.map(x => `<li>${esc(x)}</li>`).join('');
    q('#eaMentorFeed').innerHTML = '<p>ИИ-наставник видит вашу рабочую книгу, формулы и действия. Начните выполнять шаг за шагом!</p>';

    window.BahonIQVoice?.stop();
    renderLessons();
    renderGrid();
    setStep('learn');
  }

  function resetCurrentLesson() {
    if (!confirm('Сбросить рабочую книгу к начальным данным урока?')) return;
    localStorage.removeItem(KEY_PREFIX + state.lesson.id);
    restore();
    renderGrid();
    mentor('Таблица сброшена к исходным данным урока.');
  }

  function setStep(x) {
    qa('[data-ea-step]').forEach(b => b.classList.toggle('active', b.dataset.eaStep === x));
    q('#eaLearn').classList.toggle('hidden', x !== 'learn');
    q('#eaEditor').classList.toggle('hidden', x !== 'practice');
    q('#eaReview').classList.toggle('hidden', x !== 'review');
  }

  async function validate() {
    const d = await api('/api/excel-academy/validate/' + state.lesson.id, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workbook: state.book })
    });

    q('#eaScore').textContent = d.score + '%';
    q('#eaResults').innerHTML = d.results.map(x =>
      `<div class="${x.passed ? 'ok' : ''}">${x.passed ? '✓' : '○'} ${esc(x.message)}</div>`
    ).join('');

    q('#eaComplete').classList.toggle('hidden', !d.passed);
    setStep('review');
    mentor(d.passed ? 'Отлично! Задание выполнено верно. Нажмите «Завершить урок».' : 'Не все пункты выполнены. Нажмите «Вернуться к таблице» и исправьте.');
  }

  function mentor(t) {
    q('#eaMentorFeed')?.insertAdjacentHTML('beforeend', `<p>${esc(t)}</p>`);
    const f = q('#eaMentorFeed');
    if (f) f.scrollTop = f.scrollHeight;
  }

  async function ask() {
    const question = q('#eaQuestion').value.trim();
    if (!question) return;
    const d = await api('/api/excel-academy/mentor/' + state.lesson.id, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, workbook: state.book })
    });
    mentor(d.answer);
    q('#eaQuestion').value = '';
  }

  function complete() {
    state.done.add(state.lesson.id);
    localStorage.setItem(PROGRESS_KEY, JSON.stringify([...state.done]));
    updateProgress();
    renderLessons();

    const i = state.course.lessons.findIndex(x => x.id === state.lesson.id);
    const n = state.course.lessons[i + 1];
    if (n) {
      state.stage = n.stage_id;
      renderStages();
      openLesson(n.id);
    }
  }

  function resetCourseProgress() {
    if (!confirm('Сбросить весь прогресс Excel Academy? Это действие нельзя отменить.')) {
      return;
    }
    state.done.clear();
    try {
      localStorage.setItem(PROGRESS_KEY, '[]');
      localStorage.removeItem(OLD_PROGRESS_KEY);
      localStorage.removeItem('bahoniq_excel_academy_progress');
      if (state.course && Array.isArray(state.course.lessons)) {
        state.course.lessons.forEach(l => {
          localStorage.removeItem(KEY_PREFIX + l.id);
        });
      }
    } catch (e) {
      console.warn('Failed to clear Excel Academy progress:', e);
    }
    state.stage = 1;
    updateProgress();
    renderStages();
    renderLessons();
    openLesson('1-1');
  }

  function updateProgress() {
    const n = state.done.size;
    const p = Math.round(n / 72 * 100);
    q('#eaProgressText').textContent = `${n} / 72 (${p}%)`;
    q('#eaProgressFill').style.width = p + '%';
  }

  async function importXlsx(file) {
    const fd = new FormData();
    fd.append('file', file);
    state.book = await api('/api/excel-academy/import', { method: 'POST', body: fd });
    state.active = 0;
    renderGrid();
    save();
  }

  async function exportXlsx() {
    const blob = await api('/api/excel-academy/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workbook: state.book })
    });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${state.lesson?.title || 'Excel_Academy'}.xlsx`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 500);
  }

  // Bind UI Controls
  function bind() {
    q('#eaStart').onclick = () => setStep('practice');
    qa('[data-ea-step]').forEach(b => b.onclick = () => setStep(b.dataset.eaStep));

    q('#eaFormula').onkeydown = e => {
      if (e.key === 'Enter') {
        edit(state.selected, e.target.value);
        q('#eaGrid')?.focus();
      }
    };

    q('#eaAddSheet').onclick = addSheet;
    q('#eaBold').onclick = () => applyStyle('bold', !getCell(state.selected).style?.bold);
    q('#eaCenter').onclick = () => applyStyle('align', 'center');
    q('#eaMoney').onclick = () => applyStyle('format', 'currency');
    q('#eaFill').onchange = e => applyStyle('background', e.target.value);

    qa('[data-ea-op]').forEach(b => b.onclick = () => runOperation(b.dataset.eaOp));
    qa('[data-ea-chart]').forEach(b => b.onclick = () => createChart(b.dataset.eaChart));
    q('#eaPivot').onclick = createPivot;

    q('#eaValidate').onclick = validate;
    q('#eaBack').onclick = () => setStep('practice');
    q('#eaComplete').onclick = complete;
    q('#eaAsk').onclick = ask;
    q('#eaSearch').oninput = e => renderLessons(e.target.value);

    q('#eaResetLesson') && (q('#eaResetLesson').onclick = resetCurrentLesson);
    q('#eaResetProgressBtn') && (q('#eaResetProgressBtn').onclick = resetCourseProgress);

    q('#eaImport').onchange = e => e.target.files[0] && importXlsx(e.target.files[0]);
    q('#eaExport').onclick = exportXlsx;
    q('#eaChartClose').onclick = () => q('#eaChartModal')?.classList.remove('open');

    // BahonIQ Voice v1 — Mentor Voice Bar & Microphone Dictation
    let eaMentorVoice = q('#eaMentorVoiceBar');
    if (!eaMentorVoice && q('#eaQuestion')) {
      eaMentorVoice = document.createElement('div');
      eaMentorVoice.id = 'eaMentorVoiceBar';
      q('#eaQuestion').insertAdjacentElement('beforebegin', eaMentorVoice);
      window.BahonIQVoice?.createVoiceBar({
        container: eaMentorVoice,
        moduleId: 'excel',
        inputEl: '#eaQuestion',
        labelText: 'Озвучить объяснение',
        getText: () => {
          const pList = qa('#eaMentorFeed p');
          return pList.length ? pList[pList.length - 1].textContent : '';
        }
      });
    }
  }

  // Initial loader
  window.loadExcelAcademy = async () => {
    if (state.loaded) return;
    try {
      state.course = await api('/api/excel-academy/curriculum');
      bind();
      renderStages();
      updateProgress();
      openLesson('1-1');
      state.loaded = true;
    } catch (err) {
      console.error('Failed to load Excel Academy:', err);
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelector('[data-open="excelAcademy"]')?.addEventListener('click', () => {
      setTimeout(window.loadExcelAcademy, 0);
    });
  });
})();
