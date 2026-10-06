#!/usr/bin/env python3
"""
Hardware-Accelerated Shield Renderer & Preview Generator
Applies Delogo, Gaussian Blur, Pixelated Mosaic, or Solid Matte Masks to videos via FFmpeg NVENC.
Generates verification preview frames for visual inspection.
"""
import os
import sys
import subprocess
import cv2
import numpy as np
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def test_nvenc():
    try:
        res = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=5)
        return "h264_nvenc" in res.stdout
    except Exception:
        return False

HAS_NVENC = test_nvenc()

def build_filter_graph(mode, box, width, height):
    """
    Constructs FFmpeg video filter string for the specified obscuration mode and box [x,y,w,h].
    """
    x, y, w, h = box
    # Ensure even dimensions for compatibility
    x = x - (x % 2)
    y = y - (y % 2)
    w = max(2, w - (w % 2))
    h = max(2, h - (h % 2))

    if mode == "delogo":
        # delogo requires x, y >= 1 and x+w <= width-1, y+h <= height-1
        delogo_x = max(1, x)
        delogo_y = max(1, y)
        delogo_w = min(w, width - delogo_x - 1)
        delogo_h = min(h, height - delogo_y - 1)
        return f"delogo=x={delogo_x}:y={delogo_y}:w={delogo_w}:h={delogo_h}:show=0"

    elif mode == "gaussian_blur":
        return f"[0:v]crop={w}:{h}:{x}:{y},boxblur=luma_radius=20:luma_power=3[b];[0:v][b]overlay={x}:{y}"

    elif mode == "mosaic":
        # Mosaic downsamples the ROI by 16x using nearest neighbor then upsamples
        return f"[0:v]crop={w}:{h}:{x}:{y},scale=iw/16:ih/16:flags=neighbor,scale={w}:{h}:flags=neighbor[m];[0:v][m]overlay={x}:{y}"

    elif mode == "solid_mask":
        return f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black@1.0:t=fill"

    else:
        # Fallback to delogo
        return f"delogo=x={x}:y={y}:w={w}:h={h}:show=0"

def render_shielded_video(source_path, output_path, mode="delogo", box=None, overwrite=True):
    """
    Renders video with shield applied.
    """
    src = Path(source_path).resolve()
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot read video: {src}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if box is None:
        # Default top-right corner
        box = [int(0.76 * width), int(0.02 * height), int(0.22 * width), int(0.12 * height)]

    vf_filter = build_filter_graph(mode, box, width, height)
    vcodec = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19"] if HAS_NVENC else ["-c:v", "libx264", "-crf", "19", "-preset", "fast"]

    cmd = [
        "ffmpeg", "-y" if overwrite else "-n",
        "-i", str(src),
        "-filter_complex" if "[" in vf_filter else "-vf", vf_filter,
        *vcodec,
        "-c:a", "copy",
        str(out)
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # Fallback to CPU libx264 if NVENC errored
        if HAS_NVENC:
            cmd_fallback = [
                "ffmpeg", "-y" if overwrite else "-n",
                "-i", str(src),
                "-filter_complex" if "[" in vf_filter else "-vf", vf_filter,
                "-c:v", "libx264", "-crf", "19", "-preset", "fast",
                "-c:a", "copy",
                str(out)
            ]
            res2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
            if res2.returncode != 0:
                raise RuntimeError(f"FFmpeg render error: {res2.stderr}")
        else:
            raise RuntimeError(f"FFmpeg render error: {res.stderr}")

    return str(out)

def generate_shield_preview(source_path, box, preview_path=None, sample_sec=1.5):
    """
    Extracts a frame, overlays a comparison showing Original vs Shielded ROI, and saves a JPEG.
    """
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(sample_sec * fps))
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return None

    x, y, w, h = box
    preview_img = frame.copy()

    # Draw neon cyan bounding box around ROI
    cv2.rectangle(preview_img, (x, y), (x + w, y + h), (255, 255, 0), 2)
    # Apply simulated blur to ROI in preview image
    roi = preview_img[y:y+h, x:x+w]
    if roi.size > 0:
        blurred_roi = cv2.GaussianBlur(roi, (45, 45), 0)
        preview_img[y:y+h, x:x+w] = blurred_roi

    # Add label
    cv2.putText(preview_img, f"SHIELD MASK [{w}x{h}]", (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

    out_p = Path(preview_path or (str(Path(source_path).with_suffix("")) + "_shield_preview.jpg"))
    out_p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_p), preview_img)
    return str(out_p)
