from config import (
    BAHONIQ_FOLDER,
    THEME_FILE,
    DAY_THEME,
    NIGHT_THEME,
)

from state import state


# ============================================================
# THEME
# ============================================================

def get_theme():
    """
    Возвращает словарь текущей темы.
    """

    if state.current_theme == "night":
        return NIGHT_THEME

    return DAY_THEME


# ============================================================
# THEME VALUE
# ============================================================

def theme_value(name):
    """
    Возвращает конкретное значение текущей темы.

    Примеры:

        theme_value("bg")
        theme_value("text")
        theme_value("card")
    """

    return get_theme()[name]


# ============================================================
# LOAD THEME
# ============================================================

def load_theme():
    """
    Загружает сохранённую тему из theme.txt.
    """

    try:

        if THEME_FILE.exists():

            saved_theme = (
                THEME_FILE
                .read_text(
                    encoding="utf-8"
                )
                .strip()
                .lower()
            )

            if saved_theme in (
                "day",
                "night",
            ):

                state.current_theme = saved_theme

    except Exception:

        # Если файл отсутствует,
        # повреждён или недоступен,
        # оставляем дневную тему.

        state.current_theme = "day"


# ============================================================
# SAVE THEME
# ============================================================

def save_theme():
    """
    Сохраняет текущую тему.
    """

    try:

        BAHONIQ_FOLDER.mkdir(
            parents=True,
            exist_ok=True,
        )

        THEME_FILE.write_text(
            state.current_theme,
            encoding="utf-8",
        )

    except Exception:

        # Ошибка сохранения темы
        # не должна ломать приложение.

        pass


# ============================================================
# TOGGLE THEME
# ============================================================

def toggle_theme():
    """
    Переключает тему:

        day -> night
        night -> day

    После переключения
    сохраняет выбор пользователя.
    """

    if state.current_theme == "day":

        state.current_theme = "night"

    else:

        state.current_theme = "day"

    save_theme()