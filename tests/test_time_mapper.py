"""
Unit tests for TimeMapper module.
"""

import pytest
from harness.time_mapper import TimeMapper


def test_source_to_sequence_frame_identical_fps():
    # At 24 fps, source in at frame 100, sequence in at frame 0.
    # Source climax at 150 -> offset is 50 frames -> sequence frame 50.
    seq_frame = TimeMapper.source_to_sequence_frame(
        source_frame=150,
        source_in_frame=100,
        sequence_in_frame=0,
        source_fps=24.0,
        sequence_fps=24.0,
    )
    assert seq_frame == 50


def test_source_to_sequence_frame_conformed_fps():
    # Source is 30 fps, Sequence is 24 fps (ratio 0.8)
    # Source offset = 100 frames -> conformed offset = round(100 * 24 / 30) = 80 frames
    seq_frame = TimeMapper.source_to_sequence_frame(
        source_frame=200,
        source_in_frame=100,
        sequence_in_frame=10,
        source_fps=30.0,
        sequence_fps=24.0,
    )
    assert seq_frame == 90  # 10 + 80


def test_sequence_to_source_frame():
    # Invert the 30 fps -> 24 fps translation
    src_frame = TimeMapper.sequence_to_source_frame(
        sequence_frame=90,
        sequence_in_frame=10,
        source_in_frame=100,
        sequence_fps=24.0,
        source_fps=30.0,
    )
    assert src_frame == 200


def test_assemble_contiguous_timeline():
    mapper = TimeMapper(default_sequence_fps=24.0)
    incidents = [
        {
            "incident_id": "clip_1",
            "source_ref": {
                "source_in_frame": 0,
                "source_out_frame": 48,  # 2.0s at 24fps
                "source_climax_frame": 24,
                "source_fps": 24.0,
            },
            "sound_operations": [
                {"type": "climax_sfx", "asset_id": "sfx_punch", "track": "A4", "sync_to_master_frame": 0}
            ],
        },
        {
            "incident_id": "clip_2",
            "source_ref": {
                "source_in_frame": 100,
                "source_out_frame": 172,  # 72 frames -> 3.0s at 24fps
                "source_climax_frame": 148,  # 48 frames offset
                "source_fps": 24.0,
            },
            "sound_operations": [
                {"type": "climax_sfx", "asset_id": "sfx_crash", "track": "A4", "sync_to_master_frame": 0}
            ],
        },
    ]

    assembled = mapper.assemble_contiguous_timeline(incidents, start_frame=0)

    # First clip
    assert assembled[0]["master_timeline"]["sequence_in_frame"] == 0
    assert assembled[0]["master_timeline"]["sequence_out_frame"] == 48
    assert assembled[0]["master_timeline"]["mapped_climax_frame"] == 24
    assert assembled[0]["sound_operations"][0]["sync_to_master_frame"] == 24

    # Second clip placed immediately at frame 48 (Zero Gap)
    assert assembled[1]["master_timeline"]["sequence_in_frame"] == 48
    assert assembled[1]["master_timeline"]["sequence_out_frame"] == 120  # 48 + 72
    assert assembled[1]["master_timeline"]["mapped_climax_frame"] == 96  # 48 + 48
    assert assembled[1]["sound_operations"][0]["sync_to_master_frame"] == 96


def test_apply_ripple_shift():
    mapper = TimeMapper(default_sequence_fps=24.0)
    incidents = [
        {
            "incident_id": "c1",
            "master_timeline": {"sequence_in_frame": 0, "sequence_out_frame": 50, "mapped_climax_frame": 25},
        },
        {
            "incident_id": "c2",
            "master_timeline": {"sequence_in_frame": 50, "sequence_out_frame": 100, "mapped_climax_frame": 75},
            "sound_operations": [{"type": "climax_sfx", "sync_to_master_frame": 75}],
        },
    ]

    shifted = mapper.apply_ripple_shift(incidents, start_index=1, delta_frames=10)
    # Clip 1 unchanged
    assert shifted[0]["master_timeline"]["sequence_in_frame"] == 0
    # Clip 2 shifted by +10 frames
    assert shifted[1]["master_timeline"]["sequence_in_frame"] == 60
    assert shifted[1]["master_timeline"]["sequence_out_frame"] == 110
    assert shifted[1]["master_timeline"]["mapped_climax_frame"] == 85
    assert shifted[1]["sound_operations"][0]["sync_to_master_frame"] == 85


def test_verify_payoff_window():
    # 24 fps, 0.8s requires round(0.8 * 24) = 19 frames hold
    is_valid, deficit = TimeMapper.verify_payoff_window(
        sequence_out_frame=50,
        mapped_climax_frame=30,  # hold = 20 frames >= 19
        sequence_fps=24.0,
        min_reaction_sec=0.8,
    )
    assert is_valid is True
    assert deficit == 0

    # Truncated reaction: hold = 10 frames < 19
    is_valid, deficit = TimeMapper.verify_payoff_window(
        sequence_out_frame=40,
        mapped_climax_frame=30,
        sequence_fps=24.0,
        min_reaction_sec=0.8,
    )
    assert is_valid is False
    assert deficit == 9
