import ast
from pathlib import Path


def test_all_academy_sections_are_enabled_without_prerequisites():
    source = Path(__file__).resolve().parents[1].joinpath("ui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    update_status = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_update_status"
    )
    access_calls = [
        node for node in ast.walk(update_status)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "set_enabled"
    ]
    assert len(access_calls) == 1
    assert isinstance(access_calls[0].args[1], ast.Constant)
    assert access_calls[0].args[1].value is True
    assert "('python', 'sql', 'architecture', 'builder', 'tutor', 'tests')" in source
