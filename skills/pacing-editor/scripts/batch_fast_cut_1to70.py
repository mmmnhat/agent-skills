"""
Batch Fast-Cut Engine for ITV-Moments-script-61 (Clips 01 to 70).
Scans all 67 clips, computes Ultra-Tight Fast-Cut In/Out boundaries:
- Setup: <= 3.5s
- Climax: <= 3.0s
- Payoff: <= 3.5s
- Total clip duration: 6s - 12s (Max 15s)
Outputs state/kb101_tight_cuts_1to70.json.
"""

import os
import sys
import json
import time
from pathlib import Path
import cv2
import numpy as np

FOLDER = r"E:\ITV\Project\kb101\ITV-Moments-script-61"
OUTPUT_JSON = r"E:\.agents\state\kb101_tight_cuts_1to70.json"


def analyze_clip_tight_window(file_path: str) -> dict:
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return {
            "file": os.path.basename(file_path),
            "error": "Cannot open file",
            "in_point": 0.0,
            "out_point": 10.0,
            "duration": 10.0,
        }

    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = total_frames / fps

    # If clip is already short (<= 7s), keep it mostly as is, maybe trim 0.5s head wobble
    if dur <= 7.0:
        cap.release()
        in_s = min(0.5, dur * 0.1) if dur > 3.0 else 0.0
        out_s = dur
        return {
            "file": os.path.basename(file_path),
            "orig_duration": round(dur, 2),
            "in_point": round(in_s, 2),
            "out_point": round(out_s, 2),
            "duration": round(out_s - in_s, 2),
            "note": "Short clip preserved with minimal head trim",
        }

    # For clips > 7s, sample motion curve in RAM at 2 fps
    step = max(1, int(fps / 2.0))
    diffs = []
    ts = []
    prev_g = None

    # Limit max sampled frames to 300 to keep it ultra fast (< 0.5s per video)
    if total_frames // step > 300:
        step = total_frames // 300

    for f_idx in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        sm = cv2.resize(frame, (80, 45), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY)
        if prev_g is not None:
            diffs.append(float(np.mean(cv2.absdiff(g, prev_g))))
        else:
            diffs.append(0.0)
        ts.append(f_idx / fps)
        prev_g = g

    cap.release()

    if not diffs:
        return {
            "file": os.path.basename(file_path),
            "orig_duration": round(dur, 2),
            "in_point": 0.0,
            "out_point": min(10.0, dur),
            "duration": min(10.0, dur),
        }

    # Find the primary Action Peak
    peak_idx = int(np.argmax(diffs))
    peak_t = ts[peak_idx]

    # Special handling for 01.mp4 (our snake video where peak was in car, but real action is climbing leg)
    base_name = os.path.basename(file_path)
    if base_name == "01.mp4":
        # Snake climbing leg climax
        peak_t = 75.0

    # Calculate tight window around peak:
    # Setup: up to 3.0s before peak
    # Payoff: up to 3.5s after peak
    in_s = max(0.0, peak_t - 3.0)
    out_s = min(dur, peak_t + 3.5)

    # If peak was too close to start (e.g. peak_t < 2.0), expand tail slightly to reach ~6s
    if (out_s - in_s) < 5.0 and dur >= 6.0:
        out_s = min(dur, in_s + 6.0)

    # Hard ceiling: max 12.0s duration
    if (out_s - in_s) > 12.0:
        out_s = in_s + 12.0

    return {
        "file": base_name,
        "orig_duration": round(dur, 2),
        "peak_sec": round(peak_t, 2),
        "in_point": round(in_s, 2),
        "out_point": round(out_s, 2),
        "duration": round(out_s - in_s, 2),
        "note": "Ultra-tight fast-cut window",
    }


def main():
    t0 = time.time()
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    files = sorted([os.path.join(FOLDER, f) for f in os.listdir(FOLDER) if f.endswith(".mp4")])
    print(f"Scanning {len(files)} clips in {FOLDER}...")

    results = []
    total_orig_sec = 0.0
    total_tight_sec = 0.0

    for i, p in enumerate(files):
        res = analyze_clip_tight_window(p)
        results.append(res)
        orig_d = res.get("orig_duration", res.get("duration", 0.0))
        tight_d = res.get("duration", 0.0)
        total_orig_sec += orig_d
        total_tight_sec += tight_d
        if (i + 1) % 10 == 0 or (i + 1) == len(files):
            print(f"  Processed {i+1}/{len(files)} clips... ({time.time()-t0:.1f}s)")

    summary = {
        "total_clips": len(results),
        "total_original_duration_sec": round(total_orig_sec, 2),
        "total_original_duration_min": round(total_orig_sec / 60.0, 2),
        "total_tight_duration_sec": round(total_tight_sec, 2),
        "total_tight_duration_min": round(total_tight_sec / 60.0, 2),
        "time_saved_percent": round((1.0 - total_tight_sec / max(1.0, total_orig_sec)) * 100, 1),
        "analysis_elapsed_sec": round(time.time() - t0, 2),
        "clips": results,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nCompleted in {summary['analysis_elapsed_sec']}s!")
    print(f"Original duration: {summary['total_original_duration_min']} mins")
    print(f"Ultra-Tight duration: {summary['total_tight_duration_min']} mins (Saved {summary['time_saved_percent']}%)")
    print(f"Saved to: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
