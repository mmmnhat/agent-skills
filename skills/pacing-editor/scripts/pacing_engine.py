#!/usr/bin/env python3
"""
Pacing & Speed Ramping Engine
Analyzes scenes, computes dynamic retention curves, allocates timeline slots on Track V1,
and coordinates automated sound design (SFX on A2, BGM on A3).
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from sfx_scoring import get_best_sfx, get_best_bgm
except ImportError:
    from .sfx_scoring import get_best_sfx, get_best_bgm

def load_config():
    cfg_file = Path(__file__).resolve().parent.parent / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

CONFIG = load_config()

def generate_pacing_plan(scenes_input, sequence_name="Pacing_Master", platform="reels_shorts", add_sfx=True, add_bgm=True):
    """
    Constructs a full timeline manifest from scenes_context.json or list of clips.
    """
    platform_cfg = CONFIG.get("target_platforms", {}).get(platform, {
        "aspect_ratio": "9:16",
        "resolution": [1080, 1920],
        "fps": 60,
        "max_clip_duration_sec": 4.5,
        "speed_ramp_climax": 0.5
    })

    scenes = []
    if isinstance(scenes_input, (str, Path)):
        p = Path(scenes_input).resolve()
        if p.is_file() and p.suffix.lower() == ".json":
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                scenes = data.get("scenes", [])
        elif p.is_dir():
            for f in sorted(p.glob("*.mp4")):
                scenes.append({"clip_path": str(f).replace("\\", "/"), "scene_id": f.stem, "duration_sec": 4.0})
    elif isinstance(scenes_input, list):
        scenes = scenes_input

    if not scenes:
        raise ValueError("No valid scenes provided to pacing engine.")

    v1_track = []
    a2_track = []
    a3_track = []

    current_timeline_time = 0.0

    # Cache transition SFX and Climax SFX
    whoosh_asset = get_best_sfx(CONFIG.get("sound_design", {}).get("transition_sfx_intent", "whoosh chuyen canh"))
    impact_asset = get_best_sfx(CONFIG.get("sound_design", {}).get("climax_sfx_intent", "impact boom"))

    for i, sc in enumerate(scenes):
        clip_path = sc.get("clip_path") or sc.get("file_path")
        if not clip_path or not os.path.exists(clip_path):
            continue

        raw_dur = float(sc.get("duration") or sc.get("duration_sec") or 3.0)
        max_dur = platform_cfg.get("max_clip_duration_sec", 4.5)
        # Cap duration for maximum short-form retention
        source_in = 0.0
        source_out = min(raw_dur, max_dur)
        effective_dur = source_out - source_in

        # Determine motion landmarks
        landmarks = sc.get("temporal_landmarks") or sc.get("motion_landmarks") or {}
        climax_rel = float(landmarks.get("action_peak_rel_sec") or landmarks.get("climax_sec") or (effective_dur * 0.55))
        
        # Calculate speed ramping
        climax_speed = platform_cfg.get("speed_ramp_climax", 0.5)
        speed_curve = [
            {"phase": "lead_in", "speed": 1.0, "duration_sec": round(climax_rel * 0.7, 2)},
            {"phase": "climax", "speed": climax_speed, "duration_sec": round(climax_rel * 0.3 + 0.4, 2)},
            {"phase": "recovery", "speed": 1.5, "duration_sec": round(max(0.2, effective_dur - climax_rel - 0.4), 2)}
        ]

        clip_timeline_in = current_timeline_time
        # Duration on timeline with ramping approximation
        timeline_clip_dur = round(effective_dur, 3)
        clip_timeline_out = round(clip_timeline_in + timeline_clip_dur, 3)
        climax_timeline_time = round(clip_timeline_in + climax_rel, 3)

        v1_track.append({
            "clip_id": sc.get("scene_id", f"scene_{i+1:03d}"),
            "file_path": clip_path,
            "timeline_in": clip_timeline_in,
            "timeline_out": clip_timeline_out,
            "source_in": source_in,
            "source_out": source_out,
            "speed_curve": speed_curve,
            "optical_flow": True,
            "climax_marker": climax_timeline_time
        })

        # Add Audio Effects (A2)
        if add_sfx:
            # 1. Transition Whoosh at edit cut (for all clips except very first)
            if i > 0 and whoosh_asset:
                a2_track.append({
                    "sfx_id": f"whoosh_cut_{i:03d}",
                    "file_path": whoosh_asset["file_path"],
                    "role": "transition",
                    "timeline_in": max(0.0, clip_timeline_in - 0.25),
                    "volume_db": CONFIG.get("sound_design", {}).get("default_volumes", {}).get("sfx_db", -2.0)
                })

            # 2. Climax Impact at action peak
            if impact_asset:
                a2_track.append({
                    "sfx_id": f"impact_climax_{i:03d}",
                    "file_path": impact_asset["file_path"],
                    "role": "climax_impact",
                    "timeline_in": climax_timeline_time,
                    "volume_db": CONFIG.get("sound_design", {}).get("default_volumes", {}).get("sfx_db", -2.0)
                })

        current_timeline_time = clip_timeline_out

    # Add Background Music (A3)
    if add_bgm and current_timeline_time > 0.0:
        bgm_asset = get_best_bgm()
        if bgm_asset:
            a3_track.append({
                "bgm_id": "master_bgm",
                "file_path": bgm_asset["file_path"],
                "timeline_in": 0.0,
                "timeline_out": round(current_timeline_time, 3),
                "ducked": True
            })

    manifest = {
        "sequence_name": sequence_name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": {
            "aspect_ratio": platform_cfg.get("aspect_ratio", "9:16"),
            "resolution": platform_cfg.get("resolution", [1080, 1920]),
            "fps": platform_cfg.get("fps", 60)
        },
        "total_duration_seconds": round(current_timeline_time, 3),
        "total_scenes": len(v1_track),
        "tracks": {
            "V1": v1_track,
            "A2": a2_track,
            "A3": a3_track
        }
    }
    return manifest
