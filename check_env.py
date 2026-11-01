"""
System & Environment Verification for OpenClip.
Checks Python version, FFmpeg availability, hardware acceleration (NVENC, QuickSync, AMF),
and GPU acceleration for faster-whisper / OpenCV.
"""

import os
import shutil
import subprocess
import sys
from typing import Dict, Any


def check_python() -> Dict[str, Any]:
    version = sys.version_info
    valid = version.major == 3 and version.minor >= 10
    return {
        "status": valid,
        "version": f"{version.major}.{version.minor}.{version.micro}",
        "message": "Python >= 3.10 is required" if not valid else "Python version is compatible"
    }


def check_ffmpeg() -> Dict[str, Any]:
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    
    if not ffmpeg_path:
        return {
            "status": False,
            "path": None,
            "version": None,
            "message": "FFmpeg not found in system PATH. Please install FFmpeg and add to PATH."
        }
    
    try:
        proc = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, check=True)
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "FFmpeg installed"
        
        # Probe which encoder actually works with current hardware and driver
        candidate_encoders = [
            ("h264_nvenc", "NVIDIA NVENC (GPU Accelerated)"),
            ("h264_qsv", "Intel QuickSync (GPU Accelerated)"),
            ("h264_amf", "AMD AMF (GPU Accelerated)"),
            ("h264_mf", "Windows Media Foundation (GPU/HW)"),
            ("libx264", "CPU Multi-threaded (libx264)")
        ]
        best_hw = "libx264"
        hw_desc = "CPU Multi-threaded (libx264)"

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        for enc, desc in candidate_encoders:
            try:
                test_cmd = [
                    ffmpeg_path, "-y",
                    "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
                    "-c:v", enc,
                    "-f", "null", "-"
                ]
                test_p = subprocess.run(
                    test_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    timeout=3
                )
                if test_p.returncode == 0:
                    best_hw = enc
                    hw_desc = desc
                    break
            except Exception:
                continue

        return {
            "status": True,
            "path": ffmpeg_path,
            "ffprobe_path": ffprobe_path,
            "version": first_line,
            "recommended_encoder": best_hw,
            "recommended_encoder_desc": hw_desc
        }
    except Exception as e:
        return {
            "status": False,
            "path": ffmpeg_path,
            "message": f"FFmpeg error: {e}"
        }


def check_gpu() -> Dict[str, Any]:
    cuda_available = False
    device_name = "CPU Only"

    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            cuda_available = True
            device_name = f"CUDA ({ctranslate2.get_cuda_device_count()} GPU detected)"
    except Exception:
        pass
    
    try:
        import torch
        if torch.cuda.is_available():
            cuda_available = True
            device_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
        
    return {
        "cuda_available": cuda_available,
        "device_name": device_name
    }


def run_full_check() -> Dict[str, Any]:
    py_info = check_python()
    ffmpeg_info = check_ffmpeg()
    gpu_info = check_gpu()
    
    overall_ok = py_info["status"] and ffmpeg_info["status"]
    
    return {
        "overall_ok": overall_ok,
        "python": py_info,
        "ffmpeg": ffmpeg_info,
        "gpu": gpu_info
    }


if __name__ == "__main__":
    report = run_full_check()
    print("=" * 60)
    print("           OPENCLIP - ENVIRONMENT VERIFICATION")
    print("=" * 60)
    print(f"Python: {report['python']['version']} -> {'OK' if report['python']['status'] else 'FAIL'}")
    if report["ffmpeg"]["status"]:
        print(f"FFmpeg: {report['ffmpeg']['version']}")
        print(f"Hardware Encoder: {report['ffmpeg']['recommended_encoder_desc']}")
    else:
        print(f"FFmpeg: NOT FOUND! ({report['ffmpeg'].get('message')})")
    print(f"AI Acceleration: {report['gpu']['device_name']} (CUDA: {report['gpu']['cuda_available']})")
    print("=" * 60)
    if report["overall_ok"]:
        print("Ready for OpenClip processing!")
    else:
        print("Warning: Some required dependencies are missing.")
