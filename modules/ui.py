import os
import tempfile
import uuid
from datetime import datetime, timedelta

import dotenv
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from .interface import Ui_MainWindow
from .litellm_generate import Worker_litellm
from .local_generate import Worker_Local
from .activity_memory import ActivityMemory
from .text_generate import TextSummaryWorker

SCRLLM_ENV_FILE = os.getenv("SCRLLM_ENV_FILE", ".env")
DEFAULT_MODEL_ID = "gemini/gemini-3.1.flash-lite"
DEFAULT_CAPTURE_INTERVAL_SECONDS = 60
DEFAULT_ACTIVITY_DATA_DIRECTORY = "~/.screenshot_llm/activity"
COMPACT_WINDOW_WIDTH = 360
COMPACT_WINDOW_HEIGHT = 170
CAPTURE_PROMPT = (
    "Summarize only the key visible activity in this screenshot.\n"
    "Return only short lines in this exact style:\n"
    "Productive behaviour: educational youtube video\n"
    "Productive behaviour: LaTeX writeup\n"
    "Unproductive behaviour: Youtube football highlights\n"
    "Unproductive behaviour: Instagram\n"
    "Use only the most relevant key points. Do not add explanations, bullets, numbering, or extra text."
)
HOURLY_SUMMARY_PROMPT = (
    "Write one concise, natural-language summary of this hour's activity observations. "
    "Describe what the person mainly did and mention meaningful switching or distractions. "
    "Do not mention screenshots, observations, timestamps, productivity labels, or uncertainty. "
    "Return only the summary sentence, with no heading, bullets, or extra commentary."
)


class ScreenshotAnalyzer(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.compact_mode = False
        self.capture_in_progress = False
        self.capture_paused = False
        self.current_capture_path = None
        self.current_worker = None
        self.summary_workers = []
        self.pending_summary_hours = []
        self.queued_summary_hours = set()
        self.active_hour = self.current_hour()

        self.load_config()
        self.activity_memory = ActivityMemory(self.ACTIVITY_DATA_DIRECTORY)
        self.apply_config_to_controls()
        self.setup_runtime_ui()
        self.setup_capture_timer()
        self.setup_hourly_summary_timer()
        self.reconcile_completed_hours()

        QTimer.singleShot(250, self.capture_and_describe)

    def load_config(self):
        dotenv.load_dotenv(SCRLLM_ENV_FILE, override=True)
        self.LLM_API_MODEL = os.getenv("LLM_API_KEY") or ""
        self.LLM_MODEL_ID = os.getenv("LLM_MODEL_ID") or DEFAULT_MODEL_ID
        self.CAPTURE_INTERVAL_SECONDS = self.parse_capture_interval(os.getenv("CAPTURE_INTERVAL_SECONDS"))
        self.OLLAMA = os.getenv("OLLAMA") or "0"
        self.DARK_MODE = os.getenv("DARK_MODE") or "0"
        self.ICON_SCHEME = os.getenv("ICON_SCHEME") or "default"
        self.ACTIVITY_DATA_DIRECTORY = os.getenv("ACTIVITY_DATA_DIRECTORY") or DEFAULT_ACTIVITY_DATA_DIRECTORY

    def parse_capture_interval(self, value):
        try:
            interval = int(value) if value else DEFAULT_CAPTURE_INTERVAL_SECONDS
        except ValueError:
            interval = DEFAULT_CAPTURE_INTERVAL_SECONDS
        return max(5, interval)

    def apply_config_to_controls(self):
        self.api_key_input.setText(self.LLM_API_MODEL)
        self.model_id_input.setText(self.LLM_MODEL_ID)
        self.capture_interval_input.setText(str(self.CAPTURE_INTERVAL_SECONDS))
        self.icon_scheme_combobox.setCurrentText(self.ICON_SCHEME)
        self.ollama_checkbox.setChecked(self.OLLAMA == "1")
        self.dark_mode_checkbox.setChecked(self.DARK_MODE == "1")

    def setup_runtime_ui(self):
        self.description_text.setReadOnly(True)
        self.description_text.setPlainText("Capturing the first screenshot...")
        self.latest_description = ""
        self.status_label.setText(f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
        self.setWindowTitle("ControlMe")
        self.pause_button.clicked.connect(self.toggle_capture_loop)
        self.save_button.clicked.connect(self.save_config)
        self.reset_config.clicked.connect(self.reset_configurations)
        self.capture_interval_input.returnPressed.connect(self.save_config)
        self.update_compact_label()
        self.update_compact_mode()

    def setup_capture_timer(self):
        self.capture_timer = QTimer(self)
        self.capture_timer.setInterval(self.CAPTURE_INTERVAL_SECONDS * 1000)
        self.capture_timer.timeout.connect(self.capture_and_describe)
        self.capture_timer.start()
        self.capture_paused = False
        self.pause_button.setText("⏸ Pause")
        self.update_compact_label()

    def setup_hourly_summary_timer(self):
        self.hourly_summary_timer = QTimer(self)
        self.hourly_summary_timer.setSingleShot(True)
        self.hourly_summary_timer.timeout.connect(self.rollover_hour)
        self.schedule_next_hour_rollover()

    @staticmethod
    def current_hour(now=None):
        return (now or datetime.now()).replace(minute=0, second=0, microsecond=0)

    def schedule_next_hour_rollover(self):
        now = datetime.now()
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        milliseconds = max(1, int((next_hour - now).total_seconds() * 1000))
        self.hourly_summary_timer.start(milliseconds)

    def rollover_hour(self):
        completed_hour = self.active_hour
        self.active_hour = self.current_hour()
        if completed_hour < self.active_hour:
            self.queue_hourly_summary(completed_hour)
        self.reconcile_completed_hours()
        self.schedule_next_hour_rollover()

    def reconcile_completed_hours(self):
        """Queue every recorded hour that ended while the app was not running."""
        for completed_hour in self.activity_memory.completed_unsummarized_hours(self.active_hour):
            self.queue_hourly_summary(completed_hour)

    def queue_hourly_summary(self, completed_hour):
        completed_hour = completed_hour.replace(minute=0, second=0, microsecond=0)
        if (
            completed_hour in self.queued_summary_hours
            or self.activity_memory.has_summary(completed_hour)
        ):
            return

        self.queued_summary_hours.add(completed_hour)
        self.pending_summary_hours.append(completed_hour)
        self.start_next_hourly_summary()

    def start_next_hourly_summary(self):
        if self.summary_workers or not self.pending_summary_hours:
            return

        completed_hour = self.pending_summary_hours.pop(0)
        observations = self.activity_memory.read_hour(completed_hour)
        if not observations:
            self.queued_summary_hours.discard(completed_hour)
            self.start_next_hourly_summary()
            return

        self.start_hourly_summary_worker(completed_hour, observations)

    def start_hourly_summary_worker(self, completed_hour, observations):
        self.load_config()
        capture_interval_seconds = self.CAPTURE_INTERVAL_SECONDS
        worker = TextSummaryWorker(
            observations,
            self.LLM_API_MODEL,
            self.LLM_MODEL_ID,
            self.OLLAMA == "1",
            HOURLY_SUMMARY_PROMPT,
        )
        worker.finished.connect(
            lambda summary, hour=completed_hour, source_observations=observations,
            interval=capture_interval_seconds, active_worker=worker: self.save_hourly_summary(
                hour, summary, source_observations, interval, active_worker
            )
        )
        worker.error.connect(
            lambda error, hour=completed_hour, active_worker=worker: self.handle_hourly_summary_error(
                hour, error, active_worker
            )
        )
        self.summary_workers.append(worker)
        worker.start()

    def save_hourly_summary(self, completed_hour, summary, observations, capture_interval_seconds, worker):
        self.activity_memory.save_summary(
            completed_hour, summary, observations, capture_interval_seconds
        )
        if worker in self.summary_workers:
            self.summary_workers.remove(worker)
        self.queued_summary_hours.discard(completed_hour)
        self.start_next_hourly_summary()

    def handle_hourly_summary_error(self, completed_hour, error, worker):
        print(f"Unable to summarise {completed_hour:%Y-%m-%d %H:00}: {error}")
        if worker in self.summary_workers:
            self.summary_workers.remove(worker)
        self.queued_summary_hours.discard(completed_hour)
        self.start_next_hourly_summary()

    def set_capture_loop_paused(self, paused, message=None):
        self.capture_paused = paused
        if paused:
            self.capture_timer.stop()
            self.pause_button.setText("▶ Resume")
            if message:
                self.status_label.setText(message)
        else:
            self.pause_button.setText("⏸ Pause")
            self.status_label.setText(message or f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
            self.capture_timer.start()
        self.update_compact_label()

    def toggle_capture_loop(self):
        if self.capture_paused:
            self.set_capture_loop_paused(False, f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
            QTimer.singleShot(250, self.capture_and_describe)
        else:
            self.set_capture_loop_paused(True, "Capture loop paused.")

    def save_config(self):
        llm_api_model = self.api_key_input.text()
        llm_model_id = self.model_id_input.text() or DEFAULT_MODEL_ID
        capture_interval_seconds = self.parse_capture_interval(self.capture_interval_input.text())
        icon_scheme = self.icon_scheme_combobox.currentText()

        with open(SCRLLM_ENV_FILE, "w") as env_file:
            env_file.write(f"LLM_API_KEY={llm_api_model}\n")
            env_file.write(f"LLM_MODEL_ID={llm_model_id}\n")
            env_file.write(f"CAPTURE_INTERVAL_SECONDS={capture_interval_seconds}\n")
            env_file.write(f"OLLAMA={'1' if self.ollama_checkbox.isChecked() else '0'}\n")
            env_file.write(f"DARK_MODE={'1' if self.dark_mode_checkbox.isChecked() else '0'}\n")
            env_file.write(f"ICON_SCHEME={icon_scheme}\n")
            env_file.write(f"ACTIVITY_DATA_DIRECTORY={self.ACTIVITY_DATA_DIRECTORY}\n")

        self.load_config()
        self.apply_config_to_controls()
        self.restart_capture_timer()
        self.status_label.setText(f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
        self.show_message("Configuration saved successfully!")

    def reset_configurations(self):
        with open(SCRLLM_ENV_FILE, "w") as env_file:
            env_file.write("LLM_API_KEY=\n")
            env_file.write(f"LLM_MODEL_ID={DEFAULT_MODEL_ID}\n")
            env_file.write(f"CAPTURE_INTERVAL_SECONDS={DEFAULT_CAPTURE_INTERVAL_SECONDS}\n")
            env_file.write("OLLAMA=0\n")
            env_file.write("DARK_MODE=0\n")
            env_file.write("ICON_SCHEME=default\n")
            env_file.write(f"ACTIVITY_DATA_DIRECTORY={DEFAULT_ACTIVITY_DATA_DIRECTORY}\n")

        self.load_config()
        self.apply_config_to_controls()
        self.restart_capture_timer()
        self.description_text.setPlainText("Configuration reset. Waiting for the next capture.")
        self.status_label.setText(f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
        self.latest_description = ""
        self.update_compact_label()
        self.show_message("Configuration reset successfully!")

    def restart_capture_timer(self):
        self.capture_timer.stop()
        self.capture_timer.setInterval(self.CAPTURE_INTERVAL_SECONDS * 1000)
        if not self.capture_paused:
            self.capture_timer.start()

    def capture_and_describe(self):
        if self.capture_in_progress or self.capture_paused:
            return

        self.capture_in_progress = True
        self.status_label.setText("Capturing screenshot...")
        self.update_compact_label()
        self.setWindowOpacity(0.0)
        QTimer.singleShot(150, self.perform_capture)

    def perform_capture(self):
        try:
            import pyscreenshot as ImageGrab
        except ImportError as exc:
            self.restore_window_visibility()
            self.set_capture_loop_paused(True, "Capture loop paused because pyscreenshot is missing.")
            self.capture_in_progress = False
            self.show_error_message(str(exc))
            return

        try:
            image = ImageGrab.grab()
            image.thumbnail((1000, 700))
        except Exception as exc:
            self.restore_window_visibility()
            self.set_capture_loop_paused(True, "Capture loop paused because the screen capture failed.")
            self.capture_in_progress = False
            self.show_error_message(str(exc))
            return

        self.restore_window_visibility()

        self.current_capture_path = self.save_capture_to_tempfile(image)
        self.status_label.setText("Writing description...")
        self.update_compact_label()
        self.start_description_worker()

    def restore_window_visibility(self):
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self.activateWindow()

    def save_capture_to_tempfile(self, image):
        capture_name = f"screenshot_llm_{uuid.uuid4().hex}.png"
        capture_path = os.path.join(tempfile.gettempdir(), capture_name)
        image.save(capture_path, "PNG")
        return capture_path

    def start_description_worker(self):
        self.load_config()
        model_id = (self.LLM_MODEL_ID or "").strip()
        if not model_id:
            self.set_capture_loop_paused(True, "Capture loop paused because the model ID is missing.")
            self.capture_in_progress = False
            self.show_error_message("Model ID is required.")
            return

        if self.OLLAMA == "1":
            worker = Worker_Local(self.current_capture_path, self.LLM_API_MODEL, model_id, CAPTURE_PROMPT)
        else:
            worker = Worker_litellm(self.current_capture_path, self.LLM_API_MODEL, model_id, CAPTURE_PROMPT)

        worker.finished.connect(self.handle_description_finished)
        worker.error.connect(self.handle_description_error)
        worker.start()
        self.current_worker = worker

    def handle_description_finished(self, description):
        self.latest_description = description.strip()
        self.activity_memory.append_observation(datetime.now(), self.latest_description)
        self.description_text.setPlainText(self.latest_description)
        self.status_label.setText(
            f"Last updated {datetime.now().strftime('%H:%M:%S')} | every {self.CAPTURE_INTERVAL_SECONDS} seconds"
        )
        self.update_compact_label()
        self.finish_capture_cycle()

    def handle_description_error(self, error):
        self.set_capture_loop_paused(True, "Capture loop paused because description generation failed.")
        self.show_error_message(error)
        self.finish_capture_cycle()

    def finish_capture_cycle(self):
        if self.current_capture_path and os.path.exists(self.current_capture_path):
            try:
                os.remove(self.current_capture_path)
            except OSError:
                pass

        self.current_capture_path = None
        self.current_worker = None
        self.capture_in_progress = False

        if not self.capture_paused and not self.capture_timer.isActive():
            self.capture_timer.start()
        self.update_compact_label()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_compact_mode()

    def update_compact_mode(self):
        if not hasattr(self, "tab_widget") or not hasattr(self, "compact_label"):
            return

        compact = self.width() <= COMPACT_WINDOW_WIDTH or self.height() <= COMPACT_WINDOW_HEIGHT
        if compact == getattr(self, "compact_mode", False):
            return

        self.compact_mode = compact
        self.tab_widget.setVisible(not compact)
        self.compact_label.setVisible(compact)

        if compact:
            self.verticalLayout.setContentsMargins(6, 6, 6, 6)
            self.verticalLayout.setSpacing(0)
        else:
            self.verticalLayout.setContentsMargins(20, 20, 20, 20)
            self.verticalLayout.setSpacing(20)

        self.update_compact_label()

    def update_compact_label(self):
        if not hasattr(self, "compact_label"):
            return

        summary = getattr(self, "latest_description", "").strip()
        self.compact_label.setText(summary or "Waiting for summary.")

    def show_message(self, message):
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Message")
        message_box.setIcon(QMessageBox.Icon.NoIcon)
        message_box.setText(message)
        message_box.exec()

    def show_error_message(self, error):
        error_message = QMessageBox(self)
        error_message.setIcon(QMessageBox.Icon.Critical)
        error_message.setWindowTitle("Error")
        error_message.setText(f"Error occurred. Please try again. Error: {error}")
        error_message.exec()

    def closeEvent(self, event):
        event.accept()
