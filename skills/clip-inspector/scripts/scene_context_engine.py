#!/usr/bin/env python3
"""
Intelligent Semantic Scene Context Synthesizer for Clip-Inspector
Generates rich narrative, visual, situational, and audio context for video clips.
Accurately diagnoses incomplete action fragments where events are split into 2-3 clips.
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
    arc_info = phases.get("narrative_arc", {})
    
    is_tail_truncated = arc_info.get("is_tail_truncated", False)
    is_head_truncated = arc_info.get("is_head_truncated", False)
    is_complete_arc = arc_info.get("is_complete_arc", not (is_tail_truncated or is_head_truncated))

    lead_in = phases.get("lead_in", [0.0, max(0.0, peak_sec - 1.0)])
    climax = phases.get("climax", [max(0.0, peak_sec - 1.0), min(duration, peak_sec + 1.0)])
    recovery = phases.get("recovery") or [min(duration, peak_sec + 1.0), duration]

    # 1. Determine Narrative Role, Completeness & Action Diagnosis
    if is_tail_truncated and not is_head_truncated:
        narrative_role = f"Phần 1: Khởi phát & Cắt lửng trên không (Cần ghép clip sau)"
        action_type = "mid_air_jump_cutoff"
        mood = "shocking_unresolved"
        structural_diagnosis = (
            "Cấu trúc Setup-Build up-Climax-Reaction chưa trọn vẹn do đây là clip chưa hoàn chỉnh "
            "(tình huống bị tách ra làm 2-3 clip nhỏ). Cảnh kết thúc lửng khi người/vật thể đang ở giữa không trung, "
            "chưa có pha tiếp đất (Impact) và phản ứng (Reaction)."
        )
        missing_phases = ["impact_landing", "reaction_recovery"]
    elif is_head_truncated and not is_tail_truncated:
        narrative_role = f"Phần {shot_idx}: Tiếp đất & Va chạm & Phản ứng (Phần tiếp nối)"
        action_type = "landing_impact_reaction"
        mood = "dramatic_resolution"
        structural_diagnosis = (
            f"Clip tiếp nối của sự kiện #{inc_id}: Bắt đầu ngay lúc đang bay/rơi (khuyết thiếu setup ban đầu), "
            "tiếp đất va chạm và hoàn tất bằng phản ứng hiện trường."
        )
        missing_phases = ["initial_setup", "approach_takeoff"]
    elif is_tail_truncated and is_head_truncated:
        narrative_role = "Mảnh cao trào giữa chừng (Incomplete Mid-action)"
        action_type = "mid_action_fragment"
        mood = "tense"
        structural_diagnosis = (
            "Clip hành động giữa chừng: Khuyết thiếu cả phần mở đầu chuẩn bị lẫn kết thúc phản ứng do bị cắt vụn."
        )
        missing_phases = ["setup", "reaction"]
    else:
        if scene_id == 1:
            narrative_role = "Hook / Mở đầu trọn vẹn"
        elif duration >= 8.0:
            narrative_role = "Diễn biến tình huống dài trọn vẹn (Complete Incident Arc)"
        else:
            narrative_role = "Tình huống kịch tính trọn vẹn (Setup -> Climax -> Reaction)"
        action_type = "complete_action_arc"
        mood = "dramatic"
        structural_diagnosis = "Cấu trúc trọn vẹn đầy đủ 4 giai đoạn: Setup -> Build-up -> Climax -> Reaction/Recovery."
        missing_phases = []

    # 2. Motion Intensity
    motion_intensity = "high" if (duration <= 5.0 or peak_sec <= 2.5 or is_tail_truncated) else "medium"

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

    unblur_status = "Đã bóc tách và khử sạch viền mờ rác hai bên (Clean Unblurred)" if has_blur else "Khung hình nguyên bản (Native Frame)"

    # 4. Continuity Note
    same_grp = scene_info.get("same_scene_group", {})
    if same_grp.get("is_multi_shot"):
        tot_shots = same_grp.get("total_shots_in_incident", 2)
        all_clips = same_grp.get("all_incident_clips", [])
        relation_note = f"CÙNG SỰ KIỆN #{inc_id}: Phân đoạn {shot_idx}/{tot_shots} trong chuỗi clip ({', '.join(all_clips)})."
    else:
        relation_note = f"SỰ KIỆN ĐỘC LẬP #{inc_id}: Cú máy đơn độc lập."

    # 5. Situation Summary in Vietnamese
    lead_dur = round(lead_in[1] - lead_in[0], 2)
    climax_dur = round(climax[1] - climax[0], 2)
    rec_dur = round(recovery[1] - recovery[0], 2) if recovery else 0.0

    summary_parts = []
    if not is_complete_arc:
        summary_parts.append(f"[{structural_diagnosis}]")
    else:
        summary_parts.append(f"Tình huống trọn vẹn trong {duration:.2f}s.")

    summary_parts.append(f"Khởi điểm diễn biến trong {lead_dur}s đầu.")
    summary_parts.append(f"Đạt đỉnh kịch tính/va chạm tại {peak_sec:.2f}s (pha cao trào kéo dài {climax_dur}s).")
    if recovery and rec_dur > 0.3:
        summary_parts.append(f"Hồi phục/phản ứng hiện trường trong {rec_dur}s cuối.")
    elif is_tail_truncated:
        summary_parts.append(f"Cảnh bị cắt dở tại {duration:.2f}s khi đang bay trên không (không có pha phản ứng trong clip này).")
    situation_summary = " ".join(summary_parts)

    title = f"Cảnh {scene_id:03d} - {narrative_role.split('(')[0].strip()} [{aspect_ratio}]"

    tags = [
        f"incident_{inc_id}",
        aspect_ratio.replace(":", "_"),
        f"motion_{motion_intensity}",
        mood
    ]
    if not is_complete_arc:
        tags.extend(["incomplete_fragment", "needs_continuation_stitch"])
    else:
        tags.append("complete_arc")

    return {
        "title": title,
        "narrative_role": narrative_role,
        "situation_summary": situation_summary,
        "action_type": action_type,
        "motion_intensity": motion_intensity,
        "mood": mood,
        "narrative_arc": {
            "is_complete_arc": is_complete_arc,
            "status": arc_info.get("status", "complete_narrative_arc"),
            "structural_diagnosis": structural_diagnosis,
            "missing_phases": missing_phases,
            "panel_labels": arc_info.get("panel_labels", ["1: Setup", "2: Build-up", "3: Climax", "4: Reaction"])
        },
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
            "is_multi_shot": bool(is_cont or shot_idx > 1 or same_grp.get("is_multi_shot")),
            "relation_note": relation_note
        },
        "tags": tags
    }
