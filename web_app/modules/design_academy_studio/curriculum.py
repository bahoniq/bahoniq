"""Учебная программа Design Academy Studio.

Содержимое отделено от интерфейса и API, чтобы последующие этапы можно было
расширять без разрастания одного монолитного файла.
"""

from __future__ import annotations

from copy import deepcopy


STAGES = [
    {"id": 1, "title": "Основы Figma", "subtitle": "Холст, фигуры, текст и точная компоновка", "lessons": 12},
    {"id": 2, "title": "Векторная графика", "subtitle": "Pen Tool, контуры, маски и иконки", "lessons": 12, "planned": True},
    {"id": 3, "title": "UI-дизайн", "subtitle": "Цвет, типографика и интерфейсы", "lessons": 14, "planned": True},
    {"id": 4, "title": "Компоненты и Auto Layout", "subtitle": "Компоненты, варианты и адаптивность", "lessons": 12, "planned": True},
    {"id": 5, "title": "UX и прототипирование", "subtitle": "Сценарии, wireframe и прототипы", "lessons": 10, "planned": True},
    {"id": 6, "title": "Дизайн-система и проекты", "subtitle": "Система компонентов и портфолио", "lessons": 12, "planned": True},
]


def _lesson(number: int, title: str, summary: str, theory: str, task: str, *, tool: str,
            checks: list[dict], starter: list[dict] | None = None) -> dict:
    tool_names = {"frame": "Фрейм", "rectangle": "Прямоугольник", "ellipse": "Круг", "text": "Текст", "select": "Выбор"}
    return {
        "id": f"1-{number}", "stage_id": 1, "number": number, "title": title,
        "summary": summary, "theory": theory, "task": task, "tool": tool,
        "checks": checks, "starter": starter or [],
        "steps": [
            f"Выберите инструмент «{tool_names.get(tool, tool)}» на панели редактора.",
            "Создайте объект на холсте и выделите его.",
            "Введите точные значения из задания в панели «Свойства».",
            "Сверьте тип объекта и его название в списке слоёв.",
            "Нажмите «Проверить работу» и исправьте отмеченные пункты.",
        ],
    }


LESSONS = [
    _lesson(1, "Рабочая область и первый фрейм", "Создаём основу будущего экрана.",
            "Фрейм — это самостоятельная область интерфейса. Он задаёт размер экрана и хранит вложенные элементы.",
            "Создайте фрейм размером 720 × 420 px и назовите его «Экран приложения».", tool="frame",
            checks=[{"kind": "type", "type": "frame", "min": 1}, {"kind": "size", "type": "frame", "width": 720, "height": 420, "tolerance": 8}]),
    _lesson(2, "Слои и порядок объектов", "Учимся управлять наложением элементов.",
            "Каждый объект находится на отдельном слое. Объект выше в списке отображается поверх объектов ниже.",
            "Создайте внутри фрейма два прямоугольника и поднимите меньший над большим.", tool="rectangle",
            checks=[{"kind": "type", "type": "rectangle", "min": 2}]),
    _lesson(3, "Базовые фигуры", "Собираем композицию из прямоугольника и круга.",
            "Простые интерфейсы строятся из базовых фигур. Точные размеры и единые радиусы важнее количества эффектов.",
            "Создайте карточку 320 × 160 px и круглый контейнер 48 × 48 px.", tool="rectangle",
            checks=[{"kind": "size", "type": "rectangle", "width": 320, "height": 160, "tolerance": 6}, {"kind": "size", "type": "ellipse", "width": 48, "height": 48, "tolerance": 5}]),
    _lesson(4, "Текст и типографика", "Добавляем заголовок и описание.",
            "Заголовок должен быть заметнее описания: используйте больший размер и более высокий вес шрифта.",
            "Добавьте заголовок размером 24 px и описание размером 14 px.", tool="text",
            checks=[{"kind": "type", "type": "text", "min": 2}, {"kind": "font_size", "value": 24, "tolerance": 1}]),
    _lesson(5, "Координаты и размеры", "Настраиваем элементы численно.",
            "Панель свойств позволяет задавать точные координаты и размеры вместо приблизительного перемещения мышью.",
            "Создайте прямоугольник 280 × 96 px в позиции X=80, Y=80.", tool="rectangle",
            checks=[{"kind": "geometry", "type": "rectangle", "x": 80, "y": 80, "width": 280, "height": 96, "tolerance": 5}]),
    _lesson(6, "Выравнивание", "Формируем аккуратную горизонтальную группу.",
            "Выравнивание создаёт визуальный порядок. Элементы одной группы должны иметь общую ось.",
            "Разместите три круга одинакового размера на одной горизонтальной линии.", tool="ellipse",
            checks=[{"kind": "type", "type": "ellipse", "min": 3}, {"kind": "aligned_y", "type": "ellipse", "tolerance": 4}]),
    _lesson(7, "Сетка и отступы", "Используем ритм 8 px.",
            "Система отступов 8 px делает интерфейс предсказуемым: 8, 16, 24 и 32 px образуют единый ритм.",
            "Создайте две карточки одинакового размера с промежутком 24 px.", tool="rectangle",
            checks=[{"kind": "type", "type": "rectangle", "min": 2}, {"kind": "gap", "type": "rectangle", "value": 24, "tolerance": 5}]),
    _lesson(8, "Заливка и обводка", "Создаём контраст без лишней яркости.",
            "Заливка формирует поверхность, а тонкая обводка отделяет её от фона. Для тёмной темы достаточно обводки 1 px.",
            "Создайте карточку с заливкой #132238 и обводкой #2B4160 толщиной 1 px.", tool="rectangle",
            checks=[{"kind": "fill", "type": "rectangle", "value": "#132238"}, {"kind": "stroke", "type": "rectangle", "value": "#2B4160", "width": 1}]),
    _lesson(9, "Скругления и прозрачность", "Смягчаем геометрию интерфейса.",
            "Одинаковый радиус связывает карточки в систему. Прозрачность используйте только для второстепенных элементов.",
            "Создайте прямоугольник с радиусом 16 px и прозрачностью 80%.", tool="rectangle",
            checks=[{"kind": "radius", "type": "rectangle", "value": 16, "tolerance": 2}, {"kind": "opacity", "type": "rectangle", "value": .8, "tolerance": .05}]),
    _lesson(10, "Группировка", "Объединяем связанные элементы.",
            "Группа позволяет перемещать несколько связанных элементов как единое целое и сохранять порядок слоёв.",
            "Создайте фигуру и текст, выделите их и объедините в группу.", tool="select",
            checks=[{"kind": "type", "type": "group", "min": 1}]),
    _lesson(11, "Организация слоёв", "Даём объектам понятные названия.",
            "Названия Rectangle 17 ничего не объясняют. Используйте смысловые имена: Card, Icon, Title, Description.",
            "Создайте минимум три объекта и переименуйте каждый, убрав стандартные названия.", tool="select",
            checks=[{"kind": "named", "min": 3}]),
    _lesson(12, "Проект: карточка BahonIQ", "Собираем первый законченный элемент интерфейса.",
            "Итоговая карточка объединяет поверхность, иконку, заголовок и описание. Соблюдайте иерархию и внутренние отступы.",
            "Создайте карточку 360 × 140 px, контейнер иконки 48 × 48 px, заголовок и описание. Радиус карточки — 16 px.", tool="rectangle",
            checks=[{"kind": "size", "type": "rectangle", "width": 360, "height": 140, "tolerance": 8}, {"kind": "size", "type": "ellipse", "width": 48, "height": 48, "tolerance": 5}, {"kind": "type", "type": "text", "min": 2}, {"kind": "radius", "type": "rectangle", "value": 16, "tolerance": 3}]),
]


def get_curriculum() -> dict:
    return {"title": "Design Academy Studio", "total_lessons": 72, "available_lessons": 12,
            "stages": deepcopy(STAGES), "lessons": deepcopy(LESSONS)}


def get_lesson(lesson_id: str) -> dict | None:
    return next((deepcopy(item) for item in LESSONS if item["id"] == lesson_id), None)
