import traceback

from bootstrap import start_app


def main():

    try:

        start_app()

    except BaseException:

        error_file = "BahonIQ_error.log"

        try:

            with open(
                error_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    "=== BAHONIQ — ОШИБКА ЗАПУСКА ===\n\n"
                )

                traceback.print_exc(
                    file=f
                )

        except Exception:

            pass


if __name__ == "__main__":

    main()