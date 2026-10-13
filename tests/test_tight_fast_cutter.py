"""
Unit tests for TightFastCutter module enforcing ultra-tight fast-cut ceilings.
"""

import pytest
from harness.tight_fast_cutter import TightFastCutter


def test_tight_fast_cutter_ceilings():
    # Synthetic motion curve for a 170-second video with peaks at 10s, 75s, 150s
    timestamps = [float(i) for i in range(170)]
    motion_curve = [0.1] * 170
    motion_curve[10] = 8.0   # Setup peak
    motion_curve[75] = 12.0  # Main Climax peak
    motion_curve[150] = 7.0  # Payoff peak

    beats = TightFastCutter._extract_tight_windows(timestamps, motion_curve, 170.0)

    # 1. Must produce exactly 3 beats: SETUP, CLIMAX, PAYOFF
    assert len(beats) == 3
    setup, climax, payoff = beats

    # 2. Check strict ceilings
    assert setup["duration"] <= TightFastCutter.MAX_SETUP_SEC  # <= 3.5s
    assert climax["duration"] <= TightFastCutter.MAX_CLIMAX_SEC  # <= 3.0s
    assert payoff["duration"] <= TightFastCutter.MAX_PAYOFF_SEC  # <= 3.5s

    total_duration = sum(b["duration"] for b in beats)
    assert total_duration <= TightFastCutter.MAX_TOTAL_INCIDENT_SEC  # <= 15.0s
    assert total_duration >= 5.0


def test_calculate_tight_premiere_cuts():
    beats = [
        {"beat": "SETUP", "start_sec": 5.0, "end_sec": 8.0, "duration": 3.0},
        {"beat": "CLIMAX", "start_sec": 75.0, "end_sec": 78.0, "duration": 3.0},
        {"beat": "PAYOFF", "start_sec": 150.0, "end_sec": 153.0, "duration": 3.0},
    ]

    # Clip starts at 180.0s on timeline
    result = TightFastCutter.calculate_tight_premiere_cuts(180.0, beats)
    assert result["total_kept_duration"] == 9.0
    assert len(result["keep_ranges"]) == 3
    # Check absolute timeline coordinates
    assert result["keep_ranges"][0]["timeline_start"] == 185.0
    assert result["keep_ranges"][0]["timeline_end"] == 188.0
    assert result["keep_ranges"][1]["timeline_start"] == 255.0
    assert result["keep_ranges"][1]["timeline_end"] == 258.0
    assert result["keep_ranges"][2]["timeline_start"] == 330.0
    assert result["keep_ranges"][2]["timeline_end"] == 333.0
