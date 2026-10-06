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
    t1 = start_sec + min(duration * 0.12, 1.0)
    t2 = start_sec + (duration * 0.40)
    t3 = start_sec + (duration * 0.65)
    t4 = start_sec + min(duration * 0.88, max(0.1, duration - 0.3))
    timestamps = [t1, t2, t3, t4]

    panels_raw = []
    grays = []
    for t in timestamps:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ret, frame = cap.read()
        if not ret or frame is None:
            panels_raw.append(None)
            grays.append(None)
            continue
        if crop_box:
            cbx, cby, cbw, cbh = crop_box
            if cbw > 10 and cbh > 10 and cby + cbh <= frame.shape[0] and cbx + cbw <= frame.shape[1]:
                frame = frame[cby:cby+cbh, cbx:cbx+cbw]
        panels_raw.append(frame)
        small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        grays.append(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))

    motion_diffs = []
    for i in range(1, len(grays)):
        if grays[i] is not None and grays[i-1] is not None:
            motion_diffs.append(float(np.mean(cv2.absdiff(grays[i], grays[i-1]))))
        else:
            motion_diffs.append(0.0)

    peak_idx = int(np.argmax(motion_diffs)) if motion_diffs else 1
    sample_peaks = [round(duration * 0.35, 2), round(duration * 0.60, 2), round(duration * 0.80, 2)]
    peak_rel_sec = sample_peaks[peak_idx] if peak_idx < len(sample_peaks) else round(duration * 0.60, 2)
    peak_score = max(motion_diffs) if motion_diffs else 0.0

    # Detect whether the clip is an incomplete fragment
    has_no_recovery_room = bool((duration - peak_rel_sec) <= 1.0)
    is_tail_truncated = bool(has_no_recovery_room and peak_score > 2.0)
    has_no_lead_room = bool(peak_rel_sec <= 0.8)
    is_head_truncated = bool(has_no_lead_room and peak_score > 2.0)

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

    # Assemble 4 Keyframe Panels for Filmstrip using already fetched frames
    if out_strip_path:
        target_h = 240
        panels = []
        for i, frame in enumerate(panels_raw):
            label = panel_labels[i]
            if frame is None:
                panel = np.zeros((target_h, int(target_h * 16 / 9), 3), dtype=np.uint8)
            else:
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
