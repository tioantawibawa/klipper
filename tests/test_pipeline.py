"""
End-to-End Pipeline Verification Test for OpenClip.
Tests:
1. Audio extraction (16kHz WAV).
2. Word-level subtitle generation (.ass with pop-up & per-word colors).
3. 9:16 Face tracking crop calculation.
4. Video rendering with 9:16 crop & subtitle burning.
"""

import os
import sys
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.audio_extractor import AudioExtractor
from src.core.transcriber import WordTimestamp, TranscriptionSegment, TranscriptionResult
from src.core.moment_detector import MomentDetector, MomentClip
from src.core.face_tracker import FaceTracker
from src.core.subtitle_generator import SubtitleGenerator, SubtitleStyle
from src.core.video_editor import VideoEditor, RenderConfig


def generate_synthetic_video(output_mp4: str, duration: int = 15):
    """Generate a clean synthetic 16:9 test video using FFmpeg."""
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    
    # Generate test video with bouncing ball / moving shape to simulate movement
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        f"-i", f"testsrc=duration={duration}:size=1280x720:rate=30",
        "-f", "lavfi",
        f"-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        output_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print(f"[TEST] Synthetic test video generated: {output_mp4}")


def run_test():
    test_dir = os.path.join(os.path.dirname(__file__), "output_test")
    os.makedirs(test_dir, exist_ok=True)
    
    sample_video = os.path.join(test_dir, "sample_input.mp4")
    generate_synthetic_video(sample_video, duration=15)

    print("\n--- 1. Testing Audio Extractor ---")
    extractor = AudioExtractor()
    wav_path = os.path.join(test_dir, "sample_audio.wav")
    extractor.extract_wav(sample_video, output_wav_path=wav_path)
    assert os.path.exists(wav_path), "WAV extraction failed"
    print(f"Audio extracted successfully: {wav_path} ({os.path.getsize(wav_path)} bytes)")

    print("\n--- 2. Testing Subtitle Generator (Animated ASS) ---")
    sub_gen = SubtitleGenerator(
        style=SubtitleStyle.BOLD_YELLOW,
        words_per_group=3,
        canvas_width=1080,
        canvas_height=1920
    )
    
    # Simulate realistic word timestamps (like speech)
    mock_words = [
        WordTimestamp("RAHASIA", 1.0, 1.5),
        WordTimestamp("MEMBUAT", 1.5, 2.0),
        WordTimestamp("VIDEO", 2.0, 2.5),
        WordTimestamp("VIRAL", 2.5, 3.2),
        WordTimestamp("DENGAN", 3.5, 3.9),
        WordTimestamp("OPENCLIP", 4.0, 4.8),
        WordTimestamp("100%", 5.0, 5.5),
        WordTimestamp("LOKAL", 5.5, 6.2),
        WordTimestamp("DAN", 6.5, 6.8),
        WordTimestamp("GRATIS!", 6.9, 7.8),
    ]

    ass_path = os.path.join(test_dir, "test_captions.ass")
    sub_gen.generate_ass(mock_words, ass_path, time_offset=0.0)
    assert os.path.exists(ass_path), "ASS generation failed"
    print(f"ASS Subtitle file created: {ass_path}")

    with open(ass_path, "r", encoding="utf-8") as f:
        ass_content = f.read()
    print("Sample generated ASS events:")
    for line in ass_content.splitlines():
        if line.startswith("Dialogue:"):
            print("  ", line)

    print("\n--- 3. Testing Face Tracker & 9:16 Auto-Framing ---")
    tracker = FaceTracker()
    crop_w, crop_h, crop_x, crop_y, trajectory = tracker.track_clip(
        sample_video,
        start_time=1.0,
        end_time=8.0,
        sample_interval=0.5
    )
    print(f"Computed 9:16 Crop: {crop_w}x{crop_h} at (x={crop_x}, y={crop_y})")
    assert crop_w > 0 and crop_h > 0, "Invalid crop dimensions"

    print("\n--- 4. Testing Video Editor & FFmpeg Render ---")
    editor = VideoEditor()
    rendered_output = os.path.join(test_dir, "rendered_short_916.mp4")
    
    # Render with CPU or auto-detected encoder
    render_cfg = RenderConfig(
        output_dir=test_dir,
        encoder="libx264",  # Safe for test environment
        scale_to_1080p=True,
        burn_subtitles=True
    )

    def on_render_progress(pct, msg):
        print(f"  [Render] {pct:.1f}% -> {msg}")

    final_clip = editor.render_short_clip(
        video_path=sample_video,
        start_time=1.0,
        duration=7.0,
        crop_w=crop_w,
        crop_h=crop_h,
        crop_x=crop_x,
        crop_y=crop_y,
        ass_subtitles_path=ass_path,
        output_filename=rendered_output,
        config=render_cfg,
        progress_callback=on_render_progress
    )

    assert os.path.exists(final_clip), "Render output does not exist"
    out_size = os.path.getsize(final_clip)
    print(f"\n[SUCCESS] Final 9:16 Short Video Rendered: {final_clip} ({out_size / 1024:.1f} KB)")
    
    # Check resolution with ffprobe or opencv
    import cv2
    cap = cv2.VideoCapture(final_clip)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    print(f"Video Dimensions: {fw}x{fh} (Aspect Ratio: {fw/fh:.3f} ~= 9:16 = 0.5625) @ {fps:.1f} fps")
    assert fw == 1080 and fh == 1920, f"Expected 1080x1920, got {fw}x{fh}"
    print("[ALL TESTS PASSED] OpenClip processing pipeline verified successfully!")


if __name__ == "__main__":
    run_test()
