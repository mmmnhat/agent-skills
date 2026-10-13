"""
End-to-End Integration test for Harness self-healing repair cycle.
Simulates a damaged timeline, audits invariants, generates patch plan, applies repairs, and re-audits.
"""

import copy
import pytest
from harness.evaluator import HarnessEvaluator
from harness.patch_generator import PatchGenerator
from harness.run_pipeline import build_edit_plan_from_scenes, generate_simulated_timeline_state


def test_full_pipeline_self_healing_cycle():
    test_context = "E:/test-dung-ai/test_skills_run/clean_cut_retest/scenes_context.json"
    fps = 23.976

    # 1. Build normal edit plan and simulated state
    edit_plan = build_edit_plan_from_scenes(test_context, fps=fps)
    clean_state = generate_simulated_timeline_state(edit_plan)

    # 2. Inject artificial defects to stress test the harness:
    # Defect A (INV-01): Introduce a 6-frame black gap between clip 1 and clip 2
    corrupted_state = copy.deepcopy(clean_state)
    corrupted_state["tracks"]["V1"][1]["start_frame"] += 6
    corrupted_state["tracks"]["V1"][1]["end_frame"] += 6

    # Defect B (INV-02): Misalign the SFX for scene 2 by +5 frames
    corrupted_state["tracks"]["A4"][1]["start_frame"] += 5

    # Defect C (INV-04): Misplace an audio clip onto reserved track A2
    corrupted_state["tracks"]["A2"].append({
        "name": "rogue_clip_a2",
        "start_frame": 100,
        "end_frame": 150,
    })

    # Defect D (INV-03): High audio level violating headroom (+0.8 dBFS)
    corrupted_state["master_true_peak_dbfs"] = 0.8

    expected_climaxes = [
        {"incident_id": inc["incident_id"], "mapped_climax_frame": inc["master_timeline"]["mapped_climax_frame"]}
        for inc in edit_plan["incidents"]
    ]

    evaluator = HarnessEvaluator(sequence_fps=fps)

    # First Audit: MUST FAIL with all 4 invariant violations
    qa_report_1 = evaluator.audit_timeline(corrupted_state, expected_climaxes, cycle_index=1)
    assert qa_report_1["overall_status"] == "FAIL_REPAIRABLE"
    assert qa_report_1["invariants_results"]["INV-01"]["status"] == "FAIL"
    assert qa_report_1["invariants_results"]["INV-02"]["status"] == "FAIL"
    assert qa_report_1["invariants_results"]["INV-03"]["status"] == "FAIL"
    assert qa_report_1["invariants_results"]["INV-04"]["status"] == "FAIL"

    # Generate Patch Plan
    patch_plan = PatchGenerator.generate_patch_plan(qa_report_1)
    assert set(patch_plan["triggered_by_invariants"]) == {"INV-01", "INV-02", "INV-03", "INV-04"}

    # Simulate applying patch plan
    repaired_state = copy.deepcopy(corrupted_state)
    for op in patch_plan["operations"]:
        op_type = op["op_type"]
        if op_type == "ripple_delete":
            # Close the gap on V1
            repaired_state["tracks"]["V1"][1]["start_frame"] += op["delta_frames"]
            repaired_state["tracks"]["V1"][1]["end_frame"] += op["delta_frames"]
        elif op_type == "move_clip" and op["track"] == "A4":
            # Re-align SFX
            repaired_state["tracks"]["A4"][1]["start_frame"] += op["delta_frames"]
        elif op_type == "move_clip_to_track":
            # Clear A2
            repaired_state["tracks"]["A2"].clear()
        elif op_type == "adjust_audio_levels":
            # Attenuate master audio
            repaired_state["master_true_peak_dbfs"] += op["gain_db"]

    # Second Audit: MUST PASS 100%
    qa_report_2 = evaluator.audit_timeline(repaired_state, expected_climaxes, cycle_index=2)
    assert qa_report_2["overall_status"] == "PASS"
    assert qa_report_2["invariants_results"]["INV-01"]["status"] == "PASS"
    assert qa_report_2["invariants_results"]["INV-02"]["status"] == "PASS"
    assert qa_report_2["invariants_results"]["INV-03"]["status"] == "PASS"
    assert qa_report_2["invariants_results"]["INV-04"]["status"] == "PASS"
