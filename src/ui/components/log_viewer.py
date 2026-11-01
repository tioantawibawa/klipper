"""
Real-time Colored Log Viewer Widget for OpenClip.
Displays status logs with syntax color coding and auto-scrolling.
"""

import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QFrame, QApplication
)


class LogViewerWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header bar
        header_layout = QHBoxLayout()
        title = QLabel("📋 Log Proses Real-Time")
        title.setStyleSheet("font-weight: bold; color: #94A3B8; font-size: 12px; background: transparent;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.clear_btn = QPushButton("Bersihkan")
        self.clear_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.clear_btn.clicked.connect(self.clear_logs)
        header_layout.addWidget(self.clear_btn)

        self.copy_btn = QPushButton("Salin")
        self.copy_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.copy_btn.clicked.connect(self.copy_logs)
        header_layout.addWidget(self.copy_btn)

        layout.addLayout(header_layout)

        # Text Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #0E1015;
                color: #CBD5E1;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 11px;
                border: 1px solid #232733;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.console)

    def log(self, level: str, message: str):
        """Append a log message with timestamp and level color."""
        now_str = datetime.datetime.now().strftime("%H:%M:%S")

        level_upper = level.upper()
        if "SUCCESS" in level_upper or "OK" in level_upper:
            badge_color = "#10B981"  # Emerald
        elif "AI" in level_upper or "WHISPER" in level_upper:
            badge_color = "#A855F7"  # Purple
        elif "RENDER" in level_upper or "FFMPEG" in level_upper:
            badge_color = "#F59E0B"  # Amber
        elif "WARN" in level_upper:
            badge_color = "#EAB308"  # Yellow
        elif "ERROR" in level_upper or "FAIL" in level_upper:
            badge_color = "#EF4444"  # Red
        else:
            badge_color = "#38BDF8"  # Cyan

        escaped_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_line = (
            f"<span style='color: #64748B;'>[{now_str}]</span> "
            f"<span style='color: {badge_color}; font-weight: bold;'>[{level_upper}]</span> "
            f"<span style='color: #E2E8F0;'>{escaped_msg}</span>"
        )

        self.console.append(html_line)
        # Auto-scroll to bottom
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_logs(self):
        self.console.clear()

    def copy_logs(self):
        text = self.console.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.log("INFO", "Log berhasil disalin ke clipboard.")
