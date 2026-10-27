import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk

from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog


PROJECT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"
SETTINGS_FILE = BASE_DIR / "settings.json"
HISTORY_FILE = BASE_DIR / "history.json"
DESCRIPTIONS_FILE = BASE_DIR / "descriptions.json"

for folder in (SCRIPTS_DIR, RESULTS_DIR, LOGS_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


class ScriptManager:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("BahonIQ  ???????? ????????")
        self.window.geometry("1080x720")
        self.window.minsize(850, 580)

        self.scripts = []
        self.input_path = ""
        self.input_type = ""
        self.results_path = str(RESULTS_DIR)
        self.running = False
        self.current_process = None

        settings = read_json(SETTINGS_FILE, {})
        self.input_path = settings.get("input_path", "")
        self.input_type = settings.get("input_type", "")
        self.results_path = settings.get(
            "results_path", str(RESULTS_DIR)
        )
        self.auto_open_results = tk.BooleanVar(
            value=settings.get("auto_open_results", False)
        )

        self.search_var = tk.StringVar()
        self.input_var = tk.StringVar()
        self.results_var = tk.StringVar(value=self.results_path)
        self.status_var = tk.StringVar(value="????? ? ??????")

        self.build_ui()
        self.refresh_scripts()
        self.update_input_label()

        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

    def build_ui(self):
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text="???????? ????????",
            font=("Segoe UI", 17, "bold")
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text="?????????? Python-???????, ?????????? ?? ? ?????????????? ??????????."
        ).pack(anchor="w", pady=(2, 12))

        main = ttk.Panedwindow(outer, orient="horizontal")
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main, padding=(0, 0, 10, 0))
        right = ttk.Frame(main)
        main.add(left, weight=1)
        main.add(right, weight=3)

        ttk.Label(left, text="?????? ????????").pack(anchor="w")

        search_row = ttk.Frame(left)
        search_row.pack(fill="x", pady=(5, 6))

        search_entry = ttk.Entry(
            search_row, textvariable=self.search_var
        )
        search_entry.pack(fill="x", expand=True)
        self.search_var.trace_add(
            "write", lambda *_: self.refresh_scripts()
        )

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)

        self.script_list = tk.Listbox(
            list_frame,
            font=("Segoe UI", 10),
            activestyle="dotbox",
            exportselection=False
        )
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical",
            command=self.script_list.yview
        )
        self.script_list.configure(yscrollcommand=scrollbar.set)
        self.script_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.script_list.bind(
            "<<ListboxSelect>>", self.on_script_selected
        )
        self.script_list.bind(
            "<Double-Button-1>", lambda _: self.run_selected()
        )

        left_buttons = ttk.Frame(left)
        left_buttons.pack(fill="x", pady=(8, 0))

        ttk.Button(
            left_buttons, text="???????? .py",
            command=self.add_script
        ).pack(fill="x", pady=2)

        ttk.Button(
            left_buttons, text="???????? ????????? ????????",
            command=self.add_multiple_scripts
        ).pack(fill="x", pady=2)

        ttk.Button(
            left_buttons, text="???????? ??????",
            command=self.refresh_scripts
        ).pack(fill="x", pady=2)

        ttk.Button(
            left_buttons, text="?????????????",
            command=self.rename_script
        ).pack(fill="x", pady=2)

        ttk.Button(
            left_buttons, text="??????? ??????",
            command=self.delete_script
        ).pack(fill="x", pady=2)

        ttk.Button(
            left_buttons, text="???????? ???????",
            command=self.edit_description
        ).pack(fill="x", pady=2)

        ttk.Button(
            left_buttons, text="??????? ????? ???????",
            command=self.open_selected_script_folder
        ).pack(fill="x", pady=2)

        ttk.Label(right, text="????????? ??????").pack(anchor="w")

        self.selected_name = ttk.Label(
            right, text="??????? ???????? ??????",
            font=("Segoe UI", 12, "bold")
        )
        self.selected_name.pack(anchor="w", pady=(4, 2))

        self.description_label = ttk.Label(
            right, text="???????? ?? ??????",
            wraplength=650, justify="left"
        )
        self.description_label.pack(anchor="w", pady=(0, 12))

        input_box = ttk.LabelFrame(
            right, text="??????? ??????", padding=8
        )
        input_box.pack(fill="x", pady=(0, 8))

        ttk.Label(
            input_box, textvariable=self.input_var,
            wraplength=650
        ).pack(anchor="w", fill="x")

        input_buttons = ttk.Frame(input_box)
        input_buttons.pack(fill="x", pady=(6, 0))

        ttk.Button(
            input_buttons, text="??????? ????",
            command=self.choose_input_file
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            input_buttons, text="??????? ?????",
            command=self.choose_input_folder
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            input_buttons, text="???????? ?????",
            command=self.clear_input
        ).pack(side="left")

        result_box = ttk.LabelFrame(
            right, text="????? ???????????", padding=8
        )
        result_box.pack(fill="x", pady=(0, 8))

        ttk.Label(
            result_box, textvariable=self.results_var,
            wraplength=650
        ).pack(anchor="w", fill="x")

        result_buttons = ttk.Frame(result_box)
        result_buttons.pack(fill="x", pady=(6, 0))

        ttk.Button(
            result_buttons, text="???????? ?????",
            command=self.choose_results_folder
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            result_buttons, text="??????? ??????????",
            command=self.open_results_folder
        ).pack(side="left")

        ttk.Checkbutton(
            result_box,
            text="????????? ????? ??????????? ????? ???????",
            variable=self.auto_open_results,
            command=self.save_settings
        ).pack(anchor="w", pady=(6, 0))

        run_row = ttk.Frame(right)
        run_row.pack(fill="x", pady=(0, 8))

        self.run_button = ttk.Button(
            run_row, text=" ????????? ??????",
            command=self.run_selected
        )
        self.run_button.pack(side="left", padx=(0, 6))

        self.stop_button = ttk.Button(
            run_row, text=" ??????????",
            command=self.stop_selected,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=6)

        ttk.Button(
            run_row, text="??????? ????????? ???",
            command=self.open_latest_log
        ).pack(side="left", padx=6)

        ttk.Button(
            run_row, text="??????? ????????",
            command=self.show_history
        ).pack(side="left", padx=6)

        ttk.Button(
            run_row, text="??????????",
            command=self.show_statistics
        ).pack(side="left", padx=6)

        ttk.Label(right, text="????? ? ????????? ???????").pack(
            anchor="w"
        )

        output_frame = ttk.Frame(right)
        output_frame.pack(fill="both", expand=True, pady=(4, 0))

        self.output = tk.Text(
            output_frame,
            height=12,
            wrap="word",
            font=("Consolas", 9),
            state="disabled"
        )
        output_scroll = ttk.Scrollbar(
            output_frame, orient="vertical",
            command=self.output.yview
        )
        self.output.configure(yscrollcommand=output_scroll.set)
        self.output.pack(side="left", fill="both", expand=True)
        output_scroll.pack(side="right", fill="y")

        ttk.Label(
            outer, textvariable=self.status_var,
            relief="sunken", anchor="w", padding=5
        ).pack(fill="x", pady=(10, 0))

    def save_settings(self):
        write_json(SETTINGS_FILE, {
            "input_path": self.input_path,
            "input_type": self.input_type,
            "results_path": self.results_path,
            "auto_open_results": self.auto_open_results.get()
        })

    def refresh_scripts(self):
        selected_name = None
        if hasattr(self, "script_list"):
            selection = self.script_list.curselection()
            if selection:
                selected_name = self.script_list.get(selection[0])

        query = self.search_var.get().strip().casefold()
        self.scripts = sorted(
            SCRIPTS_DIR.glob("*.py"),
            key=lambda p: p.name.casefold()
        )

        self.script_list.delete(0, "end")
        visible = []

        descriptions = read_json(DESCRIPTIONS_FILE, {})

        for script in self.scripts:
            description = descriptions.get(script.name, "")
            if not description:
                try:
                    lines = script.read_text(
                        encoding="utf-8-sig", errors="replace"
                    ).splitlines()[:12]
                    comments = [
                        line.lstrip()[1:].strip()
                        for line in lines
                        if line.lstrip().startswith("#")
                        and line.lstrip() not in ("#!/usr/bin/env python",)
                    ]
                    description = comments[0] if comments else ""
                except OSError:
                    description = ""

            if query and query not in (
                script.name + " " + description
            ).casefold():
                continue

            visible.append(script)
            self.script_list.insert("end", script.name)

        self.visible_scripts = visible

        if selected_name:
            for index, script in enumerate(visible):
                if script.name == selected_name:
                    self.script_list.selection_set(index)
                    self.script_list.activate(index)
                    break

        if self.script_list.curselection():
            self.on_script_selected()
        else:
            self.selected_name.configure(text="??????? ???????? ??????")
            self.description_label.configure(text="???????? ?? ??????")

    def selected_script(self):
        selection = self.script_list.curselection()
        if not selection:
            return None
        index = selection[0]
        if index >= len(self.visible_scripts):
            return None
        return self.visible_scripts[index]

    def on_script_selected(self, _event=None):
        script = self.selected_script()
        if not script:
            return

        descriptions = read_json(DESCRIPTIONS_FILE, {})
        description = descriptions.get(script.name, "")

        if not description:
            try:
                lines = script.read_text(
                    encoding="utf-8-sig", errors="replace"
                ).splitlines()[:12]
                comments = [
                    line.lstrip()[1:].strip()
                    for line in lines
                    if line.lstrip().startswith("#")
                ]
                description = comments[0] if comments else ""
            except OSError:
                description = ""

        self.selected_name.configure(text=script.name)
        self.description_label.configure(
            text=description or "???????? ?? ??????"
        )

    def add_script(self):
        source = filedialog.askopenfilename(
            parent=self.window,
            title="???????? Python-??????",
            filetypes=[("Python scripts", "*.py")]
        )
        if not source:
            return

        source_path = Path(source)
        destination = SCRIPTS_DIR / source_path.name

        if source_path.resolve() == destination.resolve():
            self.refresh_scripts()
            self.status_var.set("?????? ??? ????????? ? ??????? ?????")
            return

        if destination.exists():
            overwrite = messagebox.askyesno(
                "???? ??? ??????????",
                f"{destination.name} ??? ????. ???????? ????",
                parent=self.window
            )
            if not overwrite:
                return

        try:
            shutil.copy2(source_path, destination)
            self.refresh_scripts()
            self.status_var.set(f"???????? ??????: {destination.name}")
        except Exception as exc:
            messagebox.showerror(
                "?????? ??????????", str(exc), parent=self.window
            )

    def add_multiple_scripts(self):
        sources = filedialog.askopenfilenames(
            parent=self.window,
            title="???????? ????????? Python-????????",
            filetypes=[("Python scripts", "*.py")]
        )
        if not sources:
            return

        added = 0
        skipped = 0
        errors = []

        for source in sources:
            source_path = Path(source)
            destination = SCRIPTS_DIR / source_path.name

            try:
                if source_path.resolve() == destination.resolve():
                    skipped += 1
                    continue

                if destination.exists():
                    replace = messagebox.askyesno(
                        "???? ??? ??????????",
                        f"{destination.name} ??? ????. ???????? ????",
                        parent=self.window
                    )
                    if not replace:
                        skipped += 1
                        continue

                shutil.copy2(source_path, destination)
                added += 1

            except Exception as exc:
                errors.append(f"{source_path.name}: {exc}")

        self.refresh_scripts()
        summary = (
            f"?????????: {added}\n"
            f"?????????: {skipped}\n"
            f"??????: {len(errors)}"
        )

        if errors:
            summary += "\n\n" + "\n".join(errors[:10])

        self.status_var.set(
            f"???????? ?????????? ?????????: {added} ?????????"
        )
        messagebox.showinfo(
            "?????????? ????????",
            summary,
            parent=self.window
        )

    def rename_script(self):
        script = self.selected_script()
        if not script:
            messagebox.showwarning(
                "??????????????", "???????? ??????.",
                parent=self.window
            )
            return

        name = simpledialog.askstring(
            "????????????? ??????",
            "????? ??? ??? ?????????? .py:",
            initialvalue=script.stem,
            parent=self.window
        )
        if name is None:
            return

        name = name.strip()
        if (
            not name or name in (".", "..")
            or any(ch in name for ch in '\\/:*?"<>|')
        ):
            messagebox.showerror(
                "???????????? ???", "??????? ?????????? ???.",
                parent=self.window
            )
            return

        destination = SCRIPTS_DIR / (name + ".py")
        if destination.exists() and destination != script:
            messagebox.showerror(
                "??????????????", "????? ???? ??? ??????????.",
                parent=self.window
            )
            return

        descriptions = read_json(DESCRIPTIONS_FILE, {})
        old_description = descriptions.pop(script.name, None)

        try:
            script.rename(destination)
            if old_description is not None:
                descriptions[destination.name] = old_description
                write_json(DESCRIPTIONS_FILE, descriptions)
            self.refresh_scripts()
            self.status_var.set("?????? ????????????")
        except Exception as exc:
            messagebox.showerror(
                "?????? ??????????????", str(exc),
                parent=self.window
            )

    def delete_script(self):
        script = self.selected_script()
        if not script:
            messagebox.showwarning(
                "????????", "???????? ??????.",
                parent=self.window
            )
            return

        if not messagebox.askyesno(
            "??????? ???????",
            f"??????? ???? {script.name} ?? ??????????\n"
            "???????? ???? ?? ????????? ????????? ?? ?????????.",
            parent=self.window
        ):
            return

        try:
            script.unlink()
            descriptions = read_json(DESCRIPTIONS_FILE, {})
            descriptions.pop(script.name, None)
            write_json(DESCRIPTIONS_FILE, descriptions)
            self.refresh_scripts()
            self.status_var.set("?????? ??????")
        except Exception as exc:
            messagebox.showerror(
                "?????? ????????", str(exc), parent=self.window
            )

    def edit_description(self):
        script = self.selected_script()
        if not script:
            messagebox.showwarning(
                "????????", "???????? ??????.",
                parent=self.window
            )
            return

        descriptions = read_json(DESCRIPTIONS_FILE, {})
        current = descriptions.get(script.name, "")

        value = simpledialog.askstring(
            "???????? ???????",
            f"??????? ???????? ??? {script.name}:",
            initialvalue=current,
            parent=self.window
        )
        if value is None:
            return

        descriptions[script.name] = value.strip()
        write_json(DESCRIPTIONS_FILE, descriptions)
        self.on_script_selected()
        self.status_var.set("???????? ?????????")

    def choose_input_file(self):
        path = filedialog.askopenfilename(
            parent=self.window, title="???????? ??????? ????"
        )
        if path:
            self.input_path = path
            self.input_type = "file"
            self.update_input_label()
            self.save_settings()

    def choose_input_folder(self):
        path = filedialog.askdirectory(
            parent=self.window, title="???????? ??????? ?????"
        )
        if path:
            self.input_path = path
            self.input_type = "folder"
            self.update_input_label()
            self.save_settings()

    def clear_input(self):
        self.input_path = ""
        self.input_type = ""
        self.update_input_label()
        self.save_settings()

    def update_input_label(self):
        if self.input_path:
            self.input_var.set(
                f"{self.input_type}: {self.input_path}"
            )
        else:
            self.input_var.set(
                "?? ???????. ?????? ????? ??????? ??? ????????? ??????? ??????."
            )

    def choose_results_folder(self):
        path = filedialog.askdirectory(
            parent=self.window,
            title="???????? ????? ??? ???????????",
            initialdir=self.results_path
            if Path(self.results_path).is_dir() else str(RESULTS_DIR)
        )
        if path:
            self.results_path = path
            Path(path).mkdir(parents=True, exist_ok=True)
            self.results_var.set(path)
            self.save_settings()

    def open_folder(self, path):
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror(
                "?? ??????? ??????? ?????", str(exc),
                parent=self.window
            )

    def open_results_folder(self):
        self.open_folder(self.results_path)

    def open_selected_script_folder(self):
        script = self.selected_script()
        if not script:
            messagebox.showwarning(
                "????? ???????", "???????? ??????.",
                parent=self.window
            )
            return
        self.open_folder(script.parent)

    def append_output(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def run_selected(self):
        script = self.selected_script()
        if not script:
            messagebox.showwarning(
                "??????", "??????? ???????? ??????.",
                parent=self.window
            )
            return

        if self.running:
            messagebox.showinfo(
                "??????", "?????? ??? ???????????.",
                parent=self.window
            )
            return

        if not messagebox.askyesno(
            "????????????? ???????",
            f"????????? ???????\n\n{script.name}\n\n"
            "?????????? ?????? ???????, ??????? ?????????.",
            parent=self.window
        ):
            return

        try:
            Path(self.results_path).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(
                "????? ???????????", str(exc), parent=self.window
            )
            return

        self.save_settings()
        self.running = True
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

        started = datetime.now()
        stamp = started.strftime("%Y%m%d_%H%M%S")
        log_path = LOGS_DIR / f"{script.stem}_{stamp}.log"

        env = os.environ.copy()
        env["BAHONIQ_RESULTS_DIR"] = self.results_path
        env["BAHONIQ_INPUT_PATH"] = self.input_path
        env["BAHONIQ_INPUT_TYPE"] = self.input_type

        command = [sys.executable, "-u", str(script)]
        if self.input_path:
            command.append(self.input_path)

        self.status_var.set(f"???????????: {script.name}")
        self.append_output(
            f"??????: {started:%Y-%m-%d %H:%M:%S}\n"
            f"??????: {script.name}\n"
            f"??????????: {self.results_path}\n\n"
        )

        threading.Thread(
            target=self._run_worker,
            args=(script, command, env, log_path, started),
            daemon=True
        ).start()

    def _run_worker(self, script, command, env, log_path, started):
        return_code = -1
        error_text = ""

        try:
            with log_path.open("w", encoding="utf-8") as log:
                log.write(f"Script: {script}\n")
                log.write(f"Started: {started.isoformat()}\n\n")

                self.current_process = subprocess.Popen(
                    command,
                    cwd=str(PROJECT_DIR),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1
                )

                if self.current_process.stdout:
                    for line in self.current_process.stdout:
                        log.write(line)
                        log.flush()
                        self.window.after(
                            0, self.append_output, line
                        )

                return_code = self.current_process.wait()

                if return_code != 0:
                    error_text = f"??? ??????????: {return_code}"

                log.write(
                    f"\nFinished: {datetime.now().isoformat()}\n"
                    f"Exit code: {return_code}\n"
                )

        except Exception as exc:
            error_text = str(exc)
            try:
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(f"\nERROR: {error_text}\n")
            except OSError:
                pass

        finished = datetime.now()
        record = {
            "script": script.name,
            "started": started.isoformat(timespec="seconds"),
            "finished": finished.isoformat(timespec="seconds"),
            "seconds": round((finished - started).total_seconds(), 2),
            "return_code": return_code,
            "success": return_code == 0 and not error_text,
            "log": str(log_path),
            "input_path": self.input_path,
            "results_path": self.results_path,
            "error": error_text
        }

        history = read_json(HISTORY_FILE, [])
        if not isinstance(history, list):
            history = []
        history.append(record)
        write_json(HISTORY_FILE, history[-500:])

        self.window.after(
            0, self._finish_run, record
        )

    def _finish_run(self, record):
        self.running = False
        self.current_process = None
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

        if record["success"]:
            message = (
                f"??????? ?????????: {record['script']} "
                f"({record['seconds']} ???.)"
            )
        else:
            message = (
                f"?????? ??????????: {record['script']}. "
                f"{record['error'] or '????????? ???.'}"
            )

        self.status_var.set(message)
        self.append_output("\n" + message + "\n")
        self.append_output(f"???: {record['log']}\n")

        if self.auto_open_results.get():
            self.open_results_folder()

    def stop_selected(self):
        process = self.current_process

        if not self.running or process is None:
            return

        if not messagebox.askyesno(
            "?????????? ??????????",
            "????????????? ?????????? ??????? ???????",
            parent=self.window
        ):
            return

        try:
            process.terminate()
            self.status_var.set("?????????? ??????? ?????????...")
        except Exception as exc:
            messagebox.showerror(
                "?????? ?????????", str(exc),
                parent=self.window
            )

    def open_latest_log(self):
        logs = sorted(
            LOGS_DIR.glob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if not logs:
            messagebox.showinfo(
                "??????", "????? ???? ???.", parent=self.window
            )
            return
        try:
            os.startfile(str(logs[0]))
        except Exception as exc:
            messagebox.showerror(
                "??????", str(exc), parent=self.window
            )

    def show_history(self):
        history = read_json(HISTORY_FILE, [])
        win = tk.Toplevel(self.window)
        win.title("??????? ????????")
        win.geometry("850x500")

        text = tk.Text(win, wrap="word", font=("Consolas", 9))
        scroll = ttk.Scrollbar(
            win, orient="vertical", command=text.yview
        )
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        if not history:
            text.insert("end", "??????? ???????? ???? ?????.")
        else:
            for item in reversed(history):
                status = "???????" if item.get("success") else "??????"
                text.insert(
                    "end",
                    f"[{status}] {item.get('script', '')}\n"
                    f"??????: {item.get('started', '')}\n"
                    f"????????????: {item.get('seconds', 0)} ???.\n"
                    f"????: {item.get('input_path', '')}\n"
                    f"???: {item.get('log', '')}\n"
                    f"{item.get('error', '')}\n"
                    + "-" * 65 + "\n"
                )
        text.configure(state="disabled")

    def show_statistics(self):
        history = read_json(HISTORY_FILE, [])
        if not isinstance(history, list):
            history = []

        total = len(history)
        successful = sum(1 for item in history if item.get("success"))
        failed = total - successful
        duration = sum(
            float(item.get("seconds", 0) or 0) for item in history
        )

        messagebox.showinfo(
            "?????????? ????????",
            f"????? ????????: {total}\n"
            f"????????: {successful}\n"
            f"? ????????: {failed}\n"
            f"????? ????? ??????????: {duration:.1f} ???.\n"
            f"???????? ? ?????: {len(list(SCRIPTS_DIR.glob('*.py')))}",
            parent=self.window
        )

    def close_window(self):
        self.save_settings()
        self.window.destroy()


def open_script_manager(parent):
    return ScriptManager(parent)
