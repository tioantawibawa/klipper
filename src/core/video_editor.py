"""
Video Editor & FFmpeg Render Engine.
Crops video to 9:16, burns animated ASS subtitles, slices highlights,
and renders with GPU Hardware Acceleration (NVENC/QuickSync/AMF/MediaFoundation)
or automatic fallback to multi-threaded CPU (libx264).
"""

import os
import re
import shutil
import subprocess
from collections import deque
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any


@dataclass
class RenderConfig:
    output_dir: str = "outputs"
    encoder: str = "auto"              # 'auto', 'h264_nvenc', 'h264_qsv', 'h264_amf', 'h264_mf', 'libx264'
    scale_to_1080p: bool = True       # Scale to 1080x1920
    framing_mode: str = "fit_blur"    # 'fit_blur' (Fit 16:9 + Blur BG) or 'crop_face' (9:16 Crop)
    crf: int = 20                     # 18-24 for libx264
    nvenc_cq: int = 23                # CQ for NVENC
    audio_bitrate: str = "192k"
    burn_subtitles: bool = True


class VideoEditor:
    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self._current_process: Optional[subprocess.Popen] = None
        self._cancelled = False
        self._cached_encoder: Optional[str] = None

    def cancel(self):
        self._cancelled = True
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
            except Exception:
                pass

    def _test_encoder(self, encoder: str) -> bool:
        """Run a 0.1-second null test to verify if the encoder actually works with current drivers."""
        try:
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-f", "lavfi",
                "-i", "nullsrc=s=64x64:d=0.1",
                "-c:v", encoder,
                "-f", "null",
                "-"
            ]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            proc = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                timeout=3
            )
            return proc.returncode == 0
        except Exception:
            return False

    def detect_best_encoder(self) -> str:
        """
        Detect the best working video encoder by testing execution against current hardware and drivers.
        Tests in order: NVENC -> QuickSync -> AMF -> Media Foundation -> libx264 (CPU).
        """
        if self._cached_encoder:
            return self._cached_encoder

        candidates = ["h264_nvenc", "h264_qsv", "h264_amf", "h264_mf"]
        for cand in candidates:
            if self._test_encoder(cand):
                self._cached_encoder = cand
                return cand

        self._cached_encoder = "libx264"
        return "libx264"

    def render_short_clip(
        self,
        video_path: str,
        start_time: float,
        duration: float,
        crop_w: int,
        crop_h: int,
        crop_x: int,
        crop_y: int,
        ass_subtitles_path: Optional[str] = None,
        output_filename: Optional[str] = None,
        config: Optional[RenderConfig] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Render a 9:16 vertical short clip with crop and animated subtitles.
        Automatically falls back to libx264 if hardware encoder fails at runtime.
        """
        self._cancelled = False
        config = config or RenderConfig()

        os.makedirs(config.output_dir, exist_ok=True)
        if not output_filename:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_filename = f"{base_name}_short_{int(start_time)}s.mp4"

        output_path = (
            output_filename
            if os.path.isabs(output_filename)
            else os.path.join(config.output_dir, output_filename)
        )

        # Encoder selection
        chosen_encoder = config.encoder
        if chosen_encoder == "auto":
            chosen_encoder = self.detect_best_encoder()

        try:
            return self._execute_render(
                video_path=video_path,
                start_time=start_time,
                duration=duration,
                crop_w=crop_w,
                crop_h=crop_h,
                crop_x=crop_x,
                crop_y=crop_y,
                ass_subtitles_path=ass_subtitles_path,
                output_path=output_path,
                encoder=chosen_encoder,
                config=config,
                progress_callback=progress_callback
            )
        except Exception as e:
            # If a hardware encoder failed and we haven't tried libx264 yet, retry with CPU libx264
            if chosen_encoder != "libx264" and not self._cancelled:
                if progress_callback:
                    progress_callback(5.0, f"Hardware encoder '{chosen_encoder}' failed. Falling back to CPU (libx264)...")
                return self._execute_render(
                    video_path=video_path,
                    start_time=start_time,
                    duration=duration,
                    crop_w=crop_w,
                    crop_h=crop_h,
                    crop_x=crop_x,
                    crop_y=crop_y,
                    ass_subtitles_path=ass_subtitles_path,
                    output_path=output_path,
                    encoder="libx264",
                    config=config,
                    progress_callback=progress_callback
                )
            else:
                raise e

    def _execute_render(
        self,
        video_path: str,
        start_time: float,
        duration: float,
        crop_w: int,
        crop_h: int,
        crop_x: int,
        crop_y: int,
        ass_subtitles_path: Optional[str],
        output_path: str,
        encoder: str,
        config: RenderConfig,
        progress_callback: Optional[Callable[[float, str], None]]
    ) -> str:
        escaped_ass = ""
        if config.burn_subtitles and ass_subtitles_path and os.path.exists(ass_subtitles_path):
            escaped_ass = os.path.abspath(ass_subtitles_path).replace("\\", "/")
            escaped_ass = escaped_ass.replace(":", r"\:")
            escaped_ass = escaped_ass.replace("'", r"'\\\''")

        if config.framing_mode == "fit_blur":
            # 16:9 Full video centered on 1080x1920 with aesthetic blurred background (No text/infographic cutoff)
            filter_complex = (
                "[0:v]split=2[v_bg][v_fg];"
                "[v_bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5,eq=brightness=-0.08[bg];"
                "[v_fg]scale=1080:-2[fg];"
            )
            if escaped_ass:
                filter_complex += f"[bg][fg]overlay=0:(H-h)/2,ass='{escaped_ass}'[outv]"
            else:
                filter_complex += "[bg][fg]overlay=0:(H-h)/2[outv]"

            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-ss", f"{start_time:.3f}",
                "-t", f"{duration:.3f}",
                "-i", video_path,
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-map", "0:a?",
                "-c:v", encoder,
            ]
        else:
            # 9:16 Crop
            filters = []
            filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")
            if config.scale_to_1080p:
                filters.append("scale=1080:1920:flags=lanczos")
            if escaped_ass:
                filters.append(f"ass='{escaped_ass}'")
            vf_str = ",".join(filters)

            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-ss", f"{start_time:.3f}",
                "-t", f"{duration:.3f}",
                "-i", video_path,
                "-vf", vf_str,
                "-c:v", encoder,
            ]

        # Encoder specific options
        if encoder == "h264_nvenc":
            cmd.extend(["-preset", "p4", "-cq", str(config.nvenc_cq), "-b:v", "0"])
        elif encoder == "h264_qsv":
            cmd.extend(["-preset", "medium", "-global_quality", "23"])
        elif encoder == "h264_amf":
            cmd.extend(["-quality", "balanced", "-rc", "cqp", "-qp_i", "22", "-qp_p", "22"])
        elif encoder == "h264_mf":
            cmd.extend(["-b:v", "5000k"])
        else:
            # CPU libx264
            cmd.extend(["-preset", "fast", "-crf", str(config.crf), "-threads", "0"])

        cmd.extend([
            "-c:a", "aac",
            "-b:a", config.audio_bitrate,
            "-avoid_negative_ts", "make_zero",
            output_path
        ])

        if progress_callback:
            progress_callback(5.0, f"Initializing FFmpeg render ({encoder})...")

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self._current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True,
            startupinfo=startupinfo,
            encoding='utf-8',
            errors='replace'
        )

        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
        fps_pattern = re.compile(r"fps=\s*(\d+(\.\d+)?)")

        # Rolling buffer for error reporting
        recent_stderr = deque(maxlen=30)

        while True:
            if self._cancelled:
                self._current_process.terminate()
                raise Exception("Rendering cancelled by user.")

            line = self._current_process.stderr.readline()
            if not line and self._current_process.poll() is not None:
                break

            if line:
                recent_stderr.append(line.strip())
                if progress_callback:
                    # Parse progress
                    time_match = time_pattern.search(line)
                    fps_match = fps_pattern.search(line)
                    if time_match:
                        h, m, s = float(time_match.group(1)), float(time_match.group(2)), float(time_match.group(3))
                        cur_sec = h * 3600 + m * 60 + s
                        pct = min(99.0, max(5.0, (cur_sec / max(0.1, duration)) * 100.0))
                        fps_val = fps_match.group(1) if fps_match else "?"
                        progress_callback(pct, f"Rendering 9:16 Short ({encoder}): {pct:.1f}% ({fps_val} fps, {cur_sec:.1f}s / {duration:.1f}s)")

        returncode = self._current_process.poll()
        if returncode != 0:
            if self._cancelled:
                raise Exception("Rendering cancelled.")
            filtered_err = [
                l for l in recent_stderr
                if not l.startswith(("configuration:", "built with", "libav", "ffmpeg version"))
            ]
            err_details = "\n".join(filtered_err if filtered_err else recent_stderr)
            raise RuntimeError(f"FFmpeg rendering failed with {encoder} (code {returncode}):\n{err_details}")

        if progress_callback:
            progress_callback(100.0, f"Render complete: {os.path.basename(output_path)}")

        return os.path.abspath(output_path)
