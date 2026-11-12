"""Shared Tk editor; tokenisation is independent of the GUI and testable."""
import builtins
import io
import keyword
import re
import tokenize
import tkinter as tk

SQL_WORDS = set('SELECT FROM WHERE JOIN LEFT RIGHT INNER OUTER ON AS AND OR NOT NULL IS IN BETWEEN LIKE GROUP BY HAVING ORDER ASC DESC LIMIT DISTINCT COUNT SUM AVG MIN MAX INSERT INTO VALUES UPDATE SET DELETE CREATE TABLE VIEW INDEX TRIGGER PRIMARY KEY FOREIGN REFERENCES UNIQUE CHECK DEFAULT WITH RECURSIVE UNION ALL INTERSECT EXCEPT CASE WHEN THEN ELSE END OVER PARTITION ROW_NUMBER RANK LAG BEGIN COMMIT ROLLBACK PRAGMA'.split())


def syntax_tokens(code, language='python'):
    """Return (tag, start offset, end offset), including unfinished buffers."""
    if language not in {'python','sql','json'}: return []
    if language == 'python':
        lines = code.splitlines(keepends=True)
        offsets = [0]
        for line in lines: offsets.append(offsets[-1] + len(line))
        def offset(pos):
            row, col = pos
            return offsets[min(row-1, len(offsets)-1)] + col
        result = []
        try:
            for item in tokenize.generate_tokens(io.StringIO(code).readline):
                tag = None
                if item.type == tokenize.STRING: tag = 'string'
                elif item.type == tokenize.COMMENT: tag = 'comment'
                elif item.type == tokenize.NUMBER: tag = 'number'
                elif item.type == tokenize.NAME:
                    if keyword.iskeyword(item.string): tag = 'keyword'
                    elif hasattr(builtins, item.string): tag = 'builtin'
                if tag: result.append((tag, offset(item.start), offset(item.end)))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
        return result
    pattern = r"--[^\n]*|/\*[\s\S]*?(?:\*/|$)|'(?:''|[^'])*'|\"(?:\\.|[^\"\\])*\"|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]+\b"
    result = []
    for m in re.finditer(pattern, code):
        value = m.group()
        if value.startswith(('--', '/*')): tag = 'comment'
        elif value.startswith(('"', "'")): tag = 'string'
        elif value[0].isdigit(): tag = 'number'
        elif language == 'sql' and value.upper() in SQL_WORDS: tag = 'keyword'
        elif language == 'json' and value in {'true', 'false', 'null'}: tag = 'keyword'
        else: continue
        result.append((tag, m.start(), m.end()))
    return result


def indent_for(line):
    leading = re.match(r'[ \t]*', line)[0].replace('\t', '    ')
    return leading + ('    ' if line.rstrip().endswith(':') else '')


class CodeEditor(tk.Text):
    COLORS = {'keyword': '#C792EA', 'builtin': '#82AAFF', 'string': '#C3E88D',
              'number': '#F78C6C', 'comment': '#81948B'}

    def __init__(self, master, language='python', **kwargs):
        kwargs.setdefault('undo', True)
        kwargs.setdefault('wrap', 'none')
        kwargs.setdefault('font', ('Consolas', 11))
        kwargs.setdefault('bg', '#10221B'); kwargs.setdefault('fg', '#E8F5EE')
        kwargs.setdefault('insertbackground', 'white')
        kwargs['padx'] = 58
        super().__init__(master, **kwargs)
        self.language = language
        self._pending = None
        self._initial = None
        self._popup = None
        self._external_scroll = None
        # A child placed inside Text uses its padded content origin on Tk.
        # Keep the gutter as a sibling, in the reserved left padding instead.
        self.gutter = tk.Canvas(master, width=47, bg='#172C27', highlightthickness=0)
        for tag, color in self.COLORS.items(): self.tag_configure(tag, foreground=color)
        self.tag_configure('bracket', background='#38664C', foreground='white')
        super().configure(yscrollcommand=self._scrolled)
        self.bind('<<Modified>>', self._modified, add='+')
        self.bind('<Configure>', lambda e: self._redraw(), add='+')
        self.bind('<Map>', lambda e: self._redraw(), add='+')
        self.bind('<Unmap>', lambda e: self.gutter.place_forget(), add='+')
        self.bind('<KeyRelease>', lambda e: self._brackets(), add='+')
        self.bind('<ButtonRelease-1>', lambda e: self._brackets(), add='+')
        self.bind('<Return>', self._newline)
        self.bind('<Tab>', self._tab)
        self.bind('<Control-space>', self._complete)
        self.bind('<Control-a>', self._select_all)
        self.bind('<Control-A>', self._select_all)
        self.menu = tk.Menu(self, tearoff=False)
        for label, event in [('Копировать', '<<Copy>>'), ('Вырезать', '<<Cut>>'), ('Вставить', '<<Paste>>'),
                             ('Отменить', '<<Undo>>'), ('Повторить', '<<Redo>>')]:
            self.menu.add_command(label=label, command=lambda ev=event: self.event_generate(ev))
        self.menu.add_separator(); self.menu.add_command(label='Выделить всё', command=self._select_all)
        self.bind('<Button-3>', self._menu)
        self.bind('<Destroy>', self._destroy, add='+')
        self._initial = self.after_idle(self.refresh)

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict): kwargs = dict(cnf, **kwargs); cnf = None
        if 'yscrollcommand' in kwargs and hasattr(self, 'gutter'):
            self._external_scroll = kwargs.pop('yscrollcommand')
        return super().configure(cnf, **kwargs)

    config = configure

    def set_language(self, name):
        suffix = name.rsplit('.', 1)[-1].lower()
        self.language = {'py': 'python', 'python': 'python', 'sql': 'sql', 'json': 'json'}.get(suffix, 'plain')
        self.refresh()

    def _scrolled(self, first, last):
        if self._external_scroll:
            if callable(self._external_scroll): self._external_scroll(first, last)
            else: self.tk.call(self._external_scroll, first, last)
        self._redraw()

    def _modified(self, event=None):
        if not self.edit_modified(): return
        self.edit_modified(False)
        if self._pending: self.after_cancel(self._pending)
        self._pending = self.after(120, self.refresh)

    def refresh(self):
        self._initial = None
        self._pending = None
        if not self.winfo_exists(): return
        code = self.get('1.0', 'end-1c')
        for tag in self.COLORS: self.tag_remove(tag, '1.0', 'end')
        # Bound editor work for large source files.
        if len(code) <= 200_000:
            for tag, start, end in syntax_tokens(code, self.language):
                self.tag_add(tag, f'1.0+{start}c', f'1.0+{end}c')
        self.tag_raise('sel'); self._redraw()

    def _redraw(self):
        if not hasattr(self, 'gutter') or not self.winfo_exists(): return
        if not self.winfo_ismapped():
            self.gutter.place_forget();return
        self.gutter.place(x=self.winfo_x()+2, y=self.winfo_y()+2,
                          width=47, height=max(1,self.winfo_height()-4))
        tk.Misc.tkraise(self.gutter)
        self.gutter.delete('all')
        index = self.index('@0,0')
        while True:
            info = self.dlineinfo(index)
            if info is None: break
            self.gutter.create_text(40, info[1]-2, anchor='ne', text=index.split('.')[0],
                                    fill='#91AA9C', font=self.cget('font'))
            next_index = self.index(index + '+1line')
            if self.compare(next_index, '<=', index) or self.compare(next_index, '>=', 'end'):break
            index = next_index

    def _newline(self, event=None):
        if self.cget('state') == 'disabled': return 'break'
        if self.tag_ranges('sel'): self.delete('sel.first', 'sel.last')
        line = self.get('insert linestart', 'insert')
        self.insert('insert', '\n' + (indent_for(line) if self.language == 'python' else ''))
        self.see('insert'); return 'break'

    def _tab(self, event=None):
        if self.cget('state') != 'disabled': self.insert('insert', '    ')
        return 'break'

    def _select_all(self, event=None):
        self.tag_add('sel', '1.0', 'end-1c'); return 'break'

    def _menu(self, event):
        try: self.menu.tk_popup(event.x_root, event.y_root)
        finally: self.menu.grab_release()
        return 'break'

    def _brackets(self):
        self.tag_remove('bracket', '1.0', 'end')
        code = self.get('1.0', 'end-1c')
        if len(code) > 200_000: return
        pos = len(self.get('1.0', 'insert')) - 1
        if pos < 0 or code[pos:pos+1] not in '()[]{}': return
        ignored = [(a,b) for tag,a,b in syntax_tokens(code, self.language) if tag in {'string','comment'}]
        skip = lambda n: any(a <= n < b for a,b in ignored)
        if skip(pos): return
        pairs = {'(': ')', '[': ']', '{': '}'}
        char = code[pos]; forward = char in pairs
        target = pairs[char] if forward else next(k for k,v in pairs.items() if v == char)
        depth = 0
        for n in range(pos, len(code) if forward else -1, 1 if forward else -1):
            if skip(n): continue
            if code[n] == char: depth += 1
            elif code[n] == target:
                depth -= 1
                if depth == 0:
                    for x in (pos,n): self.tag_add('bracket', f'1.0+{x}c', f'1.0+{x+1}c')
                    break

    def _complete(self, event=None):
        if self.cget('state') == 'disabled': return 'break'
        code = self.get('1.0', 'insert'); match = re.search(r'\w+$', code)
        prefix = match[0] if match else ''
        vocabulary = (set(keyword.kwlist) | set(dir(builtins)) if self.language == 'python' else SQL_WORDS)
        vocabulary |= set(re.findall(r'\b[A-Za-z_]\w*\b', self.get('1.0','end-1c')))
        options = sorted(w for w in vocabulary if w.lower().startswith(prefix.lower()) and w != prefix)[:20]
        if not options: return 'break'
        if self._popup and self._popup.winfo_exists(): self._popup.destroy()
        popup = tk.Toplevel(self); self._popup = popup; popup.overrideredirect(True)
        x,y,_,height = self.bbox('insert') or (0,0,0,15)
        popup.geometry(f'+{self.winfo_rootx()+x}+{self.winfo_rooty()+y+height}')
        listing = tk.Listbox(popup, height=min(8,len(options)), exportselection=False)
        listing.pack()
        for word in options: listing.insert('end',word)
        listing.selection_set(0); listing.focus_set()
        def accept(e=None):
            if listing.curselection():
                self.delete(f'insert-{len(prefix)}c','insert'); self.insert('insert',listing.get(listing.curselection()[0]))
            popup.destroy(); self._popup = None; self.focus_set(); return 'break'
        listing.bind('<Return>',accept); listing.bind('<Double-Button-1>',accept)
        listing.bind('<Escape>',lambda e:(popup.destroy(),self.focus_set()))
        popup.bind('<FocusOut>',lambda e: popup.destroy())
        return 'break'

    def _destroy(self, event):
        if event.widget is self:
            for job in (self._pending,self._initial):
                if job:self.after_cancel(job)
            self._pending = self._initial = None
            if self.gutter.winfo_exists():self.gutter.destroy()
