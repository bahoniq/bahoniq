import tkinter as tk

from config import (
    APP_NAME,
    LIGHT,
)

from state import state

from services.settings_service import (
    load_theme,
)


# ============================================================
# START APPLICATION
# ============================================================

def start_app():
    """
    Запускает главное окно BahonIQ.
    """

    # --------------------------------------------------------
    # ROOT
    # --------------------------------------------------------

    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("bahoniq.workcenter.v2")
    except Exception:
        pass

    root = tk.Tk()
    # Скрываем окно до полной отрисовки интерфейса, чтобы не мелькал чёрный экран с белым квадратом
    root.withdraw()

    state.root = root

    from pathlib import Path
    assets_dir = Path(__file__).resolve().parent / "assets"
    ico_p = assets_dir / "icon.ico"
    png_p = assets_dir / "logo.png"

    if ico_p.is_file():
        try:
            root.iconbitmap(str(ico_p))
        except Exception:
            pass

    if png_p.is_file():
        try:
            from PIL import Image, ImageTk
            p_img = ImageTk.PhotoImage(Image.open(png_p).resize((32, 32)))
            root.iconphoto(True, p_img)
            root._app_icon_ref = p_img
        except Exception:
            pass


    # --------------------------------------------------------
    # WINDOW
    # --------------------------------------------------------

    root.title(
        APP_NAME
    )

    root.geometry(
        "1100x760"
    )

    root.minsize(
        950,
        680
    )

    root.configure(
        bg=LIGHT
    )


    # --------------------------------------------------------
    # MAXIMIZE
    # --------------------------------------------------------


    # --------------------------------------------------------
    # LOAD SETTINGS
    # --------------------------------------------------------

    load_theme()


    # --------------------------------------------------------
    # MAIN WINDOW
    # --------------------------------------------------------

    from app.main_window import MainWindow


    MainWindow(
        root
    )

    # Дорисовываем все виджеты в скрытом окне и только затем показываем его развёрнутым
    root.update_idletasks()
    try:
        root.state("zoomed")
    except Exception:
        pass
    root.update_idletasks()
    root.deiconify()
    root.lift()
    root.update()


    # --------------------------------------------------------
    # START LOOP
    # --------------------------------------------------------

    root.mainloop()