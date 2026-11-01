"""
Video Preview Player Widget for OpenClip.
Provides local video playback, timeline scrubbing, play/pause controls,
and external player opening.
"""

import os
import sys
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QFrame
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


class VideoPlayerWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.current_video_path: str = ""
        self.duration_ms: int = 0

        self._init_player()
        self._init_ui()

    def _init_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Video Surface Widget
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        self.video_widget.setMinimumHeight(240)
        self.player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget)

        # Scrubber Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self._set_position)
        layout.addWidget(self.slider)

        # Controls Row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedWidth(40)
        self.play_btn.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_btn)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #94A3B8; font-size: 11px; background: transparent;")
        controls_layout.addWidget(self.time_label)

        controls_layout.addStretch()

        self.open_ext_btn = QPushButton("↗ Buka di Sistem")
        self.open_ext_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        self.open_ext_btn.clicked.connect(self.open_in_system_player)
        controls_layout.addWidget(self.open_ext_btn)

        layout.addLayout(controls_layout)

    def load_video(self, video_path: str):
        if not os.path.exists(video_path):
            return

        self.current_video_path = os.path.abspath(video_path)
        self.player.setSource(QUrl.fromLocalFile(self.current_video_path))
        self.play_btn.setText("▶")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")

    def _on_position_changed(self, position):
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self._update_time_label(position, self.duration_ms)

    def _on_duration_changed(self, duration):
        self.duration_ms = duration
        self.slider.setRange(0, duration)
        self._update_time_label(self.player.position(), duration)

    def _set_position(self, position):
        self.player.setPosition(position)

    def _update_time_label(self, pos_ms, dur_ms):
        cur_s = int(pos_ms // 1000)
        tot_s = int(dur_ms // 1000)
        cur_m, cur_s = divmod(cur_s, 60)
        tot_m, tot_s = divmod(tot_s, 60)
        self.time_label.setText(f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}")

    def open_in_system_player(self):
        if self.current_video_path and os.path.exists(self.current_video_path):
            if sys.platform == 'win32':
                os.startfile(self.current_video_path)
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.Popen(['open', self.current_video_path])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', self.current_video_path])
