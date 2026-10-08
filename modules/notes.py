import tkinter as tk
from tkinter import messagebox

from config import NOTES_FILE
from services.settings_service import get_theme


# ============================================================
# BAHONIQ — NOTES
# ============================================================

class NotesWindow:

    def __init__(self, parent):

        self.parent = parent

        self.window = tk.Toplevel(
            parent
        )

        self.window.title(
            "BahonIQ — Заметки"
        )

        self.window.geometry(
            "850x650"
        )

        self.window.minsize(
            600,
            450
        )

        self.window.transient(
            parent
        )

        # Чтобы не запускать сохранение после закрытия
        self.closing = False

        # ID таймера автосохранения
        self.autosave_id = None


        # ----------------------------------------------------
        # THEME
        # ----------------------------------------------------

        self.theme = get_theme()


        # ----------------------------------------------------
        # BUILD
        # ----------------------------------------------------

        self.build()


        # ----------------------------------------------------
        # LOAD
        # ----------------------------------------------------

        self.load_notes()


        # ----------------------------------------------------
        # CLOSE EVENT
        # ----------------------------------------------------

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.close_window
        )


        # ----------------------------------------------------
        # AUTOSAVE
        # ----------------------------------------------------

        self.autosave()


        # ----------------------------------------------------
        # FOCUS
        # ----------------------------------------------------

        self.text.focus_set()


    # ========================================================
    # BUILD
    # ========================================================

    def build(self):

        self.window.configure(
            bg=self.theme["bg"]
        )


        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = tk.Frame(
            self.window,
            bg=self.theme["card"],
            height=60,
        )

        header.pack(
            fill="x",
            padx=15,
            pady=(15, 8),
        )

        header.pack_propagate(
            False
        )


        title = tk.Label(
            header,
            text="📝  Заметки",
            font=(
                "Segoe UI",
                17,
                "bold",
            ),
            bg=self.theme["card"],
            fg=self.theme["text"],
        )

        title.pack(
            side="left",
            padx=15,
        )


        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        buttons = tk.Frame(
            header,
            bg=self.theme["card"],
        )

        buttons.pack(
            side="right",
            padx=10,
        )


        clear_button = tk.Button(
            buttons,
            text="Очистить",
            command=self.clear_notes,
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=7,
            bg=self.theme["hover"],
            fg=self.theme["text"],
            activebackground=self.theme["border"],
        )

        clear_button.pack(
            side="left",
            padx=3,
        )


        save_button = tk.Button(
            buttons,
            text="Сохранить",
            command=self.save_notes,
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=7,
            bg="#009246",
            fg="#FFFFFF",
            activebackground="#007A3A",
            activeforeground="#FFFFFF",
        )

        save_button.pack(
            side="left",
            padx=3,
        )


        # ----------------------------------------------------
        # TEXT AREA
        # ----------------------------------------------------

        text_frame = tk.Frame(
            self.window,
            bg=self.theme["card"],
        )

        text_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(0, 10),
        )


        scrollbar = tk.Scrollbar(
            text_frame
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )


        self.text = tk.Text(
            text_frame,

            font=(
                "Segoe UI",
                11,
            ),

            wrap="word",

            undo=True,

            bg=self.theme["input"],

            fg=self.theme["text"],

            insertbackground=self.theme["text"],

            selectbackground="#2563EB",

            selectforeground="#FFFFFF",

            relief="flat",

            bd=0,

            padx=18,

            pady=15,

            yscrollcommand=scrollbar.set,
        )

        self.text.pack(
            side="left",
            fill="both",
            expand=True,
        )


        scrollbar.configure(
            command=self.text.yview
        )


        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status = tk.Label(
            self.window,
            text="Готово",
            font=(
                "Segoe UI",
                9,
            ),
            bg=self.theme["bg"],
            fg=self.theme["gray"],
            anchor="w",
        )

        self.status.pack(
            fill="x",
            padx=18,
            pady=(0, 12),
        )


        # ----------------------------------------------------
        # KEYBOARD SHORTCUTS
        # ----------------------------------------------------

        # Сохранить
        self.text.bind(
            "<Control-s>",
            self.shortcut_save,
        )

        # Выделить всё
        self.text.bind(
            "<Control-a>",
            self.select_all,
        )

        # Копировать
        self.text.bind(
            "<Control-c>",
            self.copy_text,
        )

        # Вырезать
        self.text.bind(
            "<Control-x>",
            self.cut_text,
        )

        # Вставить
        self.text.bind(
            "<Control-v>",
            self.paste_text,
        )

        # Альтернативная вставка Windows
        self.text.bind(
            "<Shift-Insert>",
            self.paste_text,
        )

        # Альтернативное копирование
        self.text.bind(
            "<Control-Insert>",
            self.copy_text,
        )


        # ----------------------------------------------------
        # RIGHT CLICK MENU
        # ----------------------------------------------------

        self.context_menu = tk.Menu(
            self.window,
            tearoff=0,
        )

        self.context_menu.add_command(
            label="Вырезать",
            command=self.cut_text,
        )

        self.context_menu.add_command(
            label="Копировать",
            command=self.copy_text,
        )

        self.context_menu.add_command(
            label="Вставить",
            command=self.paste_text,
        )

        self.context_menu.add_separator()

        self.context_menu.add_command(
            label="Выделить всё",
            command=self.select_all,
        )

        self.text.bind(
            "<Button-3>",
            self.show_context_menu,
        )


    # ========================================================
    # LOAD NOTES
    # ========================================================

    def load_notes(self):

        try:

            if NOTES_FILE.exists():

                content = NOTES_FILE.read_text(
                    encoding="utf-8"
                )

                self.text.delete(
                    "1.0",
                    "end"
                )

                self.text.insert(
                    "1.0",
                    content
                )

                self.set_status(
                    "Заметки загружены"
                )

            else:

                self.set_status(
                    "Новая заметка"
                )

        except Exception as e:

            self.set_status(
                f"Ошибка загрузки: {e}"
            )


    # ========================================================
    # SAVE NOTES
    # ========================================================

    def save_notes(self):

        if self.closing:
            return


        try:

            NOTES_FILE.parent.mkdir(
                parents=True,
                exist_ok=True
            )


            content = self.text.get(
                "1.0",
                "end-1c"
            )


            NOTES_FILE.write_text(
                content,
                encoding="utf-8"
            )


            self.set_status(
                "Сохранено ✓"
            )


        except Exception as e:

            messagebox.showerror(
                "Ошибка",
                f"Не удалось сохранить заметки:\n\n{e}",
                parent=self.window,
            )


    # ========================================================
    # AUTOSAVE
    # ========================================================

    def autosave(self):

        if self.closing:
            return


        try:

            NOTES_FILE.parent.mkdir(
                parents=True,
                exist_ok=True
            )


            content = self.text.get(
                "1.0",
                "end-1c"
            )


            NOTES_FILE.write_text(
                content,
                encoding="utf-8"
            )


        except Exception:
            pass


        # Следующее автосохранение через 5 секунд

        if not self.closing:

            try:

                self.autosave_id = self.window.after(
                    5000,
                    self.autosave
                )

            except Exception:
                pass


    # ========================================================
    # CLOSE WINDOW
    # ========================================================

    def close_window(self):

        if self.closing:
            return


        self.closing = True


        # ----------------------------------------------------
        # CANCEL AUTOSAVE TIMER
        # ----------------------------------------------------

        if self.autosave_id is not None:

            try:

                self.window.after_cancel(
                    self.autosave_id
                )

            except Exception:
                pass

            self.autosave_id = None


        # ----------------------------------------------------
        # FINAL SAVE BEFORE CLOSE
        # ----------------------------------------------------

        try:

            NOTES_FILE.parent.mkdir(
                parents=True,
                exist_ok=True
            )


            content = self.text.get(
                "1.0",
                "end-1c"
            )


            NOTES_FILE.write_text(
                content,
                encoding="utf-8"
            )

        except Exception as e:

            # Даже если сохранение не удалось,
            # окно всё равно можно закрыть.

            try:

                messagebox.showerror(
                    "Ошибка сохранения",
                    f"Не удалось сохранить заметки:\n\n{e}",
                    parent=self.window,
                )

            except Exception:
                pass


        # ----------------------------------------------------
        # DESTROY
        # ----------------------------------------------------

        try:

            self.window.destroy()

        except Exception:
            pass


    # ========================================================
    # CLEAR
    # ========================================================

    def clear_notes(self):

        answer = messagebox.askyesno(
            "Очистить заметки?",
            "Удалить весь текущий текст?",
            parent=self.window,
        )


        if not answer:
            return


        self.text.delete(
            "1.0",
            "end"
        )


        self.save_notes()


        self.set_status(
            "Заметки очищены"
        )


    # ========================================================
    # COPY
    # ========================================================

    def copy_text(self, event=None):

        try:

            selected = self.text.get(
                "sel.first",
                "sel.last"
            )

        except tk.TclError:

            return "break"


        try:

            self.window.clipboard_clear()

            self.window.clipboard_append(
                selected
            )

            self.window.update()

            self.set_status(
                "Скопировано ✓"
            )

        except Exception:

            pass


        return "break"


    # ========================================================
    # CUT
    # ========================================================

    def cut_text(self, event=None):

        try:

            selected = self.text.get(
                "sel.first",
                "sel.last"
            )

        except tk.TclError:

            return "break"


        try:

            self.window.clipboard_clear()

            self.window.clipboard_append(
                selected
            )

            self.window.update()


            # Удаляем выделенный текст

            self.text.delete(
                "sel.first",
                "sel.last"
            )


            self.set_status(
                "Вырезано ✓"
            )

        except Exception:

            pass


        return "break"


    # ========================================================
    # PASTE
    # ========================================================

    def paste_text(self, event=None):

        try:

            # Получаем текст из системного буфера

            clipboard_text = self.window.clipboard_get()


        except tk.TclError:

            self.set_status(
                "Буфер обмена пуст"
            )

            return "break"


        except Exception as e:

            self.set_status(
                f"Ошибка вставки: {e}"
            )

            return "break"


        try:

            # ------------------------------------------------
            # Если есть выделение — удаляем его.
            # Новый текст заменит старый.
            # ------------------------------------------------

            try:

                self.text.delete(
                    "sel.first",
                    "sel.last"
                )

            except tk.TclError:

                pass


            # ------------------------------------------------
            # Вставляем текст в текущую позицию курсора
            # ------------------------------------------------

            self.text.insert(
                "insert",
                clipboard_text
            )


            self.set_status(
                "Вставлено ✓"
            )


        except Exception as e:

            self.set_status(
                f"Ошибка вставки: {e}"
            )


        return "break"


    # ========================================================
    # SELECT ALL
    # ========================================================

    def select_all(self, event=None):

        self.text.tag_add(
            "sel",
            "1.0",
            "end-1c"
        )

        self.text.mark_set(
            "insert",
            "1.0"
        )

        self.text.see(
            "insert"
        )

        return "break"


    # ========================================================
    # CTRL + S
    # ========================================================

    def shortcut_save(self, event=None):

        self.save_notes()

        return "break"


    # ========================================================
    # CONTEXT MENU
    # ========================================================

    def show_context_menu(self, event):

        try:

            self.text.focus_set()

            self.context_menu.tk_popup(
                event.x_root,
                event.y_root
            )

        finally:

            self.context_menu.grab_release()


        return "break"


    # ========================================================
    # STATUS
    # ========================================================

    def set_status(self, text):

        if self.closing:
            return


        try:

            self.status.configure(
                text=text
            )

            self.window.after(
                2500,
                lambda: (
                    self.status.configure(
                        text="Готово"
                    )
                    if not self.closing
                    else None
                ),
            )

        except Exception:
            pass


# ============================================================
# OPEN NOTES
# ============================================================

def open_notes(parent):

    NotesWindow(
        parent
    )