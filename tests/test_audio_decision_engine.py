"""
Unit tests for AudioDecisionEngine.
"""

import pytest
from harness.audio_decision_engine import AudioDecisionEngine


def test_authentic_transient_preservation():
    engine = AudioDecisionEngine(transient_threshold_dbfs=-18.0)
    # Scene with real glass shatter captured on camera (-12.0 dBFS > -18.0)
    scene_meta = {
        "audio_transient_detected": True,
        "transient_dbfs": -12.0,
        "speech_detected": False,
        "material_type": "glass",
    }

    ops = engine.evaluate_incident_audio(
        scene_metadata=scene_meta,
        mapped_climax_frame=120,
        sequence_in_frame=60,
        is_first_incident=False,
    )

    # Must contain original_audio_boost on A1
    a1_boost = [op for op in ops if op.get("track") == "A1"]
    assert len(a1_boost) == 1
    assert a1_boost[0]["type"] == "original_audio_boost"
    assert a1_boost[0]["gain_db"] > 0

    # Must NOT contain artificial impact SFX on A4
    a4_sfx = [op for op in ops if op.get("track") == "A4"]
    assert len(a4_sfx) == 0


def test_silent_cctv_triggers_contextual_sfx():
    engine = AudioDecisionEngine()
    # CCTV footage with metal collision, no audio transient
    scene_meta = {
        "audio_transient_detected": False,
        "transient_dbfs": -60.0,
        "speech_detected": False,
        "material_type": "metal",
    }

    ops = engine.evaluate_incident_audio(
        scene_metadata=scene_meta,
        mapped_climax_frame=150,
        sequence_in_frame=100,
        is_first_incident=False,
    )

    # Must contain climax_sfx on A4 with metal asset
    a4_sfx = [op for op in ops if op.get("track") == "A4"]
    assert len(a4_sfx) == 1
    assert a4_sfx[0]["type"] == "climax_sfx"
    assert "metal" in a4_sfx[0]["asset_id"]
    assert a4_sfx[0]["sync_to_master_frame"] == 150


def test_speech_presence_attenuates_sfx():
    engine = AudioDecisionEngine()
    # CCTV with someone talking / laughing: SFX should be attenuated to -6dB
    scene_meta = {
        "audio_transient_detected": False,
        "speech_detected": True,
        "material_type": "wood",
    }

    ops = engine.evaluate_incident_audio(
        scene_metadata=scene_meta,
        mapped_climax_frame=200,
        sequence_in_frame=150,
        is_first_incident=True,
    )

    a4_sfx = [op for op in ops if op.get("track") == "A4"]
    assert len(a4_sfx) == 1
    assert a4_sfx[0]["gain_db"] == -6.0


def test_voiceover_track_a2_integrity():
    engine = AudioDecisionEngine()
    scene_meta = {
        "audio_transient_detected": False,
        "speech_detected": False,
        "material_type": "concrete",
    }

    ops = engine.evaluate_incident_audio(
        scene_metadata=scene_meta,
        mapped_climax_frame=100,
        sequence_in_frame=0,
        is_first_incident=True,
    )

    # Check that A2 is never assigned
    a2_ops = [op for op in ops if op.get("track", "").upper() == "A2"]
    assert len(a2_ops) == 0

    # Safety auditor returns 0 errors
    violations = AudioDecisionEngine.audit_track_safety(ops)
    assert len(violations) == 0

    # Injecting invalid op triggers violation
    bad_ops = ops + [{"type": "bad_vo", "track": "A2"}]
    assert len(AudioDecisionEngine.audit_track_safety(bad_ops)) == 1
