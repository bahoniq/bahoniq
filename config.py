from pathlib import Path


# ============================================================
# APPLICATION
# ============================================================

APP_NAME = "BahonIQ — Work Center"


# ============================================================
# PATHS
# ============================================================

DESKTOP = Path.home() / "Desktop"

DOWNLOADS = Path.home() / "Downloads"

DOCUMENTS = Path.home() / "Documents"


# ============================================================
# BAHONIQ DATA
# ============================================================

BAHONIQ_FOLDER = (
    Path.home()
    / "AppData"
    / "Local"
    / "BahonIQ"
)


NOTES_FILE = (
    BAHONIQ_FOLDER
    / "notes.txt"
)


THEME_FILE = (
    BAHONIQ_FOLDER
    / "theme.txt"
)


# ============================================================
# INSTRUCTIONS
# ============================================================

INSTRUCTIONS_FOLDER = (
    DESKTOP
    / "Инструкции"
)


# ============================================================
# ANYDESK
# ============================================================

ANYDESK_FOLDER = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "AnyDesk"
)


# ============================================================
# IGNORE FILES
# ============================================================

IGNORE_FILES = {
    "rabochiy_zapusk.py",
    "start_ccu.bat",
}


# ============================================================
# SYSTEMS
# ============================================================

SYSTEMS = [

    (
        "🎓",
        "Platonus",
        "https://platonus.kaznmu.edu.kz/"
    ),

    (
        "🛠",
        "Поддержка",
        "https://support.platonus.kz/"
    ),

    (
        "✈",
        "Telegram",
        "https://web.telegram.org/"
    ),

    (
        "💬",
        "WhatsApp",
        "https://web.whatsapp.com/"
    ),

    (
        "✉",
        "Gmail",
        "https://mail.google.com/mail/u/0/#inbox"
    ),

    (
        "🏢",
        "Salem Office",
        "https://salemoffice.kaznmu.edu.kz/sign-in"
    ),
]


# ============================================================
# COLORS
# ============================================================

GREEN = "#00B8D4"

GREEN_DARK = "#0097B2"

GREEN_LIGHT = "#E6FAFD"


WHITE = "#FFFFFF"


RED = "#E10600"

RED_DARK = "#B30500"

RED_LIGHT = "#FDECEC"


DARK = "#172033"

TEXT = "#172033"

GRAY = "#667085"

LIGHT = "#F5F7F8"

BORDER = "#E3E7EB"


BLUE = "#2563EB"

BLUE_LIGHT = "#EFF6FF"


HOVER = "#F0F3F5"


GOLD = "#C9A227"

GOLD_LIGHT = "#FBF6E5"


# ============================================================
# THEMES
# ============================================================

DAY_THEME = {

    # Violet: премиальная графитово-фиолетовая тема. Имя DAY_THEME
    # сохранено только ради совместимости со старой конфигурацией.
    "bg": "#171425",

    "card": "#29233D",

    "text": "#F7F3FF",

    "gray": "#BDB2D7",

    "border": "#4A3D68",

    "hover": "#352D4D",

    "input": "#211B32",
}


NIGHT_THEME = {

    "bg": "#101722",

    "card": "#182231",

    "text": "#F1F5F9",

    "gray": "#AAB4C3",

    "border": "#2A3748",

    "hover": "#243244",

    "input": "#111B28",
}


# ============================================================
# RGB
# ============================================================

RGB_SPEEDS = [
    80,
    50,
    30,
    15,
]


RGB_SPEED_NAMES = [
    "Медленно",
    "Нормально",
    "Быстро",
    "Турбо",
]


RGB_MODES = [
    "Rainbow",
    "Scan",
    "Wave",
    "Comet",
]
# BahonIQ — Git test
