"""
Unit tests for HarnessEvaluator module.
"""

import pytest
from harness.evaluator import HarnessEvaluator


def test_inv01_zero_gaps():
    evaluator = HarnessEvaluator(sequence_fps=24.0)

    # 1. Contiguous clips -> PASS
    clean_v1 = [
        {"name": "clip_01", "start_frame": 0, "end_frame": 50},
        {"name": "clip_02", "start_frame": 50, "end_frame": 120},
    ]
    res = evaluator.evaluate_inv01_zero_gaps(clean_v1)
    assert res["status"] == "PASS"
    assert res["error_count"] == 0

    # 2. 5-frame gap between clips -> FAIL
    gapped_v1 = [
        {"name": "clip_01", "start_frame": 0, "end_frame": 50},
        {"name": "clip_02", "start_frame": 55, "end_frame": 120},
    ]
    res = evaluator.evaluate_inv01_zero_gaps(gapped_v1)
    assert res["status"] == "FAIL"
    assert res["error_count"] == 1
    assert res["violations"][0]["gap_size_frames"] == 5
    assert res["violations"][0]["gap_start_frame"] == 50
    assert res["violations"][0]["gap_end_frame"] == 55


def test_inv02_sfx_sync():
    evaluator = HarnessEvaluator(sequence_fps=24.0)

    climaxes = [{"incident_id": "inc_1", "mapped_climax_frame": 100}]

    # In-sync (offset 0)
    sfx_synced = [{"name": "metal_hit", "start_frame": 100}]
    res = evaluator.evaluate_inv02_sfx_sync(sfx_synced, climaxes)
    assert res["status"] == "PASS"

    # Within 1-frame tolerance (+1 frame)
    sfx_tol = [{"name": "metal_hit", "start_frame": 101}]
    res = evaluator.evaluate_inv02_sfx_sync(sfx_tol, climaxes)
    assert res["status"] == "PASS"

    # Misaligned (+4 frames late)
    sfx_late = [{"name": "metal_hit", "start_frame": 104}]
    res = evaluator.evaluate_inv02_sfx_sync(sfx_late, climaxes)
    assert res["status"] == "FAIL"
    assert res["violations"][0]["delta_frames"] == 4


def test_inv03_headroom():
    evaluator = HarnessEvaluator()

    # Pass: -1.5 dBFS <= -1.0 dBFS
    res = evaluator.evaluate_inv03_headroom(-1.5)
    assert res["status"] == "PASS"

    # Fail: 0.2 dBFS > -1.0 dBFS
    res = evaluator.evaluate_inv03_headroom(0.2)
    assert res["status"] == "FAIL"
    assert res["violations"][0]["overshoot_db"] == 1.2


def test_inv04_voiceover_track():
    evaluator = HarnessEvaluator()

    # Empty A2 -> PASS
    res = evaluator.evaluate_inv04_voiceover_track([])
    assert res["status"] == "PASS"

    # Audio clip on A2 -> FAIL
    res = evaluator.evaluate_inv04_voiceover_track([{"name": "accidental_sfx", "start_frame": 0, "end_frame": 50}])
    assert res["status"] == "FAIL"
    assert res["error_count"] == 1


def test_inv05_payoff_window():
    evaluator = HarnessEvaluator(sequence_fps=24.0)
    climaxes = [{"incident_id": "inc_1", "mapped_climax_frame": 50}]

    # 24 fps, 0.8s requires 19 frames hold
    # Clip ends at 75 -> hold is 25 frames -> PASS
    v1_ok = [{"name": "c1", "start_frame": 0, "end_frame": 75}]
    res = evaluator.evaluate_inv05_payoff_window(v1_ok, climaxes)
    assert res["status"] == "PASS"

    # Clip ends at 60 -> hold is 10 frames < 19 -> FAIL
    v1_short = [{"name": "c1", "start_frame": 0, "end_frame": 60}]
    res = evaluator.evaluate_inv05_payoff_window(v1_short, climaxes)
    assert res["status"] == "FAIL"
    assert res["violations"][0]["deficit_frames"] == 9


def test_circuit_breaker_tripped():
    evaluator = HarnessEvaluator(sequence_fps=24.0)
    # Timeline with gap
    state = {
        "sequence_name": "Seq_01",
        "tracks": {
            "V1": [
                {"name": "c1", "start_frame": 0, "end_frame": 50},
                {"name": "c2", "start_frame": 60, "end_frame": 100},
            ],
            "A2": [],
            "A4": [],
        },
        "master_true_peak_dbfs": -3.0,
    }

    # Cycle 1 returns FAIL_REPAIRABLE
    r1 = evaluator.audit_timeline(state, [], cycle_index=1)
    assert r1["overall_status"] == "FAIL_REPAIRABLE"

    # Cycle 3 returns CIRCUIT_BREAKER_TRIPPED
    r3 = evaluator.audit_timeline(state, [], cycle_index=3)
    assert r3["overall_status"] == "CIRCUIT_BREAKER_TRIPPED"
