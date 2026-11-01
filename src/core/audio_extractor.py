"""
Audio Extractor module using FFmpeg.
Extracts 16kHz mono WAV suitable for Faster-Whisper transcription.
"""

import os
import subprocess
import shutil
from typing import Optional, Callable


class AudioExtractor:
    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"

    def extract_wav(
        self,
        video_path: str,
        output_wav_path: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Extract audio from video file to 16kHz mono WAV.
        
        Args:
            video_path: Path to input video.
            output_wav_path: Destination path for WAV. If None, generated automatically.
            progress_callback: Optional progress reporter.
            
        Returns:
            Path to extracted WAV file.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not output_wav_path:
            base, _ = os.path.splitext(video_path)
            output_wav_path = f"{base}_16k.wav"

        if progress_callback:
            progress_callback(10.0, "Extracting audio stream to 16kHz WAV...")

        # FFmpeg command: -y (overwrite), -vn (no video), -acodec pcm_s16le, -ar 16000, -ac 1
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_wav_path
        ]

        # Use creationflags to prevent popup console on Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo
        )

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed:\n{proc.stderr}")

        if progress_callback:
            progress_callback(100.0, "Audio extraction finished.")

        return os.path.abspath(output_wav_path)
