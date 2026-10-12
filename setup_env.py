#!/usr/bin/env python3
"""
Antigravity Video Editorial Suite — 1-Step Environment Bootstrap & Auto-Prober
Automatically tests system dependencies, probes the best GPU hardware encoder,
and generates your machine-specific config.local.json.
"""
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def log(msg):
    print(msg, flush=True)

def check_python():
    log("\n[1/4] Checking Python environment...")
    v = sys.version_info
    log(f"  • Python Version: {v.major}.{v.minor}.{v.micro}")
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        log("  [!] Warning: Python 3.10 or higher is recommended.")
    else:
        log("  ✓ Python version OK.")

def check_dependencies():
    log("\n[2/4] Checking required Python libraries...")
    required = ["cv2", "scenedetect", "numpy"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            log(f"  ✓ Library '{pkg}' is installed.")
        except ImportError:
            missing.append(pkg)
            log(f"  ✗ Library '{pkg}' is missing.")
            
    if missing:
        pip_pkgs = [p if p != "cv2" else "opencv-python" for p in missing]
        log(f"  -> Installing missing packages: {' '.join(pip_pkgs)}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *pip_pkgs])
            log("  ✓ All required libraries installed successfully.")
        except Exception as e:
            log(f"  [!] Failed to install libraries automatically: {e}")
            log(f"      Please run manually: pip install {' '.join(pip_pkgs)}")

def probe_hardware_encoder():
    log("\n[3/4] Auto-probing best Hardware Encoder for FFmpeg...")
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        for p in [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg"
        ]:
            if os.path.isfile(p):
                ffmpeg_bin = p
                break
                
    if not ffmpeg_bin:
        log("  [!] FFmpeg executable not found in PATH!")
        log("      Please install FFmpeg and add it to your system PATH.")
        return "libx264"

    log(f"  • FFmpeg found at: {ffmpeg_bin}")

    candidates = [
        ("h264_nvenc", "NVIDIA NVENC Hardware Acceleration"),
        ("h264_videotoolbox", "Apple Silicon VideoToolbox Hardware Acceleration"),
        ("h264_qsv", "Intel QuickSync Video Hardware Acceleration"),
        ("h264_amf", "AMD AMF Hardware Acceleration"),
        ("libx264", "Universal CPU Software Encoder (Fallback)")
    ]

    detected_encoder = "libx264"
    for enc, desc in candidates:
        test_cmd = [
            ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=black:s=160x90:d=0.1",
            "-c:v", enc, "-f", "null", "-"
        ]
        try:
            res = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                detected_encoder = enc
                log(f"  ✓ Confirmed encoder: {enc} ({desc})")
                break
        except Exception:
            continue

    return detected_encoder

def configure_asset_paths():
    log("\n[4/4] Configuring Asset Folders (SFX / Music)...")
    log("  (Mỗi editor có cách tổ chức kho riêng. Bạn có thể dán đường dẫn thư mục của bạn)")
    log("  (Nếu chưa có hoặc muốn cấu hình sau, chỉ cần nhấn Enter để bỏ qua)")

    default_sfx = "E:/Video Asset/SFX" if os.path.exists("E:/Video Asset/SFX") else ""
    default_bgm = "E:/Video Asset/Music" if os.path.exists("E:/Video Asset/Music") else ""

    try:
        sfx_in = input(f"  • Thư mục SFX [mặc định: {default_sfx}]: ").strip()
        sfx_path = sfx_in if sfx_in else default_sfx

        bgm_in = input(f"  • Thư mục BGM / Nhạc nền [mặc định: {default_bgm}]: ").strip()
        bgm_path = bgm_in if bgm_in else default_bgm
    except EOFError:
        sfx_path = default_sfx
        bgm_path = default_bgm

    return sfx_path.replace("\\", "/"), bgm_path.replace("\\", "/")

def main():
    log("=" * 70)
    log("🎬 ANTIGRAVITY VIDEO EDITORIAL SUITE — SETUP & ENVIRONMENT BOOTSTRAP")
    log("=" * 70)

    check_python()
    check_dependencies()
    encoder = probe_hardware_encoder()
    sfx_dir, bgm_dir = configure_asset_paths()

    local_config = {
        "hardware": {
            "encoder": encoder,
            "probed_at": os.environ.get("COMPUTERNAME", "localhost")
        },
        "asset_directories": {
            "sfx_dir": sfx_dir,
            "bgm_dir": bgm_dir
        },
        "target_platforms": {
            "reels_shorts": {
                "aspect_ratio": "9:16",
                "resolution": [1080, 1920],
                "fps": 60,
                "max_clip_duration_sec": 4.5
            },
            "landscape_youtube": {
                "aspect_ratio": "16:9",
                "resolution": [1920, 1080],
                "fps": 60,
                "max_clip_duration_sec": 8.0
            }
        },
        "audio_layout": {
            "tracks": {
                "V1": "Video Clips",
                "A1": "Original Ambient Sound",
                "A2": "Voiceover (Reserved Blank)",
                "A3": "Transition SFX (Whoosh)",
                "A4": "Climax SFX (Impact / Punch)",
                "A5": "Background Music (Ducked BGM)"
            }
        }
    }

    root_dir = Path(__file__).resolve().parent
    out_cfg = root_dir / "config.local.json"
    with open(out_cfg, "w", encoding="utf-8") as f:
        json.dump(local_config, f, indent=2, ensure_ascii=False)

    log("\n" + "=" * 70)
    log("✅ THIẾT LẬP THÀNH CÔNG!")
    log(f"  • File cấu hình cục bộ đã lưu: {out_cfg}")
    log("  • File này đã được thêm vào .gitignore (an toàn, không bao giờ bị conflict khi git pull)")
    log("  • Bây giờ bạn có thể mở Antigravity và chat tự nhiên:")
    log("      \"Tách scene cho tôi video này: <đường_dẫn_video>\"")
    log("      \"Dựng sequence các clip theo W-Curve 30s\"")
    log("=" * 70)

if __name__ == "__main__":
    main()
