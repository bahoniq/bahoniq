import tkinter as tk
from datetime import datetime


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


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow:

    def __init__(self, root):

        self.root = root

        state.root = root

        self.build()

        self.update_clock()

        self.apply_theme()

        rgb_initialize()


    # ========================================================
    # BUILD
    # ========================================================

    def build(self):

        self.root.configure(
            bg=get_theme()["bg"]
        )


        # ----------------------------------------------------
        # ITALIAN FLAG TOP
        # ----------------------------------------------------

        self.create_italy_header_flag()


        # ----------------------------------------------------
        # RGB
        # ----------------------------------------------------

        self.create_rgb_canvases()


        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        self.create_header()


        # ----------------------------------------------------
        # MAIN AREA
        # ----------------------------------------------------

        self.create_main_area()


        # ----------------------------------------------------
        # FOOTER
        # ----------------------------------------------------

        self.create_footer()


    # ========================================================
    # ITALIAN FLAG HEADER
    # ========================================================

    def create_italy_header_flag(self):

        self.italy_flag = tk.Frame(
            self.root,
            height=8,
            bd=0,
        )

        self.italy_flag.pack(
            fill="x",
            side="top",
        )

        self.italy_flag.pack_propagate(
            False
        )


        self.flag_green = tk.Frame(
            self.italy_flag,
            bg=ITALY_GREEN,
        )

        self.flag_green.pack(
            side="left",
            fill="both",
            expand=True,
        )


        self.flag_white = tk.Frame(
            self.italy_flag,
            bg=ITALY_WHITE,
        )

        self.flag_white.pack(
            side="left",
            fill="both",
            expand=True,
        )


        self.flag_red = tk.Frame(
            self.italy_flag,
            bg=ITALY_RED,
        )

        self.flag_red.pack(
            side="left",
            fill="both",
            expand=True,
        )


    # ========================================================
    # RGB CANVASES
    # ========================================================

    def create_rgb_canvases(self):

        self.rgb_canvas = tk.Canvas(
            self.root,
            height=15,
            bd=0,
            highlightthickness=0,
        )

        self.rgb_canvas.pack(
            fill="x",
            side="top",
        )


        self.rgb_canvas_bottom = tk.Canvas(
            self.root,
            height=4,
            bd=0,
            highlightthickness=0,
        )


        state.rgb_canvas = self.rgb_canvas

        state.rgb_canvas_bottom = (
            self.rgb_canvas_bottom
        )


    # ========================================================
    # HEADER
    # ========================================================

    def create_header(self):

        self.header = tk.Frame(
            self.root,
            height=78,
            bd=0,
        )

        self.header.pack(
            fill="x",
            padx=20,
            pady=(10, 12),
        )

        self.header.pack_propagate(
            False
        )


        state.header = self.header


        # ----------------------------------------------------
        # BRAND
        # ----------------------------------------------------

        self.brand_frame = tk.Frame(
            self.header,
            bd=0,
        )

        self.brand_frame.pack(
            side="left",
            fill="y",
        )


        state.brand_frame = (
            self.brand_frame
        )


        # Green dot

        self.logo_dot = tk.Label(
            self.brand_frame,
            text="●",
            font=(
                "Segoe UI",
                17,
                "bold",
            ),
            fg=ITALY_GREEN,
            bd=0,
        )

        self.logo_dot.pack(
            side="left",
            padx=(0, 6),
        )


        # BahonIQ

        self.logo = tk.Label(
            self.brand_frame,
            text="BahonIQ",
            font=(
                "Segoe UI",
                25,
                "bold",
            ),
            fg=ITALY_GREEN_DARK,
            bd=0,
        )

        self.logo.pack(
            side="left",
            padx=(0, 5),
        )


        # Red accent

        self.logo_accent = tk.Label(
            self.brand_frame,
            text="●",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            fg=ITALY_RED,
            bd=0,
        )

        self.logo_accent.pack(
            side="left",
            padx=(0, 4),
            pady=(12, 0),
        )


        self.logo_subtitle = tk.Label(
            self.brand_frame,
            text="WORK CENTER",
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            fg="#6E7772",
            bd=0,
        )

        self.logo_subtitle.pack(
            side="left",
            padx=5,
            pady=(18, 0),
        )


        # ----------------------------------------------------
        # RIGHT CONTROLS
        # ----------------------------------------------------

        self.controls = tk.Frame(
            self.header,
            bd=0,
        )

        self.controls.pack(
            side="right",
            fill="y",
        )


        # ----------------------------------------------------
        # CLOCK
        # ----------------------------------------------------

        self.clock_label = tk.Label(
            self.controls,
            text="00:00:00",
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
            fg="#68716C",
            bd=0,
        )

        self.clock_label.pack(
            side="left",
            padx=10,
        )


        state.clock_label = (
            self.clock_label
        )


        # ----------------------------------------------------
        # THEME
        # ----------------------------------------------------

        self.theme_button = tk.Button(
            self.controls,
            text="☀ Тема",
            command=self.change_theme,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
        )

        self.theme_button.pack(
            side="left",
            padx=4,
        )


        state.theme_button = (
            self.theme_button
        )


        # ----------------------------------------------------
        # RGB
        # ----------------------------------------------------

        self.rgb_button = tk.Button(
            self.controls,
            text="🇮🇹 RGB: OFF",
            command=rgb_toggle,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
        )

        self.rgb_button.pack(
            side="left",
            padx=4,
        )


        state.rgb_button = (
            self.rgb_button
        )


        # ----------------------------------------------------
        # SPEED
        # ----------------------------------------------------

        self.rgb_speed_button = tk.Button(
            self.controls,
            text="⚡ Нормально",
            command=rgb_speed_change,
            font=(
                "Segoe UI",
                9,
            ),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=8,
        )

        self.rgb_speed_button.pack(
            side="left",
            padx=4,
        )


        state.rgb_speed_button = (
            self.rgb_speed_button
        )


        # ----------------------------------------------------
        # MODE
        # ----------------------------------------------------

        self.rgb_mode_button = tk.Button(
            self.controls,
            text="🎨 Rainbow",
            command=rgb_mode_change,
            font=(
                "Segoe UI",
                9,
            ),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=8,
        )

        self.rgb_mode_button.pack(
            side="left",
            padx=4,
        )


        state.rgb_mode_button = (
            self.rgb_mode_button
        )


    # ========================================================
    # MAIN AREA
    # ========================================================

    def create_main_area(self):

        self.main = tk.Frame(
            self.root,
            bd=0,
        )

        self.main.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 15),
        )


        state.main = self.main


        # ----------------------------------------------------
        # LEFT
        # ----------------------------------------------------

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

        left.pack_propagate(
            False
        )


        # ----------------------------------------------------
        # SYSTEMS CARD
        # ----------------------------------------------------

        self.systems_card = tk.Frame(
            left,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )

        self.systems_card.pack(
            fill="both",
            expand=True,
        )


        state.systems_card = (
            self.systems_card
        )


        # Italian green top accent

        self.systems_accent = tk.Frame(
            self.systems_card,
            height=5,
            bg=ITALY_GREEN,
            bd=0,
        )

        self.systems_accent.pack(
            fill="x",
        )

        self.systems_accent.pack_propagate(
            False
        )


        self.systems_header = tk.Label(
            self.systems_card,
            text="🌐  Системы",
            font=(
                "Segoe UI",
                15,
                "bold",
            ),
            anchor="w",
            padx=18,
            pady=15,
            bd=0,
        )

        self.systems_header.pack(
            fill="x"
        )


        state.systems_header = (
            self.systems_header
        )


        # ----------------------------------------------------
        # SYSTEM BUTTONS
        # ----------------------------------------------------

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
                font=(
                    "Segoe UI",
                    10,
                    "bold",
                ),
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=15,
                pady=11,
                command=lambda u=url: self.open_url(u),
            )

            button.pack(
                fill="x",
                pady=3,
            )

            # Save Italian accent information
            button.italy_system_button = True

            if index % 2 == 0:
                button.italy_accent = ITALY_GREEN
            else:
                button.italy_accent = ITALY_RED


        # ----------------------------------------------------
        # QUICK LAUNCH
        # ----------------------------------------------------

        self.quick_launch_button = tk.Button(
            self.systems_card,
            text="🚀  Запустить все системы",
            command=self.open_all_systems,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
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


        # ----------------------------------------------------
        # RIGHT
        # ----------------------------------------------------

        self.right = tk.Frame(
            self.main,
            bd=0,
        )

        self.right.pack(
            side="left",
            fill="both",
            expand=True,
        )


        state.right = self.right


        # ----------------------------------------------------
        # WELCOME CARD
        # ----------------------------------------------------

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


        state.welcome_card = (
            self.welcome_card
        )


        self.welcome_inner = tk.Frame(
            self.welcome_card,
            bd=0,
        )

        self.welcome_inner.pack(
            fill="x",
            padx=25,
            pady=22,
        )


        state.welcome_inner = (
            self.welcome_inner
        )


        # ----------------------------------------------------
        # WELCOME TITLE
        # ----------------------------------------------------

        self.welcome_title = tk.Label(
            self.welcome_inner,
            text="Добро пожаловать в BahonIQ",
            font=(
                "Segoe UI",
                22,
                "bold",
            ),
            anchor="w",
            bd=0,
        )

        self.welcome_title.pack(
            anchor="w"
        )


        self.welcome_text = tk.Label(
            self.welcome_inner,
            text=(
                "Рабочий центр для ежедневных "
                "задач и систем поддержки."
            ),
            font=(
                "Segoe UI",
                11,
            ),
            anchor="w",
            bd=0,
        )

        self.welcome_text.pack(
            anchor="w",
            pady=(5, 0),
        )


        # ----------------------------------------------------
        # ITALIAN DECORATIVE LINE
        # ----------------------------------------------------

        self.welcome_flag = tk.Frame(
            self.welcome_inner,
            height=4,
            bd=0,
        )

        self.welcome_flag.pack(
            fill="x",
            pady=(18, 0),
        )

        self.welcome_flag.pack_propagate(
            False
        )


        tk.Frame(
            self.welcome_flag,
            bg=ITALY_GREEN,
        ).pack(
            side="left",
            fill="both",
            expand=True,
        )


        tk.Frame(
            self.welcome_flag,
            bg=ITALY_WHITE,
        ).pack(
            side="left",
            fill="both",
            expand=True,
        )


        tk.Frame(
            self.welcome_flag,
            bg=ITALY_RED,
        ).pack(
            side="left",
            fill="both",
            expand=True,
        )


        state.welcome_line = (
            self.welcome_flag
        )


        # ----------------------------------------------------
        # TOOLS
        # ----------------------------------------------------

        self.tools_frame = tk.Frame(
            self.right,
            bd=0,
        )

        self.tools_frame.pack(
            fill="both",
            expand=True,
        )


        state.tools_frame = (
            self.tools_frame
        )


        self.tools_title = tk.Label(
            self.tools_frame,
            text="🛠  Инструменты",
            font=(
                "Segoe UI",
                15,
                "bold",
            ),
            anchor="w",
            bd=0,
        )

        self.tools_title.pack(
            anchor="w",
            pady=(3, 10),
        )


        state.tools_title = (
            self.tools_title
        )


        # ----------------------------------------------------
        # TOOL GRID
        # ----------------------------------------------------

        tools_grid = tk.Frame(
            self.tools_frame,
            bd=0,
        )

        tools_grid.pack(
            fill="both",
            expand=True,
        )


        tools = [

            (
                "📁",
                "Проводник",
            ),

            (
                "📝",
                "Заметки",
            ),

            (
                "📚",
                "Библиотека",
            ),

            (
                "🧹",
                "Очистка",
            ),

            (
                "🔍",
                "Дубликаты",
            ),

            (
                "🖥",
                "AnyDesk",
            ),

            (
                "📄",
                "PDF Center",
            ),

        ]


        for index, (icon, name) in enumerate(tools):

            row = index // 3

            column = index % 3


            # Italian accent:
            # green / white / red
            accent_colors = [
                "#D9F0E3",   # зелёный — чуть насыщеннее
                "#F7F8F8",   # белый — чуть заметнее
                "#F2DADB",   # красный — чуть насыщеннее
            ]

            accent_color = accent_colors[
                column
            ]


            button = tk.Button(
                tools_grid,
                text=f"{icon}\n{name}",
                font=(
                    "Segoe UI",
                    11,
                    "bold",
                ),
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

            tools_grid.grid_columnconfigure(
                column,
                weight=1,
            )


        for row in range(3):

            tools_grid.grid_rowconfigure(
                row,
                weight=1,
            )


    # ========================================================
    # FOOTER
    # ========================================================

    def create_footer(self):

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

        self.footer.pack_propagate(
            False
        )


        state.footer = self.footer


        # ----------------------------------------------------
        # ITALIAN FLAG
        # ----------------------------------------------------

        self.footer_flag = tk.Frame(
            self.footer,
            width=90,
            height=22,
            bd=0,
        )

        self.footer_flag.pack(
            side="left",
            pady=5,
        )

        self.footer_flag.pack_propagate(
            False
        )


        tk.Frame(
            self.footer_flag,
            bg=ITALY_GREEN,
        ).pack(
            side="left",
            fill="both",
            expand=True,
        )


        tk.Frame(
            self.footer_flag,
            bg=ITALY_WHITE,
        ).pack(
            side="left",
            fill="both",
            expand=True,
        )


        tk.Frame(
            self.footer_flag,
            bg=ITALY_RED,
        ).pack(
            side="left",
            fill="both",
            expand=True,
        )


        state.footer_flag = (
            self.footer_flag
        )


        # ----------------------------------------------------
        # FOOTER TEXT
        # ----------------------------------------------------

        self.footer_text = tk.Label(
            self.footer,
            text=(
                "BahonIQ — Work Center"
                "   •   Ready"
            ),
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            fg="#68716C",
            bd=0,
        )

        self.footer_text.pack(
            side="left",
            padx=10,
        )


    # ========================================================
    # CLOCK
    # ========================================================

    def update_clock(self):

        if state.clock_label is None:
            return


        now = datetime.now()


        state.clock_label.configure(
            text=now.strftime(
                "%H:%M:%S"
            )
        )


        self.root.after(
            1000,
            self.update_clock,
        )


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


        self.root.configure(
            bg=theme["bg"]
        )


        self.update_widget_colors(
            self.root,
            theme,
        )


        # ----------------------------------------------------
        # ITALIAN HEADER
        # ----------------------------------------------------

        try:

            self.logo.configure(
                fg=ITALY_GREEN_DARK
            )

            self.logo_dot.configure(
                fg=ITALY_GREEN
            )

            self.logo_accent.configure(
                fg=ITALY_RED
            )

            self.logo_subtitle.configure(
                fg=theme["gray"]
            )

            self.clock_label.configure(
                fg=theme["gray"]
            )

        except Exception:
            pass


        # ----------------------------------------------------
        # THEME BUTTON
        # ----------------------------------------------------

        if state.theme_button is not None:

            if state.current_theme == "night":

                state.theme_button.configure(
                    text="🌙 Тема"
                )

            else:

                state.theme_button.configure(
                    text="☀ Тема"
                )


        # ----------------------------------------------------
        # ITALIAN SPECIAL ELEMENTS
        # ----------------------------------------------------

        try:

            # Main cards

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


            # Systems header

            if state.systems_header is not None:

                state.systems_header.configure(
                    fg=ITALY_GREEN_DARK,
                    bg=theme["card"],
                )


            # Welcome title

            if self.welcome_title is not None:

                self.welcome_title.configure(
                    fg=ITALY_GREEN_DARK,
                    bg=theme["card"],
                )


            # Welcome text

            if self.welcome_text is not None:

                self.welcome_text.configure(
                    bg=theme["card"],
                    fg=theme["text"],
                )


            # Tools title

            if self.tools_title is not None:

                self.tools_title.configure(
                    fg=ITALY_RED_DARK,
                    bg=theme["card"],
                )


            # Footer

            self.footer.configure(
                bg=theme["bg"]
            )

            self.footer_text.configure(
                bg=theme["bg"],
                fg=theme["gray"],
            )


            # Quick launch remains red

            self.quick_launch_button.configure(
                bg=ITALY_RED,
                fg=ITALY_WHITE,
                activebackground=ITALY_RED_DARK,
                activeforeground=ITALY_WHITE,
            )


            # Systems buttons

            for child in (
                self.systems_card
                .winfo_children()
            ):

                if isinstance(
                    child,
                    tk.Frame,
                ):

                    for button in child.winfo_children():

                        if isinstance(
                            button,
                            tk.Button,
                        ):

                            if hasattr(
                                button,
                                "italy_system_button",
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
                                        if accent
                                        == ITALY_GREEN
                                        else ITALY_RED_LIGHT
                                    ),
                                    activeforeground=(
                                        accent
                                    ),
                                )


        except Exception:
            pass


    # ========================================================
    # UPDATE WIDGET COLORS
    # ========================================================

    def update_widget_colors(
        self,
        widget,
        theme,
    ):

        try:

            if isinstance(
                widget,
                (
                    tk.Frame,
                    tk.LabelFrame,
                ),
            ):

                widget.configure(
                    bg=theme["card"]
                )


            elif isinstance(
                widget,
                tk.Label,
            ):

                widget.configure(
                    bg=theme["card"],
                    fg=theme["text"],
                )


            elif isinstance(
                widget,
                tk.Button,
            ):

                # Do not overwrite special Italian buttons

                if hasattr(
                    widget,
                    "italy_tool_button",
                ):

                    pass

                elif hasattr(
                    widget,
                    "italy_system_button",
                ):

                    pass

                elif widget == self.quick_launch_button:

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

            self.update_widget_colors(
                child,
                theme,
            )


        # ----------------------------------------------------
        # SPECIAL ELEMENTS
        # ----------------------------------------------------

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

            webbrowser.open(
                url
            )

        except Exception:
            pass


    # ========================================================
    # QUICK LAUNCH — ALL SYSTEMS
    # ========================================================

    def open_all_systems(self):

        """
        Открыть все системы из SYSTEMS
        по отдельности в браузере.
        """

        for icon, name, url in SYSTEMS:

            self.open_url(
                url
            )


    # ========================================================
    # OPEN TOOL
    # ========================================================

    def open_tool(self, name):

        if name == "Заметки":

            open_notes(
                self.root
            )

            return


        if name == "Проводник":

            import os

            os.startfile(
                os.path.expanduser("~")
            )

            return


        if name == "Очистка":

            open_cleanup(
                self.root
            )

            return


        if name == "AnyDesk":

            open_anydesk(
                self.root
            )

            return


        if name == "Дубликаты":

            open_duplicates(
                self.root
            )

            return


        if name == "PDF Center":

            open_pdf_center(
                self.root
            )

            return


        self.tool_placeholder(
            name
        )


    # ========================================================
    # TOOL PLACEHOLDER
    # ========================================================

    def tool_placeholder(self, name):

        message = tk.Toplevel(
            self.root
        )

        message.title(
            name
        )

        message.geometry(
            "420x220"
        )

        message.configure(
            bg=get_theme()["card"]
        )

        message.transient(
            self.root
        )

        message.grab_set()


        title = tk.Label(
            message,
            text=name,
            font=(
                "Segoe UI",
                18,
                "bold",
            ),
            bg=get_theme()["card"],
            fg=ITALY_GREEN_DARK,
        )

        title.pack(
            pady=(35, 10)
        )


        text = tk.Label(
            message,
            text=(
                "Модуль будет подключён "
                "на следующем этапе."
            ),
            font=(
                "Segoe UI",
                10,
            ),
            bg=get_theme()["card"],
            fg=get_theme()["gray"],
        )

        text.pack(
            pady=5
        )


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

        button.pack(
            pady=20
        )