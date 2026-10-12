#!/usr/bin/env python3
"""
Intelligent Audio Scoring & SFX Selector for Pacing Editor
Integrates directly with asset-indexer to score and fetch optimal sound effects (Whooshes, Impacts, Risers)
and Background Music (BGM) based on scene dynamics and learned preferences ("Hỏi và Nhớ").
"""
import os
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Dynamically resolve asset-indexer directory
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
ASSET_INDEXER_DIR = SKILL_ROOT / "asset-indexer" / "scripts"
if str(ASSET_INDEXER_DIR) not in sys.path:
    sys.path.append(str(ASSET_INDEXER_DIR))

# Resolve local config for custom asset directories
LOCAL_CONFIG_PATH = SKILL_ROOT.parent / "config.local.json"
LOCAL_CFG = {}
if LOCAL_CONFIG_PATH.exists():
    try:
        with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as f:
            LOCAL_CFG = json.load(f)
    except Exception:
        pass

try:
    from search_engine import search_assets
except Exception:
    search_assets = None

def get_best_sfx(intent, category="SFX", max_duration=3.0):
    """
    Queries asset-indexer for the most suitable SFX file matching the intent.
    Falls back to direct filesystem search if indexer is unavailable.
    """
    if search_assets:
        try:
            results = search_assets(
                query=intent,
                category=category,
                media_type="audio",
                max_duration=max_duration,
                top_k=3
            )
            if results:
                best = results[0]["asset"]
                return {
                    "file_path": best["full_path"],
                    "duration": best.get("duration", 1.0),
                    "file_name": best["file_name"],
                    "source": "asset_index"
                }
        except Exception:
            pass

    # Fallback: scan custom SFX directory directly
    sfx_cand = LOCAL_CFG.get("asset_directories", {}).get("sfx_dir") or r"E:\Video Asset\SFX"
    sfx_root = Path(sfx_cand) if sfx_cand else None
    if sfx_root and sfx_root.exists():
        kw = intent.lower().split()[0]
        for f in sfx_root.rglob("*.mp3"):
            if kw in f.name.lower():
                return {
                    "file_path": str(f.resolve()).replace("\\", "/"),
                    "duration": 1.2,
                    "file_name": f.name,
                    "source": "filesystem_scan"
                }
        for f in sfx_root.rglob("*.wav"):
            if kw in f.name.lower():
                return {
                    "file_path": str(f.resolve()).replace("\\", "/"),
                    "duration": 1.0,
                    "file_name": f.name,
                    "source": "filesystem_scan"
                }

    return None

def get_best_bgm(mood="upbeat", max_duration=120.0):
    """
    Fetches Background Music for Audio Track A3.
    """
    if search_assets:
        try:
            results = search_assets(
                query=mood,
                category="Music",
                media_type="audio",
                min_duration=15.0,
                top_k=2
            )
            if results:
                best = results[0]["asset"]
                return {
                    "file_path": best["full_path"],
                    "duration": best.get("duration", 60.0),
                    "file_name": best["file_name"]
                }
        except Exception:
            pass

    # Fallback to custom Music folder
    music_cand = LOCAL_CFG.get("asset_directories", {}).get("bgm_dir") or r"E:\Video Asset\Music"
    music_root = Path(music_cand) if music_cand else None
    if music_root and music_root.exists():
        for f in music_root.rglob("*.*"):
            if f.suffix.lower() in [".mp3", ".wav", ".m4a"]:
                return {
                    "file_path": str(f.resolve()).replace("\\", "/"),
                    "duration": 60.0,
                    "file_name": f.name
                }
    return None
