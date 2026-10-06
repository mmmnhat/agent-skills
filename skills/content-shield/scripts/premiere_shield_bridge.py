#!/usr/bin/env python3
"""
Premiere Pro MCP Bridge for Content Shield
Generates timeline instructions and executes MCP calls to create Adjustment Layers on track V2,
applying Gaussian Blur / Fast Blur / Mosaic with Crop boundaries or moving Keyframes.
"""
import os
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def generate_premiere_plan(shield_manifest):
    """
    Translates a ContentShieldManifest into a concrete sequence of Premiere Pro MCP calls.
    """
    source_file = shield_manifest["source_file"]
    video_w = shield_manifest["video_dimensions"]["width"]
    video_h = shield_manifest["video_dimensions"]["height"]
    jobs = shield_manifest.get("shield_jobs", [])

    timeline_steps = []

    for job in jobs:
        box = job["initial_box"]
        x, y, w, h = box
        mode = job["mode"]
        is_static = job.get("is_static", True)
        target_track = job.get("premiere_bridge", {}).get("target_track", "V2")

        # Convert box [x,y,w,h] to Crop percentages (Left, Top, Right, Bottom)
        left_pct = round((x / video_w) * 100.0, 2)
        top_pct = round((y / video_h) * 100.0, 2)
        right_pct = round(((video_w - (x + w)) / video_w) * 100.0, 2)
        bottom_pct = round(((video_h - (y + h)) / video_h) * 100.0, 2)

        effect_name = "Gaussian Blur"
        if mode == "mosaic":
            effect_name = "Mosaic"

        step = {
            "job_id": job["job_id"],
            "target_track": target_track,
            "crop_percentages": {
                "left": left_pct,
                "top": top_pct,
                "right": right_pct,
                "bottom": bottom_pct,
                "edge_feather": 10.0
            },
            "effect_to_apply": effect_name,
            "effect_properties": {
                "Blurriness": 35.0 if effect_name == "Gaussian Blur" else 20.0
            },
            "mcp_actions": [
                {
                    "action": "add_adjustment_layer",
                    "params": {"track_index": 1} # V2 is track index 1
                },
                {
                    "action": "crop_clip",
                    "params": {
                        "left": left_pct,
                        "top": top_pct,
                        "right": right_pct,
                        "bottom": bottom_pct,
                        "edge_feather": 10.0
                    }
                },
                {
                    "action": "apply_effect",
                    "params": {"effect_name": effect_name}
                }
            ]
        }

        # If dynamic trajectory with multiple keyframes, add keyframe instructions
        trajectory = job.get("keyframe_trajectory", [])
        if not is_static and len(trajectory) > 2:
            keyframe_steps = []
            for kf in trajectory:
                kx, ky, kw, kh = kf["box"]
                t_sec = kf["time_sec"]
                kf_left = round((kx / video_w) * 100.0, 2)
                kf_top = round((ky / video_h) * 100.0, 2)
                keyframe_steps.append({
                    "time_seconds": t_sec,
                    "crop_left": kf_left,
                    "crop_top": kf_top
                })
            step["motion_keyframes"] = keyframe_steps

        timeline_steps.append(step)

    return {
        "source_file": source_file,
        "premiere_bridge_steps": timeline_steps
    }

def save_premiere_plan(shield_manifest, output_json_path):
    plan = generate_premiere_plan(shield_manifest)
    out_p = Path(output_json_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return str(out_p)
