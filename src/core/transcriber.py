"""
Audio Transcriber using faster-whisper.
Extracts word-level timestamps and segment information.
"""

import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class TranscriptionSegment:
    id: int
    start: float
    end: float
    text: str
    words: List[WordTimestamp] = field(default_factory=list)
    avg_logprob: float = 0.0


@dataclass
class TranscriptionResult:
    language: str
    language_probability: float
    duration: float
    segments: List[TranscriptionSegment] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)

    @property
    def total_words(self) -> int:
        return sum(len(s.words) for s in self.segments)


class WhisperTranscriber:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto"
    ):
        """
        Initialize Faster-Whisper transcriber.
        
        Args:
            model_size: 'tiny', 'base', 'small', 'medium'.
            device: 'cuda', 'cpu', or 'auto'.
            compute_type: 'int8', 'float16', 'float32', or 'auto'.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _resolve_device_and_type(self):
        dev = self.device
        ctype = self.compute_type

        if dev == "auto":
            has_cuda = False
            # Check ctranslate2 first (used directly by faster-whisper)
            try:
                import ctranslate2
                has_cuda = ctranslate2.get_cuda_device_count() > 0
            except Exception:
                pass

            # Check PyTorch if available
            if not has_cuda:
                try:
                    import torch
                    has_cuda = torch.cuda.is_available()
                except Exception:
                    pass

            dev = "cuda" if has_cuda else "cpu"

        if ctype == "auto":
            if dev == "cuda":
                ctype = "float16"
            else:
                # int8 is fast on CPU with lower memory usage
                ctype = "int8"

        return dev, ctype

    def load_model(self, progress_callback: Optional[Callable[[float, str], None]] = None):
        """Load or download Whisper model with automatic CPU fallback on failure."""
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel

        dev, ctype = self._resolve_device_and_type()
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "openclip_whisper")

        try:
            if progress_callback:
                progress_callback(10.0, f"Loading Whisper model '{self.model_size}' ({dev}, {ctype})...")

            self._model = WhisperModel(
                self.model_size,
                device=dev,
                compute_type=ctype,
                download_root=cache_dir
            )
        except Exception as e:
            # If CUDA fails (e.g. missing cudnn/cublas DLLs), fallback to CPU int8
            if dev != "cpu":
                if progress_callback:
                    progress_callback(15.0, f"CUDA initialization failed ({e}), falling back to CPU (int8)...")
                self.device = "cpu"
                self.compute_type = "int8"
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=cache_dir
                )
            else:
                raise e

        if progress_callback:
            progress_callback(30.0, f"Whisper model '{self.model_size}' loaded successfully ({self._model.model.device}).")

        return self._model

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file with word-level timestamps.
        
        Args:
            audio_path: Path to 16kHz WAV file.
            language: Optional language code (e.g. 'id' for Indonesian, 'en' for English).
                      If None, auto-detects.
            progress_callback: Callback receiving (percentage, status_text).
            
        Returns:
            TranscriptionResult object.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self.load_model(progress_callback)

        if progress_callback:
            progress_callback(35.0, "Transcribing speech & analyzing word timestamps...")

        segments_iter, info = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,  # Voice activity detection to ignore silence
            vad_parameters=dict(min_silence_duration_ms=500),
            beam_size=5
        )

        total_duration = info.duration or 1.0
        parsed_segments: List[TranscriptionSegment] = []

        seg_idx = 0
        for seg in segments_iter:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append(WordTimestamp(
                        word=w.word,
                        start=w.start,
                        end=w.end,
                        probability=getattr(w, 'probability', 1.0)
                    ))

            parsed_segments.append(TranscriptionSegment(
                id=seg_idx,
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                words=words,
                avg_logprob=getattr(seg, 'avg_logprob', 0.0)
            ))
            seg_idx += 1

            # Estimate progress based on current segment end vs total duration
            if progress_callback and total_duration > 0:
                pct = min(95.0, 35.0 + (seg.end / total_duration) * 60.0)
                status = f"Transcribed {seg.end:.1f}s / {total_duration:.1f}s: \"{seg.text[:35]}...\""
                progress_callback(pct, status)

        if progress_callback:
            progress_callback(100.0, f"Transcription complete ({len(parsed_segments)} segments).")

        return TranscriptionResult(
            language=info.language,
            language_probability=info.language_probability,
            duration=info.duration,
            segments=parsed_segments
        )
