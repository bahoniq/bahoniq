import colorsys
import math

from config import (
    RGB_SPEEDS,
    RGB_SPEED_NAMES,
    RGB_MODES,
)

from state import state


# ============================================================
# ITALY COLORS
# ============================================================

ITALY_GREEN = "#009246"
ITALY_WHITE = "#FFFFFF"
ITALY_RED = "#CE2B37"


# ============================================================
# RGB COLOR
# ============================================================

def rgb_color(position):
    """
    Возвращает RGB-цвет по позиции.
    """

    position = position % 1.0

    r, g, b = colorsys.hsv_to_rgb(
        position,
        1.0,
        1.0,
    )

    return (
        int(r * 255),
        int(g * 255),
        int(b * 255),
    )


# ============================================================
# RGB MODE
# ============================================================

def rgb_mode_change():
    """
    Переключает режим RGB.
    """

    state.rgb_mode_index += 1

    if state.rgb_mode_index >= len(RGB_MODES):
        state.rgb_mode_index = 0

    update_rgb_buttons()


# ============================================================
# RGB SPEED
# ============================================================

def rgb_speed_change():
    """
    Переключает скорость RGB.
    """

    state.rgb_speed_index += 1

    if state.rgb_speed_index >= len(RGB_SPEEDS):
        state.rgb_speed_index = 0

    update_rgb_buttons()


# ============================================================
# RGB START
# ============================================================

def rgb_start():
    """
    Запускает RGB-анимацию.
    """

    if state.rgb_enabled:
        return

    state.rgb_enabled = True

    if state.root is not None:
        rgb_animate()


# ============================================================
# RGB STOP
# ============================================================

def rgb_stop():
    """
    Останавливает RGB-анимацию
    и очищает полосы.
    """

    state.rgb_enabled = False

    if (
        state.root is not None
        and state.rgb_after_id is not None
    ):
        try:
            state.root.after_cancel(
                state.rgb_after_id
            )
        except Exception:
            pass

        state.rgb_after_id = None

    # Очищаем полосы
    try:
        if state.rgb_canvas is not None:
            state.rgb_canvas.delete("all")

        if state.rgb_canvas_bottom is not None:
            state.rgb_canvas_bottom.delete("all")

    except Exception:
        pass


# ============================================================
# RGB TOGGLE
# ============================================================

def rgb_toggle():
    """
    Включает / выключает RGB.
    """

    if state.rgb_enabled:
        rgb_stop()
    else:
        rgb_start()

    update_rgb_buttons()


# ============================================================
# RGB BUTTONS
# ============================================================

def update_rgb_buttons():
    """
    Обновляет подписи RGB-кнопок.
    """

    try:

        if state.rgb_button is not None:

            if state.rgb_enabled:
                state.rgb_button.configure(
                    text="🇮🇹 RGB: ON"
                )
            else:
                state.rgb_button.configure(
                    text="🇮🇹 RGB: OFF"
                )

        if state.rgb_speed_button is not None:

            state.rgb_speed_button.configure(
                text=(
                    "⚡ "
                    + RGB_SPEED_NAMES[
                        state.rgb_speed_index
                    ]
                )
            )

        if state.rgb_mode_button is not None:

            state.rgb_mode_button.configure(
                text=(
                    "🎨 "
                    + RGB_MODES[
                        state.rgb_mode_index
                    ]
                )
            )

    except Exception:
        pass


# ============================================================
# ITALIAN FLAG MOVEMENT
# ============================================================

def italy_color(position):
    """
    Возвращает цвет движущегося
    итальянского флага.

    position:
        0.0 - 1.0
    """

    position = position % 1.0

    # Три основные зоны:
    #
    # 0.00 - 0.333 = GREEN
    # 0.333 - 0.666 = WHITE
    # 0.666 - 1.00 = RED

    if position < 0.333:

        return ITALY_GREEN

    elif position < 0.666:

        return ITALY_WHITE

    else:

        return ITALY_RED


# ============================================================
# RGB DRAW
# ============================================================

def draw_rgb_canvas(canvas):
    """
    Рисует движущуюся итальянскую RGB-полосу.
    """

    if canvas is None:
        return

    try:

        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()

        if width <= 1:
            width = 1100

        if height <= 1:
            height = 15

        # Количество сегментов.
        # Чем больше сегментов — тем плавнее движение.
        segments = max(
            60,
            int(width / 5)
        )

        mode = RGB_MODES[
            state.rgb_mode_index
        ]

        # ----------------------------------------------------
        # РИСУЕМ ПОЛОСУ
        # ----------------------------------------------------

        for i in range(segments):

            progress = i / segments

            # Движение итальянских цветов
            position = (
                progress
                + state.rgb_position
            ) % 1.0

            # ------------------------------------------------
            # RAINBOW
            #
            # Оставляем итальянские цвета,
            # но делаем плавный переход.
            # ------------------------------------------------

            if mode == "Rainbow":

                # Три цветовые зоны
                if position < 0.333:

                    local = position / 0.333

                    color = interpolate_color(
                        ITALY_GREEN,
                        ITALY_WHITE,
                        local
                    )

                elif position < 0.666:

                    local = (
                        position - 0.333
                    ) / 0.333

                    color = interpolate_color(
                        ITALY_WHITE,
                        ITALY_RED,
                        local
                    )

                else:

                    local = (
                        position - 0.666
                    ) / 0.334

                    color = interpolate_color(
                        ITALY_RED,
                        ITALY_GREEN,
                        local
                    )

            # ------------------------------------------------
            # SCAN
            # ------------------------------------------------

            elif mode == "Scan":

                distance = abs(
                    progress
                    - state.rgb_position
                )

                brightness = max(
                    0.25,
                    1.0 - distance * 4.0
                )

                base_color = italy_color(
                    position
                )

                color = adjust_brightness(
                    base_color,
                    brightness
                )

            # ------------------------------------------------
            # WAVE
            # ------------------------------------------------

            elif mode == "Wave":

                wave = (
                    math.sin(
                        (
                            progress * 10.0
                        )
                        + state.rgb_position * 12.0
                    )
                    + 1.0
                ) / 2.0

                base_color = italy_color(
                    position
                )

                brightness = (
                    0.45
                    + wave * 0.55
                )

                color = adjust_brightness(
                    base_color,
                    brightness
                )

            # ------------------------------------------------
            # COMET
            # ------------------------------------------------

            else:

                distance = (
                    progress
                    - state.rgb_position
                ) % 1.0

                brightness = max(
                    0.18,
                    1.0 - distance * 3.5
                )

                base_color = italy_color(
                    position
                )

                color = adjust_brightness(
                    base_color,
                    brightness
                )

            # ------------------------------------------------
            # SEGMENT
            # ------------------------------------------------

            x1 = (
                i
                * width
                / segments
            )

            x2 = (
                (i + 1)
                * width
                / segments
            )

            canvas.create_rectangle(
                x1,
                0,
                x2 + 1,
                height,
                fill=color,
                outline=color,
            )

    except Exception:
        pass


# ============================================================
# COLOR INTERPOLATION
# ============================================================

def interpolate_color(
    color1,
    color2,
    amount
):
    """
    Плавный переход между двумя цветами.
    """

    amount = max(
        0.0,
        min(1.0, amount)
    )

    r1 = int(color1[1:3], 16)
    g1 = int(color1[3:5], 16)
    b1 = int(color1[5:7], 16)

    r2 = int(color2[1:3], 16)
    g2 = int(color2[3:5], 16)
    b2 = int(color2[5:7], 16)

    r = int(
        r1 + (r2 - r1) * amount
    )

    g = int(
        g1 + (g2 - g1) * amount
    )

    b = int(
        b1 + (b2 - b1) * amount
    )

    return "#{:02X}{:02X}{:02X}".format(
        r,
        g,
        b
    )


# ============================================================
# BRIGHTNESS
# ============================================================

def adjust_brightness(
    color,
    brightness
):
    """
    Изменяет яркость цвета.
    """

    brightness = max(
        0.0,
        min(1.0, brightness)
    )

    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)

    r = int(r * brightness)
    g = int(g * brightness)
    b = int(b * brightness)

    return "#{:02X}{:02X}{:02X}".format(
        r,
        g,
        b
    )


# ============================================================
# RGB ANIMATION
# ============================================================

def rgb_animate():
    """
    Основной цикл RGB-анимации.
    """

    if not state.rgb_enabled:
        return

    try:

        # Скорость движения
        state.rgb_position += (
            0.004
            * state.rgb_direction
        )

        state.rgb_position %= 1.0

        # ----------------------------------------------------
        # MAIN RGB
        # ----------------------------------------------------

        draw_rgb_canvas(
            state.rgb_canvas
        )

        # ----------------------------------------------------
        # BOTTOM RGB
        # ----------------------------------------------------

        draw_rgb_canvas(
            state.rgb_canvas_bottom
        )

        # ----------------------------------------------------
        # NEXT FRAME
        # ----------------------------------------------------

        delay = RGB_SPEEDS[
            state.rgb_speed_index
        ]

        if state.root is not None:

            state.rgb_after_id = (
                state.root.after(
                    delay,
                    rgb_animate
                )
            )

    except Exception:

        state.rgb_after_id = None


# ============================================================
# RGB INITIALIZE
# ============================================================

def rgb_initialize():
    """
    Первоначальная настройка RGB.
    """

    state.rgb_position = 0.0

    state.rgb_direction = 1

    update_rgb_buttons()