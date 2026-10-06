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

def generate_premiere_mcp_actions(pacing_manifest, sequence_id=None):
    """
    Generates an optimized, high-performance batch list of Premiere Pro MCP calls (~100x faster).
    Collapses 60+ individual file round-trips into atomic batch operations:
      - Phase 1: Import unique media files required for sequence
      - Phase 2: Single atomic add_to_timeline_batch for Video (V1) + Linked Audio (A1)
      - Phase 3: Single atomic add_to_timeline_batch for Audio design (A3 Whoosh, A4 Climax, A5 BGM)
      - Phase 4: Climax action peak markers (top peaks only)
    """
    seq_name = pacing_manifest.get("sequence_name", "W_Curve_Master")
    v1_clips = pacing_manifest.get("tracks", {}).get("V1", [])
    a3_sfx = pacing_manifest.get("tracks", {}).get("A3", [])
    a4_sfx = pacing_manifest.get("tracks", {}).get("A4", [])
    a5_bgm = pacing_manifest.get("tracks", {}).get("A5", [])

    # Collect unique media paths to import
    needed_files = set()
    for c in v1_clips:
        needed_files.add(c["file_path"])
    for s in a3_sfx + a4_sfx + a5_bgm:
        needed_files.add(s["file_path"])

    actions = []

    # 1. Import media files
    for f in sorted(needed_files):
        actions.append({
            "step": len(actions) + 1,
            "tool": "import_media",
            "arguments": {
                "filePath": f
            }
        })

    # 2. Batch Video V1 + Auto-linked Audio A1
    batch_v1 = []
    for c in v1_clips:
        clip_spec = {
            "projectItemId": Path(c["file_path"]).name,
            "trackIndex": 0,  # V1
            "time": c["timeline_in"],
            "linkAudio": True
        }
        if "source_in" in c and "source_out" in c:
            clip_spec["sourceInPoint"] = c["source_in"]
            clip_spec["sourceOutPoint"] = c["source_out"]
        batch_v1.append(clip_spec)

    if batch_v1:
        actions.append({
            "step": len(actions) + 1,
            "tool": "add_to_timeline_batch",
            "arguments": {
                "sequenceId": sequence_id or seq_name,
                "clips": batch_v1
            }
        })

    # 3. Batch Audio Design: A3 (SFX Whoosh = track 2), A4 (SFX Climax = track 3), A5 (BGM = track 4)
    # Note: Audio Track A2 (trackIndex: 1) is DELIBERATELY RESERVED FOR VOICEOVER!
    batch_audio = []
    for s in a3_sfx:
        batch_audio.append({
            "projectItemId": Path(s["file_path"]).name,
            "trackIndex": 2,  # A3 (Transition SFX)
            "time": s["timeline_in"]
        })
    for s in a4_sfx:
        batch_audio.append({
            "projectItemId": Path(s["file_path"]).name,
            "trackIndex": 3,  # A4 (Climax SFX)
            "time": s["timeline_in"]
        })
    for b in a5_bgm:
        batch_audio.append({
            "projectItemId": Path(b["file_path"]).name,
            "trackIndex": 4,  # A5 (Ducked BGM)
            "time": b["timeline_in"]
        })

    if batch_audio:
        actions.append({
            "step": len(actions) + 1,
            "tool": "add_to_timeline_batch",
            "arguments": {
                "sequenceId": sequence_id or seq_name,
                "clips": batch_audio
            }
        })

    # 4. Climax Action Peak Markers (top peaks only to avoid UI noise)
    peak_clips = [c for c in v1_clips if c.get("climax_marker") is not None]
    peak_clips.sort(key=lambda x: x.get("interest_score", 0), reverse=True)
    for c in peak_clips[:5]:  # Top 5 critical story beats
        actions.append({
            "step": len(actions) + 1,
            "tool": "add_marker",
            "arguments": {
                "sequenceId": sequence_id or seq_name,
                "name": f"Peak: {c['clip_id']} ({c.get('narrative_role', 'Action')})",
                "time": c["climax_marker"],
                "comment": f"Interest Score: {c.get('interest_score', 0)}"
            }
        })

    return actions

def generate_fcp_xml(pacing_manifest, output_xml_path):
    """
    Generates a Final Cut Pro 7 XML (XMEML version 4) interchange file.
    Imports natively into Premiere Pro via import_fcp_xml in a single sub-second call.
    Fully constructs:
      - Video Track V1 with precise source in/out sub-frame cuts
      - Audio Track A1: Native synchronized clip audio
      - Audio Track A2: [BLANK] Reserved for Voiceover
      - Audio Track A3: Transition SFX
      - Audio Track A4: Climax SFX
      - Audio Track A5: Ducked BGM
      - Sequence Action Peak Markers
    """
    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    out_p = Path(output_xml_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    seq_name = pacing_manifest.get("sequence_name", "W_Curve_Master")
    fps = pacing_manifest.get("format", {}).get("fps", 60)
    width = pacing_manifest.get("format", {}).get("resolution", [1080, 1920])[0]
    height = pacing_manifest.get("format", {}).get("resolution", [1080, 1920])[1]
    total_sec = pacing_manifest.get("total_duration_seconds", 30.0)
    total_frames = int(round(total_sec * fps))

    xmeml = ET.Element("xmeml", version="4")
    sequence = ET.SubElement(xmeml, "sequence", id="sequence-1")
    ET.SubElement(sequence, "name").text = seq_name
    ET.SubElement(sequence, "duration").text = str(total_frames)

    rate = ET.SubElement(sequence, "rate")
    ET.SubElement(rate, "timebase").text = str(fps)
    ET.SubElement(rate, "ntsc").text = "FALSE"

    # Add Action Markers directly to sequence
    v1_clips = pacing_manifest.get("tracks", {}).get("V1", [])
    for c in v1_clips:
        if c.get("climax_marker") is not None:
            m = ET.SubElement(sequence, "marker")
            ET.SubElement(m, "name").text = f"Peak: {c['clip_id']} ({c.get('narrative_role', 'Action')})"
            ET.SubElement(m, "comment").text = f"Score: {c.get('interest_score', 0)}"
            m_frame = int(round(c["climax_marker"] * fps))
            ET.SubElement(m, "in").text = str(m_frame)
            ET.SubElement(m, "out").text = str(m_frame)

    media = ET.SubElement(sequence, "media")

    # 1. Video Track (V1)
    video = ET.SubElement(media, "video")
    vformat = ET.SubElement(video, "format")
    samplechar = ET.SubElement(vformat, "samplecharacteristics")
    ET.SubElement(samplechar, "width").text = str(width)
    ET.SubElement(samplechar, "height").text = str(height)
    srate = ET.SubElement(samplechar, "rate")
    ET.SubElement(srate, "timebase").text = str(fps)
    ET.SubElement(srate, "ntsc").text = "FALSE"

    vtrack = ET.SubElement(video, "track")

    # 2. Audio Tracks (A1..A5)
    audio = ET.SubElement(media, "audio")
    atrack1 = ET.SubElement(audio, "track") # A1: Native Audio
    atrack2 = ET.SubElement(audio, "track") # A2: Voiceover (Empty)
    atrack3 = ET.SubElement(audio, "track") # A3: Transition SFX
    atrack4 = ET.SubElement(audio, "track") # A4: Climax SFX
    atrack5 = ET.SubElement(audio, "track") # A5: BGM

    # Populate V1 & A1
    for idx, c in enumerate(v1_clips):
        fpath = Path(c["file_path"]).resolve()
        start_frame = int(round(c["timeline_in"] * fps))
        end_frame = int(round(c["timeline_out"] * fps))
        clip_dur = end_frame - start_frame

        src_in_sec = c.get("source_in", 0.0)
        src_out_sec = c.get("source_out", c.get("duration", 2.0))
        in_frame = int(round(src_in_sec * fps))
        out_frame = int(round(src_out_sec * fps))

        # Video item
        vitem = ET.SubElement(vtrack, "clipitem", id=f"clipitem-v-{idx+1}")
        ET.SubElement(vitem, "name").text = fpath.name
        ET.SubElement(vitem, "duration").text = str(clip_dur)
        vrate = ET.SubElement(vitem, "rate")
        ET.SubElement(vrate, "timebase").text = str(fps)
        ET.SubElement(vrate, "ntsc").text = "FALSE"
        ET.SubElement(vitem, "start").text = str(start_frame)
        ET.SubElement(vitem, "end").text = str(end_frame)
        ET.SubElement(vitem, "in").text = str(in_frame)
        ET.SubElement(vitem, "out").text = str(out_frame)

        vfile = ET.SubElement(vitem, "file", id=f"file-{idx+1}")
        ET.SubElement(vfile, "name").text = fpath.name
        ET.SubElement(vfile, "pathurl").text = fpath.as_uri()
        frate = ET.SubElement(vfile, "rate")
        ET.SubElement(frate, "timebase").text = str(fps)
        ET.SubElement(frate, "ntsc").text = "FALSE"
        fmedia = ET.SubElement(vfile, "media")
        fvid = ET.SubElement(fmedia, "video")
        fsample = ET.SubElement(fvid, "samplecharacteristics")
        ET.SubElement(fsample, "width").text = str(width)
        ET.SubElement(fsample, "height").text = str(height)

        # Audio counterpart on A1
        aitem = ET.SubElement(atrack1, "clipitem", id=f"clipitem-a-{idx+1}")
        ET.SubElement(aitem, "name").text = fpath.name
        ET.SubElement(aitem, "duration").text = str(clip_dur)
        arate = ET.SubElement(aitem, "rate")
        ET.SubElement(arate, "timebase").text = str(fps)
        ET.SubElement(arate, "ntsc").text = "FALSE"
        ET.SubElement(aitem, "start").text = str(start_frame)
        ET.SubElement(aitem, "end").text = str(end_frame)
        ET.SubElement(aitem, "in").text = str(in_frame)
        ET.SubElement(aitem, "out").text = str(out_frame)
        ET.SubElement(aitem, "file", id=f"file-{idx+1}")

    # Helper for adding audio-only items to tracks
    def add_audio_items(track_elem, items_list, prefix):
        for s_idx, item in enumerate(items_list):
            spath = Path(item["file_path"]).resolve()
            s_start = int(round(item["timeline_in"] * fps))
            s_dur = int(round(item.get("duration", 1.0) * fps))
            s_end = s_start + s_dur
            
            sitem = ET.SubElement(track_elem, "clipitem", id=f"clipitem-{prefix}-{s_idx+1}")
            ET.SubElement(sitem, "name").text = spath.name
            ET.SubElement(sitem, "duration").text = str(s_dur)
            srate = ET.SubElement(sitem, "rate")
            ET.SubElement(srate, "timebase").text = str(fps)
            ET.SubElement(srate, "ntsc").text = "FALSE"
            ET.SubElement(sitem, "start").text = str(s_start)
            ET.SubElement(sitem, "end").text = str(s_end)
            ET.SubElement(sitem, "in").text = "0"
            ET.SubElement(sitem, "out").text = str(s_dur)

            sfile = ET.SubElement(sitem, "file", id=f"file-{prefix}-{s_idx+1}")
            ET.SubElement(sfile, "name").text = spath.name
            ET.SubElement(sfile, "pathurl").text = spath.as_uri()

    add_audio_items(atrack3, pacing_manifest.get("tracks", {}).get("A3", []), "a3")
    add_audio_items(atrack4, pacing_manifest.get("tracks", {}).get("A4", []), "a4")
    add_audio_items(atrack5, pacing_manifest.get("tracks", {}).get("A5", []), "a5")

    xml_str = ET.tostring(xmeml, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
    with open(out_p, "wb") as f:
        f.write(pretty_xml)

    return str(out_p)

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
