import os
import sys
import traceback
from pathlib import Path


# ============================================================
# BAHONIQ — LAUNCHER
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


def write_error():

    try:

        error_file = BASE_DIR / "BahonIQ_launcher_error.log"

        with open(
            error_file,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                "=== BAHONIQ LAUNCHER ERROR ===\n\n"
            )

            traceback.print_exc(
                file=f
            )

    except Exception:

        pass


def main():

    try:

        os.chdir(
            BASE_DIR
        )

        if str(BASE_DIR) not in sys.path:

            sys.path.insert(
                0,
                str(BASE_DIR)
            )

        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")

        from main import main as start_bahoniq

        start_bahoniq()

    except BaseException:

        write_error()


if __name__ == "__main__":

    main()