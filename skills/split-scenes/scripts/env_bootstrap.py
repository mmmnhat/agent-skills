import sys
import os
import shutil
import subprocess
import importlib

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Mapping of module name to pip package name
REQUIRED_PACKAGES = {
    'cv2': 'opencv-python',
    'numpy': 'numpy',
    'scipy': 'scipy',
    'skimage': 'scikit-image',
    'librosa': 'librosa',
    'faster_whisper': 'faster-whisper',
    'yt_dlp': 'yt-dlp'
}

def ensure_package(module_name, pip_name=None):
    """Checks if a module is installed; if missing, automatically installs it via pip."""
    pip_name = pip_name or module_name
    try:
        importlib.import_module(module_name)
    except ImportError:
        print(f"📦 [split-scenes] Đang thiếu thư viện '{module_name}'. Tự động cài đặt '{pip_name}'...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name],
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            print(f"✅ [split-scenes] Cài đặt thành công '{pip_name}'!")
        except Exception as e:
            print(f"❌ [split-scenes] Lỗi khi cài đặt '{pip_name}': {e}")
            raise e

def ensure_cli(command_name):
    """Checks if a system CLI tool exists (e.g. ffmpeg); if missing on macOS, attempts brew install."""
    if not shutil.which(command_name):
        print(f"⚙️ [split-scenes] Đang thiếu công cụ hệ thống: '{command_name}'...")
        if sys.platform == 'darwin' and shutil.which('brew'):
            print(f"Tự động cài đặt '{command_name}' qua Homebrew...")
            try:
                subprocess.check_call(['brew', 'install', command_name])
                print(f"✅ Đã cài đặt xong '{command_name}'!")
            except Exception as e:
                print(f"❌ Không thể tự cài đặt '{command_name}': {e}")
        else:
            print(f"⚠️ Vui lòng cài đặt '{command_name}' vào PATH hệ thống.")

def auto_setup(skip_cli=False):
    """Automatically verify and install all required Python packages and CLI tools."""
    if not skip_cli:
        ensure_cli('ffmpeg')
        ensure_cli('ffprobe')
    for mod, pip_name in REQUIRED_PACKAGES.items():
        ensure_package(mod, pip_name)

# Run auto_setup immediately upon import
auto_setup()
