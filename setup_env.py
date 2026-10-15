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

def register_antigravity_skills(root_dir):
    log("\n[5/5] Registering Skills globally into Antigravity...")
    gemini_cfg_dir = Path(os.path.expanduser("~/.gemini/config"))
    skills_path = (root_dir / "skills").resolve()
    
    if not gemini_cfg_dir.exists():
        try:
            gemini_cfg_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log(f"  [!] Không thể tạo thư mục Antigravity config: {e}")
            return
        
    skills_json_file = gemini_cfg_dir / "skills.json"
    data = {"entries": []}
    if skills_json_file.exists():
        try:
            with open(skills_json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"entries": []}
            
    entries = data.get("entries", [])
    already_present = any(
        Path(e.get("path", "")).resolve() == skills_path 
        for e in entries if isinstance(e, dict) and "path" in e
    )
    
    if not already_present:
        entries.append({"path": str(skills_path)})
        data["entries"] = entries
        try:
            with open(skills_json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log(f"  ✓ Đã đăng ký skills vào {skills_json_file}")
            log(f"    -> Đường dẫn skills: {skills_path}")
        except Exception as e:
            log(f"  [!] Lỗi ghi file skills.json: {e}")
    else:
        log(f"  ✓ Skills đã được đăng ký từ trước trong: {skills_json_file}")

def sync_agent_rules(root_dir):
    agents_src = root_dir / "AGENTS.md"
    if not agents_src.exists():
        return
    try:
        content = agents_src.read_text(encoding="utf-8")
        # Sync to GEMINI.md
        (root_dir / "GEMINI.md").write_text(content, encoding="utf-8")
        # Sync to CLAUDE.md for Claude Code
        (root_dir / "CLAUDE.md").write_text(content, encoding="utf-8")
        # Sync to .cursorrules for Cursor AI
        (root_dir / ".cursorrules").write_text(content, encoding="utf-8")
        
        # Sync to Claude global directory (~/.claude/CLAUDE.md)
        claude_home = Path.home() / ".claude"
        if claude_home.exists():
            (claude_home / "CLAUDE.md").write_text(content, encoding="utf-8")
            log(f"  ✓ Đã đồng bộ CLAUDE.md toàn cục tại: {claude_home / 'CLAUDE.md'}")
            
            # Sync skills to ~/.claude/skills
            claude_skills = claude_home / "skills"
            claude_skills.mkdir(parents=True, exist_ok=True)
            src_skills = root_dir / "skills"
            if src_skills.exists():
                for s_dir in src_skills.iterdir():
                    if s_dir.is_dir() and not s_dir.name.startswith("."):
                        target_dir = claude_skills / s_dir.name
                        shutil.copytree(s_dir, target_dir, dirs_exist_ok=True)
                log(f"  ✓ Đã cài đặt VisionCut skills vào Claude: {claude_skills}")
        
        # Also copy to workspace root (parent of .agents)
        workspace_root = root_dir.parent
        if workspace_root.exists() and workspace_root != root_dir:
            (workspace_root / "CLAUDE.md").write_text(content, encoding="utf-8")
            (workspace_root / "AGENTS.md").write_text(content, encoding="utf-8")
    except Exception as e:
        log(f"  [!] Không thể đồng bộ tệp chỉ thị: {e}")

def main():
    log("=" * 70)
    log("🎬 ANTIGRAVITY VIDEO EDITORIAL SUITE — SETUP & ENVIRONMENT BOOTSTRAP")
    log("=" * 70)

    root_dir = Path(__file__).resolve().parent

    # Support command-line target installation
    target_install = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install-to" and len(sys.argv) > 2:
            target_install = Path(sys.argv[2]).resolve()
        elif sys.argv[1].startswith("--install-to="):
            target_install = Path(sys.argv[1].split("=", 1)[1]).resolve()

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

    out_cfg = root_dir / "config.local.json"
    with open(out_cfg, "w", encoding="utf-8") as f:
        json.dump(local_config, f, indent=2, ensure_ascii=False)

    register_antigravity_skills(root_dir)
    sync_agent_rules(root_dir)

    if target_install:
        log(f"\n[+] Đang cài đặt vào workspace: {target_install}...")
        target_agents = target_install / ".agents"
        target_agents.mkdir(parents=True, exist_ok=True)
        # Copy rule files and config
        for f_name in ["AGENTS.md", "GEMINI.md", "CLAUDE.md", ".cursorrules", "config.local.json"]:
            src = root_dir / f_name
            if src.exists():
                shutil.copy2(src, target_agents / f_name)
                # also place in target workspace root
                shutil.copy2(src, target_install / f_name)
        log(f"  ✓ Đã thiết lập chỉ thị AI Video Editor tại: {target_install}")

    log("\n" + "=" * 70)
    log("✅ THIẾT LẬP THÀNH CÔNG!")
    log(f"  • File cấu hình cục bộ đã lưu: {out_cfg}")
    log("  • File này đã được thêm vào .gitignore (an toàn, không bao giờ bị conflict khi git pull)")
    log("  • Chỉ thị AI (AGENTS.md, GEMINI.md, CLAUDE.md, .cursorrules) đã được đồng bộ.")
    log("  • Bây giờ bạn có thể mở Antigravity/Cursor/Claude Code và chat tự nhiên:")
    log("      \"Tách scene cho tôi video này: <đường_dẫn_video>\"")
    log("      \"Dựng sequence các clip theo W-Curve 30s\"")
    log("=" * 70)

if __name__ == "__main__":
    main()
