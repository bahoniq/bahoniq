
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
    # КОНТРОЛЬНЫЕ СУММЫ И ИДЕНТИФИКАЦИЯ ФАЙЛОВ
    # ============================================================

    @staticmethod
    def _file_fingerprint(path):
        """Вычисляет SHA-256 файла, не загружая его целиком в память."""
        digest = hashlib.sha256()

        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()

    @classmethod
    def _capture_file_identity(cls, path):
        """
        Запоминает идентичность файла для безопасной очистки.

        SHA-256 проверяет содержимое, а системные атрибуты помогают
        обнаружить замену файла после создания.
        """
        path = Path(path)

        stat_before = path.stat()
        fingerprint = cls._file_fingerprint(path)
        stat_after = path.stat()

        before_identity = (
            stat_before.st_dev,
            stat_before.st_ino,
            stat_before.st_size,
            stat_before.st_mtime_ns,
        )
        after_identity = (
            stat_after.st_dev,
            stat_after.st_ino,
            stat_after.st_size,
            stat_after.st_mtime_ns,
        )

        if before_identity != after_identity:
            raise RuntimeError(
                "Файл результата изменился во время проверки "
                "его идентичности."
            )

        return {
            "device": stat_after.st_dev,
            "inode": stat_after.st_ino,
            "size": stat_after.st_size,
            "mtime_ns": stat_after.st_mtime_ns,
            "sha256": fingerprint,
        }

    @classmethod
    def _remove_owned_output(cls, path, expected_identity):
        """
        Удаляет только проверенный файл, созданный текущим выполнением.

        Если файл исчез, был заменён или изменился, он не удаляется.
        """
        path = Path(path)

        if not isinstance(expected_identity, dict):
            return False

        try:
            current_identity = cls._capture_file_identity(path)
        except FileNotFoundError:
            return False
        except OSError:
            return False
        except Exception:
            return False

        identity_fields = (
            "device",
            "inode",
            "size",
            "mtime_ns",
            "sha256",
        )

        if any(
            current_identity.get(field) != expected_identity.get(field)
            for field in identity_fields
        ):
            return False

        try:
            # Повторная проверка непосредственно перед удалением.
            latest_stat = path.stat()

            if (
                latest_stat.st_dev != expected_identity["device"]
                or latest_stat.st_ino != expected_identity["inode"]
                or latest_stat.st_size != expected_identity["size"]
                or latest_stat.st_mtime_ns != expected_identity["mtime_ns"]
            ):
                return False

            path.unlink()
            return True

        except FileNotFoundError:
            return False
        except OSError:
            return False

    # ============================================================
    # СОЗДАНИЕ ЗАДАЧИ
    # ============================================================

    def create_task(self, instruction, source_path, output_dir=None):
        """Создаёт задачу и регистрирует её в журнале."""

        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("Описание задания не должно быть пустым.")

        if (
            not isinstance(source_path, (str, Path))
            or not str(source_path).strip()
        ):
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
        """Переводит задачу в FAILED, если переход разрешён."""

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
        """Разрешает только имя файла без пути к каталогу."""

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

        if (
            not isinstance(plan_source_value, str)
            or not plan_source_value.strip()
        ):
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

        if (
            not isinstance(plan_output_value, str)
            or not plan_output_value.strip()
        ):
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

        if (
            not isinstance(plan.get("operations"), list)
            or not plan["operations"]
        ):
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

            fingerprint_before = self._file_fingerprint(source)
            source_stat = source.stat()

            analysis = analyze_workbook(source)

            fingerprint_after = self._file_fingerprint(source)

            if fingerprint_before != fingerprint_after:
                raise RuntimeError(
                    "Исходный файл изменился во время анализа. "
                    "Повтори подготовку плана."
                )

            if output_filename is None:
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

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
        """Возвращает последнюю сохранённую контрольную точку."""

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
        """
        Выполняет план после подтверждения.

        Если проверка созданного файла не пройдёт, пытается удалить
        только тот результат, идентичность которого удалось подтвердить.
        Исходный файл и неизвестные файлы не удаляются.
        """

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
        planned_output = Path(plan["output"]).expanduser().resolve()

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

        if planned_output.exists():
            raise FileExistsError(
                f"Файл результата уже существует:\n{planned_output}\n\n"
                "Выполнение отменено, чтобы не перезаписать файл."
            )

        self.engine.add_event(
            task_id,
            "user_confirmed",
            "Пользователь подтвердил выполнение плана.",
            {
                "source_sha256": expected_fingerprint,
                "planned_output": str(planned_output),
            },
        )

        owned_output_identity = None
        verification_passed = False

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

            if not isinstance(result, dict):
                raise RuntimeError(
                    "Исполнитель вернул результат неверного формата."
                )

            result_output_value = result.get("output")

            if (
                not isinstance(result_output_value, str)
                or not result_output_value.strip()
            ):
                raise RuntimeError(
                    "Исполнитель не указал путь итогового файла."
                )

            output = Path(
                result_output_value
            ).expanduser().resolve()

            # Нельзя принимать другой путь вместо утверждённого плана.
            if output != planned_output:
                raise RuntimeError(
                    "Путь результата исполнителя не совпадает "
                    "с путём, утверждённым в плане. "
                    "Неизвестный файл не будет удалён автоматически."
                )

            if not output.is_file():
                raise RuntimeError(
                    "Файл результата не найден после выполнения."
                )

            # Сразу фиксируем идентичность созданного результата.
            # Эта запись нужна для безопасной очистки при ошибке проверки.
            owned_output_identity = self._capture_file_identity(output)

            if output.stat().st_size == 0:
                raise RuntimeError(
                    "Файл результата пуст."
                )

            # Исполнитель должен сообщить контрольную сумму результата.
            expected_output_hash = result.get("output_sha256")

            if (
                not isinstance(expected_output_hash, str)
                or not expected_output_hash
            ):
                raise RuntimeError(
                    "Исполнитель не предоставил контрольную сумму "
                    "итогового файла. Результат не подтверждён."
                )

            if owned_output_identity["sha256"] != expected_output_hash:
                raise RuntimeError(
                    "Контрольная сумма итогового файла не совпадает "
                    "с контрольной суммой, возвращённой исполнителем."
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

            self.engine.transition(
                task_id,
                TaskStatus.VERIFYING,
                "Файл создан. Проверяем итоговую книгу.",
            )

            if self._file_fingerprint(source) != expected_fingerprint:
                raise RuntimeError(
                    "Контрольная сумма исходного файла изменилась "
                    "во время выполнения."
                )

            # execute_operations already reopens the saved workbook in
            # read-only mode, verifies its sheet list and checks the output
            # hash. Running analyze_workbook here repeated a full statistical
            # scan (duplicates, blanks, examples) although verification only
            # needs structural evidence. For split_to_sheets we additionally
            # reconcile input and distributed row counts from the executor.
            result_sheets = result.get("sheets", [])
            if not isinstance(result_sheets, list) or not result_sheets:
                raise RuntimeError(
                    "Проверка не пройдена: исполнитель не подтвердил листы."
                )

            split_checks = []
            for change in result.get("changes", []):
                if change.get("type") != "split_to_sheets":
                    continue
                source_rows = change.get("source_data_rows")
                distributed_rows = change.get("distributed_rows")
                created_sheets = change.get("created_sheets", [])
                if (
                    not isinstance(source_rows, int)
                    or not isinstance(distributed_rows, int)
                    or source_rows != distributed_rows
                    or not created_sheets
                ):
                    raise RuntimeError(
                        "Проверка разделения не пройдена: количество строк "
                        "до и после операции не совпадает."
                    )
                split_checks.append({
                    "source_rows": source_rows,
                    "distributed_rows": distributed_rows,
                    "created_sheet_count": len(created_sheets),
                })

            verification = {
                "mode": "structural_fast",
                "sheet_count": len(result_sheets),
                "sheets": result_sheets,
                "split_to_sheets": split_checks,
                "output_sha256": owned_output_identity["sha256"],
            }

            if result.get("source_was_modified") is not False:
                raise RuntimeError(
                    "Результат не подтверждает сохранность исходника."
                )

            # После успешных проверок сам Excel-файл считается проверенным.
            # Ошибки последующей записи журнала не должны удалять
            # уже проверенный результат.
            verification_passed = True

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
                "Итоговый Excel-файл открыт и структурно проверен.",
                {
                    "output": str(output),
                    "sheet_count": verification["sheet_count"],
                    "file_size": output.stat().st_size,
                    "output_sha256": owned_output_identity["sha256"],
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
            # Удаляем результат только при ошибке до успешной проверки.
            # Если файл был заменён или изменён, безопасная очистка
            # откажется удалять его.
            if not verification_passed and owned_output_identity is not None:
                removed = self._remove_owned_output(
                    planned_output,
                    owned_output_identity,
                )

                if removed:
                    self._record_error(
                        task_id,
                        "output_cleanup",
                        "Непрошедший проверку результат удалён: ",
                        exc,
                    )
                else:
                    self._record_error(
                        task_id,
                        "output_cleanup_skipped",
                        (
                            "Результат не удалён: файл отсутствует, "
                            "изменён или его идентичность не подтверждена. "
                            "Причина ошибки: "
                        ),
                        exc,
                    )

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
