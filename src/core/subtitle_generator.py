"""
Animated Captions Engine for OpenClip.
Generates ASS (Advanced SubStation Alpha) subtitle files with word-level highlighting
and pop animations for TikTok, Reels, and YouTube Shorts (KlipDong / Hormozi style).
"""

import os
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from .transcriber import WordTimestamp, TranscriptionSegment


class SubtitleStyle(str, Enum):
    BOLD_YELLOW = "bold_yellow"
    GREEN_HIGHLIGHT = "green_highlight"
    CLEAN_WHITE = "clean_white"
    FLAME_ORANGE = "flame_orange"


@dataclass
class StyleConfig:
    name: str
    primary_color: str    # &HAABBGGRR
    highlight_color: str  # &HAABBGGRR
    outline_color: str    # &HAABBGGRR
    font_name: str
    font_size: int
    bold: int
    outline: int
    shadow: int
    alignment: int        # 2 = Bottom center, 5 = Screen center, 8 = Top center
    margin_v: int         # Vertical margin from edge


STYLE_PRESETS = {
    SubtitleStyle.BOLD_YELLOW: StyleConfig(
        name="BoldYellow",
        primary_color="&H00FFFFFF",     # White
        highlight_color="&H0000E6FF",   # Vibrant Gold / Yellow
        outline_color="&H00000000",     # Solid Black Outline
        font_name="Arial Black",
        font_size=20,
        bold=1,
        outline=3,
        shadow=2,
        alignment=2,
        margin_v=90
    ),
    SubtitleStyle.GREEN_HIGHLIGHT: StyleConfig(
        name="GreenHighlight",
        primary_color="&H00FFFFFF",     # White
        highlight_color="&H0032FF00",   # Neon Green
        outline_color="&H00000000",     # Solid Black Outline
        font_name="Arial Black",
        font_size=20,
        bold=1,
        outline=3,
        shadow=2,
        alignment=2,
        margin_v=90
    ),
    SubtitleStyle.CLEAN_WHITE: StyleConfig(
        name="CleanWhite",
        primary_color="&H00A0A0A0",     # Muted Silver for inactive
        highlight_color="&H00FFFFFF",   # Crisp White for active
        outline_color="&H00181818",     # Charcoal outline
        font_name="Arial",
        font_size=19,
        bold=1,
        outline=2,
        shadow=1,
        alignment=2,
        margin_v=90
    ),
    SubtitleStyle.FLAME_ORANGE: StyleConfig(
        name="FlameOrange",
        primary_color="&H00FFFFFF",     # White
        highlight_color="&H000066FF",   # Hot Orange
        outline_color="&H00000000",     # Solid Black Outline
        font_name="Arial Black",
        font_size=20,
        bold=1,
        outline=3,
        shadow=2,
        alignment=2,
        margin_v=90
    ),
}


class SubtitleGenerator:
    def __init__(
        self,
        style: SubtitleStyle = SubtitleStyle.BOLD_YELLOW,
        words_per_group: int = 3,
        canvas_width: int = 608,
        canvas_height: int = 1080
    ):
        self.style_config = STYLE_PRESETS.get(style, STYLE_PRESETS[SubtitleStyle.BOLD_YELLOW])
        self.words_per_group = words_per_group
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """Format seconds into ASS timestamp: H:MM:SS.cs (centiseconds)."""
        seconds = max(0.0, seconds)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds - int(seconds)) * 100))
        if cs >= 100:
            cs = 99
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def generate_ass(
        self,
        words: List[WordTimestamp],
        output_ass_path: str,
        time_offset: float = 0.0,
        pop_scale: int = 115
    ) -> str:
        """
        Generate ASS file with word-by-word highlighting and pop animation.
        
        Args:
            words: List of WordTimestamp (word, start, end).
            output_ass_path: Destination path for .ass file.
            time_offset: Subtracted from word timestamps (e.g. clip start_time) so subtitles start at 0.
            pop_scale: Font scale percent for currently active word (default 115%).
            
        Returns:
            Absolute path to generated ASS file.
        """
        cfg = self.style_config

        # Group words into chunks of N words
        filtered_words = [
            w for w in words
            if w.word.strip() and (w.end - time_offset) >= 0
        ]

        # Break words into punchy lines (2-4 words each)
        word_groups: List[List[WordTimestamp]] = []
        current_group: List[WordTimestamp] = []

        for w in filtered_words:
            # Adjust timestamp relative to clip start
            rel_w = WordTimestamp(
                word=w.word.strip().upper(),
                start=max(0.0, w.start - time_offset),
                end=max(0.0, w.end - time_offset),
                probability=w.probability
            )
            current_group.append(rel_w)

            # Split if reached group limit or word has sentence punctuation
            has_punct = any(p in rel_w.word for p in ['.', '!', '?', ','])
            if len(current_group) >= self.words_per_group or (len(current_group) >= 2 and has_punct):
                word_groups.append(current_group)
                current_group = []

        if current_group:
            word_groups.append(current_group)

        # ASS File Header
        lines = [
            "[Script Info]",
            "Title: OpenClip Viral Captions",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            f"PlayResX: {self.canvas_width}",
            f"PlayResY: {self.canvas_height}",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{cfg.font_name},{cfg.font_size},{cfg.primary_color},&H000000FF,{cfg.outline_color},&H80000000,{cfg.bold},0,0,0,100,100,1,0,1,{cfg.outline},{cfg.shadow},{cfg.alignment},20,20,{cfg.margin_v},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        # Generate dialogue events for each word in the group
        for group in word_groups:
            if not group:
                continue

            for active_idx, active_word in enumerate(group):
                start_str = self._format_ass_time(active_word.start)
                end_str = self._format_ass_time(active_word.end)

                if active_word.end <= active_word.start:
                    continue

                # Build line text where active_word has highlight color + scale pop
                phrase_parts = []
                for i, w in enumerate(group):
                    clean_text = w.word.replace('{', '').replace('}', '')
                    if i == active_idx:
                        # Active word: Highlight color + pop animation
                        phrase_parts.append(
                            f"{{\\c{cfg.highlight_color}\\fscx{pop_scale}\\fscy{pop_scale}\\b1}}{clean_text}{{\\r}}"
                        )
                    else:
                        # Inactive word: Primary color
                        phrase_parts.append(
                            f"{{\\c{cfg.primary_color}\\fscx100\\fscy100\\b1}}{clean_text}{{\\r}}"
                        )

                line_text = " ".join(phrase_parts)
                lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{line_text}")

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_ass_path)), exist_ok=True)
        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return os.path.abspath(output_ass_path)
