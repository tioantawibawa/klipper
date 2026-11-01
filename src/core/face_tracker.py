"""
Face Tracker & Dynamic 9:16 Auto-Framing Engine.
Uses OpenCV and MediaPipe to detect speaker faces and generate smooth 9:16 vertical crop coordinates.
"""

import os
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable


@dataclass
class CropRegion:
    x: int
    y: int
    width: int
    height: int
    timestamp: float


class FaceTracker:
    def __init__(
        self,
        target_aspect_ratio: float = 9.0 / 16.0,
        smoothing_factor: float = 0.15,
        deadband_ratio: float = 0.05
    ):
        """
        Args:
            target_aspect_ratio: 9/16 for vertical shorts.
            smoothing_factor: EMA smoothing factor (0.05 = very slow pan, 0.3 = fast pan).
            deadband_ratio: Margin of motion before panning kicks in.
        """
        self.target_aspect_ratio = target_aspect_ratio
        self.smoothing_factor = smoothing_factor
        self.deadband_ratio = deadband_ratio
        self._face_cascade = None

    def _get_haar_cascade(self):
        import cv2
        if self._face_cascade is None:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(cascade_path):
                self._face_cascade = cv2.CascadeClassifier(cascade_path)
        return self._face_cascade

    def detect_face_in_frame(self, frame_bgr, mp_detector=None) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect the primary speaker's face bounding box (x, y, w, h).
        Uses MediaPipe if available, falls back to OpenCV Haar Cascade.
        """
        import cv2

        h, w = frame_bgr.shape[:2]

        # 1. Try MediaPipe Face Detection
        if mp_detector is not None:
            try:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                results = mp_detector.process(frame_rgb)
                if results and results.detections:
                    # Pick detection with largest bounding box
                    best_box = None
                    max_area = 0
                    for det in results.detections:
                        bbox = det.location_data.relative_bounding_box
                        bx = int(bbox.xmin * w)
                        by = int(bbox.ymin * h)
                        bw = int(bbox.width * w)
                        bh = int(bbox.height * h)
                        area = bw * bh
                        if area > max_area:
                            max_area = area
                            best_box = (bx, by, bw, bh)
                    if best_box:
                        return best_box
            except Exception:
                pass

        # 2. Fallback to OpenCV Haar Cascade
        cascade = self._get_haar_cascade()
        if cascade is not None:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(faces) > 0:
                # Return largest face
                faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                return tuple(faces[0])

        return None

    def calculate_crop_dimensions(self, orig_w: int, orig_h: int) -> Tuple[int, int]:
        """Compute target 9:16 crop width and height (both even numbers)."""
        target_h = orig_h
        target_w = int(round(target_h * self.target_aspect_ratio))
        # Ensure even numbers
        if target_w % 2 != 0:
            target_w += 1
        if target_h % 2 != 0:
            target_h -= 1
        
        # In case video is already narrower than 9:16
        if target_w > orig_w:
            target_w = orig_w - (orig_w % 2)
            target_h = int(round(target_w / self.target_aspect_ratio))
            if target_h % 2 != 0:
                target_h -= 1

        return target_w, target_h

    def track_clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        sample_interval: float = 0.25,  # Sample every 250ms for high speed
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[int, int, int, int, List[CropRegion]]:
        """
        Analyze speaker position during the clip interval [start_time, end_time].
        
        Returns:
            (crop_w, crop_h, representative_x, representative_y, trajectory)
        """
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        crop_w, crop_h = self.calculate_crop_dimensions(orig_w, orig_h)
        default_x = max(0, (orig_w - crop_w) // 2)
        default_y = max(0, (orig_h - crop_h) // 2)

        # Initialize MediaPipe detector if possible
        mp_detector = None
        try:
            import mediapipe as mp
            if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_detection'):
                mp_detector = mp.solutions.face_detection.FaceDetection(
                    model_selection=1,  # 1 for full-range / distance
                    min_detection_confidence=0.5
                )
        except Exception:
            pass

        start_frame = int(start_time * fps)
        end_frame = min(total_frames, int(end_time * fps))
        step_frames = max(1, int(sample_interval * fps))

        trajectory: List[CropRegion] = []
        smoothed_center_x = float(default_x + crop_w / 2.0)
        deadband_px = orig_w * self.deadband_ratio

        current_frame = start_frame
        while current_frame <= end_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            t = current_frame / fps
            face = self.detect_face_in_frame(frame, mp_detector)

            if face is not None:
                fx, fy, fw, fh = face
                target_center_x = fx + fw / 2.0
            else:
                target_center_x = smoothed_center_x

            # Apply deadband & Exponential Moving Average (EMA)
            delta = target_center_x - smoothed_center_x
            if abs(delta) > deadband_px:
                smoothed_center_x += self.smoothing_factor * delta

            # Clamp crop window within frame boundaries
            crop_x = int(round(smoothed_center_x - crop_w / 2.0))
            crop_x = max(0, min(orig_w - crop_w, crop_x))
            # Ensure crop_x is even for ffmpeg
            if crop_x % 2 != 0:
                crop_x = max(0, crop_x - 1)

            trajectory.append(CropRegion(
                x=crop_x,
                y=default_y,
                width=crop_w,
                height=crop_h,
                timestamp=t
            ))

            current_frame += step_frames
            if progress_callback and (end_frame > start_frame):
                pct = min(100.0, ((current_frame - start_frame) / (end_frame - start_frame)) * 100.0)
                progress_callback(pct, f"Face tracking 9:16: {t - start_time:.1f}s / {end_time - start_time:.1f}s")

        cap.release()
        if mp_detector and hasattr(mp_detector, 'close'):
            mp_detector.close()

        # If trajectory is empty, fallback to center
        if not trajectory:
            trajectory.append(CropRegion(
                x=default_x,
                y=default_y,
                width=crop_w,
                height=crop_h,
                timestamp=start_time
            ))

        # Calculate representative / median crop_x for stable framing
        avg_x = int(round(sum(r.x for r in trajectory) / len(trajectory)))
        avg_x = max(0, min(orig_w - crop_w, avg_x))
        if avg_x % 2 != 0:
            avg_x = max(0, avg_x - 1)

        return crop_w, crop_h, avg_x, default_y, trajectory
