import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from modules.ui import ScreenshotAnalyzer


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Control Me")
    app.setDesktopFileName("Control_Me")
    app.setWindowIcon(QIcon("icon.ico"))

    window = ScreenshotAnalyzer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
