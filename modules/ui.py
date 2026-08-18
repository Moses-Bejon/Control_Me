import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
import traceback
from typing import Any

import dotenv
import markdown
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QCloseEvent, QColor, QPalette, QResizeEvent
from PyQt6.QtWidgets import (
    QMainWindow, QMessageBox, QFrame, QLabel, QVBoxLayout
)

from .interface import UiMainWindow
from .litellm_generate import WorkerLitellm
from .local_generate import WorkerLocal
from .activity_memory import ActivityMemory
from .text_generate import ConversationWorker, TextSummaryWorker
from .prompts import CAPTURE_PROMPT, HOURLY_SUMMARY_PROMPT, CHAT_SYSTEM_PROMPT, FEEDBACK_NOTIFICATION_PROMPT

SCRLLM_ENV_FILE = os.getenv("SCRLLM_ENV_FILE", ".env")
DEFAULT_MODEL_ID = "gemini/gemini-3.1-flash-lite"
DEFAULT_CAPTURE_INTERVAL_SECONDS = 120
PAUSE_REMINDER_INTERVAL_MILLISECONDS = 120_000
DEFAULT_ACTIVITY_DATA_DIRECTORY = "~/.control_me/activity"
COMPACT_WINDOW_WIDTH = 360
COMPACT_WINDOW_HEIGHT = 170

class ChatMessageWidget(QFrame):
    def __init__(self, message: str, is_user: bool) -> None:
        super().__init__()
        self.is_user = is_user
        
        # Create layout and label
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)
        
        # Convert markdown to HTML
        html_content = markdown.markdown(message, extensions=['nl2br', 'extra'])
        
        label = QLabel(html_content)
        label.setWordWrap(True)
        
        # Set alignment based on message type
        if is_user:
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(label)
        self.setLayout(layout)
        
        # Apply palette-based coloring (respects app theme)
        self._apply_palette(is_user)
    
    def _apply_palette(self, is_user: bool) -> None:
        palette = self.palette()
        if is_user:
            palette.setColor(QPalette.ColorRole.Window, QColor("#E3F2FD"))
        else:
            palette.setColor(QPalette.ColorRole.Window, QColor("#F5F5F5"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)


class ScreenshotAnalyzer(QMainWindow, UiMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setup_ui(self)

        self.compact_mode = False
        self.capture_in_progress = False
        self.capture_paused = False
        self.current_capture_path = None
        self.current_worker = None
        self.chat_worker = None
        self.feedback_worker = None
        self.conversation = []
        self.summary_workers = []
        self.pending_summary_hours = []
        self.queued_summary_hours = set()
        self.active_hour = self.current_hour()
        
        self.load_config()
        venvpath = os.getenv("VENVPATH", os.path.expanduser("~/.control_me/"))
        self.prompts_log_path = os.path.join(venvpath, "prompts.log")
        
        # Clear prompts.log at the start of a new session
        try:
            with open(self.prompts_log_path, "w") as log_file:
                pass  # Opening in write mode clears the file
        except Exception as e:
            print(f"Failed to clear prompts.log: {e}")
        
        # Replace QTextEdit with scrollable message container
        self._setup_chat_container()
        
        self.activity_memory = ActivityMemory(self.ACTIVITY_DATA_DIRECTORY)
        self.apply_config_to_controls()
        self.setup_runtime_ui()
        self.setup_tray_icon()
        self.setup_capture_timer()
        self.setup_pause_reminder_timer()
        self.setup_hourly_summary_timer()
        self.reconcile_completed_hours()

        QTimer.singleShot(250, self.capture_and_describe)
    
    def _setup_chat_container(self) -> None:
        from PyQt6.QtWidgets import QScrollArea
        
        # Find and remove the old conversation_text widget
        layout = self.tab1_layout
        layout.removeWidget(self.conversation_text)
        self.conversation_text.deleteLater()
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        # Create container widget and layout for messages
        container = QFrame()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(10)
        container_layout.addStretch()
        container.setLayout(container_layout)
        
        scroll_area.setWidget(container)
        layout.addWidget(scroll_area, stretch=1)
        
        # Store references
        self.conversation_text = scroll_area
        self.chat_messages_container = container
        self.chat_messages_layout = container_layout

    def notify(self, message: str, critical: bool = False) -> None:
        """Show a brief desktop notification.

        Uses the system tray if available; otherwise falls back to updating the status label.
        """
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon

            if QSystemTrayIcon.isSystemTrayAvailable() and getattr(self, "tray_icon", None):
                # Use the tray icon to display a transient notification
                self.tray_icon.showMessage(
                    "ControlMe",
                    message,
                    QSystemTrayIcon.MessageIcon.Critical if critical else QSystemTrayIcon.MessageIcon.Warning,
                    3000,
                )
                return
        except Exception:
            traceback.print_exc()

        # Fallback when no system tray is available, or tray notifications fail.
        try:
            self.status_label.setText(message)
        except Exception:
            traceback.print_exc()

    def setup_tray_icon(self) -> None:
        """Create and show a system tray icon if the platform supports it.

        This enables non-modal notifications using QSystemTrayIcon.showMessage.
        Adds a context menu with an Exit action so the user can quit from the tray.
        """
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
            from PyQt6.QtGui import QIcon, QAction

            if QSystemTrayIcon.isSystemTrayAvailable():
                self.tray_icon = QSystemTrayIcon(self)
                # Use the window icon if available; otherwise an empty QIcon
                icon = self.windowIcon() or QIcon(self)
                self.tray_icon.setIcon(icon)
                self.tray_icon.setToolTip("Control Me")

                # Build a simple context menu with an Exit
                tray_menu = QMenu(self)
                exit_action = QAction("Exit", self)
                exit_action.triggered.connect(lambda: QApplication.instance().quit())
                tray_menu.addAction(exit_action)

                # Attach the menu to the tray icon
                try:
                    self.tray_icon.setContextMenu(tray_menu)
                except Exception:
                    # Some platforms may require a different API; ignore if it fails
                    traceback.print_exc()

                # Ensure the tray icon is visible so showMessage will work on many platforms
                self.tray_icon.show()
            else:
                self.tray_icon = None
        except Exception:
            # If creating a tray icon fails for any reason, keep going without it
            self.tray_icon = None
            traceback.print_exc()

    def load_config(self) -> None:
        dotenv.load_dotenv(SCRLLM_ENV_FILE, override=True)
        self.LLM_API_MODEL = os.getenv("LLM_API_KEY") or ""
        self.LLM_MODEL_ID = os.getenv("LLM_MODEL_ID") or DEFAULT_MODEL_ID
        self.CAPTURE_INTERVAL_SECONDS = self.parse_capture_interval(os.getenv("CAPTURE_INTERVAL_SECONDS"))
        self.OLLAMA = os.getenv("OLLAMA") or "0"
        self.DARK_MODE = os.getenv("DARK_MODE") or "0"
        self.ICON_SCHEME = os.getenv("ICON_SCHEME") or "default"
        self.ACTIVITY_DATA_DIRECTORY = os.getenv("ACTIVITY_DATA_DIRECTORY") or DEFAULT_ACTIVITY_DATA_DIRECTORY

    def log_prompt_response(
        self, speaker: str, message: str | list[dict[str, str]]
    ) -> None:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.prompts_log_path, "a") as log_file:
                if speaker == "User":
                    # Add separator before user messages
                    log_file.write("\n" + "=" * 80 + "\n")
                log_file.write(f"[{timestamp}] {speaker}:\n{message}\n")
        except Exception as e:
            print(f"Failed to log prompt/response: {e}")

    def parse_capture_interval(self, value: str | None) -> int:
        try:
            interval = int(value) if value else DEFAULT_CAPTURE_INTERVAL_SECONDS
        except ValueError:
            interval = DEFAULT_CAPTURE_INTERVAL_SECONDS
        return max(5, interval)

    def apply_config_to_controls(self) -> None:
        self.api_key_input.setText(self.LLM_API_MODEL)
        self.model_id_input.setText(self.LLM_MODEL_ID)
        self.capture_interval_input.setText(str(self.CAPTURE_INTERVAL_SECONDS))
        self.icon_scheme_combobox.setCurrentText(self.ICON_SCHEME)
        self.ollama_checkbox.setChecked(self.OLLAMA == "1")
        self.dark_mode_checkbox.setChecked(self.DARK_MODE == "1")

    def setup_runtime_ui(self) -> None:
        self.latest_description = ""
        self.saved_config_values = self.config_control_values()
        self.has_unsaved_config_changes = False
        self.setup_unsaved_changes_warning()
        self.status_label.setText(f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
        self.setWindowTitle("ControlMe")
        self.pause_button.clicked.connect(self.toggle_capture_loop)
        self.send_button.clicked.connect(self.send_chat_message)
        self.message_input.returnPressed.connect(self.send_chat_message)
        self.save_button.clicked.connect(self.save_config)
        self.reset_config.clicked.connect(self.reset_configurations)
        self.capture_interval_input.returnPressed.connect(self.save_config)
        self.api_key_input.textChanged.connect(self.update_unsaved_changes_warning)
        self.model_id_input.textChanged.connect(self.update_unsaved_changes_warning)
        self.capture_interval_input.textChanged.connect(self.update_unsaved_changes_warning)
        self.icon_scheme_combobox.currentTextChanged.connect(self.update_unsaved_changes_warning)
        self.ollama_checkbox.toggled.connect(self.update_unsaved_changes_warning)
        self.dark_mode_checkbox.toggled.connect(self.update_unsaved_changes_warning)
        self.update_compact_label()
        self.update_compact_mode()

    def setup_unsaved_changes_warning(self) -> None:
        """Add a persistent warning for settings changed but not saved to disk."""
        self.unsaved_changes_label = QLabel(
            "Unsaved changes — press Save to apply them.", self.tab2_content
        )
        self.unsaved_changes_label.setWordWrap(True)
        self.unsaved_changes_label.setStyleSheet(
            "QLabel { color: #8A4B00; background: #FFF3CD; "
            "border: 1px solid #FFDA6A; border-radius: 4px; padding: 8px; }"
        )
        self.unsaved_changes_label.setVisible(False)
        self.tab2_layout.insertWidget(
            self.tab2_layout.indexOf(self.pause_button), self.unsaved_changes_label
        )

    def config_control_values(self) -> tuple[str, str, str, str, bool, bool]:
        """Return the editable configuration as it is currently displayed."""
        return (
            self.api_key_input.text(),
            self.model_id_input.text(),
            self.capture_interval_input.text(),
            self.icon_scheme_combobox.currentText(),
            self.ollama_checkbox.isChecked(),
            self.dark_mode_checkbox.isChecked(),
        )

    def update_unsaved_changes_warning(self, *_args: object) -> None:
        self.has_unsaved_config_changes = (
            self.config_control_values() != self.saved_config_values
        )
        self.unsaved_changes_label.setVisible(self.has_unsaved_config_changes)

    def mark_config_saved(self) -> None:
        self.saved_config_values = self.config_control_values()
        self.has_unsaved_config_changes = False
        self.unsaved_changes_label.setVisible(False)

    def send_chat_message(self) -> None:
        message = self.message_input.text().strip()
        if not message or self.chat_worker is not None:
            return

        self.message_input.clear()
        # Timestamp the outgoing user message for chronological interleaving
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conversation.append({"role": "user", "content": message, "ts": ts})
        self.append_chat_message("You", message)

        self.load_config()

        messages = self.chat_messages_with_context()

        self.log_prompt_response("System", messages)

        worker = ConversationWorker(
            messages,
            self.LLM_API_MODEL,
            self.LLM_MODEL_ID,
            self.OLLAMA == "1",
        )
        worker.finished.connect(lambda reply, active_worker=worker: self.handle_chat_finished(reply, active_worker))
        worker.error.connect(lambda error, active_worker=worker: self.handle_chat_error(error, active_worker))
        self.chat_worker = worker
        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        worker.start()

    def chat_messages_with_context(self) -> list[dict[str, str]]:
        """Build a chronologically-ordered list of messages for the LLM.

        - Hourly summaries are added as user messages and labelled with their end timestamp ([end]).
        - Each observation line in the current hour file becomes an individual user message
          prefixed with an ISO-8601 timestamp so events sort chronologically.
        - In-session conversation turns (self.conversation) must include a 'ts' ISO timestamp
          value; user turns are exposed to the model with a visible timestamp prefix, while
          assistant turns are included without an exposed timestamp but are ordered by their ts.
        """
        # Read stored data
        current_observations = self.activity_memory.read_hour(self.active_hour) or ""
        summaries = self.activity_memory.summaries_for_date(
            self.active_hour.date(), exclude_hour=self.active_hour
        )

        # timezone info: use naive datetimes (no tzinfo)

        system_msg = {"role": "system", "content": CHAT_SYSTEM_PROMPT}

        # Gather events as (dt, message_dict) so everything can be sorted chronologically
        events: list[tuple[datetime, dict[str, str]]] = []

        # Hourly summaries: use the hour_end as the event time, format visible as [end]
        if summaries:
            for hour_start, hour_end, summary in summaries:
                try:
                    t = datetime.strptime(hour_end, "%H:%M:%S").time()
                    dt = datetime(
                        self.active_hour.year,
                        self.active_hour.month,
                        self.active_hour.day,
                        t.hour,
                        t.minute,
                        t.second,
                    )
                except Exception:
                    dt = datetime.now()
                content = f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] {summary}"
                events.append((dt, {"role": "user", "content": content}))

        # Current-hour observations: each line becomes its own timestamped user message
        for line in current_observations.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                possible_time = line[:8]
                recorded_time = datetime.strptime(possible_time, "%H:%M:%S").time()
                desc = line[8:].strip()
                dt = datetime(
                    self.active_hour.year,
                    self.active_hour.month,
                    self.active_hour.day,
                    recorded_time.hour,
                    recorded_time.minute,
                    recorded_time.second,
                )
                content = f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] {desc}"
            except Exception:
                # Untimestamped observation -> place at hour start
                dt = datetime(
                    self.active_hour.year,
                    self.active_hour.month,
                    self.active_hour.day,
                    self.active_hour.hour,
                    0,
                    0,
                )
                content = f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] {line}"
            events.append((dt, {"role": "user", "content": content}))

        # In-session conversation turns: include timestamps (ts) and interleave
        for turn in self.conversation:
            # default to now if no timestamp present
            ts = turn.get("ts")
            if ts:
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    dt = datetime.now()
            else:
                dt = datetime.now()

            if turn.get("role") == "user":
                # Expose user message to LLM with visible timestamp
                content = f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] {turn.get('content', '')}"
                events.append((dt, {"role": "user", "content": content}))
            else:
                # Assistant messages should NOT include visible timestamps in content
                events.append((dt, {"role": "assistant", "content": turn.get('content', '')}))

        # Sort events chronologically
        events.sort(key=lambda e: e[0])

        # Assemble final messages list: system prompt first, then chronologically-ordered events
        messages = [system_msg] + [msg for _dt, msg in events]

        return messages

    def handle_chat_finished(self, reply: str, worker: ConversationWorker) -> None:
        reply = reply.strip()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Timestamp assistant reply for chronological interleaving but do NOT expose timestamp in content
        self.conversation.append({"role": "assistant", "content": reply, "ts": ts})
        self.append_chat_message("ControlMe", reply)
        self.log_prompt_response("ControlMe", reply)
        self.finish_chat(worker)

    def handle_chat_error(self, error: str, worker: ConversationWorker) -> None:
        reply = f"I couldn't generate a reply: {error}"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conversation.append({"role": "assistant", "content": reply, "ts": ts})
        self.append_chat_message("ControlMe", reply)
        self.log_prompt_response("ControlMe", reply)
        self.finish_chat(worker)

    def finish_chat(self, worker: ConversationWorker) -> None:
        if self.chat_worker is worker:
            self.chat_worker = None
        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.message_input.setFocus()

    def append_chat_message(self, speaker: str, message: str) -> None:
        is_user = speaker == "You"
        msg_widget = ChatMessageWidget(message, is_user)
        
        # Insert before the stretch at the end
        self.chat_messages_layout.insertWidget(
            self.chat_messages_layout.count() - 1,
            msg_widget
        )
        
        # Scroll to bottom
        scrollbar = self.conversation_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def setup_capture_timer(self) -> None:
        self.capture_timer = QTimer(self)
        self.capture_timer.setInterval(self.CAPTURE_INTERVAL_SECONDS * 1000)
        self.capture_timer.timeout.connect(self.capture_and_describe)
        self.capture_timer.start()
        self.capture_paused = False
        self.pause_button.setText("⏸ Pause")
        self.update_compact_label()

    def setup_pause_reminder_timer(self) -> None:
        """Remind the user until they resume a paused capture loop."""
        self.pause_reminder_timer = QTimer(self)
        self.pause_reminder_timer.setInterval(PAUSE_REMINDER_INTERVAL_MILLISECONDS)
        self.pause_reminder_timer.timeout.connect(self.send_pause_reminder)

    def send_pause_reminder(self) -> None:
        if self.capture_paused:
            self.notify(
                "ControlMe is still paused. Select Resume to restart activity capture.",
                critical=True,
            )

    def setup_hourly_summary_timer(self) -> None:
        self.hourly_summary_timer = QTimer(self)
        self.hourly_summary_timer.setSingleShot(True)
        self.hourly_summary_timer.timeout.connect(self.rollover_hour)
        self.schedule_next_hour_rollover()

    @staticmethod
    def current_hour(now: datetime | None = None) -> datetime:
        return (now or datetime.now()).replace(minute=0, second=0, microsecond=0)

    def schedule_next_hour_rollover(self) -> None:
        now = datetime.now()
        next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        milliseconds = max(1, int((next_hour - now).total_seconds() * 1000))
        self.hourly_summary_timer.start(milliseconds)

    def rollover_hour(self) -> None:
        completed_hour = self.active_hour
        self.active_hour = self.current_hour()
        if completed_hour < self.active_hour:
            self.queue_hourly_summary(completed_hour)
        self.reconcile_completed_hours()
        self.schedule_next_hour_rollover()

    def reconcile_completed_hours(self) -> None:
        """Queue every recorded hour that ended while the app was not running."""
        for completed_hour in self.activity_memory.completed_unsummarized_hours(self.active_hour):
            self.queue_hourly_summary(completed_hour)

    def queue_hourly_summary(self, completed_hour: datetime) -> None:
        completed_hour = completed_hour.replace(minute=0, second=0, microsecond=0)
        if (
            completed_hour in self.queued_summary_hours
            or self.activity_memory.has_summary(completed_hour)
        ):
            return

        self.queued_summary_hours.add(completed_hour)
        self.pending_summary_hours.append(completed_hour)
        self.start_next_hourly_summary()

    def start_next_hourly_summary(self) -> None:
        if self.summary_workers or not self.pending_summary_hours:
            return

        completed_hour = self.pending_summary_hours.pop(0)
        observations = self.activity_memory.read_hour(completed_hour)
        if not observations:
            self.queued_summary_hours.discard(completed_hour)
            self.start_next_hourly_summary()
            return

        self.start_hourly_summary_worker(completed_hour, observations)

    def start_hourly_summary_worker(
        self, completed_hour: datetime, observations: str
    ) -> None:
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

    def save_hourly_summary(
        self,
        completed_hour: datetime,
        summary: str,
        observations: str,
        capture_interval_seconds: int,
        worker: TextSummaryWorker,
    ) -> None:
        self.activity_memory.save_summary(
            completed_hour, summary, observations, capture_interval_seconds
        )
        if worker in self.summary_workers:
            self.summary_workers.remove(worker)
        self.queued_summary_hours.discard(completed_hour)
        self.start_next_hourly_summary()

    def handle_hourly_summary_error(
        self, completed_hour: datetime, error: str, worker: TextSummaryWorker
    ) -> None:
        print(f"Unable to summarise {completed_hour:%Y-%m-%d %H:00}: {error}")
        if worker in self.summary_workers:
            self.summary_workers.remove(worker)
        self.queued_summary_hours.discard(completed_hour)
        self.start_next_hourly_summary()

    def set_capture_loop_paused(
        self,
        paused: bool,
        message: str | None = None,
        notify_immediately: bool = False,
    ) -> None:
        self.capture_paused = paused
        if paused:
            self.capture_timer.stop()
            self.pause_button.setText("▶ Resume")
            if message:
                self.status_label.setText(message)
            if not self.pause_reminder_timer.isActive():
                self.pause_reminder_timer.start()
            if notify_immediately:
                self.notify(message or "ControlMe paused activity capture.", critical=True)
        else:
            self.pause_button.setText("⏸ Pause")
            self.status_label.setText(message or f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
            self.capture_timer.start()
            self.pause_reminder_timer.stop()
        self.update_compact_label()

    def toggle_capture_loop(self) -> None:
        if self.capture_paused:
            self.set_capture_loop_paused(False, f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
            QTimer.singleShot(250, self.capture_and_describe)
        else:
            self.set_capture_loop_paused(True, "Capture loop paused.")

    def save_config(self) -> None:
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
        self.mark_config_saved()
        self.restart_capture_timer()
        self.status_label.setText(f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
        self.show_message("Configuration saved successfully!")

    def reset_configurations(self) -> None:
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
        self.mark_config_saved()
        self.restart_capture_timer()
        self.status_label.setText(f"Capturing every {self.CAPTURE_INTERVAL_SECONDS} seconds.")
        self.latest_description = ""
        self.update_compact_label()
        self.show_message("Configuration reset successfully!")

    def possibly_give_feedback_notification(self) -> None:
        """Ask the coach whether the latest activity warrants a notification.

        This runs separately from user-initiated chat so a slow notification decision never
        blocks sending a message.  At most one decision can be in flight at a time.
        """
        if self.feedback_worker is not None:
            return

        self.load_config()
        messages = self.chat_messages_with_context()
        messages.append({"role": "system", "content": FEEDBACK_NOTIFICATION_PROMPT})

        self.log_prompt_response("System", messages)

        worker = ConversationWorker(
            messages,
            self.LLM_API_MODEL,
            self.LLM_MODEL_ID,
            self.OLLAMA == "1",
        )
        worker.finished.connect(
            lambda reply, active_worker=worker: self.handle_feedback_notification_finished(
                reply, active_worker
            )
        )
        worker.error.connect(
            lambda error, active_worker=worker: self.handle_feedback_notification_error(
                error, active_worker
            )
        )
        self.feedback_worker = worker
        worker.start()

    def handle_feedback_notification_finished(
        self, reply: str, worker: ConversationWorker
    ) -> None:
        if self.feedback_worker is not worker:
            return

        self.feedback_worker = None
        response = reply.strip()
        try:
            decision = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            print("Ignoring malformed feedback notification response.")
            return

        if not isinstance(decision, dict):
            print("Ignoring feedback notification response that is not a JSON object.")
            return

        notify = decision.get("notify")
        critical = decision.get("critical")
        message = decision.get("message")
        if not all(isinstance(value, bool) for value in (notify, critical)) or not isinstance(message, str):
            print("Ignoring feedback notification response with an invalid schema.")
            return

        self.log_prompt_response("ControlMe", reply)

        if not notify:
            return

        message = message.strip()
        if not message:
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conversation.append({"role": "assistant", "content": message, "ts": ts})
        self.append_chat_message("ControlMe", message)
        self.notify(message, critical=critical)

    def handle_feedback_notification_error(
        self, error: str, worker: ConversationWorker
    ) -> None:
        if self.feedback_worker is worker:
            self.feedback_worker = None
        print(f"Unable to generate feedback notification: {error}")

    def restart_capture_timer(self) -> None:
        self.capture_timer.stop()
        self.capture_timer.setInterval(self.CAPTURE_INTERVAL_SECONDS * 1000)
        if not self.capture_paused:
            self.capture_timer.start()

    def capture_and_describe(self) -> None:
        if self.capture_in_progress or self.capture_paused:
            return

        self.capture_in_progress = True
        self.status_label.setText("Capturing screenshot...")
        self.update_compact_label()
        QTimer.singleShot(150, self.perform_capture)

    def perform_capture(self) -> None:
        try:
            import pyscreenshot as ImageGrab
        except ImportError as exc:
            self.set_capture_loop_paused(
                True, "Capture loop paused because pyscreenshot is missing.", notify_immediately=True
            )
            self.capture_in_progress = False
            traceback.print_exc()
            self.show_error_message(str(exc))
            return

        try:
            image = ImageGrab.grab()
            image.thumbnail((1000, 700))
        except Exception as exc:
            self.set_capture_loop_paused(
                True, "Capture loop paused because the screen capture failed.", notify_immediately=True
            )
            self.capture_in_progress = False
            traceback.print_exc()
            self.show_error_message(str(exc))
            return

        self.current_capture_path = self.save_capture_to_tempfile(image)
        self.status_label.setText("Writing description...")
        self.update_compact_label()
        self.start_description_worker()

    def save_capture_to_tempfile(self, image: Any) -> str:
        capture_name = f"control_me_{uuid.uuid4().hex}.png"
        capture_path = os.path.join(tempfile.gettempdir(), capture_name)
        image.save(capture_path, "PNG")
        return capture_path

    def start_description_worker(self) -> None:
        self.load_config()
        model_id = (self.LLM_MODEL_ID or "").strip()
        if not model_id:
            self.set_capture_loop_paused(
                True, "Capture loop paused because the model ID is missing.", notify_immediately=True
            )
            self.capture_in_progress = False
            self.show_error_message("Model ID is required.")
            return

        if self.OLLAMA == "1":
            worker = WorkerLocal(self.current_capture_path, self.LLM_API_MODEL, model_id, CAPTURE_PROMPT)
        else:
            worker = WorkerLitellm(self.current_capture_path, self.LLM_API_MODEL, model_id, CAPTURE_PROMPT)

        worker.finished.connect(self.handle_description_finished)
        worker.error.connect(self.handle_description_error)
        worker.start()
        self.current_worker = worker

    def handle_description_finished(self, description: str) -> None:
        # Collapse any internal newlines/spurious whitespace from the model into single spaces
        # so each observation is written as a single line in the hourly file.
        cleaned = " ".join(description.split())
        self.latest_description = cleaned
        self.activity_memory.append_observation(datetime.now(), self.latest_description)
        try:
            self.possibly_give_feedback_notification()
        except Exception:
            # Don't allow notification failures to interrupt the capture flow.
            traceback.print_exc()
        self.status_label.setText(
            f"Last updated {datetime.now().strftime('%H:%M:%S')} | every {self.CAPTURE_INTERVAL_SECONDS} seconds"
        )
        self.update_compact_label()
        self.finish_capture_cycle()

    def handle_description_error(self, error: str) -> None:
        self.set_capture_loop_paused(
            True, "Capture loop paused because description generation failed.", notify_immediately=True
        )
        self.show_error_message(error)
        self.finish_capture_cycle()

    def finish_capture_cycle(self) -> None:
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

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_compact_mode()

    def update_compact_mode(self) -> None:
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

    def update_compact_label(self) -> None:
        if not hasattr(self, "compact_label"):
            return

        self.compact_label.setText("Open chat to ask about your activity.")

    def show_message(self, message: str) -> None:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Message")
        message_box.setIcon(QMessageBox.Icon.NoIcon)
        message_box.setText(message)
        message_box.exec()

    def show_error_message(self, error: str) -> None:
        error_message = QMessageBox(self)
        error_message.setIcon(QMessageBox.Icon.Critical)
        error_message.setWindowTitle("Error")
        error_message.setText(f"Error occurred. Please try again. Error: {error}")
        error_message.exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
