# ============================================================
# BAHONIQ — APPLICATION STATE
# ============================================================


class AppState:
    """
    Центральное состояние приложения BahonIQ.

    Здесь хранятся данные и ссылки на элементы интерфейса,
    которые используются разными модулями.
    """

    def __init__(self):

        # ====================================================
        # ROOT WINDOW
        # ====================================================

        self.root = None


        # ====================================================
        # THEME
        # ====================================================

        self.current_theme = "day"


        # ====================================================
        # RGB
        # ====================================================

        self.rgb_enabled = False

        self.rgb_speed_index = 2

        self.rgb_mode_index = 0

        self.rgb_position = 0.0

        self.rgb_direction = 1

        self.rgb_after_id = None


        # ====================================================
        # MAIN UI
        # ====================================================

        self.main = None

        self.header = None

        self.brand_frame = None

        self.right = None


        # ====================================================
        # SYSTEMS
        # ====================================================

        self.systems_card = None

        self.systems_header = None


        # ====================================================
        # WELCOME
        # ====================================================

        self.welcome_card = None

        self.welcome_inner = None

        self.welcome_line = None


        # ====================================================
        # TOOLS
        # ====================================================

        self.tools_frame = None

        self.tools_title = None


        # ====================================================
        # FOOTER
        # ====================================================

        self.footer = None

        self.footer_flag = None

        self.mini_flag = None


        # ====================================================
        # HEADER CONTROLS
        # ====================================================

        self.theme_button = None

        self.rgb_button = None

        self.rgb_speed_button = None

        self.rgb_mode_button = None

        self.clock_label = None


        # ====================================================
        # RGB CANVAS
        # ====================================================

        self.rgb_canvas = None

        self.rgb_canvas_bottom = None


# ============================================================
# GLOBAL APPLICATION STATE
# ============================================================

state = AppState()