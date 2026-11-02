"""
OpenClip Main Application Window.
Full-featured PyQt6 Desktop Dashboard with local AI processing, multi-threading,
drag-and-drop, YouTube downloader, 9:16 auto-framing, animated captions, and video preview.
"""

import os
import sys
from typing import Optional, List
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSlider, QProgressBar, QTabWidget, QListWidget,
    QListWidgetItem, QFileDialog, QFrame, QSplitter, QMessageBox, QGroupBox,
    QScrollArea
)
from PyQt6.QtGui import QIcon, QFont

from ..core.downloader import YouTubeDownloader
from ..core.subtitle_generator import SubtitleStyle
from ..pipeline import OpenClipPipeline, PipelineConfig, RenderedClipResult
from .components.drop_zone import DropZoneWidget
from .components.log_viewer import LogViewerWidget
from .components.video_player import VideoPlayerWidget
from .theme import DARK_THEME_QSS
from check_env import run_full_check


# --- Background Worker Threads ---

class DownloadWorker(QThread):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, output_dir: str):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.downloader = YouTubeDownloader(output_dir)

    def run(self):
        try:
            downloaded_file = self.downloader.download(
                self.url,
                progress_callback=lambda p, s: self.progress.emit(p, s)
            )
            self.finished.emit(downloaded_file)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.downloader.cancel()


class PipelineWorker(QThread):
    step_changed = pyqtSignal(int, int, str)
    progress_changed = pyqtSignal(float, str)
    clip_ready = pyqtSignal(object)  # RenderedClipResult
    finished_all = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path: str, config: PipelineConfig):
        super().__init__()
        self.video_path = video_path
        self.config = config
        self.pipeline = OpenClipPipeline(config)

    def run(self):
        try:
            results = self.pipeline.run(
                self.video_path,
                on_step=lambda cur, tot, name: self.step_changed.emit(cur, tot, name),
                on_progress=lambda p, s: self.progress_changed.emit(p, s),
                on_clip_ready=lambda clip: self.clip_ready.emit(clip)
            )
            self.finished_all.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def cancel(self):
        self.pipeline.cancel()


# --- Main Dashboard Window ---

class OpenClipMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenClip - 100% Local AI Short Video Clipper")
        self.resize(1280, 840)
        self.setMinimumSize(1024, 680)

        self.current_video_path: str = ""
        self.active_pipeline_worker: Optional[PipelineWorker] = None
        self.active_download_worker: Optional[DownloadWorker] = None
        self.rendered_clips: List[RenderedClipResult] = []

        # Check Environment
        self.env_info = run_full_check()

        self._init_ui()
        self.setStyleSheet(DARK_THEME_QSS)

        # Log system readiness
        self.log_viewer.log("INFO", f"OpenClip siap digunakan. Python: {self.env_info['python']['version']}")
        if self.env_info['ffmpeg']['status']:
            hw_desc = self.env_info['ffmpeg']['recommended_encoder_desc']
            self.log_viewer.log("SUCCESS", f"FFmpeg terdeteksi: {hw_desc}")
        else:
            self.log_viewer.log("ERROR", "FFmpeg tidak ditemukan! Pastikan FFmpeg terpasang di sistem PATH.")

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Header Bar
        header = self._create_header()
        main_layout.addWidget(header)

        # 2. Main Content Splitter (Left: Inputs & Settings, Right: Player & Logs)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setContentsMargins(16, 10, 16, 10)
        splitter.setHandleWidth(8)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter)

        # 3. Bottom Execution & Progress Bar
        bottom_bar = self._create_bottom_bar()
        main_layout.addWidget(bottom_bar)

    def _create_header(self) -> QWidget:
        header_frame = QFrame()
        header_frame.setObjectName("header")
        layout = QHBoxLayout(header_frame)
        layout.setContentsMargins(20, 10, 20, 10)

        # App Brand
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)
        title = QLabel("🎬 OpenClip")
        title.setObjectName("titleLabel")
        subtitle = QLabel("KlipDong Desktop Alternative • 100% Local AI (No Cloud API Required)")
        subtitle.setObjectName("subTitleLabel")
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)
        layout.addLayout(brand_layout)

        layout.addStretch()

        # Badges
        offline_badge = QLabel("🔒 100% Offline / Local")
        offline_badge.setObjectName("badgeOk")
        layout.addWidget(offline_badge)

        hw_name = self.env_info['ffmpeg'].get('recommended_encoder_desc', 'CPU')
        hw_badge = QLabel(f"⚡ {hw_name}")
        hw_badge.setObjectName("badgeHw")
        layout.addWidget(hw_badge)

        return header_frame

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("leftPanelContent")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        # Input Tabs (Local Video vs YouTube URL)
        self.tab_widget = QTabWidget()

        # Tab 1: Local Video Drag & Drop
        self.drop_zone = DropZoneWidget()
        self.drop_zone.file_selected.connect(self._on_local_file_selected)
        self.tab_widget.addTab(self.drop_zone, "📁 Video Lokal (Drag && Drop)")

        # Tab 2: YouTube URL
        youtube_tab = self._create_youtube_tab()
        self.tab_widget.addTab(youtube_tab, "🌐 Download YouTube")

        layout.addWidget(self.tab_widget)

        # Settings Configuration Card
        settings_card = self._create_settings_card()
        layout.addWidget(settings_card)
        layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_area.setWidget(panel)

        return scroll_area

    def _create_youtube_tab(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        label = QLabel("Masukkan Tautan Video YouTube:")
        label.setStyleSheet("font-weight: 600; color: #E2E8F0; font-size: 13px; background: transparent;")
        layout.addWidget(label)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.yt_url_input = QLineEdit()
        self.yt_url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.yt_url_input.setFixedHeight(36)
        self.yt_url_input.returnPressed.connect(self._on_fetch_youtube_info)
        input_row.addWidget(self.yt_url_input)

        self.yt_fetch_btn = QPushButton("🔍 Cek Info")
        self.yt_fetch_btn.setFixedHeight(36)
        self.yt_fetch_btn.setFixedWidth(110)
        self.yt_fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yt_fetch_btn.clicked.connect(self._on_fetch_youtube_info)
        input_row.addWidget(self.yt_fetch_btn)

        layout.addLayout(input_row)

        # Preview Info Card
        self.yt_info_card = QFrame()
        self.yt_info_card.setObjectName("ytInfoCard")
        self.yt_info_card.setVisible(False)
        info_layout = QVBoxLayout(self.yt_info_card)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(8)

        self.yt_title_label = QLabel("Judul Video YouTube")
        self.yt_title_label.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 13px; background: transparent;")
        self.yt_title_label.setWordWrap(True)
        info_layout.addWidget(self.yt_title_label)

        self.yt_meta_label = QLabel("Detail durasi dan kanal...")
        self.yt_meta_label.setStyleSheet("color: #94A3B8; font-size: 12px; background: transparent;")
        info_layout.addWidget(self.yt_meta_label)

        self.yt_download_btn = QPushButton("📥 Unduh Video && Masukkan ke Pipeline")
        self.yt_download_btn.setObjectName("ytDownloadBtn")
        self.yt_download_btn.setFixedHeight(40)
        self.yt_download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yt_download_btn.clicked.connect(self._on_start_youtube_download)
        info_layout.addWidget(self.yt_download_btn)

        layout.addWidget(self.yt_info_card)

        return frame

    def _create_settings_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        card_title = QLabel("⚙ Konfigurasi AI & Video 9:16")
        card_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #F8FAFC; background: transparent;")
        layout.addWidget(card_title)

        grid = QVBoxLayout()
        grid.setSpacing(8)

        # Row 1: Whisper Model & Subtitle Style
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        
        # Whisper Model
        col1 = QVBoxLayout()
        col1.setSpacing(4)
        lbl_model = QLabel("AI Model (faster-whisper):")
        lbl_model.setStyleSheet("background: transparent;")
        col1.addWidget(lbl_model)
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(34)
        self.model_combo.addItems([
            "base (Rekomendasi - Cepat & Akurat)",
            "small (Lebih Akurat untuk Audio Bising)",
            "tiny (Paling Ringan / Laptop Spek Rendah)"
        ])
        col1.addWidget(self.model_combo)
        row1.addLayout(col1)

        # Subtitle Style
        col2 = QVBoxLayout()
        col2.setSpacing(4)
        lbl_style = QLabel("Gaya Subtitle Animasi (ASS):")
        lbl_style.setStyleSheet("background: transparent;")
        col2.addWidget(lbl_style)
        self.style_combo = QComboBox()
        self.style_combo.setFixedHeight(34)
        self.style_combo.addItems([
            "Bold Yellow (Kuning Pop-Up - Gaya Viral)",
            "Green Highlight (Hijau Neon - Gaya Hormozi)",
            "Clean White (Putih Minimalis & Elegan)",
            "Flame Orange (Oranye Api - High Contrast)"
        ])
        col2.addWidget(self.style_combo)
        row1.addLayout(col2)

        grid.addLayout(row1)

        # Row 2: Framing Mode & Number of Clips
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        # 9:16 Framing Mode
        col_framing = QVBoxLayout()
        col_framing.setSpacing(4)
        lbl_framing = QLabel("Mode Framing 9:16:")
        lbl_framing.setStyleSheet("background: transparent;")
        col_framing.addWidget(lbl_framing)
        self.framing_combo = QComboBox()
        self.framing_combo.setFixedHeight(34)
        self.framing_combo.addItems([
            "Fit & Blur (Teks & Grafis Utuh - Rekomendasi)",
            "Auto-Crop 9:16 (Fokus Wajah Pembicara)"
        ])
        col_framing.addWidget(self.framing_combo)
        row2.addLayout(col_framing)

        # Top Clips Count
        col4 = QVBoxLayout()
        col4.setSpacing(4)
        lbl_count = QLabel("Jumlah Klip Terbaik:")
        lbl_count.setStyleSheet("background: transparent;")
        col4.addWidget(lbl_count)
        self.clips_count_combo = QComboBox()
        self.clips_count_combo.setFixedHeight(34)
        self.clips_count_combo.addItems(["3 Klip Terbaik", "1 Klip Terbaik", "5 Klip Terbaik"])
        col4.addWidget(self.clips_count_combo)
        row2.addLayout(col4)

        grid.addLayout(row2)

        # Row 3: Target Duration Slider & Video Encoder
        row3 = QHBoxLayout()
        row3.setSpacing(10)

        # Target Duration Slider
        col3 = QVBoxLayout()
        col3.setSpacing(4)
        self.dur_label = QLabel("Durasi Target Klip: 45 detik")
        self.dur_label.setStyleSheet("background: transparent;")
        col3.addWidget(self.dur_label)
        self.dur_slider = QSlider(Qt.Orientation.Horizontal)
        self.dur_slider.setRange(30, 60)
        self.dur_slider.setValue(45)
        self.dur_slider.setFixedHeight(24)
        self.dur_slider.valueChanged.connect(lambda v: self.dur_label.setText(f"Durasi Target Klip: {v} detik"))
        col3.addWidget(self.dur_slider)
        row3.addLayout(col3)

        # Video Encoder
        col_enc = QVBoxLayout()
        col_enc.setSpacing(4)
        lbl_enc = QLabel("Akselerasi Video (Encoder):")
        lbl_enc.setStyleSheet("background: transparent;")
        col_enc.addWidget(lbl_enc)
        self.encoder_combo = QComboBox()
        self.encoder_combo.setFixedHeight(34)
        self.encoder_combo.addItems([
            "auto (Deteksi Otomatis & Teruji)",
            "libx264 (CPU Multi-Thread - 100% Stabil)",
            "h264_mf (Windows Media Foundation HW)",
            "h264_nvenc (NVIDIA NVENC)"
        ])
        col_enc.addWidget(self.encoder_combo)
        row3.addLayout(col_enc)

        grid.addLayout(row3)

        # Row 4: Output Folder
        row4 = QHBoxLayout()
        col5 = QVBoxLayout()
        col5.setSpacing(4)
        lbl_out = QLabel("Folder Output:")
        lbl_out.setStyleSheet("background: transparent;")
        col5.addWidget(lbl_out)
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.out_dir_input = QLineEdit()
        self.out_dir_input.setFixedHeight(34)
        default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs"))
        self.out_dir_input.setText(default_out)
        out_row.addWidget(self.out_dir_input)

        self.browse_out_btn = QPushButton("Ganti...")
        self.browse_out_btn.setFixedHeight(34)
        self.browse_out_btn.setFixedWidth(75)
        self.browse_out_btn.clicked.connect(self._on_browse_output_dir)
        out_row.addWidget(self.browse_out_btn)

        col5.addLayout(out_row)
        row4.addLayout(col5)
        grid.addLayout(row4)

        layout.addLayout(grid)
        return card

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Video Preview Player Card
        self.video_player = VideoPlayerWidget()
        layout.addWidget(self.video_player)

        # 2. Generated Clips List Card
        clips_frame = QFrame()
        clips_frame.setObjectName("card")
        clips_layout = QVBoxLayout(clips_frame)
        clips_layout.setContentsMargins(12, 10, 12, 10)
        clips_layout.setSpacing(8)

        clips_header = QHBoxLayout()
        clips_title = QLabel("✂ Daftar Klip 9:16 Dihasilkan")
        clips_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #F8FAFC;")
        clips_header.addWidget(clips_title)
        clips_header.addStretch()

        self.open_output_dir_btn = QPushButton("📂 Buka Folder Hasil")
        self.open_output_dir_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        self.open_output_dir_btn.clicked.connect(self._on_open_output_folder)
        clips_header.addWidget(self.open_output_dir_btn)

        clips_layout.addLayout(clips_header)

        self.clips_list = QListWidget()
        self.clips_list.itemClicked.connect(self._on_clip_selected)
        clips_layout.addWidget(self.clips_list)

        layout.addWidget(clips_frame)

        # 3. Real-Time Log Viewer
        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer)

        return panel

    def _create_bottom_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("header")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(6)

        # Status & Step labels row
        status_row = QHBoxLayout()
        self.step_label = QLabel("Tahap: Menunggu input video...")
        self.step_label.setStyleSheet("font-weight: 600; color: #38BDF8; font-size: 13px;")
        status_row.addWidget(self.step_label)

        status_row.addStretch()

        self.progress_pct_label = QLabel("0%")
        self.progress_pct_label.setStyleSheet("font-weight: bold; color: #10B981; font-size: 13px;")
        status_row.addWidget(self.progress_pct_label)

        layout.addLayout(status_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.start_btn = QPushButton("🚀 Mulai Proses Klip 9:16 (Auto-Framing && Subtitle)")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start_processing)
        btn_row.addWidget(self.start_btn, stretch=4)

        self.cancel_btn = QPushButton("⏹ Batal")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_processing)
        btn_row.addWidget(self.cancel_btn, stretch=1)

        layout.addLayout(btn_row)

        return frame

    # --- Slots & Events ---

    def _on_local_file_selected(self, file_path: str):
        self.current_video_path = file_path
        self.log_viewer.log("INFO", f"Video lokal dipilih: {os.path.basename(file_path)}")
        self.video_player.load_video(file_path)

    def _on_fetch_youtube_info(self):
        url = self.yt_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Peringatan", "Silakan masukkan URL YouTube terlebih dahulu.")
            return

        self.log_viewer.log("INFO", f"Mengambil metadata dari URL: {url}")
        self.yt_fetch_btn.setEnabled(False)

        try:
            downloader = YouTubeDownloader()
            info = downloader.get_info(url)
            self.yt_title_label.setText(info["title"])
            self.yt_meta_label.setText(
                f"Kanal: {info['uploader']} • Durasi: {info['duration_str']} • Views: {info['view_count']:,}"
            )
            self.yt_info_card.setVisible(True)
            self.log_viewer.log("SUCCESS", f"Info didapatkan: {info['title']} ({info['duration_str']})")
        except Exception as e:
            self.yt_info_card.setVisible(False)
            self.log_viewer.log("ERROR", f"Gagal mengambil info YouTube: {e}")
            QMessageBox.critical(self, "Error", f"Gagal mengambil info video:\n{e}")
        finally:
            self.yt_fetch_btn.setEnabled(True)

    def _on_start_youtube_download(self):
        url = self.yt_url_input.text().strip()
        if not url:
            return

        out_dir = os.path.join(self.out_dir_input.text().strip(), "downloads")
        self.yt_download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.step_label.setText("Tahap: Mengunduh video dari YouTube...")
        self.log_viewer.log("INFO", "Memulai pengunduhan video...")

        self.active_download_worker = DownloadWorker(url, out_dir)
        self.active_download_worker.progress.connect(self._on_progress_update)
        self.active_download_worker.finished.connect(self._on_youtube_download_finished)
        self.active_download_worker.error.connect(self._on_worker_error)
        self.active_download_worker.start()

    def _on_youtube_download_finished(self, downloaded_file: str):
        self.yt_download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.current_video_path = downloaded_file
        self.drop_zone.set_file(downloaded_file)
        self.video_player.load_video(downloaded_file)
        self.log_viewer.log("SUCCESS", f"Video berhasil diunduh: {os.path.basename(downloaded_file)}")
        self.step_label.setText("Video YouTube siap diproses.")

    def _on_browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Pilih Folder Output", self.out_dir_input.text())
        if dir_path:
            self.out_dir_input.setText(os.path.abspath(dir_path))

    def _on_open_output_folder(self):
        folder = self.out_dir_input.text().strip()
        if os.path.exists(folder):
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.Popen(['open', folder])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', folder])
        else:
            QMessageBox.information(self, "Info", "Folder output belum dibuat.")

    def _on_clip_selected(self, item: QListWidgetItem):
        clip_path = item.data(Qt.ItemDataRole.UserRole)
        if clip_path and os.path.exists(clip_path):
            self.video_player.load_video(clip_path)
            self.video_player.player.play()
            self.log_viewer.log("INFO", f"Memutar klip: {os.path.basename(clip_path)}")

    def _on_progress_update(self, percent: float, status_text: str):
        self.progress_bar.setValue(int(percent))
        self.progress_pct_label.setText(f"{percent:.1f}%")
        self.log_viewer.log("INFO", status_text)

    def _on_step_update(self, step_idx: int, total_steps: int, step_name: str):
        msg = f"Tahap {step_idx}/{total_steps}: {step_name}"
        self.step_label.setText(msg)
        self.log_viewer.log("AI", msg)

    def _on_clip_ready(self, clip_res: RenderedClipResult):
        self.rendered_clips.append(clip_res)
        
        # Add item to list widget
        item = QListWidgetItem()
        dur_s = int(clip_res.duration)
        item.setText(
            f"🎬 Klip #{clip_res.clip_index} ({dur_s}s) • Skor Viral: {clip_res.score:.2f}\n"
            f"\"{clip_res.text_preview[:60]}...\""
        )
        item.setData(Qt.ItemDataRole.UserRole, clip_res.output_path)
        self.clips_list.addItem(item)
        self.log_viewer.log("SUCCESS", f"Klip #{clip_res.clip_index} selesai: {os.path.basename(clip_res.output_path)}")

        # Auto-play first clip in player
        if len(self.rendered_clips) == 1:
            self.video_player.load_video(clip_res.output_path)

    def _on_pipeline_finished(self, all_results: list):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.step_label.setText("🎉 Selesai! Semua klip 9:16 berhasil di-render.")
        self.progress_bar.setValue(100)
        self.progress_pct_label.setText("100%")
        self.log_viewer.log("SUCCESS", f"Pipeline selesai. Total {len(all_results)} klip 9:16 tersimpan di folder output.")
        QMessageBox.information(
            self,
            "Selesai!",
            f"Pemrosesan selesai!\n{len(all_results)} video vertikal 9:16 siap digunakan untuk TikTok/Reels/Shorts."
        )

    def _on_worker_error(self, err_msg: str):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.step_label.setText("Terjadi kesalahan saat memproses.")
        self.log_viewer.log("ERROR", err_msg)
        QMessageBox.critical(self, "Kesalahan", f"Terjadi kesalahan:\n{err_msg}")

    def _on_start_processing(self):
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            QMessageBox.warning(self, "Peringatan", "Silakan pilih atau unduh video terlebih dahulu.")
            return

        # Model mapping
        model_idx = self.model_combo.currentIndex()
        model_map = ["base", "small", "tiny"]
        chosen_model = model_map[model_idx]

        # Style mapping
        style_idx = self.style_combo.currentIndex()
        style_map = [
            SubtitleStyle.BOLD_YELLOW,
            SubtitleStyle.GREEN_HIGHLIGHT,
            SubtitleStyle.CLEAN_WHITE,
            SubtitleStyle.FLAME_ORANGE
        ]
        chosen_style = style_map[style_idx]

        # Top clips count
        count_idx = self.clips_count_combo.currentIndex()
        count_map = [3, 1, 5]
        chosen_count = count_map[count_idx]

        # Encoder mapping
        enc_idx = self.encoder_combo.currentIndex()
        enc_map = ["auto", "libx264", "h264_mf", "h264_nvenc"]
        chosen_encoder = enc_map[enc_idx]

        # Framing mode mapping
        framing_idx = self.framing_combo.currentIndex()
        framing_map = ["fit_blur", "crop_face"]
        chosen_framing = framing_map[framing_idx]

        target_dur = float(self.dur_slider.value())
        out_dir = self.out_dir_input.text().strip()

        config = PipelineConfig(
            whisper_model=chosen_model,
            target_clip_duration=target_dur,
            min_clip_duration=max(20.0, target_dur - 15.0),
            max_clip_duration=min(90.0, target_dur + 15.0),
            top_clips_count=chosen_count,
            subtitle_style=chosen_style,
            framing_mode=chosen_framing,
            output_dir=out_dir,
            scale_to_1080p=True,
            burn_subtitles=True,
            hardware_encoder=chosen_encoder
        )

        # Reset UI
        self.clips_list.clear()
        self.rendered_clips.clear()
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_pct_label.setText("0%")

        self.log_viewer.log("INFO", f"Memulai OpenClip Pipeline untuk: {os.path.basename(self.current_video_path)}")
        self.log_viewer.log("INFO", f"Model: {chosen_model} | Style: {chosen_style.value} | Framing: {chosen_framing} | Target: {target_dur}s")

        self.active_pipeline_worker = PipelineWorker(self.current_video_path, config)
        self.active_pipeline_worker.step_changed.connect(self._on_step_update)
        self.active_pipeline_worker.progress_changed.connect(self._on_progress_update)
        self.active_pipeline_worker.clip_ready.connect(self._on_clip_ready)
        self.active_pipeline_worker.finished_all.connect(self._on_pipeline_finished)
        self.active_pipeline_worker.error_occurred.connect(self._on_worker_error)
        self.active_pipeline_worker.start()

    def _on_cancel_processing(self):
        if self.active_download_worker and self.active_download_worker.isRunning():
            self.active_download_worker.cancel()
            self.log_viewer.log("WARN", "Pengunduhan dibatalkan.")
        if self.active_pipeline_worker and self.active_pipeline_worker.isRunning():
            self.active_pipeline_worker.cancel()
            self.log_viewer.log("WARN", "Pemrosesan klip dibatalkan oleh pengguna.")

        self.cancel_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        self.step_label.setText("Dibatalkan.")
