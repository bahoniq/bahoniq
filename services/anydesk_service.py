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
        "520x460"
    )

    window.minsize(
        520,
        460
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
    # AUTO-CLEANUP SCHEDULE SECTION
    # ========================================================
    sep = tk.Frame(card, bg=theme.get("border", "#333333"), height=1)
    sep.pack(fill="x", padx=20, pady=(10, 8))

    try:
        from scripts.schedule_anydesk_clean import (
            get_schedule_status,
            install_weekly_schedule,
            install_daily_schedule,
            uninstall_all,
        )
    except Exception:
        get_schedule_status = lambda: {"description": "Недоступно", "enabled": False}
        install_weekly_schedule = lambda: False
        install_daily_schedule = lambda: False
        uninstall_all = lambda: False

    sched_info = get_schedule_status()
    sched_label = tk.Label(
        card,
        text=f"⏰ Расписание автоочистки: {sched_info.get('description', 'Отключено')}",
        font=("Segoe UI", 9, "bold"),
        bg=theme["card"],
        fg="#00E5FF" if sched_info.get("enabled") else theme["gray"],
    )
    sched_label.pack(pady=3)

    btn_frame = tk.Frame(card, bg=theme["card"])
    btn_frame.pack(pady=4)

    def set_weekly():
        if install_weekly_schedule():
            sched_label.configure(text="⏰ Расписание: Пн 09:00 и Чт 17:30", fg="#00E5FF")
            status.configure(text="✓ Включено: Пн 09:00 и Чт 17:30", fg="#009246")

    def set_daily():
        if install_daily_schedule():
            sched_label.configure(text="⏰ Расписание: Каждый день в 09:00", fg="#00E5FF")
            status.configure(text="✓ Включено: Каждый день в 09:00", fg="#009246")

    def disable_sched():
        uninstall_all()
        sched_label.configure(text="⏰ Расписание: Отключено", fg=theme["gray"])
        status.configure(text="Расписание автоочистки отключено", fg=theme["gray"])

    b_weekly = tk.Button(
        btn_frame,
        text="Пн 09:00 + Чт 17:30",
        command=set_weekly,
        font=("Segoe UI", 8, "bold"),
        bg=theme.get("hover", "#222222"),
        fg=theme.get("text", "#FFFFFF"),
        relief="flat",
        cursor="hand2",
        padx=8,
        pady=4,
    )
    b_weekly.pack(side="left", padx=3)

    b_daily = tk.Button(
        btn_frame,
        text="Каждый день 09:00",
        command=set_daily,
        font=("Segoe UI", 8),
        bg=theme.get("hover", "#222222"),
        fg=theme.get("text", "#FFFFFF"),
        relief="flat",
        cursor="hand2",
        padx=8,
        pady=4,
    )
    b_daily.pack(side="left", padx=3)

    b_off = tk.Button(
        btn_frame,
        text="Отключить",
        command=disable_sched,
        font=("Segoe UI", 8),
        bg=theme.get("hover", "#222222"),
        fg=theme.get("text", "#FFFFFF"),
        relief="flat",
        cursor="hand2",
        padx=8,
        pady=4,
    )
    b_off.pack(side="left", padx=3)

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
        pady=(8, 5)
    )