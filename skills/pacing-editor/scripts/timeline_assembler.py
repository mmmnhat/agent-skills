#!/usr/bin/env python3
"""
Timeline Assembler & Dispatcher (v2.0 Studio 5-Track Edition)
Executes timeline generation either via Premiere Pro MCP Tool Calls or Headless FFmpeg Render.
Enforces Studio 5-Track Audio Layout:
  [V1] Video Track       : Video clips with hard fast-cuts & action peaks
  [A1] Audio Track 1     : Original Video Audio
  [A2] Audio Track 2     : [BLANK] RESERVED EXCLUSIVELY FOR VOICEOVER
  [A3] Audio Track 3     : Transition SFX (Whoosh)
  [A4] Audio Track 4     : Climax SFX (Impact / Punch)
  [A5] Audio Track 5     : Ducked Background Music
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

def get_best_render_encoder():
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if "h264_videotoolbox" in res.stdout:
            return "h264_videotoolbox"
        if "h264_nvenc" in res.stdout:
            return "h264_nvenc"
    except Exception:
        pass
    return "libx264"

def generate_premiere_mcp_actions(pacing_manifest):
    """
    Generates a structured list of Premiere Pro MCP calls corresponding to the 5-Track pacing manifest.
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

    # 1. Video track V1 & Original Audio A1
    v1_clips = pacing_manifest["tracks"].get("V1", [])
    for c in v1_clips:
        actions.append({
            "step": len(actions) + 1,
            "tool": "import_media",
            "arguments": {"file_path": c["file_path"]}
        })
        add_args = {
            "item_id": Path(c["file_path"]).name,
            "track_index": 0,       # V1
            "audio_track_index": 0, # A1
            "start_seconds": c["timeline_in"]
        }
        if "source_in" in c and "source_out" in c:
            add_args["in_point"] = c["source_in"]
            add_args["out_point"] = c["source_out"]
            
        actions.append({
            "step": len(actions) + 1,
            "tool": "add_to_timeline",
            "arguments": add_args
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
                    "name": f"Peak: {c['clip_id']} ({c.get('narrative_role', 'Action')})",
                    "time_seconds": c["climax_marker"],
                    "comment": f"Interest Score: {c.get('interest_score', 0)}"
                }
            })

    # Note: Audio Track A2 (audio_track_index: 1) is DELIBERATELY LEFT BLANK for Voiceover!

    # 2. Audio track A3 (Transition SFX)
    a3_sfx = pacing_manifest["tracks"].get("A3", [])
    for s in a3_sfx:
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
                "audio_track_index": 2, # A3 (Transition SFX)
                "start_seconds": s["timeline_in"]
            }
        })

    # 3. Audio track A4 (Climax SFX)
    a4_sfx = pacing_manifest["tracks"].get("A4", [])
    for s in a4_sfx:
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
                "audio_track_index": 3, # A4 (Climax SFX)
                "start_seconds": s["timeline_in"]
            }
        })

    # 4. Audio track A5 (Ducked BGM)
    a5_bgm = pacing_manifest["tracks"].get("A5", [])
    for b in a5_bgm:
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
                "audio_track_index": 4, # A5 (Background Music)
                "start_seconds": b["timeline_in"]
            }
        })

    return actions

def render_standalone_master(pacing_manifest, output_video_path):
    """
    Renders the paced sequence directly using FFmpeg concat and hardware acceleration.
    """
    out_p = Path(output_video_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    v1_clips = pacing_manifest["tracks"].get("V1", [])
    if not v1_clips:
        raise ValueError("No video clips to render.")

    concat_txt = out_p.parent / f"{out_p.stem}_concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in v1_clips:
            clean_p = c["file_path"].replace("\\", "/")
            f.write(f"file '{clean_p}'\n")
            if "source_in" in c and "source_out" in c:
                f.write(f"inpoint {c['source_in']}\n")
                f.write(f"outpoint {c['source_out']}\n")

    enc = get_best_render_encoder()
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_txt),
    ]
    if enc == "h264_videotoolbox":
        cmd.extend(["-c:v", "h264_videotoolbox", "-b:v", "6000k"])
    elif enc == "h264_nvenc":
        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19"])
    else:
        cmd.extend(["-c:v", "libx264", "-crf", "20", "-preset", "medium"])
        
    cmd.extend(["-c:a", "aac", "-b:a", "192k", str(out_p)])

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # Fallback to pure libx264
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c:v", "libx264", "-crf", "21",
            "-c:a", "aac", "-b:a", "192k",
            str(out_p)
        ]
        subprocess.run(cmd, check=True)

    if concat_txt.exists():
        concat_txt.unlink()

    return str(out_p)
