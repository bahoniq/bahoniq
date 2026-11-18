
import tkinter as tk
from pathlib import Path
from datetime import datetime
from scripts.version import VERSION

from config import (
    APP_NAME,
    SYSTEMS,
    WHITE,
    GREEN,
    GREEN_DARK,
    RED,
    BLUE,
    DAY_THEME,
    NIGHT_THEME,
)

from state import state

from services.settings_service import (
    get_theme,
    toggle_theme,
)

from ui.rgb import (
    rgb_toggle,
    rgb_speed_change,
    rgb_mode_change,
    rgb_initialize,
)

from modules.notes import open_notes
from services.cleanup import open_cleanup
from services.anydesk_service import open_anydesk
from modules.duplicate_window import open_duplicates
from modules.pdf_center import open_pdf_center
from modules.report_studio import open_report_studio
from modules.ticket_writer import open_ticket_writer
from modules.instruction_generator import open_instruction_generator
from modules.phonebook import open_phonebook


# ============================================================
# ITALY COLORS
# ============================================================

ITALY_GREEN = "#009246"
ITALY_WHITE = "#FFFFFF"
ITALY_RED = "#CE2B37"

ITALY_GREEN_DARK = "#007A3D"
ITALY_RED_DARK = "#A91F2D"

ITALY_GREEN_LIGHT = "#E8F5EE"
ITALY_RED_LIGHT = "#F9E8EA"

ITALY_BORDER = "#D9E2DC"

SURFACE = "#FFFFFF"
SURFACE_SOFT = "#F6F8F7"
TEXT_PRIMARY = "#17352A"
TEXT_MUTED = "#66756D"
CARD_BORDER = "#DDE5E1"
CARD_HOVER = "#F0F7F3"


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow:

    def __init__(self, root):
        self.root = root
        state.root = root
        self.tool_cards = []
        self.system_buttons = []

        self.apply_window_branding()

        self.build()
        self.update_clock()
        self.apply_theme()
        rgb_initialize()

    def apply_window_branding(self):
        """Подключает фирменную иконку окна и панели задач."""
        try:
            import ctypes
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("bahoniq.workcenter.v2")
            except Exception:
                pass

            project_dir = Path(__file__).resolve().parent.parent
            icon_path = project_dir / "assets" / "icon.ico"
            if icon_path.is_file():
                try:
                    self.root.iconbitmap(str(icon_path))
                except Exception:
                    pass

            logo_path = project_dir / "assets" / "logo.png"
            if logo_path.is_file():
                try:
                    from PIL import Image, ImageTk
                    p_img = ImageTk.PhotoImage(Image.open(logo_path).resize((32, 32), Image.Resampling.LANCZOS))
                    self.root.iconphoto(True, p_img)
                    self._app_icon_ref = p_img
                except Exception:
                    pass
        except Exception:
            pass

    # ========================================================
    # BUILD
    # ========================================================

    def build(self):
        self.root.configure(bg=get_theme()["bg"])

        self.create_italy_header_flag()
        self.create_rgb_canvases()
        self.create_header()
        self.create_main_area()
        self.create_footer()

    # ========================================================
    # ITALIAN FLAG HEADER
    # ========================================================

    def create_italy_header_flag(self):
        self.italy_flag = tk.Frame(
            self.root,
            height=4,
            bd=0,
        )

        self.italy_flag.pack(fill="x", side="top")
        self.italy_flag.pack_propagate(False)

        self.flag_green = tk.Frame(
            self.italy_flag,
            bg=ITALY_GREEN,
        )
        self.flag_green.pack(side="left", fill="both", expand=True)

        self.flag_white = tk.Frame(
            self.italy_flag,
            bg=ITALY_WHITE,
        )
        self.flag_white.pack(side="left", fill="both", expand=True)

        self.flag_red = tk.Frame(
            self.italy_flag,
            bg=ITALY_RED,
        )
        self.flag_red.pack(side="left", fill="both", expand=True)

    # ========================================================
    # RGB CANVASES
    # ========================================================

    def create_rgb_canvases(self):
        self.rgb_canvas = tk.Canvas(
            self.root,
            height=7,
            bd=0,
            highlightthickness=0,
        )
        self.rgb_canvas.pack(fill="x", side="top")

        self.rgb_canvas_bottom = tk.Canvas(
            self.root,
            height=4,
            bd=0,
            highlightthickness=0,
        )

        state.rgb_canvas = self.rgb_canvas
        state.rgb_canvas_bottom = self.rgb_canvas_bottom

    # ========================================================
    # HEADER
    # ========================================================

    def create_header(self):
        theme = get_theme()

        self.header = tk.Frame(
            self.root,
            height=72,
            bd=0,
            bg=theme["bg"],
        )
        self.header.pack(
            fill="x",
            padx=20,
            pady=(8, 10),
        )
        self.header.pack_propagate(False)

        state.header = self.header

        # BRAND
        self.brand_frame = tk.Frame(self.header, bd=0, bg=theme["bg"])
        self.brand_frame.pack(side="left", fill="y")
        state.brand_frame = self.brand_frame

        self.logo = tk.Label(
            self.brand_frame,
            text="BahonIQ",
            font=("Segoe UI", 22, "bold"),
            bg=theme["bg"],
            fg=ITALY_GREEN_DARK,
            bd=0,
        )
        self.logo.pack(side="left", padx=(0, 4), pady=(6, 0))

        self.logo_subtitle = tk.Label(
            self.brand_frame,
            text="|  WORK CENTER",
            font=("Segoe UI", 11, "bold"),
            bg=theme["bg"],
            fg=theme.get("gray", "#7E90A2"),
            bd=0,
        )
        self.logo_subtitle.pack(side="left", padx=4, pady=(10, 0))

        # RIGHT CONTROLS
        self.controls = tk.Frame(self.header, bd=0, bg=theme["bg"])
        self.controls.pack(side="right", fill="y")

        # ЧАСЫ
        self.clock_label = tk.Label(
            self.controls,
            text="00:00:00",
            font=("Segoe UI", 11, "bold"),
            bg=theme["bg"],
            fg="#68716C",
            bd=0,
        )
        self.clock_label.pack(side="left", padx=(0, 10), pady=(8, 0))
        state.clock_label = self.clock_label

        # КНОПКА ПЕРЕКЛЮЧЕНИЯ AQUA / VIOLET
        self.theme_button = tk.Button(
            self.controls,
            text="☾ Violet",
            command=self.change_theme,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
            bg=theme.get("card", "#183153"),
            fg=theme.get("text", "#ffffff"),
            activebackground=theme.get("hover", "#29415f"),
            activeforeground=theme.get("text", "#ffffff"),
        )
        self.theme_button.pack(side="left", padx=4, pady=(4, 0))
        state.theme_button = self.theme_button

        # RGB КНОПКИ
        self.rgb_button = tk.Button(
            self.controls,
            text="🇮🇹 RGB: OFF",
            command=rgb_toggle,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
            bg=theme.get("card", "#183153"),
            fg=theme.get("text", "#ffffff"),
            activebackground=theme.get("hover", "#29415f"),
            activeforeground=theme.get("text", "#ffffff"),
        )
        self.rgb_button.pack(side="left", padx=4, pady=(4, 0))
        state.rgb_button = self.rgb_button

        self.rgb_speed_button = tk.Button(
            self.controls,
            text="⚡ Нормально",
            command=rgb_speed_change,
            font=("Segoe UI", 9),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=8,
            bg=theme.get("card", "#183153"),
            fg=theme.get("text", "#ffffff"),
            activebackground=theme.get("hover", "#29415f"),
            activeforeground=theme.get("text", "#ffffff"),
        )
        self.rgb_speed_button.pack(side="left", padx=4, pady=(4, 0))
        state.rgb_speed_button = self.rgb_speed_button

        self.rgb_mode_button = tk.Button(
            self.controls,
            text="🎨 Rainbow",
            command=rgb_mode_change,
            font=("Segoe UI", 9),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=8,
            bg=theme.get("card", "#183153"),
            fg=theme.get("text", "#ffffff"),
            activebackground=theme.get("hover", "#29415f"),
            activeforeground=theme.get("text", "#ffffff"),
        )
        self.rgb_mode_button.pack(side="left", padx=4, pady=(4, 0))
        state.rgb_mode_button = self.rgb_mode_button

    # ========================================================
    # MAIN AREA
    # ========================================================

    def _create_main_area_legacy(self):
        self.main = tk.Frame(self.root, bd=0)
        self.main.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 15),
        )
        state.main = self.main

        # LEFT
        left = tk.Frame(
            self.main,
            width=350,
            bd=0,
        )
        left.pack(
            side="left",
            fill="y",
            padx=(0, 10),
        )
        left.pack_propagate(False)

        # SYSTEMS CARD
        self.systems_card = tk.Frame(
            left,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        self.systems_card.pack(fill="both", expand=True)
        state.systems_card = self.systems_card

        self.systems_accent = tk.Frame(
            self.systems_card,
            height=5,
            bg=ITALY_GREEN,
            bd=0,
        )
        self.systems_accent.pack(fill="x")
        self.systems_accent.pack_propagate(False)

        self.systems_header = tk.Label(
            self.systems_card,
            text="🌐  Системы",
            font=("Segoe UI", 15, "bold"),
            anchor="w",
            padx=18,
            pady=15,
            bd=0,
        )
        self.systems_header.pack(fill="x")
        state.systems_header = self.systems_header

        # SYSTEM BUTTONS
        systems_frame = tk.Frame(
            self.systems_card,
            bd=0,
        )
        systems_frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=8,
        )

        for index, (icon, name, url) in enumerate(SYSTEMS):
            button = tk.Button(
                systems_frame,
                text=f"{icon}   {name}",
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=15,
                pady=11,
                command=lambda u=url: self.open_url(u),
            )
            button.pack(fill="x", pady=3)

            button.italy_system_button = True
            button.italy_accent = (
                ITALY_GREEN if index % 2 == 0 else ITALY_RED
            )

        # QUICK LAUNCH
        self.quick_launch_button = tk.Button(
            self.systems_card,
            text="🚀  Запустить все системы",
            command=self.open_all_systems,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=15,
            pady=11,
            bg=ITALY_RED,
            fg=ITALY_WHITE,
            activebackground=ITALY_RED_DARK,
            activeforeground=ITALY_WHITE,
        )
        self.quick_launch_button.pack(
            fill="x",
            padx=12,
            pady=(8, 12),
        )

        # RIGHT
        self.right = tk.Frame(self.main, bd=0)
        self.right.pack(
            side="left",
            fill="both",
            expand=True,
        )
        state.right = self.right

        # WELCOME CARD
        self.welcome_card = tk.Frame(
            self.right,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        self.welcome_card.pack(
            fill="x",
            pady=(0, 12),
        )
        state.welcome_card = self.welcome_card

        self.welcome_inner = tk.Frame(
            self.welcome_card,
            bd=0,
        )
        self.welcome_inner.pack(
            fill="x",
            padx=25,
            pady=22,
        )
        state.welcome_inner = self.welcome_inner

        self.welcome_title = tk.Label(
            self.welcome_inner,
            text="Добро пожаловать в BahonIQ",
            font=("Segoe UI", 22, "bold"),
            anchor="w",
            bd=0,
        )
        self.welcome_title.pack(anchor="w")

        self.welcome_text = tk.Label(
            self.welcome_inner,
            text="Рабочий центр для ежедневных задач и систем поддержки.",
            font=("Segoe UI", 11),
            anchor="w",
            bd=0,
        )
        self.welcome_text.pack(anchor="w", pady=(5, 0))

        # ITALIAN DECORATIVE LINE
        self.welcome_flag = tk.Frame(
            self.welcome_inner,
            height=4,
            bd=0,
        )
        self.welcome_flag.pack(
            fill="x",
            pady=(18, 0),
        )
        self.welcome_flag.pack_propagate(False)

        tk.Frame(
            self.welcome_flag,
            bg=ITALY_GREEN,
        ).pack(side="left", fill="both", expand=True)

        tk.Frame(
            self.welcome_flag,
            bg=ITALY_WHITE,
        ).pack(side="left", fill="both", expand=True)

        tk.Frame(
            self.welcome_flag,
            bg=ITALY_RED,
        ).pack(side="left", fill="both", expand=True)

        state.welcome_line = self.welcome_flag

        # TOOLS
        self.tools_frame = tk.Frame(self.right, bd=0)
        self.tools_frame.pack(
            fill="both",
            expand=True,
        )
        state.tools_frame = self.tools_frame

        self.tools_title = tk.Label(
            self.tools_frame,
            text="🛠  Инструменты",
            font=("Segoe UI", 15, "bold"),
            anchor="w",
            bd=0,
        )
        self.tools_title.pack(anchor="w", pady=(3, 10))
        state.tools_title = self.tools_title

        # TOOL GRID
        tools_grid = tk.Frame(self.tools_frame, bd=0)
        tools_grid.pack(fill="both", expand=True)

        tools = [
            ("✦", "Ticket Writer AI"),
            ("▤", "Instruction Generator AI"),
            ("📝", "Заметки"),
            ("📊", "Excel AI"),
            ("🧹", "Очистка"),
            ("🔍", "Дубликаты"),
            ("🖥", "AnyDesk"),
            ("📄", "PDF Center"),
            ("📑", "ANALYTICS AI"),
        ]

        for index, (icon, name) in enumerate(tools):
            row = index // 3
            column = index % 3

            accent_colors = [
                "#D9F0E3",
                "#F7F8F8",
                "#F2DADB",
            ]
            accent_color = accent_colors[column]

            button = tk.Button(
                tools_grid,
                text=f"{icon}\n{name}",
                font=("Segoe UI", 11, "bold"),
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=10,
                pady=18,
                bg=accent_color,
                fg="#26312B",
                activebackground=accent_color,
                activeforeground="#26312B",
                command=lambda n=name: self.open_tool(n),
            )
            button.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=5,
                pady=5,
            )

            button.italy_tool_button = True
            button.italy_accent = [
                ITALY_GREEN,
                "#8A938E",
                ITALY_RED,
            ][column]

        for column in range(3):
            tools_grid.grid_columnconfigure(column, weight=1)

        for row in range((len(tools) + 2) // 3):
            tools_grid.grid_rowconfigure(row, weight=1)

    # ========================================================
    # MODERN MAIN AREA (v2)
    # ========================================================

    def create_main_area(self):
        """Компактная главная панель с информативными карточками модулей."""
        theme = get_theme()

        self.main = tk.Frame(self.root, bd=0, bg=theme["bg"])
        self.main.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        state.main = self.main

        # LEFT SIDEBAR
        left = tk.Frame(self.main, width=286, bd=0, bg=theme["bg"])
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)

        self.systems_card = tk.Frame(
            left,
            bd=0,
            bg=theme["card"],
            highlightthickness=1,
            highlightbackground=theme["border"],
        )
        self.systems_card.pack(fill="both", expand=True)
        state.systems_card = self.systems_card

        self.systems_accent = tk.Frame(self.systems_card, height=4, bg=ITALY_GREEN, bd=0)
        self.systems_accent.pack(fill="x")

        self.systems_header = tk.Label(
            self.systems_card,
            text="СИСТЕМЫ",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            padx=18,
            pady=16,
            bg=theme["card"],
            fg=ITALY_GREEN_DARK,
            bd=0,
        )
        self.systems_header.pack(fill="x")
        state.systems_header = self.systems_header

        systems_frame = tk.Frame(self.systems_card, bd=0, bg=theme["card"])
        systems_frame.pack(fill="x", expand=False, padx=10, pady=(0, 4))

        self.system_buttons = []
        for icon, name, url in SYSTEMS:
            button = tk.Button(
                systems_frame,
                text=f"{icon}   {name}",
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=12,
                pady=10,
                bg=theme["card"],
                fg=theme["text"],
                activebackground=theme["hover"],
                activeforeground=ITALY_GREEN_DARK,
                command=lambda u=url: self.open_url(u),
            )
            button.pack(fill="x", pady=2)
            button.italy_system_button = True
            button.italy_accent = ITALY_GREEN
            self.system_buttons.append(button)

        # КНОПКА ЗАПУСКА СИСТЕМ (ПРИЖАТА К НИЗУ САЙДБАРА)
        self.quick_launch_button = tk.Button(
            self.systems_card,
            text="↗  Открыть все системы",
            command=self.open_all_systems,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=15,
            pady=12,
            bg=ITALY_RED,
            fg=ITALY_WHITE,
            activebackground=ITALY_RED_DARK,
            activeforeground=ITALY_WHITE,
        )
        self.quick_launch_button.pack(
            side="bottom",
            fill="x",
            padx=12,
            pady=(8, 12),
        )

        # ПОЛУПРОЗРАЧНЫЙ СИЛУЭТ ИКОНКИ (ВОДЯНОЙ ЗНАК 10-15%, ЗАПОЛНЯЕТ ВСЮ ОБЛАСТЬ)
        self.watermark_frame = tk.Frame(self.systems_card, bd=0, bg=theme["card"])
        self.watermark_frame.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        self.sidebar_watermark_lbl = tk.Label(
            self.watermark_frame,
            bg=theme["card"],
            bd=0,
        )
        self.sidebar_watermark_lbl.pack(expand=True)
        self.update_sidebar_watermark(theme["card"])

        # RIGHT CONTENT
        self.right = tk.Frame(self.main, bd=0, bg=theme["bg"])
        self.right.pack(side="left", fill="both", expand=True)
        state.right = self.right

        self.welcome_card = tk.Frame(
            self.right,
            bd=0,
            bg=theme["card"],
            highlightthickness=1,
            highlightbackground=theme["border"],
            height=104,
        )
        self.welcome_card.pack(fill="x", pady=(0, 12))
        self.welcome_card.pack_propagate(False)
        state.welcome_card = self.welcome_card

        self.welcome_accent = tk.Frame(self.welcome_card, width=6, bg=ITALY_GREEN, bd=0)
        self.welcome_accent.pack(side="left", fill="y")

        self.welcome_inner = tk.Frame(self.welcome_card, bd=0, bg=theme["card"])
        self.welcome_inner.pack(side="left", fill="both", expand=True, padx=22, pady=16)
        state.welcome_inner = self.welcome_inner

        self.welcome_title = tk.Label(
            self.welcome_inner,
            text="Добро пожаловать в BahonIQ",
            font=("Segoe UI", 19, "bold"),
            anchor="w",
            bg=theme["card"],
            fg=ITALY_GREEN_DARK,
            bd=0,
        )
        self.welcome_title.pack(anchor="w")

        self.welcome_text = tk.Label(
            self.welcome_inner,
            text="Все рабочие инструменты и системы в одном центре.",
            font=("Segoe UI", 10),
            anchor="w",
            bg=theme["card"],
            fg=theme["gray"],
            bd=0,
        )
        self.welcome_text.pack(anchor="w", pady=(5, 0))

        self.welcome_status = tk.Label(
            self.welcome_card,
            text="●  СИСТЕМА ГОТОВА",
            font=("Segoe UI", 9, "bold"),
            bg=theme["card"],
            fg=ITALY_GREEN,
            padx=22,
        )
        self.welcome_status.pack(side="right", fill="y")

        # TOOL SECTION
        self.tools_frame = tk.Frame(self.right, bd=0, bg=theme["bg"])
        self.tools_frame.pack(fill="both", expand=True)
        state.tools_frame = self.tools_frame

        self.tools_heading = tk.Frame(self.tools_frame, bd=0, bg=theme["bg"])
        self.tools_heading.pack(fill="x", pady=(2, 9))
        self.tools_title = tk.Label(
            self.tools_heading,
            text="Рабочие инструменты",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
            bg=theme["bg"],
            fg=theme["text"],
            bd=0,
        )
        self.tools_title.pack(side="left")
        state.tools_title = self.tools_title

        self.tools_grid = tk.Frame(self.tools_frame, bd=0, bg=theme["bg"])
        self.tools_grid.pack(fill="both", expand=True)

        tools = [
            ("✦", "Ticket Writer AI", "Название и описание обращения", ITALY_GREEN),
            ("▤", "Instruction Generator AI", "Инструкции из текста и скриншотов", ITALY_GREEN),
            ("✎", "Заметки", "Быстрые записи и идеи", "#597A91"),
            ("▤", "Excel AI", "Умная обработка таблиц", ITALY_RED),
            ("📖", "Platonus Wiki AI", "База инструкций и умный поиск Platonus", "#0284C7"),
            ("⌕", "Дубликаты", "Поиск повторяющихся файлов", "#6F63A8"),
            ("◉", "AnyDesk", "Удалённая техническая поддержка", "#D14B56"),
            ("▧", "PDF Center", "Объединение и обработка PDF", "#2D7F79"),
            ("▥", "ANALYTICS AI", "Отчёты, аналитика и презентации", "#245E8A"),
            ("☎", "Телефонный справочник", "Внутренние номера и контакты", "#3A8D7C"),
            ("⌘", "Code Academy", "Python, SQL и архитектура BahonIQ", "#7354A5"),
            ("🎨", "Design Academy Studio", "UI/UX дизайн и векторная графика", "#E879F9"),
            ("⊞", "Excel Academy Studio", "Офисные и IT-задачи, формулы и анализ", "#10B981"),
        ]

        self.tool_cards = []
        for index, (icon, name, description, accent) in enumerate(tools):
            row, column = divmod(index, 2)
            self.create_tool_card(
                self.tools_grid, row, column, icon, name, description, accent,
                command=lambda n=name: self.open_tool(n),
            )

        for column in range(2):
            self.tools_grid.grid_columnconfigure(column, weight=1, uniform="tool")
        for row in range((len(tools) + 1) // 2):
            self.tools_grid.grid_rowconfigure(row, weight=1, uniform="toolrow")

    def create_tool_card(self, parent, row, column, icon, name, description, accent, command):
        theme = get_theme()
        frame = tk.Frame(
            parent,
            bd=0,
            bg=theme["card"],
            highlightthickness=1,
            highlightbackground=theme["border"],
            cursor="hand2",
        )
        frame.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)

        accent_bar = tk.Frame(frame, width=5, bg=accent, bd=0, cursor="hand2")
        accent_bar.pack(side="left", fill="y")

        icon_box = tk.Label(
            frame,
            text=icon,
            font=("Segoe UI Symbol", 24, "bold"),
            width=3,
            bg=theme["card"],
            fg=accent,
            bd=0,
            cursor="hand2",
        )
        icon_box.pack(side="left", fill="y", padx=(14, 8))

        text_box = tk.Frame(frame, bd=0, bg=theme["card"], cursor="hand2")
        text_box.pack(side="left", fill="both", expand=True, pady=15)

        title = tk.Label(
            text_box,
            text=name,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            bg=theme["card"],
            fg=theme["text"],
            bd=0,
            cursor="hand2",
        )
        title.pack(fill="x")

        subtitle = tk.Label(
            text_box,
            text=description,
            font=("Segoe UI", 9),
            anchor="w",
            bg=theme["card"],
            fg=theme["gray"],
            bd=0,
            cursor="hand2",
        )
        subtitle.pack(fill="x", pady=(5, 0))

        arrow = tk.Label(
            frame,
            text="›",
            font=("Segoe UI", 20),
            bg=theme["card"],
            fg=theme["gray"],
            padx=15,
            bd=0,
            cursor="hand2",
        )
        arrow.pack(side="right", fill="y")

        card = {
            "frame": frame,
            "accent": accent_bar,
            "widgets": [frame, icon_box, text_box, title, subtitle, arrow],
            "title": title,
            "subtitle": subtitle,
            "icon": icon_box,
            "arrow": arrow,
            "accent_color": accent,
            "command": command,
        }
        self.tool_cards.append(card)

        for widget in card["widgets"] + [accent_bar]:
            widget.bind("<Button-1>", lambda event, c=command: c())
            widget.bind("<Enter>", lambda event, item=card: self.set_tool_card_hover(item, True))
            widget.bind("<Leave>", lambda event, item=card: self.set_tool_card_hover(item, False))

    def set_tool_card_hover(self, card, active):
        theme = get_theme()
        background = theme["hover"] if active else theme["card"]
        for widget in card["widgets"]:
            try:
                widget.configure(bg=background)
            except tk.TclError:
                pass
        card["frame"].configure(
            highlightbackground=card["accent_color"] if active else theme["border"]
        )
        card["arrow"].configure(fg=card["accent_color"] if active else theme["gray"])

    # ========================================================
    # FOOTER
    # ========================================================

    def _create_footer_legacy(self):
        self.footer = tk.Frame(
            self.root,
            height=38,
            bd=0,
        )
        self.footer.pack(
            fill="x",
            padx=20,
            pady=(0, 10),
        )
        self.footer.pack_propagate(False)
        state.footer = self.footer

        # ITALIAN FLAG
        self.footer_flag = tk.Frame(
            self.footer,
            width=90,
            height=22,
            bd=0,
        )
        self.footer_flag.pack(side="left", pady=5)
        self.footer_flag.pack_propagate(False)

        tk.Frame(
            self.footer_flag,
            bg=ITALY_GREEN,
        ).pack(side="left", fill="both", expand=True)

        tk.Frame(
            self.footer_flag,
            bg=ITALY_WHITE,
        ).pack(side="left", fill="both", expand=True)

        tk.Frame(
            self.footer_flag,
            bg=ITALY_RED,
        ).pack(side="left", fill="both", expand=True)

        state.footer_flag = self.footer_flag

        # FOOTER TEXT WITH CENTRALIZED VERSION
        self.footer_text = tk.Label(
            self.footer,
            text=f"BahonIQ — Work Center   •   Version {VERSION}   •   Ready",
            font=("Segoe UI", 9, "bold"),
            fg="#68716C",
            bd=0,
        )
        self.footer_text.pack(side="left", padx=10)

        # ABOUT BUTTON
        self.about_button = tk.Button(
            self.footer,
            text="О программе",
            command=self.show_about,
            font=("Segoe UI", 9, "bold"),
            bg=ITALY_GREEN,
            fg=ITALY_WHITE,
            activebackground=ITALY_GREEN_DARK,
            activeforeground=ITALY_WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
        )
        self.about_button.pack(side="right", padx=(5, 0))

    def create_footer(self):
        """Компактная строка состояния без декоративных пустых блоков."""
        theme = get_theme()
        self.footer = tk.Frame(self.root, height=34, bd=0, bg=theme["bg"])
        self.footer.pack(fill="x", padx=20, pady=(0, 8))
        self.footer.pack_propagate(False)
        state.footer = self.footer

        self.footer_status_dot = tk.Label(
            self.footer,
            text="●",
            font=("Segoe UI", 8),
            bg=theme["bg"],
            fg=ITALY_GREEN,
            bd=0,
        )
        self.footer_status_dot.pack(side="left")

        self.footer_text = tk.Label(
            self.footer,
            text=f"BahonIQ Work Center   ·   Версия {VERSION}   ·   Готов к работе",
            font=("Segoe UI", 9),
            bg=theme["bg"],
            fg=theme["gray"],
            bd=0,
        )
        self.footer_text.pack(side="left", padx=7)

        self.about_button = tk.Button(
            self.footer,
            text="О программе",
            command=self.show_about,
            font=("Segoe UI", 9, "bold"),
            bg=theme["bg"],
            fg=ITALY_GREEN_DARK,
            activebackground=theme["hover"],
            activeforeground=ITALY_GREEN_DARK,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
        )
        self.about_button.pack(side="right")

    # ========================================================
    # ABOUT
    # ========================================================

    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("О программе — BahonIQ")
        about.transient(self.root)
        about.resizable(False, False)

        theme = get_theme()
        bg = theme["bg"]
        fg = theme.get("text", "#26352C")

        about.configure(bg=bg)

        width = 420
        height = 290

        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - width
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - height
        ) // 2

        about.geometry(f"{width}x{height}+{x}+{y}")

        # ITALIAN FLAG
        flag = tk.Frame(about, height=10, bd=0)
        flag.pack(fill="x")
        flag.pack_propagate(False)

        tk.Frame(flag, bg=ITALY_GREEN).pack(
            side="left", fill="both", expand=True
        )
        tk.Frame(flag, bg=ITALY_WHITE).pack(
            side="left", fill="both", expand=True
        )
        tk.Frame(flag, bg=ITALY_RED).pack(
            side="left", fill="both", expand=True
        )

        tk.Label(
            about,
            text="BahonIQ",
            font=("Segoe UI", 23, "bold"),
            bg=bg,
            fg=ITALY_GREEN,
        ).pack(pady=(25, 3))

        tk.Label(
            about,
            text="Work Center",
            font=("Segoe UI", 12, "bold"),
            bg=bg,
            fg=fg,
        ).pack()

        tk.Label(
            about,
            text=f"Версия {VERSION}",
            font=("Segoe UI", 11),
            bg=bg,
            fg=fg,
        ).pack(pady=(15, 5))

        tk.Label(
            about,
            text="Рабочий центр для повседневных задач",
            font=("Segoe UI", 9),
            bg=bg,
            fg=fg,
        ).pack(pady=(0, 15))

        tk.Button(
            about,
            text="Закрыть",
            command=about.destroy,
            font=("Segoe UI", 10, "bold"),
            bg=ITALY_GREEN,
            fg=ITALY_WHITE,
            activebackground=ITALY_GREEN_DARK,
            activeforeground=ITALY_WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=24,
            pady=6,
        ).pack()

    # ========================================================
    # CLOCK
    # ========================================================

    def update_clock(self):
        if state.clock_label is None:
            return

        now = datetime.now()
        state.clock_label.configure(text=now.strftime("%H:%M:%S"))

        self.root.after(1000, self.update_clock)

    # ========================================================
    # CHANGE THEME
    # ========================================================

    def change_theme(self):
        toggle_theme()
        self.apply_theme()

    # ========================================================
    # APPLY THEME
    # ========================================================

    def apply_theme(self):
        theme = get_theme()
        self.root.configure(bg=theme["bg"])

        self.update_widget_colors(self.root, theme)

        # ITALIAN HEADER
        try:
            self.logo.configure(fg=ITALY_GREEN_DARK)
            self.logo_dot.configure(fg=ITALY_GREEN)
            self.logo_accent.configure(fg=ITALY_RED)
            self.logo_subtitle.configure(fg=theme["gray"])
            self.clock_label.configure(fg=theme["gray"])
        except Exception:
            pass

        # THEME BUTTON
        if state.theme_button is not None:
            if state.current_theme == "night":
                state.theme_button.configure(text="☾ Violet")
            else:
                state.theme_button.configure(text="◈ Aqua")

        # ITALIAN SPECIAL ELEMENTS
        try:
            if state.systems_card is not None:
                state.systems_card.configure(
                    bg=theme["card"],
                    highlightbackground=ITALY_BORDER,
                )

            if state.welcome_card is not None:
                state.welcome_card.configure(
                    bg=theme["card"],
                    highlightbackground=ITALY_BORDER,
                )

            if state.systems_header is not None:
                state.systems_header.configure(
                    fg=ITALY_GREEN_DARK,
                    bg=theme["card"],
                )

            if self.welcome_title is not None:
                self.welcome_title.configure(
                    fg=ITALY_GREEN_DARK,
                    bg=theme["card"],
                )

            if self.welcome_text is not None:
                self.welcome_text.configure(
                    bg=theme["card"],
                    fg=theme["text"],
                )

            if self.tools_title is not None:
                self.tools_title.configure(
                    fg=ITALY_RED_DARK,
                    bg=theme["card"],
                )

            self.footer.configure(bg=theme["bg"])
            self.footer_text.configure(
                bg=theme["bg"],
                fg=theme["gray"],
            )

            self.about_button.configure(
                bg=ITALY_GREEN,
                fg=ITALY_WHITE,
                activebackground=ITALY_GREEN_DARK,
                activeforeground=ITALY_WHITE,
            )

            # QUICK LAUNCH
            self.quick_launch_button.configure(
                bg=ITALY_RED,
                fg=ITALY_WHITE,
                activebackground=ITALY_RED_DARK,
                activeforeground=ITALY_WHITE,
            )

            # SYSTEM BUTTONS
            for child in self.systems_card.winfo_children():
                if isinstance(child, tk.Frame):
                    for button in child.winfo_children():
                        if (
                            isinstance(button, tk.Button)
                            and hasattr(button, "italy_system_button")
                        ):
                            accent = getattr(
                                button,
                                "italy_accent",
                                ITALY_GREEN,
                            )

                            button.configure(
                                bg=theme["card"],
                                fg=theme["text"],
                                activebackground=(
                                    ITALY_GREEN_LIGHT
                                    if accent == ITALY_GREEN
                                    else ITALY_RED_LIGHT
                                ),
                                activeforeground=accent,
                            )

        except Exception:
            pass

        # MODERN LAYOUT COLORS
        try:
            self.main.configure(bg=theme["bg"])
            self.right.configure(bg=theme["bg"])
            self.tools_frame.configure(bg=theme["bg"])
            self.tools_heading.configure(bg=theme["bg"])
            self.tools_grid.configure(bg=theme["bg"])
            self.tools_title.configure(bg=theme["bg"], fg=theme["text"])

            self.systems_card.configure(
                bg=theme["card"],
                highlightbackground=theme["border"],
            )
            self.systems_header.configure(bg=theme["card"], fg=ITALY_GREEN_DARK)
            self.welcome_card.configure(
                bg=theme["card"],
                highlightbackground=theme["border"],
            )
            self.welcome_inner.configure(bg=theme["card"])
            self.welcome_title.configure(bg=theme["card"], fg=ITALY_GREEN_DARK)
            self.welcome_text.configure(bg=theme["card"], fg=theme["gray"])
            self.welcome_status.configure(bg=theme["card"], fg=ITALY_GREEN)

            for button in self.system_buttons:
                button.configure(
                    bg=theme["card"],
                    fg=theme["text"],
                    activebackground=theme["hover"],
                    activeforeground=ITALY_GREEN_DARK,
                )

            for card in self.tool_cards:
                for widget in card["widgets"]:
                    widget.configure(bg=theme["card"])
                card["frame"].configure(highlightbackground=theme["border"])
                card["title"].configure(fg=theme["text"])
                card["subtitle"].configure(fg=theme["gray"])
                card["icon"].configure(fg=card["accent_color"])
                card["arrow"].configure(fg=theme["gray"])

            self.footer.configure(bg=theme["bg"])
            self.footer_status_dot.configure(bg=theme["bg"], fg=ITALY_GREEN)
            self.footer_text.configure(bg=theme["bg"], fg=theme["gray"])
            self.about_button.configure(
                bg=theme["bg"],
                fg=ITALY_GREEN_DARK,
                activebackground=theme["hover"],
                activeforeground=ITALY_GREEN_DARK,
            )

            # Обновление фонового водяного знака
            self.update_sidebar_watermark(theme["card"])
        except (AttributeError, tk.TclError):
            pass

    def update_sidebar_watermark(self, bg_hex=None):
        """Создает бесшовный полупрозрачный водяной знак (силуэт фирменной иконки BahonIQ 10-15%)."""
        try:
            from PIL import Image, ImageTk
            theme = get_theme()
            if not bg_hex:
                bg_hex = theme.get("card", "#183153")

            assets_dir = Path(__file__).resolve().parent.parent / "assets"
            emblem_path = assets_dir / "user_emblem.png"
            mask_path = assets_dir / "user_emblem_mask.png"

            if not (emblem_path.is_file() and mask_path.is_file()):
                return

            rgb_img = Image.open(emblem_path).convert("RGB")
            mask_img = Image.open(mask_path).convert("L")

            # Размер, полностью заполняющий свободное пространство сайдбара
            target_w = 220
            target_h = int(rgb_img.height * (target_w / rgb_img.width))

            rgb_res = rgb_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            mask_res = mask_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

            # 13.5% непрозрачности (строго диапазон 10-15%)
            alpha_mask = mask_res.point(lambda p: int(p * 0.135))

            # Парсим hex цвет карточки
            hex_clean = bg_hex.lstrip("#")
            bg_rgb = tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
            bg_img = Image.new("RGB", (target_w, target_h), bg_rgb)

            is_dark = (0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]) < 128
            if is_dark:
                # В темной теме композируем с легким изумрудным свечением иконки
                comp = Image.composite(rgb_res, bg_img, alpha_mask)
            else:
                # В светлой теме - мягкий темный силуэт
                fg_img = Image.new("RGB", (target_w, target_h), (35, 75, 95))
                comp = Image.composite(fg_img, bg_img, alpha_mask)

            self.sidebar_watermark_img = ImageTk.PhotoImage(comp)

            if hasattr(self, "sidebar_watermark_lbl") and self.sidebar_watermark_lbl.winfo_exists():
                self.sidebar_watermark_lbl.configure(
                    image=self.sidebar_watermark_img,
                    bg=bg_hex,
                )
            if hasattr(self, "watermark_frame") and self.watermark_frame.winfo_exists():
                self.watermark_frame.configure(bg=bg_hex)
        except Exception as exc:
            pass

    # ========================================================
    # UPDATE WIDGET COLORS
    # ========================================================

    def update_widget_colors(self, widget, theme):
        try:
            if isinstance(widget, (tk.Frame, tk.LabelFrame)):
                widget.configure(bg=theme["card"])

            elif isinstance(widget, tk.Label):
                if hasattr(self, "sidebar_watermark_lbl") and widget == self.sidebar_watermark_lbl:
                    pass
                else:
                    widget.configure(
                        bg=theme["card"],
                        fg=theme["text"],
                    )

            elif isinstance(widget, tk.Button):
                # Do not overwrite special Italian buttons
                if hasattr(widget, "italy_tool_button"):
                    pass
                elif hasattr(widget, "italy_system_button"):
                    pass
                elif widget == self.quick_launch_button:
                    pass
                elif widget == self.about_button:
                    pass
                else:
                    widget.configure(
                        bg=theme["card"],
                        fg=theme["text"],
                        activebackground=theme["hover"],
                        activeforeground=theme["text"],
                    )

        except Exception:
            pass

        for child in widget.winfo_children():
            self.update_widget_colors(child, theme)

        # SPECIAL ELEMENTS
        try:
            if state.systems_card is not None:
                state.systems_card.configure(
                    bg=theme["card"],
                    highlightbackground=ITALY_BORDER,
                )

            if state.welcome_card is not None:
                state.welcome_card.configure(
                    bg=theme["card"],
                    highlightbackground=ITALY_BORDER,
                )

        except Exception:
            pass

    # ========================================================
    # OPEN URL
    # ========================================================

    def open_url(self, url):
        import webbrowser

        try:
            webbrowser.open(url)
        except Exception:
            pass

    # ========================================================
    # QUICK LAUNCH — ALL SYSTEMS
    # ========================================================

    def open_all_systems(self):
        """Открыть все системы из SYSTEMS в браузере с интервалом, чтобы ОС не отсекала вызовы."""
        import threading, time
        def _runner():
            for icon, name, url in SYSTEMS:
                self.open_url(url)
                time.sleep(0.25)
        threading.Thread(target=_runner, daemon=True).start()

    # ========================================================
    # OPEN TOOL
    # ========================================================

    def open_tool(self, name):
        if name == "Заметки":
            open_notes(self.root)
            return

        if name == "Instruction Generator AI":
            open_instruction_generator(self.root)
            return

        if name == "Ticket Writer AI":
            open_ticket_writer(self.root)
            return

        if name == "Code Academy":
            from modules.code_academy import open_code_academy
            open_code_academy(self.root)
            return

        if name == "Design Academy Studio":
            try:
                from modules.design_academy_studio import open_design_academy
                open_design_academy(self.root)
            except Exception:
                self.open_url("https://bahoniq.onrender.com/#designAcademy")
            return

        if name in ("Excel Academy Studio", "Excel Academy"):
            try:
                from modules.excel_academy_studio import open_excel_academy
                open_excel_academy(self.root)
            except Exception:
                self.open_url("https://bahoniq.onrender.com/#excelAcademy")
            return

        if name == "Телефонный справочник":
            open_phonebook(self.root)
            return

        if name == "Platonus Wiki AI":
            from modules.platonus_wiki import open_platonus_wiki
            open_platonus_wiki(self.root)
            return

        if name == "Очистка":
            open_cleanup(self.root)
            return

        if name == "AnyDesk":
            open_anydesk(self.root)
            return

        if name == "Дубликаты":
            open_duplicates(self.root)
            return

        if name == "PDF Center":
            open_pdf_center(self.root)
            return

        if name == "ANALYTICS AI":
            open_report_studio(self.root)
            return

        if name == "Excel AI":
            try:
                from modules.excel_ai.ui import ExcelAIWindow
                ExcelAIWindow(self.root)
            except Exception as exc:
                import traceback
                from tkinter import messagebox

                details = traceback.format_exc()
                print(details)

                messagebox.showerror(
                    "Ошибка запуска Excel AI",
                    f"Не удалось открыть Excel AI.\n\n"
                    f"{type(exc).__name__}: {exc}\n\n"
                    "Подробности ошибки выведены в консоль."
                )
            return

        self.tool_placeholder(name)

    # ========================================================
    # TOOL PLACEHOLDER
    # ========================================================

    def tool_placeholder(self, name):
        message = tk.Toplevel(self.root)
        message.title(name)
        message.geometry("420x220")
        message.configure(bg=get_theme()["card"])
        message.transient(self.root)
        message.grab_set()

        title = tk.Label(
            message,
            text=name,
            font=("Segoe UI", 18, "bold"),
            bg=get_theme()["card"],
            fg=ITALY_GREEN_DARK,
        )
        title.pack(pady=(35, 10))

        text = tk.Label(
            message,
            text="Модуль будет подключён на следующем этапе.",
            font=("Segoe UI", 10),
            bg=get_theme()["card"],
            fg=get_theme()["gray"],
        )
        text.pack(pady=5)

        button = tk.Button(
            message,
            text="Закрыть",
            command=message.destroy,
            relief="flat",
            bd=0,
            padx=25,
            pady=8,
            cursor="hand2",
            bg=ITALY_GREEN,
            fg=WHITE,
            activebackground=ITALY_GREEN_DARK,
            activeforeground=WHITE,
        )
        button.pack(pady=20)
