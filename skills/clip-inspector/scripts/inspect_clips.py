#!/usr/bin/env python3
"""
Clip-Inspector Main Engine
Standardizes pre-existing folders of video clips into unified scenes_context.json manifests.
Extracts 4-frame visual filmstrips, temporal action peaks, pacing phases,
unblur boundary checks, and 64-bit integer POPCNT pHash duplicate indexing.
"""
import os
import sys
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Import companion modules
try:
    from unblur_detector import detect_unblur_box
    from phash_utils import compute_dual_phash, match_hashes
    from temporal_analyzer import analyze_and_generate_filmstrip
    from scene_context_engine import synthesize_scene_context
except ImportError:
    from .unblur_detector import detect_unblur_box
    from .phash_utils import compute_dual_phash, match_hashes
    from .temporal_analyzer import analyze_and_generate_filmstrip
    from .scene_context_engine import synthesize_scene_context

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv"}

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "output_manifest": "scenes_context.json",
        "thumbnails_dir": "thumbnails",
        "check_unblur": True,
        "check_duplicates": True,
        "library_index_file": "library_index.json",
        "min_clip_duration_sec": 0.5
    }

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

def load_library_index(lib_path):
    if lib_path.exists():
        try:
            with open(lib_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"clips": []}

def save_library_index(lib_path, data):
    try:
        with open(lib_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to update library index: {e}")

def inspect_clip_folder(folder_path, output_dir=None, check_unblur=None, check_duplicates=None, limit=None):
    cfg = load_config()
    target_path = Path(folder_path).resolve()
    
    if not target_path.exists():
        raise FileNotFoundError(f"Target folder not found: {folder_path}")
        
    out_dir = Path(output_dir).resolve() if output_dir else target_path
    os.makedirs(out_dir, exist_ok=True)
    
    thumb_dir = out_dir / cfg.get("thumbnails_dir", "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    
    do_unblur = check_unblur if check_unblur is not None else cfg.get("check_unblur", True)
    do_dedup = check_duplicates if check_duplicates is not None else cfg.get("check_duplicates", True)
    min_dur = cfg.get("min_clip_duration_sec", 0.5)
    
    # Locate video files
    if target_path.is_file():
        clip_files = [target_path]
    else:
        clip_files = [
            p for p in target_path.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        ]
        clip_files.sort(key=natural_sort_key)
        
    if limit is not None and limit > 0:
        clip_files = clip_files[:limit]
        
    print(f"\n[Clip-Inspector Milestone 1] Ingesting & Analyzing Media:")
    print(f"  • Source Directory: {target_path}")
    print(f"  • Found Video Clips: {len(clip_files)}")
    print(f"  • Unblur Detection: {'Enabled' if do_unblur else 'Disabled'}")
    print(f"  • Duplicate Indexing: {'Enabled' if do_dedup else 'Disabled'}")
    print(f"  • Output Manifest: {out_dir / cfg.get('output_manifest', 'scenes_context.json')}\n")
    
    if not clip_files:
        print("  ! No video files found matching supported extensions.")
        return None

    # Load cross-video library index
    lib_filename = cfg.get("library_index_file", "library_index.json")
    lib_path = Path(__file__).resolve().parent.parent / lib_filename
    lib_index = load_library_index(lib_path)
    existing_lib_clips = lib_index.get("clips", [])
    
    scenes = []
    new_lib_entries = []
    blur_count = 0
    duplicate_count = 0
    
    for idx, clip_file in enumerate(clip_files, start=1):
        cap = cv2.VideoCapture(str(clip_file))
        if not cap.isOpened():
            print(f"  ! Warning: Unable to open {clip_file.name}, skipping.")
            continue
            
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = round(total_frames / fps, 2) if total_frames > 0 else 0.0
        
        if duration < min_dur:
            cap.release()
            continue
            
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # 1. Check Unblur / Framing
        has_blur = False
        crop_box = {"x": 0, "y": 0, "w": width, "h": height}
        aspect_ratio = f"{width}:{height}"
        
        mid_frame_idx = total_frames // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_idx)
        ret, mid_frame = cap.read()
        
        if ret and mid_frame is not None:
            if do_unblur:
                has_blur, box, aspect_ratio = detect_unblur_box(mid_frame)
                crop_box = {"x": box[0], "y": box[1], "w": box[2], "h": box[3]}
                if has_blur:
                    blur_count += 1
            else:
                aspect_ratio = "16:9" if abs(width/height - 16/9) < 0.1 else ("9:16" if abs(width/height - 9/16) < 0.1 else f"{width}:{height}")
        
        # 2. Extract Temporal Landmarks & 4-Frame Filmstrip
        strip_file_name = f"{clip_file.stem}_strip.jpg"
        strip_path = thumb_dir / strip_file_name
        
        action_peak_rel, phases, pacing_rec = analyze_and_generate_filmstrip(
            cap, fps, 0.0, duration, out_strip_path=str(strip_path)
        )
        
        # 3. Fingerprint & Deduplication Check
        h_orig, h_flip = None, None
        is_cross_dup = False
        cross_details = None
        
        if mid_frame is not None and do_dedup:
            h_orig, h_flip = compute_dual_phash(mid_frame)
            if h_orig is not None:
                for entry in existing_lib_clips:
                    is_match, dist, sim, is_flipped = match_hashes(
                        h_orig, entry.get("hash_orig"), entry.get("hash_flip"), max_dist=6
                    )
                    if is_match:
                        is_cross_dup = True
                        duplicate_count += 1
                        cross_details = {
                            "matched_source_video": entry.get("source_video"),
                            "matched_clip": entry.get("file_name"),
                            "similarity": sim,
                            "is_flipped": is_flipped
                        }
                        break
                        
                if not is_cross_dup:
                    new_lib_entries.append({
                        "source_video": target_path.name,
                        "file_name": clip_file.name,
                        "duration": duration,
                        "aspect_ratio": aspect_ratio,
                        "hash_orig": h_orig,
                        "hash_flip": h_flip
                    })
                    
        cap.release()
        
        scene_info = {
            "scene_id": idx,
            "incident_id": idx,
            "shot_index": 1,
            "is_continuation": False,
            "continuation_of": None,
            "variation_type": "base",
            "file_name": clip_file.name,
            "target_folder": "main",
            "file_path": str(clip_file.resolve()).replace("\\", "/"),
            "filmstrip_path": str(strip_path.resolve()).replace("\\", "/"),
            "start_time": 0.0,
            "end_time": duration,
            "duration": duration,
            "has_blur": has_blur,
            "crop_box": crop_box,
            "aspect_ratio": aspect_ratio,
            "native_resolution": {
                "width": crop_box["w"],
                "height": crop_box["h"]
            },
            "audio": {
                "start_snap_delta": 0.0,
                "end_snap_delta": 0.0
            },
            "temporal_landmarks": {
                "action_peak_rel_sec": action_peak_rel,
                "phases": phases,
                "pacing_recommendations": pacing_rec
            },
            "deduplication": {
                "is_intra_duplicate": False,
                "intra_details": None,
                "is_cross_duplicate": is_cross_dup,
                "cross_details": cross_details
            },
            "premiere_pro": {
                "suggested_track": "V1" if not is_cross_dup else "V2",
                "in_point": 0.0,
                "out_point": duration,
                "action_peak_marker_sec": action_peak_rel,
                "optical_flow_ready": True,
                "clip_name": f"Clip_{idx:03d}_{clip_file.stem[:20]}"
            }
        }
        scene_info["context"] = synthesize_scene_context(scene_info, source_title=target_path.name)
        scenes.append(scene_info)
        
        blur_tag = " [Blurred Margins Detected]" if has_blur else ""
        dup_tag = f" [Duplicate of {cross_details['matched_clip']}]" if is_cross_dup else ""
        print(f"  ✓ [{idx:03d}] {clip_file.name} ({duration}s, {aspect_ratio}, Peak @ {action_peak_rel}s){blur_tag}{dup_tag}")

    # Update Library Index
    if new_lib_entries and do_dedup:
        existing_lib_clips.extend(new_lib_entries)
        lib_index["clips"] = existing_lib_clips
        save_library_index(lib_path, lib_index)
        print(f"\n  ✓ Indexed {len(new_lib_entries)} new fingerprints into {lib_filename}")

    # Build Context Manifest
    context_manifest = {
        "source_video": str(target_path).replace("\\", "/"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_scenes": len(scenes),
        "total_incidents": len(scenes),
        "clean_master_scenes": len(scenes) - duplicate_count,
        "intra_duplicates_count": 0,
        "cross_duplicates_count": duplicate_count,
        "blurred_margins_count": blur_count,
        "output_directory": str(out_dir).replace("\\", "/"),
        "scenes": scenes
    }

    def json_default(o):
        if isinstance(o, (np.bool_, bool)):
            return bool(o)
        if isinstance(o, (np.integer, int)):
            return int(o)
        if isinstance(o, (np.floating, float)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    manifest_file = out_dir / cfg.get("output_manifest", "scenes_context.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(context_manifest, f, indent=2, ensure_ascii=False, default=json_default)
        
    print(f"\n[Clip-Inspector Milestone 2] Inspection Summary:")
    print(f"  • Total Clips Inspected: {len(scenes)}")
    print(f"  • Clips with Blurred Margins: {blur_count}")
    print(f"  • Cross-video Duplicates: {duplicate_count}")
    print(f"  • Manifest Ready: {manifest_file}")
    print(f"  • Filmstrips Location: {thumb_dir}")
    return str(manifest_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clip-Inspector: Standardize and Extract Landmarks from Clip Directories")
    parser.add_argument("target", help="Path to clip directory or single video clip")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory for scenes_context.json and thumbnails")
    parser.add_argument("--no-unblur", action="store_true", help="Disable blurred letterbox/pillarbox detection")
    parser.add_argument("--no-dedup", action="store_true", help="Disable duplicate fingerprint indexing")
    parser.add_argument("-l", "--limit", type=int, default=None, help="Limit number of clips to inspect")
    
    args = parser.parse_args()
    inspect_clip_folder(
        folder_path=args.target,
        output_dir=args.output_dir,
        check_unblur=not args.no_unblur,
        check_duplicates=not args.no_dedup,
        limit=args.limit
    )
