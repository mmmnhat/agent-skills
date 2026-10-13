"""
PatchGenerator: Deterministic reducer translating QA invariant failures into atomic, non-conflicting
corrective operations for Adobe Premiere Pro MCP.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class PatchGenerator:
    """
    Consumes a QAReport dictionary and produces an atomic PatchPlan.
    """

    @staticmethod
    def generate_patch_plan(qa_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes qa_report invariants_results and produces a structured PatchPlan conforming
        to schemas/patch_plan.schema.json.
        """
        sequence_name = qa_report.get("sequence_name", "Master_Sequence")
        cycle_index = qa_report.get("cycle_index", 1)
        invariants_results = qa_report.get("invariants_results", {})
        overall_status = qa_report.get("overall_status", "PASS")

        operations: List[Dict[str, Any]] = []
        triggered_invariants: List[str] = []

        # If Circuit Breaker tripped, generate warning markers rather than further mutations
        if overall_status == "CIRCUIT_BREAKER_TRIPPED":
            for inv_code, inv_data in invariants_results.items():
                if inv_data.get("status") == "FAIL":
                    triggered_invariants.append(inv_code)
                    for v in inv_data.get("violations", []):
                        target_frame = (
                            v.get("expected_frame")
                            or v.get("climax_frame")
                            or v.get("gap_start_frame")
                            or v.get("start_frame")
                            or 0
                        )
                        operations.append({
                            "op_type": "add_marker",
                            "track": "V1",
                            "start_frame": target_frame,
                            "marker_color": "Red",
                            "marker_comment": f"[QA_FAIL] {inv_code}: {v.get('reason', 'Invariant violation')}",
                        })

            return {
                "patch_id": f"patch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_cb",
                "sequence_name": sequence_name,
                "cycle_index": cycle_index,
                "triggered_by_invariants": triggered_invariants,
                "action": "CIRCUIT_BREAKER_ROLLBACK_AND_FLAG",
                "operations": operations,
            }

        # 1. INV-01: Zero Gaps on V1 -> ripple_delete
        inv01 = invariants_results.get("INV-01", {})
        if inv01.get("status") == "FAIL":
            triggered_invariants.append("INV-01")
            # Sort gaps in reverse chronological order so downstream timecodes don't invalidate upstream edits
            gaps = sorted(
                inv01.get("violations", []),
                key=lambda g: g.get("gap_start_frame", 0),
                reverse=True,
            )
            for gap in gaps:
                operations.append({
                    "op_type": "ripple_delete",
                    "track": "V1",
                    "start_frame": gap.get("gap_start_frame", 0),
                    "end_frame": gap.get("gap_end_frame", 0),
                    "delta_frames": -gap.get("gap_size_frames", 0),
                })

        # 2. INV-02: Frame-Exact SFX Sync -> move_clip
        inv02 = invariants_results.get("INV-02", {})
        if inv02.get("status") == "FAIL":
            triggered_invariants.append("INV-02")
            for viol in inv02.get("violations", []):
                delta = viol.get("delta_frames")
                clip_name = viol.get("clip_name", "")
                target_frame = viol.get("expected_frame", 0)
                if delta is not None:
                    # delta_frames in patch is the shift needed: -delta brings it to expected
                    operations.append({
                        "op_type": "move_clip",
                        "track": "A4",
                        "clip_name": clip_name,
                        "delta_frames": -delta,
                        "start_frame": target_frame,
                    })

        # 3. INV-03: Audio Headroom Protection -> adjust_audio_levels
        inv03 = invariants_results.get("INV-03", {})
        if inv03.get("status") == "FAIL":
            triggered_invariants.append("INV-03")
            for viol in inv03.get("violations", []):
                overshoot = viol.get("overshoot_db", 0.0)
                # Attenuate by overshoot + 0.5dB safety cushion
                attenuation = -(overshoot + 0.5)
                operations.append({
                    "op_type": "adjust_audio_levels",
                    "track": "Master",
                    "gain_db": round(attenuation, 2),
                })

        # 4. INV-04: Voiceover Track Integrity -> move_clip_to_track
        inv04 = invariants_results.get("INV-04", {})
        if inv04.get("status") == "FAIL":
            triggered_invariants.append("INV-04")
            for viol in inv04.get("violations", []):
                clip_name = viol.get("clip_name", "")
                dest_track = "A3" if "whoosh" in clip_name.lower() else "A4"
                operations.append({
                    "op_type": "move_clip_to_track",
                    "track": "A2",
                    "dest_track": dest_track,
                    "clip_name": clip_name,
                    "start_frame": viol.get("start_frame", 0),
                })

        # 5. INV-05: Payoff Window Preservation -> trim_clip
        inv05 = invariants_results.get("INV-05", {})
        if inv05.get("status") == "FAIL":
            triggered_invariants.append("INV-05")
            for viol in inv05.get("violations", []):
                deficit = viol.get("deficit_frames", 0)
                clip_name = viol.get("clip_name", "")
                operations.append({
                    "op_type": "trim_clip",
                    "track": "V1",
                    "clip_name": clip_name,
                    "delta_frames": deficit,
                })

        return {
            "patch_id": f"patch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "sequence_name": sequence_name,
            "cycle_index": cycle_index,
            "triggered_by_invariants": triggered_invariants,
            "operations": operations,
        }
