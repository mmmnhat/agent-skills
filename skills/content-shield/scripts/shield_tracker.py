#!/usr/bin/env python3
"""
OpenCV Visual Tracking Engine for Content Shield
Accurately detects and tracks watermarks, channel bugs, logos, and sensitive ROIs across video frames.
Supports Static Presets, Temporal Variance Auto-Pinpoint, and Multi-Frame MIL/Template Tracking.
"""
import os
import sys
import json
import cv2
import numpy as np
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

def resolve_zone_box(zone_name, width, height, custom_box=None):
    """
    Converts relative zone preset or custom input to integer pixel box [x, y, w, h].
    """
    if zone_name == "custom" and custom_box is not None:
        if len(custom_box) == 4:
            x, y, w, h = custom_box
            # If normalized (0.0 to 1.0), scale to pixel resolution
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0:
                x = int(x * width)
                y = int(y * height)
                w = int(w * width)
                h = int(h * height)
            else:
                x, y, w, h = int(x), int(y), int(w), int(h)
            # Clamp to frame bounds
            x = max(0, min(x, width - 10))
            y = max(0, min(y, height - 10))
            w = max(10, min(w, width - x))
            h = max(10, min(h, height - y))
            return [x, y, w, h]

    presets = CONFIG.get("preset_zones", {})
    if zone_name in presets and "relative_box" in presets[zone_name]:
        rx, ry, rw, rh = presets[zone_name]["relative_box"]
        x = int(rx * width)
        y = int(ry * height)
        w = int(rw * width)
        h = int(rh * height)
        return [x, y, w, h]

    # Default fallback: top_right watermark box
    return [int(0.76 * width), int(0.02 * height), int(0.22 * width), int(0.12 * height)]

def auto_pinpoint_watermark(video_path, zone_box, sample_count=15):
    """
    Samples frames across the video within zone_box and identifies the static logo / watermark
    by looking for high-frequency edge regions that have low temporal variance (static).
    Returns refined tight bounding box [x, y, w, h] or original zone_box if indistinct.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return zone_box

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 10:
        cap.release()
        return zone_box

    zx, zy, zw, zh = zone_box
    step = max(1, total_frames // (sample_count + 1))
    frames_roi = []

    for i in range(1, sample_count + 1):
        target_f = i * step
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_f)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        roi = frame[zy:zy+zh, zx:zx+zw]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        frames_roi.append(gray.astype(np.float32))

    cap.release()

    if len(frames_roi) < 3:
        return zone_box

    # Calculate temporal standard deviation
    stack = np.stack(frames_roi, axis=0)
    std_map = np.std(stack, axis=0) # Low std means static pixel across frames
    mean_map = np.mean(stack, axis=0)
    
    # Calculate spatial edges on the mean image
    sobelx = cv2.Sobel(mean_map, cv2.CV_32F, 1, 0, ksize=3)
    sobely = cv2.Sobel(mean_map, cv2.CV_32F, 0, 1, ksize=3)
    edge_map = np.sqrt(sobelx**2 + sobely**2)
    
    # Static watermark score: high edge + low variance
    norm_edge = edge_map / (np.max(edge_map) + 1e-5)
    norm_static = 1.0 - (std_map / (np.max(std_map) + 1e-5))
    watermark_mask = (norm_edge * norm_static) > 0.35

    if np.sum(watermark_mask) > 100:
        # Find contours of static features
        uint8_mask = (watermark_mask * 255).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(uint8_mask, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Pick largest contour or bounding union of all significant static contours
            boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 50]
            if boxes:
                min_x = min(b[0] for b in boxes)
                min_y = min(b[1] for b in boxes)
                max_x = max(b[0] + b[2] for b in boxes)
                max_y = max(b[1] + b[3] for b in boxes)
                
                # Add padding
                pad = 8
                nx = max(0, zx + min_x - pad)
                ny = max(0, zy + min_y - pad)
                nw = min(zw, (max_x - min_x) + 2 * pad)
                nh = min(zh, (max_y - min_y) + 2 * pad)
                return [int(nx), int(ny), int(nw), int(nh)]

    return zone_box

def track_moving_roi(video_path, initial_box, max_frames=None, sample_step=2):
    """
    Tracks initial_box across video frames using OpenCV TrackerMIL.
    Outputs a list of keyframe entries: [{"frame": f, "time_sec": t, "box": [x,y,w,h], "confidence": 1.0}]
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    limit_frames = total_frames if max_frames is None else min(total_frames, max_frames)

    ret, first_frame = cap.read()
    if not ret or first_frame is None:
        cap.release()
        raise RuntimeError(f"Could not read first frame from: {video_path}")

    # Tracker initialization
    tracker = cv2.TrackerMIL_create()
    bbox = tuple(initial_box) # (x, y, w, h)
    tracker.init(first_frame, bbox)

    keyframes = [{
        "frame": 0,
        "time_sec": 0.0,
        "box": [int(b) for b in bbox],
        "confidence": 1.0
    }]

    current_frame = 1
    last_known_box = initial_box

    while current_frame < limit_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        if current_frame % sample_step == 0:
            success, box = tracker.update(frame)
            if success:
                x, y, w, h = [int(v) for v in box]
                last_known_box = [x, y, w, h]
                conf = 0.95
            else:
                x, y, w, h = last_known_box
                conf = 0.30

            keyframes.append({
                "frame": current_frame,
                "time_sec": round(current_frame / fps, 4),
                "box": [x, y, w, h],
                "confidence": conf
            })

        current_frame += 1

    cap.release()
    return keyframes

def build_shield_manifest(video_path, zone="top_right", mode="delogo", is_static=True, custom_box=None, auto_detect=False):
    """
    Builds a complete ContentShieldManifest dictionary.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot probe video: {video_path}")
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    cap.release()

    box = resolve_zone_box(zone, width, height, custom_box)
    
    if auto_detect and is_static:
        box = auto_pinpoint_watermark(video_path, box)

    keyframes = []
    if not is_static:
        keyframes = track_moving_roi(video_path, box, sample_step=2)
    else:
        # Static: two boundary keyframes
        keyframes = [
            {"frame": 0, "time_sec": 0.0, "box": box, "confidence": 1.0},
            {"frame": max(1, total_frames - 1), "time_sec": round(duration, 4), "box": box, "confidence": 1.0}
        ]

    manifest = {
        "source_file": str(Path(video_path).resolve()).replace("\\", "/"),
        "created_at": Path(video_path).name,
        "duration_seconds": round(duration, 3),
        "video_dimensions": {"width": width, "height": height},
        "shield_jobs": [
            {
                "job_id": f"shield_{zone}_{mode}",
                "mode": mode,
                "zone_name": zone,
                "is_static": is_static,
                "initial_box": box,
                "keyframe_trajectory": keyframes,
                "premiere_bridge": {
                    "target_track": CONFIG.get("premiere_bridge", {}).get("target_track", "V2"),
                    "effect_name": CONFIG.get("premiere_bridge", {}).get("effect_name", "Gaussian Blur"),
                    "clip_node_id": None
                }
            }
        ]
    }
    return manifest
