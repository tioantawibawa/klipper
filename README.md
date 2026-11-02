# OpenClip - 100% Local AI Short Video Clipper

**OpenClip** adalah aplikasi desktop modern (Windows & macOS) alternatif dari *KlipDong Desktop*. Aplikasi ini memotong video panjang berformat horizontal (16:9) menjadi video pendek vertikal (9:16) berdurasi 30–60 detik yang dioptimalkan untuk **TikTok, Instagram Reels, dan YouTube Shorts** secara **100% lokal** di laptop pengguna tanpa memerlukan API cloud berbayar.

---

## Fitur Utama

1. **Dual Input Source**:
   - **Video Lokal**: Drag & drop file video (`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`).
   - **YouTube Downloader**: Masukkan tautan YouTube, periksa info video (thumbnail, judul, durasi), dan unduh otomatis dengan `yt-dlp`.
2. **AI Audio Transcription (Local Whisper)**:
   - Ekstraksi audio mono 16kHz via FFmpeg.
   - Menggunakan `faster-whisper` (model: `base`, `small`, atau `tiny`) dengan komputasi `int8` (CPU) atau `float16` (CUDA).
   - Menghasilkan timestamp per kata (*word-level timestamps*).
3. **Smart Moment Detection (Algoritma Momen Viral)**:
   - Menganalisis kepadatan bicara (*speech density*), ritme kata (*words per minute*), energi suara (RMS audio), dan jeda hening (*silence penalty*).
   - Memilih 1–5 cuplikan paling menarik berdurasi 30–60 detik dengan pemotongan batas kalimat yang rapi (tidak memotong kata di tengah jalan).
4. **Auto-Framing 9:16 (Speaker Tracking)**:
   - Deteksi wajah pembicara menggunakan OpenCV dan MediaPipe.
   - Perekaman trajektori wajah dengan algoritma *Exponential Moving Average (EMA)* dan *deadband margin* agar gerakan kamera vertikal 9:16 mulus dan tidak berguncang (*smooth panning*).
5. **Animated Captions Engine (ASS)**:
   - Pembuatan subtitle Advanced SubStation Alpha (`.ass`) bergaya video viral (KlipDong / Alex Hormozi style).
   - Animasi pop-up dan sorotan warna kata aktif (*per-word karaoke highlighting*).
   - Template gaya teks:
     - **Bold Yellow**: Kuning terang pop-up dengan border hitam tebal.
     - **Green Highlight**: Hijau neon ala video storytelling viral.
     - **Clean White**: Teks putih bersih minimalis modern.
     - **Flame Orange**: Oranye api berdaya tarik tinggi.
6. **Ekspor & Render Berakselerasi**:
   - Deteksi otomatis encoder hardware: **NVIDIA NVENC** (`h264_nvenc`), **Intel QuickSync** (`h264_qsv`), **AMD AMF** (`h264_amf`), atau fallback multi-threaded CPU (`libx264`).
   - Scaling otomatis ke standar vertikal 1080x1920 Full HD.
7. **Antarmuka Pengguna Modern & Asinkron**:
   - Dibuat dengan PyQt6 dalam tema gelap (*Dark Theme*) elegan.
   - Arsitektur `QThread` multi-threading menjamin UI tidak pernah freeze saat AI sedang melakukan inferensi atau rendering.
   - Progress bar, log konsol real-time dengan status badge berwarna, dan pemutar preview video internal.

---

## Struktur Proyek

```
OpenClip/
├── requirements.txt            # Dependensi Python
├── check_env.py                # Verifikasi kesiapan sistem & hardware encoder
├── main.py                     # Entry point aplikasi GUI desktop
├── run_openclip.bat            # Launcher 1-klik untuk Windows
├── src/
│   ├── __init__.py
│   ├── pipeline.py             # Koordinator pipeline end-to-end
│   ├── core/
│   │   ├── __init__.py
│   │   ├── downloader.py       # Wrapper yt-dlp & metadata extraction
│   │   ├── audio_extractor.py  # Ekstraktor audio WAV 16kHz via FFmpeg
│   │   ├── transcriber.py      # faster-whisper dengan word-level timestamps
│   │   ├── moment_detector.py  # Algoritma analisis kepadatan bicara & durasi 30-60s
│   │   ├── face_tracker.py     # 9:16 Auto-framing & smooth face tracking
│   │   ├── subtitle_generator.py # Generator ASS subtitle dengan word highlighting
│   │   └── video_editor.py     # Engine render video FFmpeg (NVENC/QSV/CPU)
│   └── ui/
│       ├── __init__.py
│       ├── theme.py            # Dark theme stylesheet (QSS)
│       ├── components/
│       │   ├── __init__.py
│       │   ├── drop_zone.py    # Widget drag & drop video lokal
│       │   ├── video_player.py # Pemutar video preview internal PyQt6
│       │   └── log_viewer.py   # Console log berwarna & auto-scroll
│       └── main_window.py      # Jendela dashboard utama PyQt6
├── tests/
│   └── test_pipeline.py        # Pengujian integrasi otomatis
└── outputs/                    # Folder penyimpanan klip vertikal 9:16
```

---

## Cara Menjalankan

### 1. Di Laptop Baru / Lain (Clone dari GitHub)
```bash
# 1. Clone repository
git clone https://github.com/tioantawibawa/klipper.git
cd klipper

# 2. Buat virtual environment (Direkomendasikan Python 3.11)
# Windows:
py -3.11 -m venv venv
.\venv\Scripts\activate

# macOS / Linux:
# python3 -m venv venv
# source venv/bin/activate

# 3. Install seluruh dependensi
pip install -r requirements.txt

# 4. Pastikan FFmpeg terpasang di sistem PATH
# Windows: winget install Gyan.FFmpeg
# macOS:   brew install ffmpeg
# Linux:   sudo apt install ffmpeg

# 5. Jalankan aplikasi
python main.py
# (Atau klik ganda run_openclip.bat di Windows)
```

---

## 2. Verifikasi Kesiapan Sistem
Jalankan verifikasi sistem untuk mendeteksi ketersediaan FFmpeg dan akselerasi GPU:
```bash
python check_env.py
```

---

## 3. Hasil Pengujian Pipeline
Pengujian otomatis end-to-end telah dijalankan melalui `tests/test_pipeline.py`:
- [x] Ekstraksi audio mono 16kHz berhasil.
- [x] Generator subtitle ASS membuat event kata aktif per centisecond (`\c&H0000E6FF\fscx115\fscy115`).
- [x] Algoritma 9:16 auto-framing menghitung koordinat pangkas dinamis.
- [x] Render FFmpeg menghasilkan video vertikal berukuran tepat **1080x1920 (9:16)** dengan subtitle menyatu (*burned-in*).
