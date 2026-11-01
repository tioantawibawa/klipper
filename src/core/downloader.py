"""
YouTube / Web Video Downloader using yt-dlp.
Supports progress hooks, metadata extraction, and custom output directories.
"""

import os
import re
from typing import Callable, Optional, Dict, Any


class YouTubeDownloader:
    def __init__(self, output_dir: str = "downloads"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def get_info(self, url: str) -> Dict[str, Any]:
        """Fetch video information without downloading."""
        import yt_dlp

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Format duration as MM:SS or HH:MM:SS
            duration_sec = info.get('duration', 0) or 0
            m, s = divmod(int(duration_sec), 60)
            h, m = divmod(m, 60)
            duration_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

            return {
                "title": info.get('title', 'Unknown Title'),
                "duration": duration_sec,
                "duration_str": duration_str,
                "uploader": info.get('uploader', 'Unknown Channel'),
                "thumbnail": info.get('thumbnail', ''),
                "view_count": info.get('view_count', 0),
                "id": info.get('id', ''),
                "url": url,
            }

    def download(
        self,
        url: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        max_height: int = 1080
    ) -> str:
        """
        Download video from YouTube or supported platforms.
        
        Args:
            url: Video URL.
            progress_callback: Callback receiving (percentage [0.0 - 100.0], status_text).
            max_height: Max video resolution height (default 1080p).
            
        Returns:
            Absolute path to downloaded video file.
        """
        import yt_dlp

        self._cancelled = False

        def hook(d):
            if self._cancelled:
                raise Exception("Download cancelled by user.")
                
            status = d.get('status')
            if status == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded_bytes = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0) or 0
                eta = d.get('eta', 0) or 0
                
                percent = (downloaded_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
                
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed > 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                eta_str = f"{eta}s" if eta else "calculating..."
                status_text = f"Downloading: {percent:.1f}% ({speed_str}, ETA: {eta_str})"
                
                if progress_callback:
                    progress_callback(percent, status_text)
            elif status == 'finished':
                if progress_callback:
                    progress_callback(99.0, "Processing audio/video merge...")

        out_template = os.path.join(self.output_dir, "%(title).100s-%(id)s.%(ext)s")
        
        ydl_opts = {
            'format': f'bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best',
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'progress_hooks': [hook],
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if progress_callback:
                progress_callback(2.0, "Extracting video stream info...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Ensure mp4 extension if merged
            base, _ = os.path.splitext(filename)
            mp4_filename = f"{base}.mp4"
            final_path = mp4_filename if os.path.exists(mp4_filename) else filename
            
            if progress_callback:
                progress_callback(100.0, "Download completed.")
                
            return os.path.abspath(final_path)
