from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VERSION_FILE = BASE_DIR / "VERSION"


def get_version():
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


VERSION = get_version()