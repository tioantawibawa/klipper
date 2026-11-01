"""
OpenClip - 100% Local AI Short Video Clipper (9:16 Vertical Video & Animated Captions).
Main Application Entry Point.
"""

import sys
import os

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.ui.main_window import OpenClipMainWindow
from check_env import run_full_check


def main():
    # CLI check mode
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        report = run_full_check()
        print("Verification Report:", report)
        sys.exit(0 if report["overall_ok"] else 1)

    # Enable High DPI scaling
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("OpenClip")
    app.setOrganizationName("OpenClipAI")

    window = OpenClipMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
