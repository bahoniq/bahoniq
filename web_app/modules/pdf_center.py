import os
import threading
import tkinter as tk

from tkinter import filedialog, messagebox
from pathlib import Path

from services.settings_service import get_theme


# ============================================================
# BAHONIQ — PDF CENTER
# ============================================================

class PDFCenter:

    def __init__(self, parent):

        self.parent = parent
        self.theme = get_theme()

        self.files = []
        self.output_folder = None

        self.build()

    # ========================================================
    # WINDOW
    # ========================================================

    def build(self):

        self.window = tk.Toplevel(
            self.parent
        )

        self.window.title(
            "BahonIQ — PDF Center"
        )

        self.window.geometry(
            "1050x720"
        )

        self.window.minsize(
            900,
            650
        )

        self.window.configure(
            bg=self.theme["bg"]
        )

        self.window.transient(
            self.parent
        )

        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.window.iconbitmap(str(icon_path))
            except Exception:
                pass

        # ====================================================
        # HEADER
        # ====================================================

        header = tk.Frame(
            self.window,
            bg=self.theme["card"],
            height=80
        )

        header.pack(
            fill="x",
            padx=18,
            pady=(18, 12)
        )

        header.pack_propagate(
            False
        )

        title = tk.Label(
            header,
            text="📄  BahonIQ PDF Center",
            font=("Segoe UI", 19, "bold"),
            bg=self.theme["card"],
            fg=self.theme["text"]
        )

        title.pack(
            side="left",
            padx=20
        )

        subtitle = tk.Label(
            header,
            text="Быстрая конвертация документов",
            font=("Segoe UI", 9),
            bg=self.theme["card"],
            fg=self.theme["gray"]
        )

        subtitle.pack(
            side="left"
        )

        # ====================================================
        # OPERATIONS CARD
        # ====================================================

        action_card = tk.Frame(
            self.window,
            bg=self.theme["card"]
        )

        action_card.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(0, 12)
        )

        action_title = tk.Label(
            action_card,
            text="Выберите операцию",
            font=("Segoe UI", 13, "bold"),
            bg=self.theme["card"],
            fg=self.theme["text"]
        )

        action_title.pack(
            anchor="w",
            padx=25,
            pady=(25, 5)
        )

        action_subtitle = tk.Label(
            action_card,
            text=(
                "Выберите операцию — затем исходный файл "
                "и папку для сохранения результата."
            ),
            font=("Segoe UI", 9),
            bg=self.theme["card"],
            fg=self.theme["gray"]
        )

        action_subtitle.pack(
            anchor="w",
            padx=25,
            pady=(0, 20)
        )

        actions = tk.Frame(
            action_card,
            bg=self.theme["card"]
        )

        actions.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 25)
        )

        # ====================================================
        # OPERATIONS
        # ====================================================

        operations = [

            ("📄  PDF → Word", "pdf_word"),

            ("📝  Word → PDF", "word_pdf"),

            ("📄  PDF → JPG", "pdf_jpg"),

            ("📄  PDF → PNG", "pdf_png"),

            ("🖼  Изображения → PDF", "images_pdf"),

            ("📚  Объединить PDF", "merge_pdf"),

            ("✂  Разделить PDF", "split_pdf"),

            ("🗜  Сжать PDF", "compress_pdf"),

            ("📑  PDF → TXT", "pdf_txt"),

            ("🤖  Спроси PDF (ИИ)", "ask_pdf"),

        ]

        for index, (text, command) in enumerate(
            operations
        ):

            button = self.make_operation_button(
                actions,
                text,
                lambda c=command, t=text:
                    self.run_operation(c, t)
            )

            row = index // 3
            column = index % 3

            button.grid(
                row=row,
                column=column,
                padx=8,
                pady=8,
                sticky="nsew"
            )

        for column in range(3):

            actions.columnconfigure(
                column,
                weight=1
            )

        for row in range((len(operations) + 2) // 3):

            actions.rowconfigure(
                row,
                weight=1
            )

        # ====================================================
        # STATUS
        # ====================================================

        self.status = tk.Label(
            self.window,
            text="Выберите операцию",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["gray"]
        )

        self.status.pack(
            fill="x",
            padx=25,
            pady=(0, 18)
        )

    # ========================================================
    # BUTTON
    # ========================================================

    def make_operation_button(
        self,
        parent,
        text,
        command
    ):

        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=15,
            pady=18,
            bg=self.theme["hover"],
            fg=self.theme["text"],
            activebackground=self.theme["border"],
            activeforeground=self.theme["text"]
        )

    # ========================================================
    # RUN OPERATION
    # ========================================================

    def run_operation(
        self,
        operation,
        operation_name
    ):

        # ----------------------------------------------------
        # ОЧИЩАЕМ ПРЕДЫДУЩИЙ СПИСОК
        # ----------------------------------------------------

        self.files = []
        self.ask_question = ""
        self.split_range_str = ""

        # ----------------------------------------------------
        # ВЫБОР ИСХОДНЫХ ФАЙЛОВ
        # ----------------------------------------------------

        files = self.select_files(
            operation
        )

        if not files:

            self.status.configure(
                text="Операция отменена."
            )

            return

        self.files = [
            Path(file)
            for file in files
        ]

        # ----------------------------------------------------
        # СПРОСИ PDF (ИИ) — СПЕЦИАЛЬНЫЙ РЕЖИМ
        # ----------------------------------------------------

        if operation == "ask_pdf":
            from tkinter import simpledialog

            question = simpledialog.askstring(
                "BahonIQ AI — Спроси PDF",
                "Задайте вопрос к документу\n(краткая выжимка, условия договора, ключевые даты/суммы):",
                parent=self.window,
                initialvalue="Сделай краткую выжимку, выдели ключевые факты, даты, суммы и условия."
            )

            if not question or not question.strip():
                self.status.configure(text="Вопрос не задан.")
                return

            self.ask_question = question.strip()
            self.status.configure(text="⏳ ИИ анализирует документ...")

            thread = threading.Thread(
                target=self.operation_worker,
                args=(operation,),
                daemon=True
            )
            thread.start()
            return

        # ----------------------------------------------------
        # РАЗДЕЛЕНИЕ PDF (ДИАПАЗОН СТРАНИЦ)
        # ----------------------------------------------------

        if operation == "split_pdf":
            from tkinter import simpledialog

            range_val = simpledialog.askstring(
                "Разделение PDF",
                "Введите диапазон страниц (например: 1-3, 5, 8-10)\nили оставьте пустым для разделения по отдельным страницам:",
                parent=self.window
            )
            self.split_range_str = (range_val or "").strip()

        # ----------------------------------------------------
        # ВЫБОР ПАПКИ РЕЗУЛЬТАТА
        # ----------------------------------------------------

        self.status.configure(
            text=f"Выбрано файлов: {len(self.files)}"
        )

        output_folder = filedialog.askdirectory(
            parent=self.window,
            title="Выберите папку для сохранения результата"
        )

        if not output_folder:

            self.status.configure(
                text="Сохранение отменено."
            )

            return

        self.output_folder = Path(
            output_folder
        )

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        # ----------------------------------------------------
        # ЗАПУСК
        # ----------------------------------------------------

        self.status.configure(
            text=f"⏳ Выполняется: {operation_name}"
        )

        thread = threading.Thread(
            target=self.operation_worker,
            args=(operation,),
            daemon=True
        )

        thread.start()

    # ========================================================
    # SELECT FILES
    # ========================================================

    def select_files(
        self,
        operation
    ):

        # ----------------------------------------------------
        # PDF → WORD
        # ----------------------------------------------------

        if operation == "pdf_word":

            return filedialog.askopenfilenames(
                parent=self.window,
                title="Выберите PDF-файл",
                filetypes=[
                    (
                        "PDF файлы",
                        "*.pdf"
                    ),
                    (
                        "Все файлы",
                        "*.*"
                    )
                ]
            )

        # ----------------------------------------------------
        # WORD → PDF
        # ----------------------------------------------------

        elif operation == "word_pdf":

            return filedialog.askopenfilenames(
                parent=self.window,
                title="Выберите Word-файл",
                filetypes=[
                    (
                        "Word документы",
                        "*.docx *.doc"
                    ),
                    (
                        "DOCX",
                        "*.docx"
                    ),
                    (
                        "DOC",
                        "*.doc"
                    ),
                    (
                        "Все файлы",
                        "*.*"
                    )
                ]
            )

        # ----------------------------------------------------
        # PDF → JPG
        # PDF → PNG
        # MERGE
        # SPLIT
        # COMPRESS
        # ----------------------------------------------------

        elif operation in {
            "pdf_jpg",
            "pdf_png",
            "merge_pdf",
            "split_pdf",
            "compress_pdf",
            "pdf_txt",
            "ask_pdf"
        }:

            return filedialog.askopenfilenames(
                parent=self.window,
                title="Выберите PDF-файл",
                filetypes=[
                    (
                        "PDF файлы",
                        "*.pdf"
                    ),
                    (
                        "Все файлы",
                        "*.*"
                    )
                ]
            )

        # ----------------------------------------------------
        # IMAGES → PDF
        # ----------------------------------------------------

        elif operation == "images_pdf":

            return filedialog.askopenfilenames(
                parent=self.window,
                title="Выберите изображения",
                filetypes=[
                    (
                        "Изображения",
                        "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"
                    ),
                    (
                        "JPG",
                        "*.jpg *.jpeg"
                    ),
                    (
                        "PNG",
                        "*.png"
                    ),
                    (
                        "BMP",
                        "*.bmp"
                    ),
                    (
                        "TIFF",
                        "*.tiff"
                    ),
                    (
                        "WEBP",
                        "*.webp"
                    ),
                    (
                        "Все файлы",
                        "*.*"
                    )
                ]
            )

        return []

    # ========================================================
    # WORKER
    # ========================================================

    def operation_worker(
        self,
        operation
    ):

        try:

            if operation == "pdf_word":

                self.pdf_to_word()

            elif operation == "pdf_jpg":

                self.pdf_to_images(
                    "jpg"
                )

            elif operation == "pdf_png":

                self.pdf_to_images(
                    "png"
                )

            elif operation == "word_pdf":

                self.word_to_pdf()

            elif operation == "images_pdf":

                self.images_to_pdf()

            elif operation == "merge_pdf":

                self.merge_pdf()

            elif operation == "split_pdf":

                self.split_pdf()

            elif operation == "compress_pdf":

                self.compress_pdf()

            elif operation == "pdf_txt":

                self.pdf_to_txt()

            elif operation == "ask_pdf":

                self.ask_pdf()

        except Exception as error:

            self.window.after(
                0,
                lambda error=error:
                    self.show_error(
                        error
                    )
            )

    # ========================================================
    # ERROR
    # ========================================================

    def show_error(
        self,
        error
    ):

        self.status.configure(
            text="❌ Ошибка"
        )

        messagebox.showerror(
            "Ошибка",
            f"Операция не выполнена:\n\n{error}",
            parent=self.window
        )

    # ========================================================
    # PDF → WORD
    # ========================================================

    def pdf_to_word(self):

        from pdf2docx import Converter

        count = 0

        for path in self.files:

            if path.suffix.lower() != ".pdf":

                continue

            output = (
                self.output_folder /
                f"{path.stem}.docx"
            )

            converter = Converter(
                str(path)
            )

            try:

                converter.convert(
                    str(output)
                )

                count += 1

            finally:

                converter.close()

        self.finished(
            f"PDF → Word завершено.\n"
            f"Файлов: {count}",
            self.output_folder
        )

    # ========================================================
    # PDF → JPG / PNG
    # ========================================================

    def pdf_to_images(
        self,
        image_format
    ):

        import fitz

        count = 0

        last_folder = self.output_folder

        for path in self.files:

            if path.suffix.lower() != ".pdf":

                continue

            document = fitz.open(
                str(path)
            )

            try:

                folder = (
                    self.output_folder /
                    path.stem
                )

                folder.mkdir(
                    parents=True,
                    exist_ok=True
                )

                last_folder = folder

                for page_number, page in enumerate(
                    document
                ):

                    pixmap = page.get_pixmap(
                        matrix=fitz.Matrix(
                            2,
                            2
                        )
                    )

                    output = (
                        folder /
                        f"{path.stem}_{page_number + 1}.{image_format}"
                    )

                    pixmap.save(
                        str(output)
                    )

                    count += 1

            finally:

                document.close()

        self.finished(
            f"PDF → {image_format.upper()} завершено.\n"
            f"Страниц: {count}",
            last_folder
        )

    # ========================================================
    # WORD → PDF
    # ========================================================

    def word_to_pdf(self):

        import win32com.client

        word = win32com.client.Dispatch(
            "Word.Application"
        )

        word.Visible = False

        count = 0

        try:

            for path in self.files:

                if path.suffix.lower() not in {
                    ".docx",
                    ".doc"
                }:

                    continue

                output = (
                    self.output_folder /
                    f"{path.stem}.pdf"
                )

                document = word.Documents.Open(
                    str(path)
                )

                try:

                    document.SaveAs(
                        str(output),
                        FileFormat=17
                    )

                    count += 1

                finally:

                    document.Close(
                        False
                    )

        finally:

            word.Quit()

        self.finished(
            f"Word → PDF завершено.\n"
            f"Файлов: {count}",
            self.output_folder
        )

    # ========================================================
    # IMAGES → PDF
    # ========================================================

    def images_to_pdf(self):

        from PIL import Image

        images = []

        try:

            for path in self.files:

                if path.suffix.lower() not in {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".bmp",
                    ".tiff",
                    ".webp",
                }:

                    continue

                image = Image.open(
                    path
                ).convert(
                    "RGB"
                )

                images.append(
                    image
                )

            if not images:

                raise ValueError(
                    "Изображения не найдены."
                )

            # ------------------------------------------------
            # ЕСЛИ ОДИН ИЛИ НЕСКОЛЬКО ФАЙЛОВ
            # ------------------------------------------------

            output = (
                self.output_folder /
                "BahonIQ_Images.pdf"
            )

            first = images[0]

            first.save(
                output,
                save_all=True,
                append_images=images[1:]
            )

        finally:

            for image in images:

                try:
                    image.close()

                except Exception:
                    pass

        self.finished(
            "Изображения объединены в PDF.\n"
            f"Файл: {output.name}",
            self.output_folder
        )

    # ========================================================
    # MERGE PDF
    # ========================================================

    def merge_pdf(self):

        from pypdf import (
            PdfWriter,
            PdfReader
        )

        writer = PdfWriter()

        count = 0

        for path in self.files:

            if path.suffix.lower() != ".pdf":

                continue

            reader = PdfReader(
                str(path)
            )

            for page in reader.pages:

                writer.add_page(
                    page
                )

            count += 1

        if count == 0:

            raise ValueError(
                "PDF-файлы не найдены."
            )

        output = (
            self.output_folder /
            "BahonIQ_Merged.pdf"
        )

        with open(
            output,
            "wb"
        ) as file:

            writer.write(
                file
            )

        self.finished(
            f"PDF объединены.\n"
            f"Файлов: {count}",
            self.output_folder
        )

    # ========================================================
    # SPLIT PDF
    # ========================================================

    def split_pdf(self):

        from pypdf import (
            PdfReader,
            PdfWriter
        )

        count = 0
        last_folder = self.output_folder

        range_text = getattr(self, "split_range_str", "").strip()

        for path in self.files:

            if path.suffix.lower() != ".pdf":
                continue

            reader = PdfReader(str(path))
            total_pages = len(reader.pages)

            if total_pages == 0:
                continue

            folder = self.output_folder / path.stem
            folder.mkdir(parents=True, exist_ok=True)
            last_folder = folder

            # Если пользователь указал конкретный диапазон (например, "1-3, 5")
            if range_text:
                target_pages = set()
                for part in range_text.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    if "-" in part:
                        sub = part.split("-", 1)
                        try:
                            s = max(1, int(sub[0].strip()))
                            e = min(total_pages, int(sub[1].strip()))
                            for i in range(s, e + 1):
                                target_pages.add(i - 1)
                        except ValueError:
                            pass
                    else:
                        try:
                            val = int(part)
                            if 1 <= val <= total_pages:
                                target_pages.add(val - 1)
                        except ValueError:
                            pass

                sorted_pages = sorted(target_pages)
                if not sorted_pages:
                    sorted_pages = list(range(total_pages))

                writer = PdfWriter()
                for p_idx in sorted_pages:
                    writer.add_page(reader.pages[p_idx])

                clean_tag = range_text.replace(" ", "").replace(",", "_").replace("-", "to")
                output = folder / f"{path.stem}_pages_{clean_tag}.pdf"
                with open(output, "wb") as f_out:
                    writer.write(f_out)
                count += len(sorted_pages)

            else:
                # Постраничное разделение всех страниц
                for number, page in enumerate(reader.pages, start=1):
                    writer = PdfWriter()
                    writer.add_page(page)
                    output = folder / f"{path.stem}_{number}.pdf"
                    with open(output, "wb") as f_out:
                        writer.write(f_out)
                    count += 1

        self.finished(
            f"PDF разделены.\n"
            f"Обработано страниц: {count}",
            last_folder
        )

    # ========================================================
    # PDF → TXT
    # ========================================================

    def pdf_to_txt(self):

        import fitz

        count = 0

        for path in self.files:

            if path.suffix.lower() != ".pdf":
                continue

            document = fitz.open(str(path))

            try:
                text_parts = []
                for num, page in enumerate(document, 1):
                    p_text = page.get_text()
                    if p_text.strip():
                        text_parts.append(f"--- Страница {num} ---\n{p_text.strip()}")

                output = self.output_folder / f"{path.stem}.txt"
                output.write_text("\n\n".join(text_parts), encoding="utf-8")
                count += 1

            finally:
                document.close()

        self.finished(
            f"PDF → TXT завершено.\n"
            f"Файлов: {count}",
            self.output_folder
        )

    # ========================================================
    # ASK PDF (ИИ-АССИСТЕНТ)
    # ========================================================

    def ask_pdf(self):

        import fitz
        from ai_service import generate_text

        path = self.files[0]
        document = fitz.open(str(path))
        extracted_text = ""

        try:
            pages_text = []
            for num, page in enumerate(document, 1):
                t = page.get_text()
                if t.strip():
                    pages_text.append(f"[Страница {num}]\n{t.strip()}")
            extracted_text = "\n\n".join(pages_text)

        finally:
            document.close()

        if not extracted_text.strip():
            raise ValueError(
                "Не удалось извлечь текст из PDF документа.\n"
                "Возможно, документ состоит только из сканов без текстового слоя."
            )

        system_prompt = (
            "Ты — ведущий ИИ-ассистент по анализу документов. Пользователь загрузил PDF и задал вопрос.\n"
            "Твоя задача — дать точный, структурированный, исчерпывающий ответ строго на основе текста документа.\n"
            "Выдели ключевые факты, даты, суммы, условия и риски. Если нужной информации нет в тексте, честно укажи это."
        )

        user_prompt = (
            f"Документ: {path.name}\n\n"
            f"Вопрос пользователя: {self.ask_question}\n\n"
            f"Текст документа (первые 40 000 символов):\n{extracted_text[:40000]}"
        )

        result_text, provider = generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2
        )

        self.window.after(
            0,
            lambda: self.show_ai_result(
                path.name,
                self.ask_question,
                result_text,
                provider
            )
        )

    def show_ai_result(self, doc_name, question, text, provider):

        self.status.configure(
            text=f"✓ Ответ ИИ получен ({provider})"
        )

        dialog = tk.Toplevel(self.window)
        dialog.title(f"BahonIQ AI — {doc_name}")
        dialog.geometry("780x580")
        dialog.configure(bg=self.theme["bg"])
        dialog.transient(self.window)

        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                dialog.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Верхняя плашка вопроса
        top_frame = tk.Frame(dialog, bg=self.theme["card"], height=65)
        top_frame.pack(fill="x", padx=14, pady=10)
        top_frame.pack_propagate(False)

        q_label = tk.Label(
            top_frame,
            text=f"Вопрос: {question}",
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["card"],
            fg=self.theme["text"],
            wraplength=640,
            justify="left"
        )
        q_label.pack(side="left", padx=15, pady=8)

        badge_color = "#00D26A" if provider == "gemini" else "#E5A93C"
        badge = tk.Label(
            top_frame,
            text=f"[{provider.upper()}]",
            font=("Segoe UI", 9, "bold"),
            bg=self.theme["card"],
            fg=badge_color
        )
        badge.pack(side="right", padx=15)

        # Область ответа
        content_frame = tk.Frame(dialog, bg=self.theme["bg"])
        content_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        scrollbar = tk.Scrollbar(content_frame)
        scrollbar.pack(side="right", fill="y")

        text_area = tk.Text(
            content_frame,
            wrap="word",
            font=("Segoe UI", 10),
            bg=self.theme["card"],
            fg=self.theme["text"],
            bd=0,
            padx=14,
            pady=14,
            yscrollcommand=scrollbar.set
        )
        text_area.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_area.yview)

        text_area.insert("1.0", text)
        text_area.config(state="disabled")

        # Нижняя панель с кнопками
        btn_frame = tk.Frame(dialog, bg=self.theme["bg"])
        btn_frame.pack(fill="x", padx=14, pady=(0, 14))

        def copy_to_clipboard():
            dialog.clipboard_clear()
            dialog.clipboard_append(text)
            copy_btn.config(text="✓ Скопировано в буфер!", bg="#00D26A")
            dialog.after(2000, lambda: copy_btn.config(text="Копировать ответ", bg=self.theme["hover"]))

        copy_btn = tk.Button(
            btn_frame,
            text="Копировать ответ",
            command=copy_to_clipboard,
            font=("Segoe UI", 10, "bold"),
            bg=self.theme["hover"],
            fg=self.theme["text"],
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2"
        )
        copy_btn.pack(side="left")

        close_btn = tk.Button(
            btn_frame,
            text="Закрыть",
            command=dialog.destroy,
            font=("Segoe UI", 10),
            bg=self.theme["card"],
            fg=self.theme["gray"],
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2"
        )
        close_btn.pack(side="right")

    # ========================================================
    # COMPRESS PDF
    # ========================================================

    def compress_pdf(self):

        import fitz

        count = 0

        for path in self.files:

            if path.suffix.lower() != ".pdf":

                continue

            document = fitz.open(
                str(path)
            )

            output = (
                self.output_folder /
                f"{path.stem}_compressed.pdf"
            )

            try:

                document.save(
                    str(output),
                    garbage=4,
                    deflate=True,
                    clean=True
                )

                count += 1

            finally:

                document.close()

        self.finished(
            f"Сжатие завершено.\n"
            f"Файлов: {count}",
            self.output_folder
        )

    # ========================================================
    # FINISHED
    # ========================================================

    def finished(
        self,
        message,
        folder
    ):

        def complete():

            self.status.configure(
                text=(
                    f"✓ {message.replace(chr(10), ' ')}"
                )
            )

            # -----------------------------------------------
            # ОТКРЫВАЕМ ПАПКУ РЕЗУЛЬТАТА
            # -----------------------------------------------

            try:

                if folder and folder.exists():

                    os.startfile(
                        str(folder)
                    )

            except Exception:
                pass

            # -----------------------------------------------
            # СООБЩЕНИЕ
            # -----------------------------------------------

            messagebox.showinfo(
                "BahonIQ PDF Center",
                message,
                parent=self.window
            )

        self.window.after(
            0,
            complete
        )


# ============================================================
# OPEN
# ============================================================

def open_pdf_center(parent):

    PDFCenter(
        parent
    )