#!/usr/bin/env python3
"""
Pacing & Speed Ramping Engine (v2.0 W-Curve & Sequential Edition)
Implements:
1. Multi-Criteria Interest Scoring: S(c) = 0.40 M(c) + 0.35 N(c) + 0.25 A(c)
2. Incident Bundle Preservation: Groups multi-angle & zoom reframe shots atomically
3. Psychological W-Curve Narrative Reordering & Duration Target Fitting
4. Hard Fast-Cut Boundary Calculation
5. Studio 5-Track Sound Design Layout:
   - V1: Video
   - A1: Original Video Clip Audio
   - A2: [BLANK] RESERVED EXCLUSIVELY FOR VOICEOVER
   - A3: Transition SFX (Whoosh synced to cuts)
   - A4: Climax SFX (Punch / Impact synced to Action Peaks)
   - A5: Ducked BGM (-12dB during climax hits)
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from sfx_scoring import get_best_sfx, get_best_bgm
except ImportError:
    from .sfx_scoring import get_best_sfx, get_best_bgm

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

import math

# --- 1. Multi-Criteria Scoring & Metrics ---

def calculate_interest_score(clip):
    """
    Computes S(c) = 0.40 * M(c) + 0.35 * N(c) + 0.25 * A(c)
    with continuous variance based on motion intensity, narrative arc,
    action peak positioning, climax duration, audio dynamics, and duration sweet spot.
    """
    landmarks = clip.get("temporal_landmarks") or clip.get("motion_landmarks") or {}
    ctx = clip.get("context") or {}
    phases = landmarks.get("phases") or {}
    pacing_rec = landmarks.get("pacing_recommendations") or {}
    dur = float(clip.get("duration") or clip.get("duration_sec") or 3.0)
    
    # 1. Motion Score M(c) in [0, 100]
    motion_val = landmarks.get("peak_motion_diff")
    if motion_val is not None:
        m_score = min(100.0, (float(motion_val) / 45.0) * 100.0)
    else:
        m_intensity = ctx.get("motion_intensity", "medium")
        base_m = 85.0 if m_intensity == "high" else (70.0 if m_intensity == "medium" else 55.0)
        
        # Climax phase duration factor (optimal climax duration is ~2.2s)
        climax_phase = phases.get("climax")
        climax_dur = (climax_phase[1] - climax_phase[0]) if climax_phase else (dur * 0.4)
        climax_ratio_factor = math.exp(-((climax_dur - 2.2) ** 2) / (2 * (1.2 ** 2)))
        
        # Action peak golden ratio positioning (~0.58 of clip)
        peak_rel = float(landmarks.get("action_peak_rel_sec") or (dur * 0.55))
        peak_pos_ratio = peak_rel / max(0.5, dur)
        peak_pos_factor = math.exp(-((peak_pos_ratio - 0.58) ** 2) / (2 * (0.18 ** 2)))
        
        # Speed ramp contrast bonus
        lead_speed = float(pacing_rec.get("suggested_speed_ramp", {}).get("lead_in_speed", 1.0))
        speed_factor = 1.08 if lead_speed >= 2.5 else 1.0
        
        m_score = base_m * (0.60 + 0.25 * climax_ratio_factor + 0.15 * peak_pos_factor) * speed_factor
        m_score = min(100.0, max(30.0, m_score))
        
    # 2. Narrative Arc Score N(c) in [0, 100]
    arc_status = (
        phases.get("narrative_arc", {}).get("status")
        or ctx.get("narrative_arc", {}).get("status")
        or pacing_rec.get("narrative_arc")
        or "complete_narrative_arc"
    )
    if "complete" in arc_status:
        n_base = 92.0
    elif "truncated_tail" in arc_status:
        # High curiosity and hook value (shocking unresolved cutoff)
        n_base = 86.0
    elif "truncated_head" in arc_status:
        n_base = 68.0
    elif "fragment" in arc_status:
        n_base = 52.0
    else:
        n_base = 72.0
        
    mood = ctx.get("mood", "")
    mood_bonus = 4.0 if mood == "shocking_unresolved" else (2.0 if mood == "dramatic" else 0.0)
    
    # Emotional resolution presence
    rec_phase = phases.get("recovery")
    rec_bonus = 3.0 if (rec_phase and (rec_phase[1] - rec_phase[0]) >= 0.4) else 0.0
    
    n_score = min(100.0, max(30.0, n_base + mood_bonus + rec_bonus))
    
    # 3. Audio Transient Score A(c) in [0, 100]
    audio_mood = ctx.get("audio", {}).get("sound_mood", "ambient")
    a_base = 88.0 if audio_mood == "impactful_action" else 72.0
    
    peak_rel = float(landmarks.get("action_peak_rel_sec") or (dur * 0.55))
    aud_peak = ctx.get("audio", {}).get("peak_impact_time_sec")
    if aud_peak is not None:
        delta = abs(float(aud_peak) - peak_rel)
        align_factor = math.exp(-delta / 0.4)
    else:
        align_factor = 0.80
    a_score = a_base * (0.80 + 0.20 * align_factor)
    
    snap_delta = abs(float(clip.get("audio", {}).get("start_snap_delta", 0.0)))
    if snap_delta < 0.15:
        a_score += 2.0
    a_score = min(100.0, max(30.0, a_score))
    
    # 4. Duration Sweet Spot Modulation (Clips between 3.0s and 6.5s have optimal retention)
    dur_factor = math.exp(-((dur - 4.5) ** 2) / (2 * (2.5 ** 2)))
    final_score = (0.40 * m_score + 0.35 * n_score + 0.25 * a_score) * (0.92 + 0.08 * dur_factor)
    return round(final_score, 3)

def bundle_incidents(scenes):
    """
    Groups scenes into atomic incident bundles based on incident_id or continuation links.
    Guarantees that sub-shots of the same incident are never split across the timeline.
    """
    bundle_map = {}
    ordered_bundle_ids = []
    
    for i, sc in enumerate(scenes):
        inc_id = sc.get("incident_id")
        if inc_id is None:
            inc_id = f"single_{i+1:03d}"
            
        if inc_id not in bundle_map:
            bundle_map[inc_id] = {
                "incident_id": inc_id,
                "shots": [],
                "scores": [],
                "bundle_score": 0.0,
                "total_raw_duration": 0.0,
                "fast_cut_duration": 0.0
            }
            ordered_bundle_ids.append(inc_id)
            
        s_score = calculate_interest_score(sc)
        sc["interest_score"] = s_score
        b = bundle_map[inc_id]
        b["shots"].append(sc)
        b["scores"].append(s_score)
        
        raw_d = float(sc.get("duration") or sc.get("duration_sec") or 3.0)
        b["total_raw_duration"] += raw_d
        
    # Calculate aggregate bundle score S(I) and fast-cut duration
    bundles = []
    for inc_id in ordered_bundle_ids:
        b = bundle_map[inc_id]
        scores = b["scores"]
        max_s = max(scores) if scores else 70.0
        residual_sum = sum(s for s in scores if s != max_s)
        b["bundle_score"] = round(max_s + 0.10 * residual_sum, 3)
        
        # Estimate fast cut duration for the bundle
        fc_dur = 0.0
        for sc in b["shots"]:
            in_p, out_p = calculate_hard_fast_cut(sc)
            sc["fast_cut_in"] = in_p
            sc["fast_cut_out"] = out_p
            sc["fast_cut_dur"] = round(out_p - in_p, 3)
            fc_dur += sc["fast_cut_dur"]
        b["fast_cut_duration"] = round(fc_dur, 2)
        bundles.append(b)
        
    return bundles

def calculate_hard_fast_cut(scene, delta_pre=1.0, delta_post=1.1, min_dur=2.0, max_dur=3.5):
    """
    Computes tight Premiere Pro In/Out points locking onto the dramatic peak:
    source_in = max(0.0, climax_time - delta_pre)
    source_out = min(duration, climax_time + delta_post)
    """
    raw_dur = float(scene.get("duration") or scene.get("duration_sec") or 3.0)
    landmarks = scene.get("temporal_landmarks") or scene.get("motion_landmarks") or {}
    climax_rel = float(landmarks.get("action_peak_rel_sec") or landmarks.get("climax_sec") or (raw_dur * 0.55))
    
    # If the clip is already very short (<= 2.5s), keep entire clip
    if raw_dur <= min_dur:
        return 0.0, raw_dur
        
    src_in = max(0.0, climax_rel - delta_pre)
    src_out = min(raw_dur, climax_rel + delta_post)
    
    # Ensure minimum brisk length
    cut_len = src_out - src_in
    if cut_len < min_dur:
        needed = min_dur - cut_len
        src_in = max(0.0, src_in - needed / 2.0)
        src_out = min(raw_dur, src_out + needed / 2.0)
        
    # Cap at max fast-cut duration
    if (src_out - src_in) > max_dur:
        excess = (src_out - src_in) - max_dur
        src_in += excess * 0.4
        src_out -= excess * 0.6
        
    # Strictly clamp within physical bounds [0.0, raw_dur]
    src_in = max(0.0, min(src_in, raw_dur - 0.2))
    src_out = min(raw_dur, max(src_in + 0.2, src_out))
    return round(src_in, 3), round(src_out, 3)

# --- 2. W-Curve Dynamic Narrative Reordering ---

def map_w_curve(bundles, target_duration=None):
    """
    Organizes incident bundles into a psychological W-Curve:
    Slot 1: Hook (Peak 1 - Rank 2)
    Slot 2: Valley 1 (Context / Rising Curiosity - Dip to Rise)
    Slot 3: Mid-Peak (Peak 2 - Rank 3)
    Slot 4: Valley 2 (Suspense / Rising Build-up - Dip to Rise)
    Slot 5: Grand Finale (Peak 3 - Rank 1 Ultimate Climax)
    """
    # 1. Target Duration Fitting
    if target_duration and target_duration > 0:
        # Sort by bundle score descending
        sorted_by_score = sorted(bundles, key=lambda b: b["bundle_score"], reverse=True)
        selected = []
        accum_dur = 0.0
        max_dur_allowed = target_duration + 2.5
        
        for b in sorted_by_score:
            b_dur = b["fast_cut_duration"]
            if (accum_dur + b_dur) <= max_dur_allowed or not selected:
                selected.append(b)
                accum_dur += b_dur
            if accum_dur >= target_duration:
                break
        working_bundles = selected
    else:
        working_bundles = list(bundles)
        
    n = len(working_bundles)
    if n <= 2:
        return sorted(working_bundles, key=lambda b: b["bundle_score"], reverse=True)
        
    # Rank bundles by score descending
    ranked = sorted(working_bundles, key=lambda b: b["bundle_score"], reverse=True)
    
    rank_1 = ranked[0]  # Grand Finale (Peak 3 - Rank 1 Ultimate Climax)
    rank_2 = ranked[1]  # Hook (Peak 1 - Rank 2 High Energy Opener)
    rank_3 = ranked[2] if n >= 3 else None  # Mid-Peak (Peak 2 - Rank 3 Midpoint Tension Spike)
    
    remaining = ranked[3:] if n >= 4 else []
    half = len(remaining) // 2
    v1_raw = remaining[:half] if half > 0 else (remaining[:1] if remaining else [])
    v2_raw = remaining[half:] if half > 0 else (remaining[1:] if len(remaining) > 1 else [])
    
    # In Valley 1: sort by ascending score so energy dips after Hook and builds up towards Mid-Peak
    valley_1 = sorted(v1_raw, key=lambda b: b["bundle_score"])
    # In Valley 2: sort by ascending score so energy dips after Mid-Peak and builds up towards Grand Finale
    valley_2 = sorted(v2_raw, key=lambda b: b["bundle_score"])
    
    w_curve_ordered = []
    
    # Slot 1: Hook (Peak 1)
    rank_2["w_curve_slot"] = "Hook (Peak 1)"
    w_curve_ordered.append(rank_2)
    
    # Slot 2: Valley 1 (Context)
    for b in valley_1:
        b["w_curve_slot"] = "Valley 1 (Context)"
        w_curve_ordered.append(b)
        
    # Slot 3: Mid-Peak (Peak 2)
    if rank_3:
        rank_3["w_curve_slot"] = "Mid-Peak (Peak 2)"
        w_curve_ordered.append(rank_3)
        
    # Slot 4: Valley 2 (Suspense)
    for b in valley_2:
        b["w_curve_slot"] = "Valley 2 (Suspense)"
        w_curve_ordered.append(b)
        
    # Slot 5: Grand Finale (Peak 3)
    rank_1["w_curve_slot"] = "Grand Finale (Peak 3)"
    w_curve_ordered.append(rank_1)
    
    return w_curve_ordered

def probe_physical_durations(scenes):
    """
    Scans physical .mp4 files on disk in parallel with ffprobe to get exact media container duration.
    Prevents any discrepancy between split theoretical timestamps and container GOP boundaries.
    """
    from concurrent.futures import ThreadPoolExecutor
    import subprocess
    
    files_to_probe = []
    for sc in scenes:
        p = sc.get("clip_path") or sc.get("file_path")
        if p and os.path.exists(p):
            files_to_probe.append(p)
            
    if not files_to_probe:
        return {}
        
    def _probe_one(fpath):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", fpath],
                capture_output=True, text=True, timeout=5
            )
            data = json.loads(r.stdout)
            return fpath, float(data["format"]["duration"])
        except Exception:
            return fpath, None

    dur_map = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for fpath, d in ex.map(_probe_one, files_to_probe):
            if d is not None:
                dur_map[fpath] = d
    return dur_map

# --- 3. Master Pacing Plan Generator ---

def generate_pacing_plan(
    scenes_input,
    sequence_name="Pacing_Master",
    platform="reels_shorts",
    mode="sequential",
    target_duration=None,
    cut_mode="fast-cut",
    add_sfx=True,
    add_bgm=True
):
    """
    Constructs the complete 5-Track Timeline Manifest.
    Modes:
      - 'sequential': Preserves 100% of input sequence. Applies hard fast-cut trimming.
      - 'w-curve': Evaluates Interest Score, preserves incident bundles, fits target-duration,
                   and reorders into W-curve narrative topology.
    """
    platform_cfg = CONFIG.get("target_platforms", {}).get(platform, {
        "aspect_ratio": "9:16",
        "resolution": [1080, 1920],
        "fps": 60,
        "max_clip_duration_sec": 4.5,
        "speed_ramp_climax": 0.5
    })

    scenes = []
    if isinstance(scenes_input, (str, Path)):
        p = Path(scenes_input).resolve()
        if p.is_file() and p.suffix.lower() == ".json":
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                scenes = data.get("scenes", [])
        elif p.is_dir():
            for f in sorted(p.glob("*.mp4")):
                scenes.append({"clip_path": str(f).replace("\\", "/"), "scene_id": f.stem, "duration_sec": 4.0})
    elif isinstance(scenes_input, list):
        scenes = scenes_input

    if not scenes:
        raise ValueError("No valid scenes provided to pacing engine.")

    # 0. Sync real physical media durations to eliminate zebra stripes and black gaps
    phys_durs = probe_physical_durations(scenes)
    for sc in scenes:
        cp = sc.get("clip_path") or sc.get("file_path")
        if cp in phys_durs:
            real_d = round(phys_durs[cp], 3)
            sc["duration"] = real_d
            sc["duration_sec"] = real_d

    # 1. Bundle multi-shot incidents
    bundles = bundle_incidents(scenes)

    # 2. Reorder or filter based on mode
    if mode == "w-curve":
        final_bundles = map_w_curve(bundles, target_duration=target_duration)
    else:
        # Sequential mode: Keep chronological bundle order, optionally apply target duration
        if target_duration and target_duration > 0:
            selected = []
            accum = 0.0
            for b in bundles:
                selected.append(b)
                accum += b["fast_cut_duration"]
                if accum >= target_duration:
                    break
            final_bundles = selected
        else:
            final_bundles = bundles

    # 3. Flatten bundles to timeline clips
    timeline_scenes = []
    for b in final_bundles:
        slot_label = b.get("w_curve_slot", "Sequential Flow")
        for sc in b["shots"]:
            sc["narrative_role"] = slot_label
            sc["bundle_id"] = b["incident_id"]
            timeline_scenes.append(sc)

    # 4. Construct Studio 5-Track Timeline Layout
    v1_track = []
    a1_track = []
    a2_track = []  # RESERVED BLANK FOR VOICEOVER
    a3_track = []  # Transition SFX
    a4_track = []  # Climax SFX
    a5_track = []  # Ducked BGM

    current_timeline_time = 0.0

    whoosh_asset = get_best_sfx(CONFIG.get("sound_design", {}).get("transition_sfx_intent", "whoosh chuyen canh"))
    impact_asset = get_best_sfx(CONFIG.get("sound_design", {}).get("climax_sfx_intent", "impact boom"))

    for i, sc in enumerate(timeline_scenes):
        clip_path = sc.get("clip_path") or sc.get("file_path")
        if not clip_path or not os.path.exists(clip_path):
            continue

        raw_dur = float(sc.get("duration") or sc.get("duration_sec") or 3.0)
        
        # Calculate In/Out boundaries
        if cut_mode == "fast-cut":
            src_in, src_out = calculate_hard_fast_cut(sc)
        else:
            src_in = 0.0
            src_out = min(raw_dur, platform_cfg.get("max_clip_duration_sec", 4.5))
            
        # Hard clamp within physical bounds
        src_in = max(0.0, min(src_in, raw_dur - 0.1))
        src_out = min(raw_dur, max(src_in + 0.1, src_out))
        effective_dur = round(src_out - src_in, 3)
        landmarks = sc.get("temporal_landmarks") or sc.get("motion_landmarks") or {}
        climax_raw = float(landmarks.get("action_peak_rel_sec") or landmarks.get("climax_sec") or (raw_dur * 0.55))
        
        # Climax relative to trimmed source_in
        climax_trimmed = max(0.2, min(effective_dur - 0.2, climax_raw - src_in))

        clip_timeline_in = round(current_timeline_time, 3)
        clip_timeline_out = round(clip_timeline_in + effective_dur, 3)
        climax_timeline_time = round(clip_timeline_in + climax_trimmed, 3)

        # Video Track (V1)
        v1_track.append({
            "clip_id": sc.get("scene_id", f"scene_{i+1:03d}"),
            "file_path": clip_path,
            "timeline_in": clip_timeline_in,
            "timeline_out": clip_timeline_out,
            "source_in": src_in,
            "source_out": src_out,
            "duration": effective_dur,
            "interest_score": sc.get("interest_score", 75.0),
            "narrative_role": sc.get("narrative_role", "Sequential"),
            "bundle_id": sc.get("bundle_id"),
            "aspect_ratio": sc.get("aspect_ratio", "9:16"),
            "optical_flow": True,
            "climax_marker": climax_timeline_time
        })

        # Track A1: Original Video Audio
        a1_track.append({
            "clip_id": f"audio_orig_{i+1:03d}",
            "file_path": clip_path,
            "timeline_in": clip_timeline_in,
            "timeline_out": clip_timeline_out,
            "source_in": src_in,
            "source_out": src_out
        })

        if add_sfx:
            # Track A3: Transition SFX (Whoosh at cut points, except clip 1)
            if i > 0 and whoosh_asset:
                a3_track.append({
                    "sfx_id": f"whoosh_cut_{i:03d}",
                    "file_path": whoosh_asset["file_path"],
                    "role": "transition",
                    "timeline_in": max(0.0, clip_timeline_in - 0.20),
                    "volume_db": CONFIG.get("sound_design", {}).get("default_volumes", {}).get("sfx_db", -3.0)
                })

            # Track A4: Climax SFX (Punch / Impact at action peak)
            if impact_asset:
                a4_track.append({
                    "sfx_id": f"climax_hit_{i:03d}",
                    "file_path": impact_asset["file_path"],
                    "role": "climax_impact",
                    "timeline_in": climax_timeline_time,
                    "volume_db": CONFIG.get("sound_design", {}).get("default_volumes", {}).get("sfx_db", -1.0)
                })

        current_timeline_time = clip_timeline_out

    # Track A5: Ducked Background Music
    if add_bgm and current_timeline_time > 0.0:
        bgm_asset = get_best_bgm()
        if bgm_asset:
            a5_track.append({
                "bgm_id": "master_bgm",
                "file_path": bgm_asset["file_path"],
                "timeline_in": 0.0,
                "timeline_out": round(current_timeline_time, 3),
                "ducked_db": -12.0
            })

    manifest = {
        "sequence_name": sequence_name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "cut_mode": cut_mode,
        "target_duration_requested": target_duration,
        "format": {
            "aspect_ratio": platform_cfg.get("aspect_ratio", "9:16"),
            "resolution": platform_cfg.get("resolution", [1080, 1920]),
            "fps": platform_cfg.get("fps", 60)
        },
        "total_duration_seconds": round(current_timeline_time, 3),
        "total_scenes": len(v1_track),
        "total_incident_bundles": len(final_bundles),
        "tracks": {
            "V1": v1_track,
            "A1": a1_track,
            "A2": a2_track,  # Reserved for Voiceover
            "A3": a3_track,  # Transition SFX
            "A4": a4_track,  # Climax SFX
            "A5": a5_track   # Ducked BGM
        }
    }
    return manifest
