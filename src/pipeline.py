"""
OpenClip Pipeline Coordinator.
Orchestrates the complete end-to-end workflow:
Audio Extraction -> Word-level Transcription -> Moment Detection ->
9:16 Face Tracking & Auto-framing -> Animated ASS Captions -> FFmpeg Export.
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Callable, Dict, Any

from .core.audio_extractor import AudioExtractor
from .core.transcriber import WhisperTranscriber, TranscriptionResult
from .core.moment_detector import MomentDetector, MomentClip
from .core.face_tracker import FaceTracker
from .core.subtitle_generator import SubtitleGenerator, SubtitleStyle
from .core.video_editor import VideoEditor, RenderConfig


@dataclass
class PipelineConfig:
    whisper_model: str = "base"
    whisper_device: str = "auto"
    whisper_compute: str = "auto"
    min_clip_duration: float = 30.0
    max_clip_duration: float = 60.0
    target_clip_duration: float = 45.0
    top_clips_count: int = 3
    subtitle_style: SubtitleStyle = SubtitleStyle.BOLD_YELLOW
    subtitle_words_per_line: int = 3
    burn_subtitles: bool = True
    scale_to_1080p: bool = True
    framing_mode: str = "fit_blur"   # "fit_blur" (Full 16:9 + Blur BG) or "crop_face" (9:16 Zoom Crop)
    output_dir: str = "outputs"
    hardware_encoder: str = "auto"


@dataclass
class RenderedClipResult:
    clip_index: int
    title: str
    output_path: str
    duration: float
    start_time: float
    end_time: float
    score: float
    text_preview: str


class OpenClipPipeline:
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.audio_extractor = AudioExtractor()
        self.transcriber = WhisperTranscriber(
            model_size=self.config.whisper_model,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute
        )
        self.moment_detector = MomentDetector(
            min_duration=self.config.min_clip_duration,
            max_duration=self.config.max_clip_duration,
            target_duration=self.config.target_clip_duration
        )
        self.face_tracker = FaceTracker()
        self.video_editor = VideoEditor()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        self.video_editor.cancel()

    def run(
        self,
        video_path: str,
        on_step: Optional[Callable[[int, int, str], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_clip_ready: Optional[Callable[[RenderedClipResult], None]] = None
    ) -> List[RenderedClipResult]:
        """
        Execute full OpenClip pipeline on a video file.
        
        Args:
            video_path: Absolute or relative path to source video.
            on_step: Callback (step_idx, total_steps, step_name).
            on_progress: Callback (percentage [0-100], status_text).
            on_clip_ready: Callback invoked when an individual clip is rendered.
            
        Returns:
            List of RenderedClipResult.
        """
        self._cancelled = False
        total_steps = 5

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        os.makedirs(self.config.output_dir, exist_ok=True)
        work_dir = os.path.join(self.config.output_dir, "temp_workspace")
        os.makedirs(work_dir, exist_ok=True)

        base_video_name = os.path.splitext(os.path.basename(video_path))[0]
        # Sanitize filename for generated media files to prevent issues with quotes, colons, or invalid chars
        safe_base_name = re.sub(r"[^\w\-.]", "_", base_video_name)
        safe_base_name = re.sub(r"_+", "_", safe_base_name).strip("_") or "clip"

        # STEP 1: Audio Extraction
        if on_step:
            on_step(1, total_steps, "Ekstraksi Audio 16kHz")
        if self._cancelled:
            raise Exception("Cancelled by user.")

        wav_path = os.path.join(work_dir, f"{safe_base_name}_16k.wav")
        self.audio_extractor.extract_wav(
            video_path,
            output_wav_path=wav_path,
            progress_callback=on_progress
        )

        # STEP 2: AI Transcription (faster-whisper)
        if on_step:
            on_step(2, total_steps, "Transkripsi AI & Word-Level Timestamps")
        if self._cancelled:
            raise Exception("Cancelled by user.")

        transcription = self.transcriber.transcribe(
            wav_path,
            progress_callback=on_progress
        )

        # STEP 3: Smart Moment Detection
        if on_step:
            on_step(3, total_steps, "Deteksi Momen Viral (Kepadatan Bicara & Jeda)")
        if self._cancelled:
            raise Exception("Cancelled by user.")

        if on_progress:
            on_progress(10.0, "Menganalisis kepadatan bicara, intonasi, dan jeda hening...")

        candidate_clips = self.moment_detector.detect_moments(
            transcription,
            audio_wav_path=wav_path,
            top_k=self.config.top_clips_count
        )

        if on_progress:
            on_progress(100.0, f"Ditemukan {len(candidate_clips)} momen terbaik untuk klip 9:16.")

        # STEP 4 & 5: Auto-Framing 9:16, Subtitle Generation, and FFmpeg Render
        rendered_results: List[RenderedClipResult] = []

        for clip_idx, clip in enumerate(candidate_clips, 1):
            if self._cancelled:
                raise Exception("Cancelled by user.")

            # STEP 4: Framing (Fit & Blur vs Face Tracking Crop)
            if self.config.framing_mode == "crop_face":
                if on_step:
                    on_step(4, total_steps, f"Face Tracking 9:16 (Klip {clip_idx}/{len(candidate_clips)})")
                crop_w, crop_h, crop_x, crop_y, trajectory = self.face_tracker.track_clip(
                    video_path,
                    start_time=clip.start_time,
                    end_time=clip.end_time,
                    progress_callback=on_progress
                )
            else:
                if on_step:
                    on_step(4, total_steps, f"Framing Fit & Blur (Klip {clip_idx}/{len(candidate_clips)})")
                crop_w, crop_h, crop_x, crop_y = 1080, 1920, 0, 0
                if on_progress:
                    on_progress(100.0, "Menyiapkan layout Fit Video & Background Blur...")

            # Subtitles Generation
            ass_path = None
            if self.config.burn_subtitles:
                sub_gen = SubtitleGenerator(
                    style=self.config.subtitle_style,
                    words_per_group=self.config.subtitle_words_per_line,
                    canvas_width=1080 if self.config.scale_to_1080p else crop_w,
                    canvas_height=1920 if self.config.scale_to_1080p else crop_h
                )
                
                # Gather words for this clip
                clip_words = []
                for s in clip.segments:
                    for w in s.words:
                        if clip.start_time <= w.end and w.start <= clip.end_time:
                            clip_words.append(w)

                ass_file = os.path.join(work_dir, f"clip_{clip_idx}_subtitles.ass")
                ass_path = sub_gen.generate_ass(
                    words=clip_words,
                    output_ass_path=ass_file,
                    time_offset=clip.start_time
                )

            # STEP 5: Render Clip
            if on_step:
                on_step(5, total_steps, f"Render Klip 9:16 FFmpeg ({clip_idx}/{len(candidate_clips)})")

            out_clip_name = f"{safe_base_name}_short_{clip_idx}_{int(clip.start_time)}s.mp4"
            out_clip_path = os.path.join(self.config.output_dir, out_clip_name)

            render_cfg = RenderConfig(
                output_dir=self.config.output_dir,
                encoder=self.config.hardware_encoder,
                scale_to_1080p=self.config.scale_to_1080p,
                burn_subtitles=self.config.burn_subtitles,
                framing_mode=self.config.framing_mode
            )

            rendered_file = self.video_editor.render_short_clip(
                video_path=video_path,
                start_time=clip.start_time,
                duration=clip.duration,
                crop_w=crop_w,
                crop_h=crop_h,
                crop_x=crop_x,
                crop_y=crop_y,
                ass_subtitles_path=ass_path,
                output_filename=out_clip_path,
                config=render_cfg,
                progress_callback=on_progress
            )

            res = RenderedClipResult(
                clip_index=clip_idx,
                title=clip.title,
                output_path=rendered_file,
                duration=clip.duration,
                start_time=clip.start_time,
                end_time=clip.end_time,
                score=clip.score,
                text_preview=clip.text_preview
            )
            rendered_results.append(res)

            if on_clip_ready:
                on_clip_ready(res)

        return rendered_results
