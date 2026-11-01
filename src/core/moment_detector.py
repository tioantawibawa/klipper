"""
Viral Moment Detector & Smart Clipping Algorithm.
Analyzes speech density, intonation/energy, silence gaps, and sentence boundaries
to extract punchy 30-60 second clips suitable for TikTok, Reels, and YouTube Shorts.
"""

import os
import wave
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from .transcriber import TranscriptionResult, TranscriptionSegment, WordTimestamp


@dataclass
class MomentClip:
    index: int
    start_time: float
    end_time: float
    duration: float
    score: float
    title: str
    text_preview: str
    speech_density: float
    words_count: int
    segments: List[TranscriptionSegment] = field(default_factory=list)

    @property
    def formatted_range(self) -> str:
        s_m, s_s = divmod(int(self.start_time), 60)
        e_m, e_s = divmod(int(self.end_time), 60)
        return f"{s_m:02d}:{s_s:02d} - {e_m:02d}:{e_s:02d} ({self.duration:.1f}s)"


class MomentDetector:
    def __init__(
        self,
        min_duration: float = 30.0,
        max_duration: float = 60.0,
        target_duration: float = 45.0
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_duration = target_duration

    def _compute_audio_energy(self, wav_path: str, start_time: float, end_time: float) -> float:
        """Calculate RMS audio energy in a time slice to detect intonation peaks."""
        if not os.path.exists(wav_path):
            return 0.5
        
        try:
            with wave.open(wav_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                
                start_frame = int(start_time * sample_rate)
                n_frames = int((end_time - start_time) * sample_rate)
                
                wf.setpos(min(start_frame, wf.getnframes() - 1))
                raw_data = wf.readframes(n_frames)
                
                if not raw_data:
                    return 0.5
                
                fmt = f"<{len(raw_data)//2}h"
                samples = struct.unpack(fmt, raw_data)
                
                # Sample a subset to keep performance fast
                step = max(1, len(samples) // 1000)
                sub_samples = samples[::step]
                
                sum_sq = sum(s * s for s in sub_samples)
                rms = (sum_sq / len(sub_samples)) ** 0.5
                
                # Normalize RMS relative to 16-bit max (32768)
                norm_energy = min(1.0, rms / 8000.0)
                return norm_energy
        except Exception:
            return 0.5

    def detect_moments(
        self,
        transcription: TranscriptionResult,
        audio_wav_path: Optional[str] = None,
        top_k: int = 5
    ) -> List[MomentClip]:
        """
        Analyze transcript and audio to find the best short moments.
        
        Args:
            transcription: TranscriptionResult from faster-whisper.
            audio_wav_path: Optional path to 16kHz WAV for RMS energy evaluation.
            top_k: Number of top clips to return.
            
        Returns:
            List of MomentClip sorted by viral potential score.
        """
        segments = transcription.segments
        if not segments:
            # If no segments, fallback to a single clip covering the audio
            duration = min(self.target_duration, transcription.duration)
            return [MomentClip(
                index=1,
                start_time=0.0,
                end_time=duration,
                duration=duration,
                score=1.0,
                title="Full Video Clip",
                text_preview="Full video segment",
                speech_density=1.0,
                words_count=0
            )]

        # Collect candidate windows based on segment start boundaries
        candidates: List[MomentClip] = []
        n_segs = len(segments)

        for i in range(n_segs):
            seg_start = segments[i].start
            # Find matching end segment that fits in [min_duration, max_duration]
            for j in range(i, n_segs):
                seg_end = segments[j].end
                dur = seg_end - seg_start

                if dur < self.min_duration:
                    continue
                if dur > self.max_duration:
                    break

                # Extract segments in this window
                window_segs = segments[i : j + 1]
                
                # 1. Speech Density
                spoken_time = sum(
                    sum(w.end - w.start for w in s.words) if s.words else (s.end - s.start)
                    for s in window_segs
                )
                speech_density = min(1.0, spoken_time / dur) if dur > 0 else 0.0

                # 2. Total words count and pacing
                words_count = sum(len(s.words) if s.words else len(s.text.split()) for s in window_segs)
                wps = words_count / dur if dur > 0 else 0.0  # words per second
                # Optimal pacing is around 2.2 to 3.5 words/sec for viral short content
                pacing_score = max(0.0, 1.0 - abs(wps - 2.8) / 2.0)

                # 3. Hook Strength (first 5 seconds of the clip)
                hook_cutoff = seg_start + 5.0
                hook_spoken_time = 0.0
                for s in window_segs:
                    if s.start < hook_cutoff:
                        s_dur = min(s.end, hook_cutoff) - s.start
                        hook_spoken_time += max(0.0, s_dur)
                hook_strength = min(1.0, hook_spoken_time / 5.0)

                # 4. Silence Gap Penalty
                max_gap = 0.0
                for k in range(len(window_segs) - 1):
                    gap = window_segs[k + 1].start - window_segs[k].end
                    if gap > max_gap:
                        max_gap = gap
                gap_penalty = min(0.3, max(0.0, (max_gap - 1.5) * 0.15))

                # 5. Audio Energy
                audio_energy = 0.5
                if audio_wav_path:
                    audio_energy = self._compute_audio_energy(audio_wav_path, seg_start, seg_end)

                # 6. Target Duration Fit
                dur_fit = 1.0 - (abs(dur - self.target_duration) / (self.max_duration - self.min_duration))
                dur_fit = max(0.0, dur_fit)

                # Final Composite Score
                score = (
                    0.35 * speech_density +
                    0.25 * hook_strength +
                    0.15 * pacing_score +
                    0.15 * audio_energy +
                    0.10 * dur_fit -
                    gap_penalty
                )
                score = max(0.01, min(1.0, score))

                # Extract preview text
                text_full = " ".join(s.text for s in window_segs)
                preview = text_full[:120] + "..." if len(text_full) > 120 else text_full
                
                # Derive punchy title from first words
                words_list = text_full.split()
                title_words = words_list[:6] if len(words_list) >= 6 else words_list
                clip_title = " ".join(title_words)
                if clip_title:
                    clip_title = clip_title[0].upper() + clip_title[1:]

                candidates.append(MomentClip(
                    index=0,
                    start_time=seg_start,
                    end_time=seg_end,
                    duration=dur,
                    score=score,
                    title=clip_title or f"Highlight Moment",
                    text_preview=preview,
                    speech_density=speech_density,
                    words_count=words_count,
                    segments=window_segs
                ))

        if not candidates:
            # Fallback if video is shorter than min_duration or no window matched
            dur = min(transcription.duration, self.max_duration)
            return [MomentClip(
                index=1,
                start_time=0.0,
                end_time=dur,
                duration=dur,
                score=0.85,
                title="Best Highlight",
                text_preview=transcription.full_text[:100] + "...",
                speech_density=0.8,
                words_count=transcription.total_words,
                segments=segments
            )]

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Non-maximum suppression (avoid highly overlapping clips)
        selected: List[MomentClip] = []
        for cand in candidates:
            overlaps = False
            for sel in selected:
                # Check overlap
                overlap_start = max(cand.start_time, sel.start_time)
                overlap_end = min(cand.end_time, sel.end_time)
                overlap_dur = max(0.0, overlap_end - overlap_start)
                min_len = min(cand.duration, sel.duration)
                
                if min_len > 0 and (overlap_dur / min_len) > 0.35:
                    overlaps = True
                    break
            if not overlaps:
                cand.index = len(selected) + 1
                selected.append(cand)
            if len(selected) >= top_k:
                break

        return selected
