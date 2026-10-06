#!/usr/bin/env python3
"""
Unified Temporal Motion, Pacing & Filmstrip Generator
Processes temporal motion curve and stitches 4-frame visual filmstrips
in a single unified pass using a shared VideoCapture handle.
"""
import os
import cv2
import numpy as np

def analyze_and_generate_filmstrip(cap, fps, start_sec, end_sec, out_strip_path=None, num_samples=12):
    """
    Analyzes visual motion energy across [start_sec, end_sec] using an open `cap` handle,
    locates Action Peak, segments pacing phases, and stitches a 4-frame filmstrip.
    """
    duration = max(0.5, end_sec - start_sec)
    sample_times = np.linspace(start_sec, end_sec, num_samples)
    
    prev_gray = None
    motion_scores = []
    
    # 1. Motion curve analysis
    for t in sample_times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ret, frame = cap.read()
        if not ret or frame is None:
            motion_scores.append(0.0)
            continue
            
        small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            motion_scores.append(float(np.mean(diff)))
        else:
            motion_scores.append(0.0)
        prev_gray = gray
        
    if len(motion_scores) > 2 and max(motion_scores) > 1.0:
        peak_idx = int(np.argmax(motion_scores))
        peak_rel_sec = round(float(sample_times[peak_idx] - start_sec), 2)
    else:
        peak_rel_sec = round(duration * 0.60, 2)
        
    climax_start = max(0.0, round(peak_rel_sec - 1.2, 2))
    climax_end = min(duration, round(peak_rel_sec + 1.2, 2))
    
    phases = {
        "lead_in": [0.0, climax_start],
        "climax": [climax_start, climax_end],
        "recovery": [climax_end, round(duration, 2)]
    }
    
    pacing_rec = {
        "is_long_clip": bool(duration >= 6.0),
        "suggested_trim": {
            "in_sec": float(max(0.0, round(peak_rel_sec - 1.5, 2))),
            "out_sec": float(min(duration, round(peak_rel_sec + 2.0, 2))),
            "trimmed_duration": float(round(min(duration, peak_rel_sec + 2.0) - max(0.0, peak_rel_sec - 1.5), 2))
        },
        "suggested_speed_ramp": {
            "lead_in_speed": 3.0 if climax_start > 2.0 else 1.0,
            "climax_speed": 1.0,
            "recovery_speed": 1.5 if (duration - climax_end) > 2.0 else 1.0,
            "premiere_pro_interpolation": "Optical Flow"
        }
    }
    
    # 2. Extract 4 Keyframe Panels for Filmstrip
    if out_strip_path:
        t1 = start_sec + min(duration * 0.12, 1.0)
        t2 = start_sec + (duration * 0.40)
        if 0.2 < peak_rel_sec < (duration - 0.2):
            t3 = start_sec + peak_rel_sec
        else:
            t3 = start_sec + (duration * 0.70)
        t4 = start_sec + max(duration * 0.88, duration - 1.0)
        
        target_h = 240
        panels = []
        timestamps = [(t1, "1: Setup"), (t2, "2: Build-up"), (t3, "3: Climax"), (t4, "4: Reaction")]
        
        for t_sec, label in timestamps:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(t_sec * fps))
            ret, frame = cap.read()
            if not ret or frame is None:
                panel = np.zeros((target_h, int(target_h * 16 / 9), 3), dtype=np.uint8)
            else:
                h, w = frame.shape[:2]
                scale = target_h / float(h)
                new_w = int(w * scale)
                panel = cv2.resize(frame, (new_w, target_h), interpolation=cv2.INTER_AREA)
                
            cv2.rectangle(panel, (0, target_h - 26), (panel.shape[1], target_h), (20, 20, 20), -1)
            cv2.putText(panel, label, (8, target_h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
            panels.append(panel)
            
        sep = np.full((target_h, 3, 3), 40, dtype=np.uint8)
        combined = []
        for i, p in enumerate(panels):
            combined.append(p)
            if i < len(panels) - 1:
                combined.append(sep)
                
        filmstrip = np.hstack(combined)
        os.makedirs(os.path.dirname(out_strip_path), exist_ok=True)
        cv2.imwrite(out_strip_path, filmstrip, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
    return peak_rel_sec, phases, pacing_rec
