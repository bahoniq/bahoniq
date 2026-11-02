
import json
import uuid
from datetime import datetime, timezone

from .database import TaskDatabase
from .models import Task, TaskStatus, TRANSITIONS


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(data):
    """Сериализует данные для SQLite и выдаёт понятную ошибку."""
    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Данные нельзя сохранить в JSON. "
            "Проверь их типы и значения."
        ) from exc


def _as_task(row):
    return Task(
        id=row["id"],
        instruction=row["instruction"],
        source_path=row["source_path"],
        output_dir=row["output_dir"],
        status=TaskStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error=row["error"],
        recovery_attempts=row["recovery_attempts"],
    )


class TaskEngine:
    """Управление заданиями, статусами, событиями и контрольными точками."""

    MAX_RECOVERY_ATTEMPTS = 3

    def __init__(self, db_path):
        self.db = TaskDatabase(db_path)

    def create_task(self, instruction, source_path=None, output_dir=None):
        if not isinstance(instruction, str):
            raise TypeError(
                "Описание задачи должно быть текстом."
            )

        instruction = instruction.strip()

        if not instruction:
            raise ValueError(
                "Описание задачи не может быть пустым."
            )

        if source_path is not None and not isinstance(source_path, str):
            raise TypeError(
                "Путь к исходному файлу должен быть строкой."
            )

        if output_dir is not None and not isinstance(output_dir, str):
            raise TypeError(
                "Путь к папке результата должен быть строкой."
            )

        task_id = uuid.uuid4().hex
        now = _now()

        with self.db.connect() as con:
            con.execute(
                """
                INSERT INTO tasks
                (
                    id, instruction, source_path, output_dir,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    instruction,
                    source_path,
                    output_dir,
                    TaskStatus.CREATED.value,
                    now,
                    now,
                ),
            )

            self._event(
                con,
                task_id,
                "created",
                "Задача создана.",
            )

        return self.get_task(task_id)

    def get_task(self, task_id):
        with self.db.connect() as con:
            row = con.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

        if row is None:
            raise KeyError(
                f"Задача не найдена: {task_id}"
            )

        return _as_task(row)

    def list_tasks(self, limit=100):
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1000
        ):
            raise ValueError(
                "limit должен быть целым числом от 1 до 1000."
            )

        with self.db.connect() as con:
            rows = con.execute(
                """
                SELECT *
                FROM tasks
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [_as_task(row) for row in rows]

    def transition(self, task_id, new_status, message="", error=None):
        """Атомарно меняет статус и записывает событие."""
        try:
            new_status = TaskStatus(new_status)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Неизвестный статус задания: {new_status!r}"
            ) from exc

        if not isinstance(message, str):
            raise TypeError(
                "Сообщение о переходе должно быть строкой."
            )

        if error is not None and not isinstance(error, str):
            error = str(error)

        now = _now()

        with self.db.connect() as con:
            con.execute("BEGIN IMMEDIATE")

            row = con.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if row is None:
                raise KeyError(
                    f"Задача не найдена: {task_id}"
                )

            old_status = TaskStatus(row["status"])

            if new_status not in TRANSITIONS[old_status]:
                raise ValueError(
                    f"Недопустимый переход: "
                    f"{old_status.value} -> {new_status.value}"
                )

            attempts = row["recovery_attempts"]

            if new_status == TaskStatus.RECOVERY:
                if attempts >= self.MAX_RECOVERY_ATTEMPTS:
                    raise ValueError(
                        "Достигнут лимит попыток восстановления."
                    )
                attempts += 1

            con.execute(
                """
                UPDATE tasks
                SET status = ?,
                    updated_at = ?,
                    error = ?,
                    recovery_attempts = ?
                WHERE id = ?
                """,
                (
                    new_status.value,
                    now,
                    error,
                    attempts,
                    task_id,
                ),
            )

            self._event(
                con,
                task_id,
                "status_changed",
                message or (
                    f"{old_status.value} -> {new_status.value}"
                ),
                {
                    "from": old_status.value,
                    "to": new_status.value,
                },
            )

        return self.get_task(task_id)

    def add_event(self, task_id, event_type, message, details=None):
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError(
                "Тип события не может быть пустым."
            )

        if not isinstance(message, str):
            raise TypeError(
                "Сообщение события должно быть строкой."
            )

        if details is None:
            details = {}

        if not isinstance(details, dict):
            raise TypeError(
                "Детали события должны быть словарём."
            )

        # Проверяем JSON до начала транзакции.
        details_json = _json_dumps(details)

        with self.db.connect() as con:
            if con.execute(
                "SELECT 1 FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone() is None:
                raise KeyError(
                    f"Задача не найдена: {task_id}"
                )

            self._event(
                con,
                task_id,
                event_type.strip(),
                message,
                details_json=details_json,
            )

    def get_events(self, task_id):
        with self.db.connect() as con:
            if con.execute(
                "SELECT 1 FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone() is None:
                raise KeyError(
                    f"Задача не найдена: {task_id}"
                )

            rows = con.execute(
                """
                SELECT *
                FROM events
                WHERE task_id = ?
                ORDER BY id
                """,
                (task_id,),
            ).fetchall()

        result = []

        for row in rows:
            event = dict(row)

            try:
                event["details"] = json.loads(
                    event.pop("details_json")
                )
            except (TypeError, json.JSONDecodeError):
                # Не теряем историю, если старые данные повреждены.
                event["details"] = {}

            result.append(event)

        return result

    def save_checkpoint(self, task_id, name, data=None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "Название контрольной точки не может быть пустым."
            )

        if data is None:
            data = {}

        data_json = _json_dumps(data)
        now = _now()

        with self.db.connect() as con:
            if con.execute(
                "SELECT 1 FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone() is None:
                raise KeyError(
                    f"Задача не найдена: {task_id}"
                )

            con.execute(
                """
                INSERT INTO checkpoints
                (
                    task_id, timestamp, checkpoint_name, data_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    task_id,
                    now,
                    name.strip(),
                    data_json,
                ),
            )

            self._event(
                con,
                task_id,
                "checkpoint",
                f"Контрольная точка: {name.strip()}",
                {"checkpoint_name": name.strip()},
            )

    @staticmethod
    def _event(
        con,
        task_id,
        event_type,
        message,
        details=None,
        details_json=None,
    ):
        if details_json is None:
            details_json = _json_dumps(
                details if details is not None else {}
            )

        con.execute(
            """
            INSERT INTO events
            (
                task_id, timestamp, event_type,
                message, details_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_id,
                _now(),
                event_type,
                message,
                details_json,
            ),
        )