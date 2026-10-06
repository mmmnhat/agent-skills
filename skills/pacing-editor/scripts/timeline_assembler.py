#!/usr/bin/env python3
"""
Timeline Assembler & Dispatcher
Executes timeline generation either via Premiere Pro MCP Tool Calls or Headless FFmpeg NVENC Render.
"""
import os
import sys
import json
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def generate_premiere_mcp_actions(pacing_manifest):
    """
    Generates a structured list of Premiere Pro MCP calls corresponding to the pacing manifest.
    """
    seq_name = pacing_manifest["sequence_name"]
    actions = [
        {
            "step": 1,
            "tool": "create_sequence",
            "arguments": {
                "name": seq_name
            }
        }
    ]

    # Video track V1
    v1_clips = pacing_manifest["tracks"].get("V1", [])
    for c in v1_clips:
        actions.append({
            "step": len(actions) + 1,
            "tool": "import_media",
            "arguments": {"file_path": c["file_path"]}
        })
        actions.append({
            "step": len(actions) + 1,
            "tool": "add_to_timeline",
            "arguments": {
                "item_id": Path(c["file_path"]).name,
                "track_index": 0,       # V1
                "audio_track_index": 0, # A1
                "start_seconds": c["timeline_in"]
            }
        })
        if c.get("optical_flow"):
            actions.append({
                "step": len(actions) + 1,
                "tool": "set_time_interpolation",
                "arguments": {
                    "node_id": Path(c["file_path"]).name,
                    "interpolation_type": 2  # Optical Flow
                }
            })
        if c.get("climax_marker"):
            actions.append({
                "step": len(actions) + 1,
                "tool": "add_marker",
                "arguments": {
                    "name": f"Climax: {c['clip_id']}",
                    "time_seconds": c["climax_marker"],
                    "comment": "Auto-detected Action Peak"
                }
            })

    # Audio track A2 (SFX)
    a2_sfx = pacing_manifest["tracks"].get("A2", [])
    for s in a2_sfx:
        actions.append({
            "step": len(actions) + 1,
            "tool": "import_media",
            "arguments": {"file_path": s["file_path"]}
        })
        actions.append({
            "step": len(actions) + 1,
            "tool": "add_to_timeline",
            "arguments": {
                "item_id": Path(s["file_path"]).name,
                "track_index": 0,
                "audio_track_index": 1, # A2
                "start_seconds": s["timeline_in"]
            }
        })

    # Audio track A3 (BGM)
    a3_bgm = pacing_manifest["tracks"].get("A3", [])
    for b in a3_bgm:
        actions.append({
            "step": len(actions) + 1,
            "tool": "import_media",
            "arguments": {"file_path": b["file_path"]}
        })
        actions.append({
            "step": len(actions) + 1,
            "tool": "add_to_timeline",
            "arguments": {
                "item_id": Path(b["file_path"]).name,
                "track_index": 0,
                "audio_track_index": 2, # A3
                "start_seconds": b["timeline_in"]
            }
        })

    return actions

def render_standalone_master(pacing_manifest, output_video_path):
    """
    Renders the paced sequence directly using FFmpeg concat and audio amix.
    """
    out_p = Path(output_video_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    v1_clips = pacing_manifest["tracks"].get("V1", [])
    if not v1_clips:
        raise ValueError("No video clips to render.")

    # Concat file list
    concat_txt = out_p.parent / f"{out_p.stem}_concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in v1_clips:
            clean_p = c["file_path"].replace("\\", "/")
            f.write(f"file '{clean_p}'\n")

    # Fast NVENC concat
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_txt),
        "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19",
        "-c:a", "aac", "-b:a", "192k",
        str(out_p)
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # Fallback to libx264
        cmd[7] = "libx264"
        cmd[9] = "-crf"
        subprocess.run(cmd, check=True)

    if concat_txt.exists():
        concat_txt.unlink()

    return str(out_p)
