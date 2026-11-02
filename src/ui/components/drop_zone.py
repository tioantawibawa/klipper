"""
Drag & Drop Video Zone Widget for OpenClip.
Supports MP4, MOV, MKV, AVI, and WEBM with metadata inspection.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QFrame, QHBoxLayout
)
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class DropZoneWidget(QFrame):
    file_selected = pyqtSignal(str)

    SUPPORTED_EXTS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("card")
        self.current_file: str = ""

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon Label
        self.icon_label = QLabel("🎬")
        self.icon_label.setStyleSheet("font-size: 30px; background: transparent;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # Primary Text
        self.title_label = QLabel("Tarik & Lepas File Video ke Sini")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #F8FAFC; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # Subtext
        self.sub_label = QLabel("Mendukung format MP4, MOV, MKV, AVI, WEBM")
        self.sub_label.setStyleSheet("font-size: 12px; color: #94A3B8; background: transparent;")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_label)

        # Browse Button
        self.browse_btn = QPushButton("📁 Pilih Video dari Laptop")
        self.browse_btn.setFixedWidth(220)
        self.browse_btn.setFixedHeight(34)
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # File Info Frame (hidden until file selected)
        self.info_frame = QFrame()
        self.info_frame.setObjectName("fileInfoFrame")
        self.info_frame.setStyleSheet("""
            QFrame#fileInfoFrame {
                background-color: #212530;
                border: 1px solid #38BDF8;
                border-radius: 8px;
            }
        """)
        self.info_frame.setVisible(False)
        info_layout = QHBoxLayout(self.info_frame)
        info_layout.setContentsMargins(14, 8, 14, 8)

        self.file_name_label = QLabel("")
        self.file_name_label.setStyleSheet("color: #38BDF8; font-weight: bold; background: transparent;")
        info_layout.addWidget(self.file_name_label)

        self.file_meta_label = QLabel("")
        self.file_meta_label.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent;")
        info_layout.addWidget(self.file_meta_label, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.info_frame)

    def _set_active_style(self, active: bool):
        if active:
            self.setStyleSheet("""
                QFrame#card {
                    background-color: #1E2330;
                    border: 2px dashed #38BDF8;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#card {
                    background-color: #1A1C23;
                    border: 1px solid #282C37;
                    border-radius: 10px;
                }
            """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                _, ext = os.path.splitext(path)
                if ext.lower() in self.SUPPORTED_EXTS:
                    event.acceptProposedAction()
                    self._set_active_style(True)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_active_style(False)

    def dropEvent(self, event: QDropEvent):
        self._set_active_style(False)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.exists(path):
                self.set_file(path)

    def _on_browse_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File Video",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All Files (*)"
        )
        if file_path:
            self.set_file(file_path)

    def set_file(self, file_path: str):
        self.current_file = os.path.abspath(file_path)
        base_name = os.path.basename(self.current_file)
        size_mb = os.path.getsize(self.current_file) / (1024 * 1024)

        # Inspect duration / resolution if OpenCV is available
        extra_info = f"{size_mb:.1f} MB"
        try:
            import cv2
            cap = cv2.VideoCapture(self.current_file)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                dur_s = frames / fps if fps > 0 else 0
                m, s = divmod(int(dur_s), 60)
                extra_info = f"{w}x{h} • {m:02d}:{s:02d} • {size_mb:.1f} MB"
                cap.release()
        except Exception:
            pass

        self.file_name_label.setText(f"📹 {base_name}")
        self.file_meta_label.setText(extra_info)
        self.info_frame.setVisible(True)
        self.sub_label.setText("File video siap diproses menjadi klip vertikal 9:16")

        self.file_selected.emit(self.current_file)
