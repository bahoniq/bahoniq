
import hashlib
import json
from datetime import datetime
from pathlib import Path

from .analyzer import analyze_workbook
from .engine import TaskEngine
from .models import TaskStatus
from .operations import plan_operations, execute_operations


class ExcelWorkflow:
    """Управление анализом, подготовкой, выполнением и историей Excel-задач."""

    def __init__(self, engine):
        if not isinstance(engine, TaskEngine):
            raise TypeError("engine должен быть экземпляром TaskEngine.")
        self.engine = engine

    # ============================================================
    # КОНТРОЛЬНАЯ СУММА ИСХОДНОГО ФАЙЛА
    # ============================================================

    @staticmethod
    def _file_fingerprint(path):
        """Вычисляет SHA-256, не загружая весь файл в память."""
        digest = hashlib.sha256()

        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()

    # ============================================================
    # СОЗДАНИЕ ЗАДАЧИ
    # ============================================================

    def create_task(self, instruction, source_path, output_dir=None):
        """Создаёт задачу и регистрирует её в журнале."""

        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Описание задания не должно быть пустым.")

        if not isinstance(source_path, (str, Path)) or not str(source_path).strip():
            raise ValueError("Не указан исходный Excel-файл.")

        source = Path(source_path).expanduser().resolve()

        if not source.is_file():
            raise FileNotFoundError(
                f"Исходный файл не найден: {source}"
            )

        if source.suffix.lower() not in {".xls", ".xlsx", ".xlsm"}:
            raise ValueError(
                "Поддерживаются файлы Excel форматов .xls, .xlsx и .xlsm."
            )

        destination = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else source.parent / "BahonIQ_Results"
        )

        if destination == source:
            raise ValueError(
                "Каталог результатов не может совпадать с исходным файлом."
            )

        task = self.engine.create_task(
            instruction=instruction.strip(),
            source_path=str(source),
            output_dir=str(destination),
        )

        self.engine.add_event(
            task.id,
            "workflow_created",
            "Задача Excel AI создана.",
            {
                "source": str(source),
                "output_dir": str(destination),
            },
        )

        return task

    # ============================================================
    # ЖУРНАЛИРОВАНИЕ ОШИБОК
    # ============================================================

    def _record_error(self, task_id, event_type, message, exc):
        """Записывает ошибку, не подменяя исходное исключение."""

        try:
            self.engine.add_event(
                task_id,
                event_type,
                message + str(exc),
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
        except Exception:
            # Ошибка журнала не должна скрывать основную ошибку.
            pass

    def _fail_if_possible(
        self,
        task_id,
        message,
        exc,
        allowed_statuses,
    ):
        """Переводит задачу в FAILED, если это разрешено моделью статусов."""

        try:
            current = self.engine.get_task(task_id)

            if current.status not in allowed_statuses:
                return

            self.engine.transition(
                task_id,
                TaskStatus.FAILED,
                message,
                error=str(exc),
            )

        except Exception as transition_error:
            self._record_error(
                task_id,
                "status_transition_error",
                "Не удалось зарегистрировать статус ошибки: ",
                transition_error,
            )

    # ============================================================
    # ПРОВЕРКА ИМЕНИ РЕЗУЛЬТАТА
    # ============================================================

    @staticmethod
    def _validate_output_filename(output_filename):
        """Разрешает только имя файла, без пути к каталогу."""

        if (
            not isinstance(output_filename, str)
            or not output_filename.strip()
            or output_filename != output_filename.strip()
            or output_filename in {".", ".."}
            or Path(output_filename).name != output_filename
            or "/" in output_filename
            or "\\" in output_filename
        ):
            raise ValueError(
                "Укажи только имя выходного файла без пути."
            )

        return output_filename

    # ============================================================
    # ПРОВЕРКА ПЛАНА
    # ============================================================

    def _validate_plan_for_task(self, task, plan):
        """Проверяет соответствие плана текущей задаче."""

        if not isinstance(plan, dict):
            raise ValueError(
                "Сохранённый план имеет неверный формат."
            )

        if plan.get("requires_confirmation") is not True:
            raise PermissionError(
                "В плане отсутствует обязательное подтверждение."
            )

        if plan.get("source_will_be_modified") is not False:
            raise ValueError(
                "План не гарантирует сохранность исходного файла."
            )

        if not task.source_path:
            raise ValueError(
                "У задачи не указан исходный Excel-файл."
            )

        source = Path(task.source_path).expanduser().resolve()

        plan_source_value = plan.get("source")

        if not isinstance(plan_source_value, str) or not plan_source_value.strip():
            raise ValueError(
                "В плане не указан исходный файл."
            )

        plan_source = Path(plan_source_value).expanduser().resolve()

        if source != plan_source:
            raise ValueError(
                "Исходный файл в сохранённом плане "
                "не совпадает с исходным файлом задачи."
            )

        expected_dir = (
            Path(task.output_dir).expanduser().resolve()
            if task.output_dir
            else source.parent / "BahonIQ_Results"
        )

        plan_output_value = plan.get("output")

        if not isinstance(plan_output_value, str) or not plan_output_value.strip():
            raise ValueError(
                "В плане не указан путь результата."
            )

        plan_output = Path(plan_output_value).expanduser().resolve()

        if plan_output.parent != expected_dir:
            raise ValueError(
                "Путь результата в плане не совпадает "
                "с каталогом результатов задачи."
            )

        if plan_output == source:
            raise ValueError(
                "Выходной файл не может совпадать с исходником."
            )

        expected_suffix = (
            ".xlsx"
            if source.suffix.lower() == ".xls"
            else source.suffix.lower()
        )

        if plan_output.suffix.lower() != expected_suffix:
            raise ValueError(
                "Для исходного .xls результат должен быть .xlsx; "
                "для .xlsx и .xlsm формат результата должен совпадать "
                "с исходным файлом."
            )

        if not isinstance(plan.get("operations"), list) or not plan["operations"]:
            raise ValueError(
                "В сохранённом плане отсутствуют операции."
            )

        if not isinstance(plan.get("steps"), list):
            raise ValueError(
                "В сохранённом плане отсутствует описание шагов."
            )

        if not source.is_file():
            raise FileNotFoundError(
                f"Исходный файл не найден: {source}"
            )

        return plan

    # ============================================================
    # ПОДГОТОВКА ПЛАНА
    # ============================================================

    def prepare(self, task_id, operations, output_filename=None):
        """Анализирует книгу и сохраняет план без выполнения операций."""

        task = self.engine.get_task(task_id)

        if task.status != TaskStatus.CREATED:
            raise ValueError(
                "Подготовить план можно только для новой задачи. "
                f"Текущий статус: {task.status.value}"
            )

        if not task.source_path:
            raise ValueError(
                "У задачи не указан исходный Excel-файл."
            )

        if not isinstance(operations, list) or not operations:
            raise ValueError(
                "Список операций пуст. Сначала разбери описание задания."
            )

        source = Path(task.source_path).expanduser().resolve()

        output_dir = (
            Path(task.output_dir).expanduser().resolve()
            if task.output_dir
            else source.parent / "BahonIQ_Results"
        )

        self.engine.transition(
            task_id,
            TaskStatus.ANALYZING,
            "Начат анализ Excel-книги.",
        )

        try:
            if not source.is_file():
                raise FileNotFoundError(
                    f"Исходный файл не найден: {source}"
                )

            # Запоминаем состояние исходного файла перед анализом.
            fingerprint_before = self._file_fingerprint(source)
            source_stat = source.stat()

            analysis = analyze_workbook(source)

            # Проверяем, что во время анализа файл не менялся.
            fingerprint_after = self._file_fingerprint(source)

            if fingerprint_before != fingerprint_after:
                raise RuntimeError(
                    "Исходный файл изменился во время анализа. "
                    "Повтори подготовку плана."
                )

            if output_filename is None:
                stamp = datetime.now().strftime(
                    "%Y%m%d_%H%M%S_%f"
                )

                output_suffix = (
                    ".xlsx"
                    if source.suffix.lower() == ".xls"
                    else source.suffix
                )

                output_filename = (
                    f"{source.stem}_BahonIQ_{stamp}{output_suffix}"
                )

            output_filename = self._validate_output_filename(
                output_filename
            )

            # Файлы .xls преобразуются в результат .xlsx.
            if source.suffix.lower() == ".xls":
                requested_suffix = Path(output_filename).suffix.lower()

                if requested_suffix in {"", ".xls"}:
                    output_filename = str(
                        Path(output_filename).with_suffix(".xlsx")
                    )
                elif requested_suffix != ".xlsx":
                    raise ValueError(
                        "Для исходного .xls укажи имя результата "
                        "с расширением .xlsx."
                    )

            output = (output_dir / output_filename).resolve()

            if output == source:
                raise ValueError(
                    "Результат не может перезаписывать исходный файл."
                )

            # Не перезаписываем ранее существующий файл.
            if output.exists():
                raise FileExistsError(
                    f"Файл результата уже существует:\n{output}\n\n"
                    "Выбери другое имя файла."
                )

            plan = plan_operations(
                source,
                output,
                operations,
            )

            self._validate_plan_for_task(task, plan)

            # Повторная проверка после построения плана.
            if self._file_fingerprint(source) != fingerprint_before:
                raise RuntimeError(
                    "Исходный файл изменился во время подготовки плана. "
                    "Повтори подготовку."
                )

            self.engine.save_checkpoint(
                task_id,
                "analysis_report",
                analysis,
            )

            self.engine.save_checkpoint(
                task_id,
                "source_fingerprint",
                {
                    "sha256": fingerprint_before,
                    "size": source_stat.st_size,
                    "mtime_ns": source_stat.st_mtime_ns,
                },
            )

            self.engine.save_checkpoint(
                task_id,
                "operation_plan",
                plan,
            )

            self.engine.add_event(
                task_id,
                "plan_ready",
                "Анализ завершён. План ожидает подтверждения.",
                {
                    "sheet_count": analysis["sheet_count"],
                    "steps": plan["steps"],
                    "output": plan["output"],
                    "source_sha256": fingerprint_before,
                },
            )

            updated = self.engine.transition(
                task_id,
                TaskStatus.PLANNED,
                "План подготовлен. Выполнение ещё не запускалось.",
            )

            return {
                "task": updated,
                "analysis": analysis,
                "plan": plan,
                "requires_confirmation": True,
            }

        except Exception as exc:
            self._fail_if_possible(
                task_id,
                "Не удалось подготовить план.",
                exc,
                {TaskStatus.ANALYZING},
            )

            self._record_error(
                task_id,
                "workflow_error",
                "Ошибка подготовки: ",
                exc,
            )

            raise

    # ============================================================
    # ЧТЕНИЕ КОНТРОЛЬНЫХ ТОЧЕК
    # ============================================================

    def _get_checkpoint(self, task_id, checkpoint_name):
        """Возвращает последнюю контрольную точку."""

        with self.engine.db.connect() as con:
            row = con.execute(
                """
                SELECT data_json
                FROM checkpoints
                WHERE task_id = ?
                  AND checkpoint_name = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (task_id, checkpoint_name),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Контрольная точка «{checkpoint_name}» не найдена."
            )

        try:
            data = json.loads(row["data_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Не удалось прочитать контрольную точку "
                f"«{checkpoint_name}»."
            ) from exc

        return data

    def get_plan(self, task_id):
        """Возвращает последний сохранённый план задачи."""

        task = self.engine.get_task(task_id)

        if task.status != TaskStatus.PLANNED:
            raise ValueError(
                f"План недоступен в статусе {task.status.value}."
            )

        plan = self._get_checkpoint(
            task_id,
            "operation_plan",
        )

        if not isinstance(plan, dict):
            raise RuntimeError(
                "Сохранённый план имеет неверный формат."
            )

        return plan

    # ============================================================
    # ПОДТВЕРЖДЕНИЕ И ВЫПОЛНЕНИЕ
    # ============================================================

    def confirm_and_execute(self, task_id, confirmed=False):
        """Выполняет план только после явного подтверждения пользователя."""

        if confirmed is not True:
            raise PermissionError(
                "Нужно проверить план и явно подтвердить выполнение."
            )

        task = self.engine.get_task(task_id)

        if task.status != TaskStatus.PLANNED:
            raise ValueError(
                "Выполнение невозможно в статусе "
                f"{task.status.value}."
            )

        plan = self.get_plan(task_id)
        self._validate_plan_for_task(task, plan)

        source = Path(task.source_path).expanduser().resolve()

        # Получаем SHA-256, сохранённый при подготовке плана.
        saved_fingerprint = self._get_checkpoint(
            task_id,
            "source_fingerprint",
        )

        if (
            not isinstance(saved_fingerprint, dict)
            or not isinstance(saved_fingerprint.get("sha256"), str)
            or not saved_fingerprint["sha256"]
        ):
            raise RuntimeError(
                "Нет контрольной суммы исходного файла. "
                "Подготовь план заново перед выполнением."
            )

        expected_fingerprint = saved_fingerprint["sha256"]

        if self._file_fingerprint(source) != expected_fingerprint:
            raise RuntimeError(
                "Исходный файл изменился после подготовки плана. "
                "Выполнение отменено. Подготовь план заново."
            )

        output_path = Path(
            plan["output"]
        ).expanduser().resolve()

        if output_path.exists():
            raise FileExistsError(
                f"Файл результата уже существует:\n{output_path}\n\n"
                "Выполнение отменено, чтобы не перезаписать файл."
            )

        self.engine.add_event(
            task_id,
            "user_confirmed",
            "Пользователь подтвердил выполнение плана.",
            {
                "source_sha256": expected_fingerprint,
            },
        )

        try:
            self.engine.transition(
                task_id,
                TaskStatus.QUEUED,
                "Задача поставлена в очередь.",
            )

            self.engine.transition(
                task_id,
                TaskStatus.RUNNING,
                "Выполнение операций начато.",
            )

            # Последняя проверка непосредственно перед запуском.
            if self._file_fingerprint(source) != expected_fingerprint:
                raise RuntimeError(
                    "Исходный файл изменился перед запуском операций. "
                    "Выполнение отменено."
                )

            result = execute_operations(
                plan,
                confirmed=True,
            )

            self.engine.transition(
                task_id,
                TaskStatus.VERIFYING,
                "Файл создан. Проверяем итоговую книгу.",
            )

            output = Path(
                result["output"]
            ).expanduser().resolve()

            if not output.is_file():
                raise RuntimeError(
                    "Файл результата не найден после выполнения."
                )

            if output.stat().st_size == 0:
                raise RuntimeError(
                    "Файл результата пуст."
                )

            expected_dir = (
                Path(task.output_dir).expanduser().resolve()
                if task.output_dir
                else source.parent / "BahonIQ_Results"
            )

            if output.parent != expected_dir:
                raise RuntimeError(
                    "Путь итогового файла не совпадает "
                    "с каталогом результатов задачи."
                )

            if output == source:
                raise RuntimeError(
                    "Итоговый файл совпадает с исходником."
                )

            # Проверяем, что исходник не изменился в ходе выполнения.
            if self._file_fingerprint(source) != expected_fingerprint:
                raise RuntimeError(
                    "Контрольная сумма исходного файла изменилась "
                    "во время выполнения."
                )

            verification = analyze_workbook(output)

            if verification.get("sheet_count", 0) < 1:
                raise RuntimeError(
                    "Проверка не пройдена: в итоговом файле нет листов."
                )

            if result.get("source_was_modified") is not False:
                raise RuntimeError(
                    "Результат не подтверждает сохранность исходника."
                )

            self.engine.save_checkpoint(
                task_id,
                "execution_result",
                result,
            )

            self.engine.save_checkpoint(
                task_id,
                "verification_report",
                verification,
            )

            self.engine.add_event(
                task_id,
                "verification_passed",
                "Итоговый Excel-файл открыт и проанализирован.",
                {
                    "output": str(output),
                    "sheet_count": verification["sheet_count"],
                    "file_size": output.stat().st_size,
                },
            )

            completed = self.engine.transition(
                task_id,
                TaskStatus.COMPLETED,
                "Операции завершены, проверка пройдена.",
            )

            return {
                "task": completed,
                "result": result,
                "verification": verification,
            }

        except Exception as exc:
            self._fail_if_possible(
                task_id,
                "Выполнение или проверка завершились ошибкой.",
                exc,
                {
                    TaskStatus.QUEUED,
                    TaskStatus.RUNNING,
                    TaskStatus.VERIFYING,
                },
            )

            self._record_error(
                task_id,
                "workflow_error",
                "Ошибка выполнения: ",
                exc,
            )

            raise

    # ============================================================
    # ИСТОРИЯ
    # ============================================================

    def get_history(self, task_id):
        """Возвращает состояние задачи и журнал событий."""

        return {
            "task": self.engine.get_task(task_id),
            "events": self.engine.get_events(task_id),
        }
