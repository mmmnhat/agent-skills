"""
Pipeline Runner: Integrates Source Understanding manifest with TimeMapper, AudioDecisionEngine,
HarnessEvaluator, and PatchGenerator.
Can be executed standalone or invoked by the Director Agent.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.time_mapper import TimeMapper
from harness.audio_decision_engine import AudioDecisionEngine
from harness.evaluator import HarnessEvaluator
from harness.patch_generator import PatchGenerator



def build_edit_plan_from_scenes(
    scenes_context_path: str,
    project_name: str = "Automated_Master_Assembly",
    fps: float = 23.976,
    resolution: List[int] = [1920, 1080],
    target_duration_sec: Optional[float] = 30.0,
) -> Dict[str, Any]:
    """
    Transforms scenes_context.json into a validated EditPlan with contiguous timeline placement
    and adaptive sound operations.
    """
    with open(scenes_context_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenes = data.get("scenes", [])
    if not scenes:
        raise ValueError(f"No scenes found in {scenes_context_path}")

    time_mapper = TimeMapper(default_sequence_fps=fps)
    audio_engine = AudioDecisionEngine()

    raw_incidents = []
    for idx, sc in enumerate(scenes):
        sc_id = str(sc.get("scene_id", idx + 1))
        file_path = sc.get("file_path", "")
        duration_sec = sc.get("duration", 5.0)
        total_frames = sc.get("total_frames", int(duration_sec * fps))

        landmarks = sc.get("temporal_landmarks", {})
        peak_rel_sec = landmarks.get("action_peak_rel_sec", duration_sec * 0.5)
        climax_frame = int(peak_rel_sec * fps)

        # Build source_ref
        source_ref = {
            "media_path": file_path,
            "source_fps": fps,
            "source_in_frame": 0,
            "source_climax_frame": climax_frame,
            "source_out_frame": total_frames,
        }

        # Role assignment (e.g. Hook for #1, then sequential)
        pacing_role = "HOOK_RANK_2" if idx == 0 else "SEQUENTIAL_CLIP"

        raw_incidents.append({
            "incident_id": f"scene_{sc_id}",
            "pacing_role": pacing_role,
            "source_ref": source_ref,
            "metadata": {
                "audio_transient_detected": sc.get("audio", {}).get("has_transient", False),
                "transient_dbfs": sc.get("audio", {}).get("transient_dbfs", -40.0),
                "speech_detected": sc.get("has_speech", False),
                "material_type": sc.get("material_type", "general"),
            },
        })

    # Assemble contiguous timeline
    assembled = time_mapper.assemble_contiguous_timeline(raw_incidents, start_frame=0, sequence_fps=fps)

    # Evaluate sound operations for each assembled incident
    for idx, inc in enumerate(assembled):
        meta = inc.pop("metadata", {})
        mapped_climax = inc["master_timeline"]["mapped_climax_frame"]
        seq_in = inc["master_timeline"]["sequence_in_frame"]

        sound_ops = audio_engine.evaluate_incident_audio(
            scene_metadata=meta,
            mapped_climax_frame=mapped_climax,
            sequence_in_frame=seq_in,
            is_first_incident=(idx == 0),
        )
        inc["sound_operations"] = sound_ops

    edit_plan = {
        "$schema": "../schemas/edit_plan.schema.json",
        "plan_id": f"plan_{Path(scenes_context_path).stem}",
        "project_name": project_name,
        "target_duration_sec": target_duration_sec,
        "resolution": resolution,
        "fps": fps,
        "audio_layout": {
            "V1": "Video Clips",
            "V2": "Adjustment Layers / Visual Shields",
            "A1": "Original Ambient Sound",
            "A2": "Voiceover (Reserved Blank)",
            "A3": "Transition Whoosh SFX",
            "A4": "Action Climax Impacts",
            "A5": "Background Music (Ducked)",
        },
        "incidents": assembled,
    }
    return edit_plan


def generate_simulated_timeline_state(edit_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a simulated Premiere Pro sequence state dictionary from an EditPlan
    for headless harness auditing.
    """
    v1_clips = []
    a4_clips = []
    a3_clips = []
    a5_clips = []

    for inc in edit_plan.get("incidents", []):
        inc_id = inc["incident_id"]
        mt = inc["master_timeline"]
        v1_clips.append({
            "name": f"{inc_id}_v1",
            "start_frame": mt["sequence_in_frame"],
            "end_frame": mt["sequence_out_frame"],
        })

        for sfx in inc.get("sound_operations", []):
            track = sfx.get("track", "")
            sync_frame = sfx.get("sync_to_master_frame", 0)
            clip_name = f"{inc_id}_{sfx.get('type')}"
            clip_entry = {
                "name": clip_name,
                "start_frame": sync_frame,
                "end_frame": sync_frame + 24,  # ~1.0s default SFX length
            }
            if track == "A4":
                a4_clips.append(clip_entry)
            elif track == "A3":
                a3_clips.append(clip_entry)
            elif track == "A5":
                a5_clips.append(clip_entry)

    timeline_state = {
        "sequence_name": edit_plan.get("project_name", "Master_Sequence"),
        "tracks": {
            "V1": v1_clips,
            "V2": [],
            "A1": [],  # Original audio linked to V1
            "A2": [],  # MUST BE EMPTY
            "A3": a3_clips,
            "A4": a4_clips,
            "A5": a5_clips,
        },
        "master_true_peak_dbfs": -2.4,  # Compliant headroom
        "review_frames_captured": [],
    }
    return timeline_state


def run_pipeline(
    scenes_context_path: str,
    output_state_dir: str = "state",
    fps: float = 23.976,
) -> Dict[str, Any]:
    """
    Executes the complete pipeline:
    1. Compiles EditPlan
    2. Simulates Timeline State
    3. Audits via HarnessEvaluator
    4. Generates PatchPlan if needed
    Saves state files to output_state_dir.
    """
    os.makedirs(output_state_dir, exist_ok=True)

    # 1. Compile EditPlan
    edit_plan = build_edit_plan_from_scenes(scenes_context_path, fps=fps)
    edit_plan_file = Path(output_state_dir) / "edit-plan.json"
    with open(edit_plan_file, "w", encoding="utf-8") as f:
        json.dump(edit_plan, f, indent=2, ensure_ascii=False)

    # 2. Extract expected climaxes
    expected_climaxes = []
    for inc in edit_plan["incidents"]:
        # Only check impact SFX climaxes if an A4 sound op exists
        has_a4 = any(s.get("track") == "A4" for s in inc.get("sound_operations", []))
        if has_a4:
            expected_climaxes.append({
                "incident_id": inc["incident_id"],
                "mapped_climax_frame": inc["master_timeline"]["mapped_climax_frame"],
            })

    # 3. Simulate Timeline State
    timeline_state = generate_simulated_timeline_state(edit_plan)

    # 4. Harness Audit
    evaluator = HarnessEvaluator(sequence_fps=fps)
    qa_report = evaluator.audit_timeline(
        timeline_state=timeline_state,
        expected_climaxes=expected_climaxes,
        cycle_index=1,
    )
    qa_report_file = Path(output_state_dir) / "qa-report.json"
    with open(qa_report_file, "w", encoding="utf-8") as f:
        json.dump(qa_report, f, indent=2, ensure_ascii=False)

    # 5. Patch Generator
    patch_plan = PatchGenerator.generate_patch_plan(qa_report)
    patch_plan_file = Path(output_state_dir) / "patch-plan.json"
    with open(patch_plan_file, "w", encoding="utf-8") as f:
        json.dump(patch_plan, f, indent=2, ensure_ascii=False)

    return {
        "edit_plan_path": str(edit_plan_file),
        "qa_report_path": str(qa_report_file),
        "patch_plan_path": str(patch_plan_file),
        "overall_status": qa_report.get("overall_status"),
        "total_incidents": len(edit_plan["incidents"]),
    }


if __name__ == "__main__":
    test_context = "E:/test-dung-ai/test_skills_run/clean_cut_retest/scenes_context.json"
    if os.path.exists(test_context):
        summary = run_pipeline(test_context)
        print(f"Pipeline executed successfully: {json.dumps(summary, indent=2)}")
    else:
        print(f"Test context not found: {test_context}")
