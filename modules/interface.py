from PyQt6 import QtCore, QtGui, QtWidgets 
import os

ui_icon_schemes = {
    "default": {
            "main_icon": "🖼️ ",
            "send_icon": "⏭️ ",
            "reset_icon": "🔃 ",
            "settings_icon": "⚙️ ",
    },
    "basic": {
            "main_icon": "🖼 ",        
            "send_icon": "⏵ ",
            "reset_icon": "⟳ ",
            "settings_icon": "⚙ ",
    },
    "trite": {
            "main_icon": "⌂ ",
            "send_icon": "☞ ",
            "reset_icon": "♲ ",
            "settings_icon": "☸ ",
    },
    "dingbat": {
            "main_icon": "✒ ",
            "send_icon": "➥ ",
            "reset_icon": "✖ ",
            "settings_icon": "❂ ",
    },
}

ui_elements = {
    "main_button": "Main",
    "settings_button": "Settings",
}

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        self.MainWindow = MainWindow

        # Convert DARK_MODE environment variable to boolean
        self.dark_mode = False

        self.icon_scheme = os.environ.get("ICON_SCHEME", "default")

        self.MainWindow.setObjectName("MainWindow")
        self.MainWindow.resize(1200, 900)
        self.MainWindow.setMinimumSize(180, 44)
        self.apply_stylesheet()
        font = QtGui.QFont("Segoe UI", 11)

        # Set window flags to make it always on top
        self.MainWindow.setWindowFlags(QtCore.Qt.WindowType.WindowStaysOnTopHint)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(20, 20, 20, 20)
        self.verticalLayout.setSpacing(20)

        self.setup_main_tab(font)
        self.setup_settings_tab(font)

        self.tab_widget = QtWidgets.QTabWidget(self.centralwidget)
        self.tab_widget.setFont(font)
        self.tab_widget.setObjectName("tab_widget")
        self.tab_widget.setMinimumSize(0, 0)
        self.tab_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Ignored,
        )
        self.tab_widget.addTab(self.tab1, f"{ui_icon_schemes[self.icon_scheme]["main_icon"]}{ui_elements["main_button"]}")
        self.tab_widget.addTab(self.tab2, f"{ui_icon_schemes[self.icon_scheme]["settings_icon"]}{ui_elements["settings_button"]}")
        self.verticalLayout.addWidget(self.tab_widget)

        self.compact_label = self.create_label("Waiting for summary.")
        self.compact_label.setObjectName("compact_label")
        self.compact_label.setFont(font)
        self.compact_label.setMinimumSize(0, 0)
        self.compact_label.setVisible(False)
        self.verticalLayout.addWidget(self.compact_label)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        # Set default position to top-right corner of the screen
        screen_geometry = QtGui.QGuiApplication.primaryScreen().geometry()
        x = screen_geometry.width() - self.MainWindow.width()
        y = 0
        self.MainWindow.move(x, y)

        # Set window icon
        icon = QtGui.QIcon("icon.ico")
        self.MainWindow.setWindowIcon(icon)

    def setup_main_tab(self, font):
        self.tab1 = QtWidgets.QWidget()
        self.tab1.setObjectName("tab1")
        self.tab1.setMinimumSize(0, 0)
        self.tab1_layout = QtWidgets.QVBoxLayout(self.tab1)
        self.tab1_layout.setObjectName("tab1_layout")
        self.tab1_layout.setSpacing(15)

        self.conversation_text = self.create_text_edit(font)
        self.conversation_text.setObjectName("conversation_text")
        self.conversation_text.setReadOnly(True)
        self.conversation_text.setMinimumSize(0, 0)
        self.conversation_text.setPlaceholderText("Ask about your day, work, or activity.")
        self.tab1_layout.addWidget(self.conversation_text, stretch=1)

        message_layout = QtWidgets.QHBoxLayout()
        message_layout.setSpacing(10)
        self.message_input = self.create_line_edit(font)
        self.message_input.setObjectName("message_input")
        self.message_input.setPlaceholderText("Send a message...")
        message_layout.addWidget(self.message_input, stretch=1)
        self.send_button = self.create_button("Send", font)
        self.send_button.setObjectName("send_button")
        message_layout.addWidget(self.send_button)
        self.tab1_layout.addLayout(message_layout)

    def setup_settings_tab(self, font):
        self.tab2 = QtWidgets.QScrollArea()
        self.tab2.setObjectName("tab2")
        self.tab2.setMinimumSize(0, 0)
        self.tab2.setWidgetResizable(True)
        self.tab2.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.tab2.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tab2_content = QtWidgets.QWidget()
        self.tab2_content.setObjectName("tab2_content")
        self.tab2_layout = QtWidgets.QVBoxLayout(self.tab2_content)
        self.tab2_layout.setObjectName("tab2_layout")
        self.tab2_layout.setContentsMargins(0, 14, 0, 0)
        self.tab2_layout.setSpacing(12)

        self.api_key_label = self.create_label("LLM API Key")
        self.api_key_label.setFont(font)
        self.tab2_layout.addWidget(self.api_key_label)

        self.api_key_input = self.create_line_edit(font)
        self.api_key_input.setPlaceholderText("Get your API key from your provider")
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.tab2_layout.addWidget(self.api_key_input)

        self.model_id_label = self.create_label("Model ID")
        self.model_id_label.setFont(font)
        self.tab2_layout.addWidget(self.model_id_label)

        self.model_id_input = self.create_line_edit(font)
        self.model_id_input.setPlaceholderText("Default: gemini/gemini-3.1.flash-lite")
        self.model_id_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
        self.tab2_layout.addWidget(self.model_id_input)

        self.icon_scheme_label = self.create_label("Icon Scheme")
        self.icon_scheme_label.setObjectName("icon_scheme_label")
        self.icon_scheme_label.setFont(font)
        self.tab2_layout.addWidget(self.icon_scheme_label)

        self.icon_scheme_combobox = QtWidgets.QComboBox(self.tab2_content)
        self.icon_scheme_combobox.setFont(font)
        self.icon_scheme_combobox.setMinimumHeight(46)
        self.icon_scheme_combobox.setCurrentText(self.icon_scheme)  # Set initial state
        self.icon_scheme_combobox.addItems(ui_icon_schemes.keys())
        self.icon_scheme_combobox.currentTextChanged.connect(self.change_icon_scheme)
        self.tab2_layout.addWidget(self.icon_scheme_combobox)

        self.capture_interval_label = self.create_label("Capture Frequency (seconds)")
        self.capture_interval_label.setFont(font)
        self.tab2_layout.addWidget(self.capture_interval_label)

        self.capture_interval_input = self.create_line_edit(font)
        self.capture_interval_input.setPlaceholderText("Default: 60")
        self.tab2_layout.addWidget(self.capture_interval_input)

        self.ollama_checkbox = QtWidgets.QCheckBox("Local model", self.tab2_content)
        self.ollama_checkbox.setFont(font)
        self.tab2_layout.addWidget(self.ollama_checkbox)

        self.dark_mode_checkbox = QtWidgets.QCheckBox("Dark Mode", self.tab2_content)
        self.dark_mode_checkbox.setFont(font)
        self.dark_mode_checkbox.setChecked(self.dark_mode)  # Set initial state
        self.dark_mode_checkbox.stateChanged.connect(self.toggle_dark_mode)
        self.tab2_layout.addWidget(self.dark_mode_checkbox)

        self.status_label = self.create_label("Waiting to capture the first screenshot.")
        self.status_label.setObjectName("status_label")
        self.status_label.setFont(font)
        self.tab2_layout.addWidget(self.status_label)

        self.pause_button = self.create_button("⏸ Pause", font)
        self.pause_button.setObjectName("pause_button")
        self.tab2_layout.addWidget(self.pause_button)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)

        self.save_button = self.create_button("Save", font)
        button_layout.addWidget(self.save_button)

        self.reset_config = self.create_button("Reset Config", font)
        button_layout.addWidget(self.reset_config)

        self.tab2_layout.addLayout(button_layout)
        self.tab2_layout.addStretch(1)
        self.tab2.setWidget(self.tab2_content)

    def toggle_dark_mode(self, state):
        self.dark_mode = state == QtCore.Qt.CheckState.Checked.value
        self.apply_stylesheet()

        # Update the DARK_MODE environment variable
        os.environ["DARK_MODE"] = "1" if self.dark_mode else "0"

    def change_icon_scheme(self, icon_scheme):
        self.icon_scheme = icon_scheme
        self.MainWindow.findChild(QtWidgets.QLabel, "icon_scheme_label").setText("Icon Scheme\n{}".format(" ".join(list(ui_icon_schemes[icon_scheme].values()))))

        self.MainWindow.findChild(QtWidgets.QTabWidget, "tab_widget").setTabText(0, f"{ui_icon_schemes[icon_scheme]["main_icon"]}{ui_elements["main_button"]}")
        self.MainWindow.findChild(QtWidgets.QTabWidget, "tab_widget").setTabText(1, f"{ui_icon_schemes[icon_scheme]["settings_icon"]}{ui_elements["settings_button"]}")

        # Update the ICON_SCHEME environment variable
        os.environ["ICON_SCHEME"] = self.icon_scheme

    def apply_stylesheet(self):
        if self.dark_mode:
            self.MainWindow.setStyleSheet(self.get_dark_stylesheet())
        else:
            self.MainWindow.setStyleSheet(self.get_light_stylesheet())

    def get_light_stylesheet(self):
        return """
            QMainWindow, QWidget {
                background-color: #ffffff;
                color: #333333;
            }
            QLabel, QTextEdit, QLineEdit, QPushButton {
                border: none;
                border-radius: 8px;
                padding: 12px;
            }
            QScrollBar {
                background: #f0f0f0;
                width: 10px;
            }
            QScrollBar::handle {
                background: #c0c0c0;
                border-radius: 5px;
            }
            QScrollBar::handle:pressed {
                background: #a0a0a0;
            }
            QLabel {
                background-color: #f8f8f8;
            }
            QTextEdit, QLineEdit {
                background-color: #f8f8f8;
                color: #333333;
            }
            QPushButton {
                background-color: #4a90e2;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a80d2;
            }
            QPushButton:pressed {
                background-color: #2a70c2;
            }
            QTabWidget::pane {
                border: none;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                color: #333333;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #4a90e2;
            }
            QCheckBox {
                color: #333333;
            }
            QComboBox {
                background-color: #f8f8f8;
                color: #333333;
                border: none;
                border-radius: 8px;
                padding: 12px
            }
            QComboBox::down-arrow {
                display: none;
            }
        """

    def get_dark_stylesheet(self):
        return """
            QMainWindow, QWidget {
                background-color: #2c2c2c;
                color: #ffffff;
            }
            QLabel, QTextEdit, QLineEdit, QPushButton {
                border: none;
                border-radius: 8px;
                padding: 12px;
            }
            QScrollBar {
                background: #3c3c3c;
                width: 10px;
            }
            QScrollBar::handle {
                background: #5c5c5c;
                border-radius: 5px;
            }
            QScrollBar::handle:pressed {
                background: #7c7c7c;
            }
            QLabel {
                background-color: #3c3c3c;
            }
            QTextEdit, QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QPushButton {
                background-color: #4a90e2;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a80d2;
            }
            QPushButton:pressed {
                background-color: #2a70c2;
            }
            QTabWidget::pane {
                border: none;
                background-color: #2c2c2c;
            }
            QTabBar::tab {
                background-color: #3c3c3c;
                color: #ffffff;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #2c2c2c;
                color: #4a90e2;
            }
            QCheckBox {
                color: #ffffff;
            }
            QComboBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px
            }
            QComboBox::down-arrow {
                display: none;
            }
        """

    def create_label(self, text=""):
        label = QtWidgets.QLabel(text, self.centralwidget)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setMinimumHeight(42)
        return label

    def create_text_edit(self, font):
        text_edit = QtWidgets.QTextEdit(self.centralwidget)
        text_edit.setFont(font)
        text_edit.setPlaceholderText("The live description appears here.")
        text_edit.setReadOnly(True)
        return text_edit

    def create_line_edit(self, font):
        line_edit = QtWidgets.QLineEdit(self.centralwidget)
        line_edit.setPlaceholderText("Enter Your Message 💬")
        line_edit.setFont(font)
        line_edit.setMinimumHeight(46)
        return line_edit

    def create_button(self, text, font, sizeX = 0, sizeY = 0):
        button = QtWidgets.QPushButton(text, self.centralwidget)
        button.setFont(font)
        button.setMinimumWidth(sizeX)
        button.setMinimumHeight(sizeY or 46)
        return button

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Screenshot LLM"))

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Screenshot LLM")
    app.setDesktopFileName("Screenshot_LLM")
    app.setWindowIcon(QtGui.QIcon("icon.ico"))
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())    
