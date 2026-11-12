from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
VERSION_FILE = BASE_DIR / "VERSION"


def get_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


VERSION = get_version()