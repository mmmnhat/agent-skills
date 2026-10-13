"""
AudioDecisionEngine: Functional decision matrix for authentic sound preservation and multi-track audio layout.
Enforces:
- Rule: Authentic acoustic preservation (boost A1 if real impact transients exist, forbid artificial SFX).
- Rule: Contextual impact SFX on Track A4 for silent / muffled source footage.
- Rule: Track A2 100% EMPTY (Reserved for Voiceover).
- Rule: Transition SFX on Track A3.
- Rule: BGM Ducking on Track A5 (-12 dBFS around climaxes and dialogue).
"""

from typing import Any, Dict, List, Optional


class AudioDecisionEngine:
    """
    Evaluates incident audio characteristics and decides track assignments, gain adjustments,
    and asset selection across the 5 standard audio tracks:
      A1: Original Clip Audio (Gain Boost / Normalization)
      A2: RESERVED BLANK FOR VOICEOVER (Must NEVER have audio assigned)
      A3: Scene Transition SFX (Whoosh, Swipe)
      A4: Action Climax Impacts (Mechanical / Physical Collisions)
      A5: Ducked Background Music
    """

    DEFAULT_TRANSIENT_THRESHOLD_DBFS = -18.0
    DEFAULT_IMPACT_GAIN_DB = -3.0
    DEFAULT_SPEECH_AWARE_SFX_GAIN_DB = -6.0
    DEFAULT_A1_BOOST_DB = 4.5
    DEFAULT_BGM_DUCKING_DB = -12.0

    # Default material SFX catalog mapping
    MATERIAL_SFX_MAP = {
        "metal": "sfx_metal_clang_heavy_01",
        "glass": "sfx_glass_shatter_sharp_01",
        "wood": "sfx_wood_crack_break_01",
        "concrete": "sfx_concrete_thud_heavy_01",
        "cardboard": "sfx_box_impact_light_01",
        "water": "sfx_water_splash_big_01",
        "body_fall": "sfx_body_thud_cushioned_01",
        "general": "sfx_impact_punch_thud_01",
    }

    def __init__(self, transient_threshold_dbfs: float = DEFAULT_TRANSIENT_THRESHOLD_DBFS):
        self.transient_threshold_dbfs = transient_threshold_dbfs

    def evaluate_incident_audio(
        self,
        scene_metadata: Dict[str, Any],
        mapped_climax_frame: int,
        sequence_in_frame: int,
        is_first_incident: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Determines the complete sound operations list for a given incident.
        Returns a list of sound operation dictionaries conforming to edit_plan schema.
        """
        operations: List[Dict[str, Any]] = []

        # Extract acoustic features
        has_transient = scene_metadata.get("audio_transient_detected", False)
        transient_level = scene_metadata.get("transient_dbfs", -99.0)
        has_speech = scene_metadata.get("speech_detected", False)
        audio_score = scene_metadata.get("audio_score", 0.0)
        material = scene_metadata.get("material_type", "general").lower()

        is_authentic_transient = has_transient or (transient_level >= self.transient_threshold_dbfs)

        # 1. Track A1: Original Audio decision
        if is_authentic_transient:
            # Genuine sound captured on camera! Boost A1 and FORBID artificial A4 SFX
            boost_gain = self.DEFAULT_A1_BOOST_DB
            if has_speech:
                # Moderate boost if speech is present to prevent clipping
                boost_gain = min(boost_gain, 3.0)

            operations.append({
                "type": "original_audio_boost",
                "track": "A1",
                "sync_to_master_frame": sequence_in_frame,
                "gain_db": boost_gain,
                "note": "Preserved authentic camera impact audio; suppressed artificial SFX",
            })
        else:
            # Source audio is silent or lack impact transients -> Insert contextual A4 SFX
            asset_id = self.MATERIAL_SFX_MAP.get(material, self.MATERIAL_SFX_MAP["general"])
            sfx_gain = (
                self.DEFAULT_SPEECH_AWARE_SFX_GAIN_DB
                if has_speech
                else self.DEFAULT_IMPACT_GAIN_DB
            )

            operations.append({
                "type": "climax_sfx",
                "asset_id": asset_id,
                "track": "A4",
                "sync_to_master_frame": mapped_climax_frame,
                "gain_db": sfx_gain,
                "note": f"Synthesized impact SFX for {material} collision",
            })

        # 2. Track A3: Transition Whoosh (add between incidents, skip before very first clip)
        if not is_first_incident:
            operations.append({
                "type": "transition_whoosh",
                "asset_id": "sfx_transition_whoosh_fast_01",
                "track": "A3",
                "sync_to_master_frame": sequence_in_frame,
                "gain_db": -6.0,
            })

        # 3. Track A5: BGM Ducking envelope around climax
        operations.append({
            "type": "bgm_ducking",
            "track": "A5",
            "sync_to_master_frame": mapped_climax_frame,
            "gain_db": self.DEFAULT_BGM_DUCKING_DB,
            "ducking_window_sec": 1.5,
        })

        return operations

    @staticmethod
    def audit_track_safety(sound_operations: List[Dict[str, Any]]) -> List[str]:
        """
        Safety check: ensures NO sound operation targets Track A2.
        Returns list of error messages (empty if valid).
        """
        violations = []
        for op in sound_operations:
            track = op.get("track", "")
            if track.upper() == "A2":
                violations.append(
                    f"INV-04 Violation: Sound operation '{op.get('type')}' was routed to reserved Voiceover track A2."
                )
        return violations
