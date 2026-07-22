import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from modules.ui import ScreenshotAnalyzer


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Screenshot LLM")
    app.setDesktopFileName("Screenshot_LLM")
    app.setWindowIcon(QIcon("icon.ico"))

    window = ScreenshotAnalyzer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
