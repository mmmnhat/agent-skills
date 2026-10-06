#!/usr/bin/env python3
"""
Intelligent Semantic Scene Context Synthesizer for Clip-Inspector
Generates rich narrative, visual, situational, and audio context for video clips.
"""
import os
import sys
from pathlib import Path

def synthesize_scene_context(scene_info, source_title=None):
    """
    Synthesizes a comprehensive semantic context dictionary for a scene.
    """
    scene_id = scene_info.get("scene_id", 1)
    inc_id = scene_info.get("incident_id", 1)
    shot_idx = scene_info.get("shot_index", 1)
    is_cont = scene_info.get("is_continuation", False)
    var_type = scene_info.get("variation_type", "base")
    duration = float(scene_info.get("duration", 3.0))
    aspect_ratio = scene_info.get("aspect_ratio", "16:9")
    has_blur = scene_info.get("has_blur", False)
    
    landmarks = scene_info.get("temporal_landmarks", {})
    peak_sec = float(landmarks.get("action_peak_rel_sec", duration * 0.55))
    phases = landmarks.get("phases", {})
    lead_in = phases.get("lead_in", [0.0, max(0.0, peak_sec - 1.0)])
    climax = phases.get("climax", [max(0.0, peak_sec - 1.0), min(duration, peak_sec + 1.0)])
    recovery = phases.get("recovery", [min(duration, peak_sec + 1.0), duration])

    # 1. Determine Narrative Role & Action Intensity
    if scene_id == 1:
        narrative_role = "Hook / Mở đầu kịch tính"
    elif is_cont:
        narrative_role = f"Góc máy bổ sung (Shot #{shot_idx} của Sự kiện #{inc_id})"
    elif peak_sec <= 2.0 and duration <= 5.0:
        narrative_role = "Cao trào xung kích (Quick Climax)"
    elif duration >= 8.0:
        narrative_role = "Diễn biến tình huống dài (Extended Incident)"
    else:
        narrative_role = "Tình huống kịch tính (Core Action Beat)"

    # 2. Motion Intensity & Action Type
    if duration <= 4.0:
        motion_intensity = "high"
        action_type = "high_motion_burst"
        mood = "shocking_action"
    elif peak_sec < duration * 0.4:
        motion_intensity = "high"
        action_type = "rapid_escalation"
        mood = "tense"
    elif duration >= 10.0:
        motion_intensity = "medium"
        action_type = "continuous_situation"
        mood = "dramatic"
    else:
        motion_intensity = "medium"
        action_type = "standard_action"
        mood = "tense"

    # 3. Framing & Visual Context
    w = scene_info.get("native_resolution", {}).get("width") or scene_info.get("crop_box", {}).get("w", 1920)
    h = scene_info.get("native_resolution", {}).get("height") or scene_info.get("crop_box", {}).get("h", 1080)
    
    if aspect_ratio == "9:16":
        framing_desc = f"Khung dọc di động 9:16 ({w}x{h}) - Phù hợp TikTok / Reels / Shorts"
    elif aspect_ratio == "1:1":
        framing_desc = f"Khung vuông 1:1 ({w}x{h}) - Phù hợp Feed / Multi-platform"
    elif aspect_ratio == "4:5":
        framing_desc = f"Khung dọc mạng xã hội 4:5 ({w}x{h})"
    else:
        framing_desc = f"Khung ngang tiêu chuẩn 16:9 ({w}x{h})"

    if has_blur:
        unblur_status = "Đã bóc tách và khử sạch viền mờ rác hai bên (Clean Unblurred)"
    else:
        unblur_status = "Khung hình nguyên bản (Native Frame)"

    # 4. Continuity Note
    if is_cont or shot_idx > 1:
        relation_note = f"CÙNG SỰ KIỆN #{inc_id}: Cú máy tiếp nối (Shot #{shot_idx}), thay đổi tỷ lệ khung hình hoặc góc phóng đại ({var_type})."
    else:
        relation_note = f"SỰ KIỆN ĐỘC LẬP #{inc_id}: Cú máy đơn độc lập hoàn chỉnh."

    # 5. Situation Summary in Vietnamese
    lead_dur = round(lead_in[1] - lead_in[0], 2)
    climax_dur = round(climax[1] - climax[0], 2)
    rec_dur = round(recovery[1] - recovery[0], 2)
    
    summary_parts = []
    if is_cont:
        summary_parts.append(f"Góc nhìn tiếp theo của sự kiện #{inc_id} ({var_type}, {aspect_ratio}).")
    else:
        summary_parts.append(f"Tình huống diễn ra trong {duration:.2f}s.")
        
    summary_parts.append(f"Khởi điểm diễn biến trong {lead_dur}s đầu.")
    summary_parts.append(f"Đạt đỉnh kịch tính/va chạm hành động tại giây thứ {peak_sec:.2f}s (pha cao trào kéo dài {climax_dur}s).")
    if rec_dur > 0.3:
        summary_parts.append(f"Thu hồi hiện trường/kết thúc trong {rec_dur}s cuối.")
    situation_summary = " ".join(summary_parts)

    # 6. Title
    title = f"Cảnh {scene_id:03d} - {narrative_role.split('(')[0].strip()} [{aspect_ratio}]"

    # 7. Tags
    tags = [
        f"incident_{inc_id}",
        aspect_ratio.replace(":", "_"),
        f"motion_{motion_intensity}",
        mood,
        "clip_inspector"
    ]
    if is_cont:
        tags.append("multi_shot_continuation")
    if has_blur:
        tags.append("unblurred")

    return {
        "title": title,
        "narrative_role": narrative_role,
        "situation_summary": situation_summary,
        "action_type": action_type,
        "motion_intensity": motion_intensity,
        "mood": mood,
        "visual": {
            "framing": framing_desc,
            "aspect_ratio": aspect_ratio,
            "resolution": f"{w}x{h}",
            "unblur_status": unblur_status,
            "variation_type": var_type
        },
        "audio": {
            "peak_impact_time_sec": peak_sec,
            "sound_mood": "impactful_action" if motion_intensity == "high" else "ambient_tension"
        },
        "continuity": {
            "incident_id": inc_id,
            "shot_index": shot_idx,
            "is_multi_shot": bool(is_cont or shot_idx > 1),
            "relation_note": relation_note
        },
        "tags": tags
    }
