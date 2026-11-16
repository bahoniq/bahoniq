from web_app.modules.design_academy_studio.curriculum import get_curriculum, get_lesson
from web_app.modules.design_academy_studio.validation import validate_document


def test_curriculum_has_six_complete_stages():
    course = get_curriculum()
    assert len(course["stages"]) == 6
    assert len(course["lessons"]) == 72
    assert course["available_lessons"] == 72
    assert course["total_lessons"] == 72


def test_lesson_is_returned_as_copy():
    lesson = get_lesson("1-1")
    assert lesson and lesson["title"]
    lesson["title"] = "changed"
    assert get_lesson("1-1")["title"] != "changed"


def test_validator_accepts_matching_frame():
    lesson = get_lesson("1-1")
    document = {"objects": [{"type": "frame", "width": 720, "height": 420}]}
    result = validate_document(document, lesson["checks"])
    assert result["passed"] is True
    assert result["score"] == 100


def test_validator_explains_incomplete_work():
    lesson = get_lesson("1-12")
    result = validate_document({"objects": []}, lesson["checks"])
    assert result["passed"] is False
    assert result["score"] == 0
    assert len(result["results"]) == len(lesson["checks"])


def test_validator_explains_wrong_object_type_with_right_size():
    lesson = get_lesson("1-3")
    document = {"objects": [
        {"type": "frame", "width": 320, "height": 160},
        {"type": "ellipse", "width": 48, "height": 48},
    ]}
    result = validate_document(document, lesson["checks"])
    assert result["score"] == 50
    assert "Фрейм" in result["results"][0]["message"]
    assert "Прямоугольник" in result["results"][0]["message"]


def test_professional_tools_have_deterministic_checks():
    cases = {
        "2-1": {"objects": [{"type": "path", "points": [{}, {}, {}, {}]}]},
        "2-4": {"objects": [{"type": "boolean", "operation": "union"}]},
        "2-7": {"objects": [{"type": "mask_group"}]},
        "4-1": {"objects": [{"type": "auto_layout"}]},
        "4-5": {"objects": [{"type": "component"}]},
        "5-4": {"objects": [{"type": "prototype_link"}]},
    }
    for lesson_id, document in cases.items():
        assert validate_document(document, get_lesson(lesson_id)["checks"])["passed"]
