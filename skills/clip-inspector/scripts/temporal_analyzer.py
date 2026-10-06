#!/usr/bin/env python3
"""
Unified Temporal Motion, Pacing & Filmstrip Generator
Processes temporal motion curve and stitches 4-frame visual filmstrips
in a single unified pass using a shared VideoCapture handle.
"""
import os
import cv2
import numpy as np

def analyze_and_generate_filmstrip(cap, fps, start_sec, end_sec, out_strip_path=None, num_samples=12, crop_box=None):
    """
    Analyzes visual motion energy across [start_sec, end_sec] using an open `cap` handle,
    locates Action Peak, segments pacing phases, and stitches a 4-frame filmstrip.
    crop_box: optional (x, y, w, h) in cap frame coordinates.
    """
    duration = max(0.5, end_sec - start_sec)
    margin = min(0.15, duration * 0.04)
    sample_times = np.linspace(start_sec + margin, end_sec - margin, num_samples)
    
    prev_gray = None
    motion_scores = []
    
    # 1. Motion curve analysis
    for t in sample_times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ret, frame = cap.read()
        if not ret or frame is None:
            motion_scores.append(0.0)
            continue
            
        if crop_box:
            cbx, cby, cbw, cbh = crop_box
            if cbw > 10 and cbh > 10 and cby + cbh <= frame.shape[0] and cbx + cbw <= frame.shape[1]:
                frame = frame[cby:cby+cbh, cbx:cbx+cbw]

        small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            motion_scores.append(float(np.mean(diff)))
        else:
            motion_scores.append(0.0)
        prev_gray = gray
        
    peak_score = max(motion_scores) if motion_scores else 0.0
    head_score = float(np.mean(motion_scores[:2])) if len(motion_scores) >= 2 else 0.0
    tail_score = float(np.mean(motion_scores[-2:])) if len(motion_scores) >= 2 else 0.0

    if len(motion_scores) > 2 and peak_score > 1.0:
        peak_idx = int(np.argmax(motion_scores))
        peak_rel_sec = round(float(sample_times[peak_idx] - start_sec), 2)
    else:
        peak_idx = int(len(motion_scores) * 0.6)
        peak_rel_sec = round(duration * 0.60, 2)

    # Detect whether the clip is an incomplete fragment (cut off in mid-action or entry mid-action)
    has_no_recovery_room = bool((duration - peak_rel_sec) <= 1.0)
    is_tail_truncated = bool(has_no_recovery_room or (peak_score > 1.0 and (tail_score >= peak_score * 0.55 or peak_idx >= len(motion_scores) - 2)))
    
    has_no_lead_room = bool(peak_rel_sec <= 0.8)
    is_head_truncated = bool(has_no_lead_room or (peak_score > 1.0 and (head_score >= peak_score * 0.55 or peak_idx <= 1)))

    if is_tail_truncated and not is_head_truncated:
        arc_status = "truncated_tail_mid_climax"
        arc_summary = "Cắt lửng giữa cao trào (Chưa tiếp đất / khuyết thiếu phản ứng do bị tách thành 2-3 clip nhỏ)"
        climax_start = max(0.0, round(peak_rel_sec - 1.2, 2))
        climax_end = round(duration, 2)
        recovery_phase = None
        panel_labels = ("1: Setup", "2: Build-up", "3: Climax Takeoff", "4: In-Flight (Cutoff)")
    elif is_head_truncated and not is_tail_truncated:
        arc_status = "truncated_head_mid_action"
        arc_summary = "Tiếp nối hành động dở dang (Khuyết thiếu phần setup ban đầu)"
        climax_start = 0.0
        climax_end = min(duration, round(peak_rel_sec + 1.2, 2))
        recovery_phase = [climax_end, round(duration, 2)]
        panel_labels = ("1: Mid-Action Entry", "2: Impact Climax", "3: Crash / Fall", "4: Reaction / Rest")
    elif is_tail_truncated and is_head_truncated:
        arc_status = "mid_action_fragment"
        arc_summary = "Mảnh hành động giữa chừng (Khuyết thiếu cả setup mở đầu và phản ứng kết thúc)"
        climax_start = 0.0
        climax_end = round(duration, 2)
        recovery_phase = None
        panel_labels = ("1: Action Entry", "2: Mid-Flight", "3: Motion Peak", "4: Action Cutoff")
    else:
        arc_status = "complete_narrative_arc"
        arc_summary = "Trọn vẹn tình huống (Setup -> Build-up -> Climax -> Reaction)"
        climax_start = max(0.0, round(peak_rel_sec - 1.2, 2))
        climax_end = min(duration, round(peak_rel_sec + 1.2, 2))
        recovery_phase = [climax_end, round(duration, 2)]
        panel_labels = ("1: Setup", "2: Build-up", "3: Climax", "4: Reaction")

    phases = {
        "lead_in": [0.0, climax_start],
        "climax": [climax_start, climax_end],
        "recovery": recovery_phase,
        "narrative_arc": {
            "is_complete_arc": (arc_status == "complete_narrative_arc"),
            "status": arc_status,
            "summary": arc_summary,
            "is_tail_truncated": is_tail_truncated,
            "is_head_truncated": is_head_truncated,
            "panel_labels": list(panel_labels)
        }
    }
    
    pacing_rec = {
        "is_long_clip": bool(duration >= 6.0),
        "is_complete_arc": bool(arc_status == "complete_narrative_arc"),
        "suggested_trim": {
            "in_sec": float(max(0.0, round(peak_rel_sec - 1.5, 2))),
            "out_sec": float(min(duration, round(peak_rel_sec + 2.0, 2))),
            "trimmed_duration": float(round(min(duration, peak_rel_sec + 2.0) - max(0.0, peak_rel_sec - 1.5), 2))
        },
        "suggested_speed_ramp": {
            "lead_in_speed": 3.0 if climax_start > 2.0 else 1.0,
            "climax_speed": 1.0,
            "recovery_speed": 1.5 if recovery_phase and (duration - climax_end) > 2.0 else 1.0,
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
        t4 = start_sec + min(duration * 0.88, max(0.1, duration - 0.3))
        
        target_h = 240
        panels = []
        timestamps = [
            (t1, panel_labels[0]),
            (t2, panel_labels[1]),
            (t3, panel_labels[2]),
            (t4, panel_labels[3])
        ]
        
        for t_sec, label in timestamps:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(t_sec * fps))
            ret, frame = cap.read()
            if not ret or frame is None:
                panel = np.zeros((target_h, int(target_h * 16 / 9), 3), dtype=np.uint8)
            else:
                if crop_box:
                    cbx, cby, cbw, cbh = crop_box
                    if cbw > 10 and cbh > 10 and cby + cbh <= frame.shape[0] and cbx + cbw <= frame.shape[1]:
                        frame = frame[cby:cby+cbh, cbx:cbx+cbw]
                h, w = frame.shape[:2]
                scale = target_h / float(h)
                new_w = max(10, int(w * scale))
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
