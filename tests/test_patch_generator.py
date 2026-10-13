"""
Unit tests for PatchGenerator module.
"""

import pytest
from harness.patch_generator import PatchGenerator


def test_patch_for_gaps():
    mock_qa = {
        "sequence_name": "Test_Seq",
        "cycle_index": 1,
        "overall_status": "FAIL_REPAIRABLE",
        "invariants_results": {
            "INV-01": {
                "status": "FAIL",
                "violations": [
                    {"gap_start_frame": 50, "gap_end_frame": 55, "gap_size_frames": 5}
                ],
            }
        },
    }

    plan = PatchGenerator.generate_patch_plan(mock_qa)
    assert "INV-01" in plan["triggered_by_invariants"]
    assert len(plan["operations"]) == 1

    op = plan["operations"][0]
    assert op["op_type"] == "ripple_delete"
    assert op["track"] == "V1"
    assert op["start_frame"] == 50
    assert op["end_frame"] == 55
    assert op["delta_frames"] == -5


def test_patch_for_misaligned_sfx():
    mock_qa = {
        "sequence_name": "Test_Seq",
        "cycle_index": 1,
        "overall_status": "FAIL_REPAIRABLE",
        "invariants_results": {
            "INV-02": {
                "status": "FAIL",
                "violations": [
                    {
                        "clip_name": "sfx_metal_01",
                        "expected_frame": 100,
                        "actual_frame": 104,
                        "delta_frames": 4,
                    }
                ],
            }
        },
    }

    plan = PatchGenerator.generate_patch_plan(mock_qa)
    assert "INV-02" in plan["triggered_by_invariants"]
    op = plan["operations"][0]
    assert op["op_type"] == "move_clip"
    assert op["track"] == "A4"
    assert op["clip_name"] == "sfx_metal_01"
    assert op["delta_frames"] == -4
    assert op["start_frame"] == 100


def test_patch_for_headroom_violation():
    mock_qa = {
        "sequence_name": "Test_Seq",
        "cycle_index": 1,
        "overall_status": "FAIL_REPAIRABLE",
        "invariants_results": {
            "INV-03": {
                "status": "FAIL",
                "violations": [{"overshoot_db": 1.2}],
            }
        },
    }

    plan = PatchGenerator.generate_patch_plan(mock_qa)
    assert "INV-03" in plan["triggered_by_invariants"]
    op = plan["operations"][0]
    assert op["op_type"] == "adjust_audio_levels"
    assert op["track"] == "Master"
    # -(1.2 + 0.5) = -1.7 dB
    assert op["gain_db"] == -1.7


def test_patch_for_voiceover_track_violation():
    mock_qa = {
        "sequence_name": "Test_Seq",
        "cycle_index": 1,
        "overall_status": "FAIL_REPAIRABLE",
        "invariants_results": {
            "INV-04": {
                "status": "FAIL",
                "violations": [{"clip_name": "whoosh_01", "start_frame": 24}],
            }
        },
    }

    plan = PatchGenerator.generate_patch_plan(mock_qa)
    assert "INV-04" in plan["triggered_by_invariants"]
    op = plan["operations"][0]
    assert op["op_type"] == "move_clip_to_track"
    assert op["track"] == "A2"
    assert op["dest_track"] == "A3"


def test_patch_for_circuit_breaker_rollback():
    mock_qa = {
        "sequence_name": "Test_Seq",
        "cycle_index": 3,
        "overall_status": "CIRCUIT_BREAKER_TRIPPED",
        "invariants_results": {
            "INV-01": {
                "status": "FAIL",
                "violations": [{"gap_start_frame": 100, "reason": "Persistent gap"}],
            }
        },
    }

    plan = PatchGenerator.generate_patch_plan(mock_qa)
    assert plan["action"] == "CIRCUIT_BREAKER_ROLLBACK_AND_FLAG"
    assert len(plan["operations"]) == 1
    op = plan["operations"][0]
    assert op["op_type"] == "add_marker"
    assert op["marker_color"] == "Red"
    assert "[QA_FAIL]" in op["marker_comment"]
