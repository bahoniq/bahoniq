import os
import shutil
import tkinter as tk
from tkinter import messagebox

from services.settings_service import get_theme


# ============================================================
# BAHONIQ — CLEANUP
# ============================================================


def get_temp_folders():

    folders = []

    user_temp = os.environ.get("TEMP")

    if user_temp:
        folders.append(user_temp)

    windows_temp = os.environ.get("TMP")

    if windows_temp and windows_temp not in folders:
        folders.append(windows_temp)

    system_temp = os.path.join(
        os.environ.get(
            "SystemRoot",
            r"C:\Windows"
        ),
        "Temp"
    )

    if system_temp not in folders:
        folders.append(system_temp)

    return folders


# ============================================================
# DELETE
# ============================================================

def delete_item(path):

    try:

        if os.path.isdir(path):

            shutil.rmtree(
                path,
                ignore_errors=True
            )

        else:

            os.remove(path)

        return True

    except Exception:

        return False


# ============================================================
# CLEAN FOLDER
# ============================================================

def clean_folder(folder):

    deleted = 0
    skipped = 0

    if not os.path.exists(folder):
        return deleted, skipped

    try:

        items = os.listdir(folder)

    except Exception:

        return deleted, skipped

    for item in items:

        full_path = os.path.join(
            folder,
            item
        )

        if delete_item(full_path):

            deleted += 1

        else:

            skipped += 1

    return deleted, skipped


# ============================================================
# CLEAN TEMP
# ============================================================

def clean_temp():

    total_deleted = 0
    total_skipped = 0

    for folder in get_temp_folders():

        deleted, skipped = clean_folder(
            folder
        )

        total_deleted += deleted
        total_skipped += skipped

    return (
        total_deleted,
        total_skipped
    )


# ============================================================
# OPEN CLEANUP
# ============================================================

def open_cleanup(parent):

    theme = get_theme()


    window = tk.Toplevel(
        parent
    )

    window.title(
        "BahonIQ — Очистка"
    )

    window.geometry(
        "560x360"
    )

    window.minsize(
        560,
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
        text="🧹  Очистка",
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
            "Очистка временных файлов Windows\n\n"
            "BahonIQ удалит временные файлы и папки,\n"
            "которые больше не используются системой.\n\n"
            "Занятые Windows файлы будут автоматически пропущены."
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
        pady=(28, 15)
    )


    # ========================================================
    # STATUS
    # ========================================================

    status = tk.Label(
        card,
        text="Готово к очистке",
        font=(
            "Segoe UI",
            10,
            "bold"
        ),
        bg=theme["card"],
        fg=theme["text"]
    )

    status.pack(
        pady=8
    )


    # ========================================================
    # CLEAN
    # ========================================================

    def start_cleanup():

        answer = messagebox.askyesno(
            "Очистка",
            (
                "Очистить временные файлы Windows?\n\n"
                "Занятые системой файлы удалены не будут."
            ),
            parent=window
        )

        if not answer:
            return


        status.configure(
            text="⏳ Выполняется очистка...",
            fg=theme["text"]
        )

        window.update_idletasks()


        try:

            deleted, skipped = clean_temp()


            status.configure(
                text=(
                    f"✓ Очистка завершена\n\n"
                    f"Удалено объектов: {deleted}\n"
                    f"Пропущено: {skipped}"
                ),
                fg="#009246"
            )


        except Exception as e:

            status.configure(
                text="Ошибка очистки",
                fg="#E10600"
            )

            messagebox.showerror(
                "Ошибка",
                f"Не удалось выполнить очистку:\n\n{e}",
                parent=window
            )


    clean_button = tk.Button(
        card,
        text="🧹  Очистить",
        command=start_cleanup,
        font=(
            "Segoe UI",
            11,
            "bold"
        ),
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=35,
        pady=11,
        bg="#009246",
        fg="#FFFFFF",
        activebackground="#007A3A",
        activeforeground="#FFFFFF"
    )

    clean_button.pack(
        pady=10
    )