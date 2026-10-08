import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox

from services.settings_service import get_theme


# ============================================================
# BAHONIQ — ANYDESK SERVICE
# ============================================================


ANYDESK_PATH = (
    os.path.expanduser(
        r"~\Desktop\AnyDesk.exe"
    )
)


ANYDESK_DATA_FOLDER = (
    os.path.expanduser(
        r"~\AppData\Roaming\AnyDesk"
    )
)


# ============================================================
# CHECK RUNNING
# ============================================================

def is_anydesk_running():

    try:

        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq AnyDesk.exe"
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        output = (
            result.stdout
            + result.stderr
        ).lower()

        return "anydesk.exe" in output

    except Exception:

        return False


# ============================================================
# START ANYDESK
# ============================================================

def start_anydesk():

    if is_anydesk_running():

        return (
            True,
            "AnyDesk уже запущен."
        )


    if not os.path.isfile(ANYDESK_PATH):

        return (
            False,
            "AnyDesk.exe не найден:\n\n"
            + ANYDESK_PATH
        )


    try:

        subprocess.Popen(
            [ANYDESK_PATH],
            cwd=os.path.dirname(
                ANYDESK_PATH
            ),
        )

        return (
            True,
            "AnyDesk запущен."
        )


    except Exception as e:

        return (
            False,
            f"Не удалось запустить AnyDesk:\n\n{e}"
        )


# ============================================================
# CLEAR ANYDESK FOLDER
# ============================================================

def clear_anydesk_folder():

    if not os.path.exists(
        ANYDESK_DATA_FOLDER
    ):

        return (
            False,
            "Папка AnyDesk не найдена:\n\n"
            + ANYDESK_DATA_FOLDER
        )


    deleted = 0
    skipped = 0


    try:

        items = os.listdir(
            ANYDESK_DATA_FOLDER
        )


        for item in items:

            path = os.path.join(
                ANYDESK_DATA_FOLDER,
                item
            )


            try:

                if os.path.isdir(path):

                    shutil.rmtree(
                        path
                    )

                else:

                    os.remove(path)


                deleted += 1


            except Exception:

                skipped += 1


        return (
            True,
            deleted,
            skipped
        )


    except Exception as e:

        return (
            False,
            f"Ошибка очистки:\n\n{e}"
        )


# ============================================================
# OPEN ANYDESK
# ============================================================

def open_anydesk(parent):

    theme = get_theme()


    window = tk.Toplevel(
        parent
    )

    window.title(
        "BahonIQ — AnyDesk"
    )

    window.geometry(
        "520x360"
    )

    window.minsize(
        520,
        360
    )

    window.configure(
        bg=theme["bg"]
    )

    window.transient(
        parent
    )


    # ========================================================
    # HEADER
    # ========================================================

    header = tk.Frame(
        window,
        bg=theme["card"],
        height=70
    )

    header.pack(
        fill="x",
        padx=18,
        pady=(18, 10)
    )

    header.pack_propagate(
        False
    )


    title = tk.Label(
        header,
        text="🖥️  AnyDesk",
        font=(
            "Segoe UI",
            17,
            "bold"
        ),
        bg=theme["card"],
        fg=theme["text"]
    )

    title.pack(
        side="left",
        padx=18
    )


    # ========================================================
    # CONTENT
    # ========================================================

    card = tk.Frame(
        window,
        bg=theme["card"]
    )

    card.pack(
        fill="both",
        expand=True,
        padx=18,
        pady=(0, 18)
    )


    description = tk.Label(
        card,
        text=(
            "Управление AnyDesk\n\n"
            "Запуск программы или очистка\n"
            "её пользовательских данных."
        ),
        font=(
            "Segoe UI",
            10
        ),
        justify="center",
        bg=theme["card"],
        fg=theme["gray"]
    )

    description.pack(
        pady=(25, 15)
    )


    # ========================================================
    # START
    # ========================================================

    def run_anydesk():

        success, message = start_anydesk()


        if success:

            status.configure(
                text="✓ " + message,
                fg="#009246"
            )

        else:

            status.configure(
                text=message,
                fg="#E10600"
            )


    start_button = tk.Button(
        card,
        text="🖥️  Запустить AnyDesk",
        command=run_anydesk,
        font=(
            "Segoe UI",
            10,
            "bold"
        ),
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=20,
        pady=9,
        bg="#009246",
        fg="#FFFFFF",
        activebackground="#007A3A",
        activeforeground="#FFFFFF"
    )

    start_button.pack(
        pady=5
    )


    # ========================================================
    # CLEAR
    # ========================================================

    def clear_anydesk():

        answer = messagebox.askyesno(
            "Очистить AnyDesk?",
            (
                "Будет очищено содержимое папки:\n\n"
                f"{ANYDESK_DATA_FOLDER}\n\n"
                "Сама папка AnyDesk останется."
            ),
            parent=window
        )


        if not answer:
            return


        result = clear_anydesk_folder()


        if result[0] is False:

            status.configure(
                text=result[1],
                fg="#E10600"
            )

            return


        deleted = result[1]
        skipped = result[2]


        status.configure(
            text=(
                f"✓ Очистка завершена\n"
                f"Удалено: {deleted} | "
                f"Пропущено: {skipped}"
            ),
            fg="#009246"
        )


    clear_button = tk.Button(
        card,
        text="🧹  Очистить AnyDesk",
        command=clear_anydesk,
        font=(
            "Segoe UI",
            10,
            "bold"
        ),
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=20,
        pady=9,
        bg=theme["hover"],
        fg=theme["text"],
        activebackground=theme["border"]
    )

    clear_button.pack(
        pady=5
    )


    # ========================================================
    # STATUS
    # ========================================================

    status = tk.Label(
        card,
        text="Готово",
        font=(
            "Segoe UI",
            9,
            "bold"
        ),
        bg=theme["card"],
        fg=theme["gray"]
    )

    status.pack(
        pady=(12, 5)
    )