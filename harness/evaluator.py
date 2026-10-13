"""
HarnessEvaluator: Closed-loop audit engine enforcing the 5 Core Timeline Invariants.
Validates Premiere Pro sequence state or synthetic timeline dictionaries against:
- INV-01: Zero Gaps on Video Track V1
- INV-02: Frame-Exact SFX Sync (tolerance <= 1 frame)
- INV-03: Master Audio Headroom Protection (True Peak <= -1.0 dBFS)
- INV-04: Voiceover Track A2 Integrity (Track A2 must be strictly empty)
- INV-05: Payoff Window Preservation (Reaction window >= 0.8s * FPS)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class HarnessEvaluator:
    """
    Audits timeline state dictionaries (compatible with premiere-pro-mcp data structures)
    and produces structured QA reports.
    """

    MAX_REPAIR_CYCLES = 3
    SFX_SYNC_TOLERANCE_FRAMES = 1
    HEADROOM_MAX_TRUE_PEAK_DBFS = -1.0
    MIN_PAYOFF_WINDOW_SEC = 0.8

    def __init__(self, sequence_fps: float = 23.976):
        self.sequence_fps = sequence_fps

    def evaluate_inv01_zero_gaps(self, v1_clips: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        INV-01: Zero Gaps on Track V1.
        Checks that clips on V1 are strictly contiguous without unrendered gaps.
        """
        violations = []
        if not v1_clips:
            return {
                "name": "Zero Gaps on V1",
                "status": "PASS",
                "error_count": 0,
                "violations": [],
            }

        sorted_clips = sorted(v1_clips, key=lambda c: c.get("start_frame", 0))
        for i in range(len(sorted_clips) - 1):
            curr_end = sorted_clips[i].get("end_frame", 0)
            next_start = sorted_clips[i + 1].get("start_frame", 0)
            if next_start > curr_end:
                gap_size = next_start - curr_end
                violations.append({
                    "gap_start_frame": curr_end,
                    "gap_end_frame": next_start,
                    "gap_size_frames": gap_size,
                    "preceding_clip": sorted_clips[i].get("name", f"clip_{i}"),
                    "following_clip": sorted_clips[i + 1].get("name", f"clip_{i+1}"),
                })

        return {
            "name": "Zero Gaps on V1",
            "status": "PASS" if not violations else "FAIL",
            "error_count": len(violations),
            "violations": violations,
        }

    def evaluate_inv02_sfx_sync(
        self,
        sfx_clips: List[Dict[str, Any]],
        expected_climaxes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        INV-02: Frame-Exact SFX Sync.
        Checks that every impact SFX on track A4 aligns to its corresponding mapped climax frame
        within +/- 1 frame.
        """
        violations = []
        # Match each expected climax to the nearest SFX clip on A4
        for climax_info in expected_climaxes:
            target_frame = climax_info.get("mapped_climax_frame", 0)
            incident_id = climax_info.get("incident_id", "unknown")

            # Look for an SFX clip close to target_frame
            matched_sfx = None
            min_dist = float("inf")
            for sfx in sfx_clips:
                sfx_start = sfx.get("start_frame", 0)
                dist = abs(sfx_start - target_frame)
                if dist < min_dist:
                    min_dist = dist
                    matched_sfx = sfx

            if matched_sfx is None:
                violations.append({
                    "incident_id": incident_id,
                    "expected_frame": target_frame,
                    "actual_frame": None,
                    "delta_frames": None,
                    "reason": "Missing expected SFX on Track A4",
                })
            elif min_dist > self.SFX_SYNC_TOLERANCE_FRAMES:
                sfx_start = matched_sfx.get("start_frame", 0)
                violations.append({
                    "incident_id": incident_id,
                    "expected_frame": target_frame,
                    "actual_frame": sfx_start,
                    "delta_frames": sfx_start - target_frame,
                    "clip_name": matched_sfx.get("name", ""),
                    "reason": f"SFX misaligned by {sfx_start - target_frame:+d} frames (tol: +/-{self.SFX_SYNC_TOLERANCE_FRAMES})",
                })

        return {
            "name": "Frame-Exact SFX Sync",
            "status": "PASS" if not violations else "FAIL",
            "error_count": len(violations),
            "violations": violations,
        }

    def evaluate_inv03_headroom(self, master_true_peak_dbfs: float) -> Dict[str, Any]:
        """
        INV-03: Audio Headroom Protection.
        Ensures Master True Peak <= -1.0 dBFS to prevent clipping distortion on mobile devices.
        """
        is_safe = master_true_peak_dbfs <= self.HEADROOM_MAX_TRUE_PEAK_DBFS
        violations = []
        if not is_safe:
            overshoot = master_true_peak_dbfs - self.HEADROOM_MAX_TRUE_PEAK_DBFS
            violations.append({
                "true_peak_dbfs": master_true_peak_dbfs,
                "max_allowed_dbfs": self.HEADROOM_MAX_TRUE_PEAK_DBFS,
                "overshoot_db": round(overshoot, 2),
                "reason": f"Master true peak {master_true_peak_dbfs:.2f} dBFS exceeds headroom limit of {self.HEADROOM_MAX_TRUE_PEAK_DBFS} dBFS",
            })

        return {
            "name": "Audio Headroom Protection",
            "status": "PASS" if is_safe else "FAIL",
            "error_count": len(violations),
            "violations": violations,
        }

    def evaluate_inv04_voiceover_track(self, a2_clips: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        INV-04: Voiceover Track Integrity.
        Ensures Track A2 contains 0 audio clips (strictly reserved for Voiceover recording).
        """
        is_clean = len(a2_clips) == 0
        violations = []
        if not is_clean:
            for clip in a2_clips:
                violations.append({
                    "clip_name": clip.get("name", "unnamed"),
                    "start_frame": clip.get("start_frame", 0),
                    "end_frame": clip.get("end_frame", 0),
                    "reason": "Track A2 is reserved strictly for Voiceover; foreign audio detected.",
                })

        return {
            "name": "Voiceover Track Integrity",
            "status": "PASS" if is_clean else "FAIL",
            "error_count": len(violations),
            "violations": violations,
        }

    def evaluate_inv05_payoff_window(
        self,
        v1_clips: List[Dict[str, Any]],
        expected_climaxes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        INV-05: Payoff Window Preservation.
        Ensures the video reaction window holds for at least min_reaction_sec (0.8s) after the climax.
        """
        violations = []
        required_hold_frames = round(self.MIN_PAYOFF_WINDOW_SEC * self.sequence_fps)

        # Match each climax to its enclosing V1 clip
        for climax_info in expected_climaxes:
            climax_frame = climax_info.get("mapped_climax_frame", 0)
            incident_id = climax_info.get("incident_id", "unknown")

            enclosing_clip = None
            for clip in v1_clips:
                c_start = clip.get("start_frame", 0)
                c_end = clip.get("end_frame", 0)
                if c_start <= climax_frame < c_end:
                    enclosing_clip = clip
                    break

            if enclosing_clip:
                actual_hold = enclosing_clip.get("end_frame", 0) - climax_frame
                if actual_hold < required_hold_frames:
                    violations.append({
                        "incident_id": incident_id,
                        "clip_name": enclosing_clip.get("name", ""),
                        "climax_frame": climax_frame,
                        "clip_end_frame": enclosing_clip.get("end_frame", 0),
                        "actual_hold_frames": actual_hold,
                        "required_hold_frames": required_hold_frames,
                        "deficit_frames": required_hold_frames - actual_hold,
                        "reason": f"Payoff truncated: held {actual_hold} frames, required {required_hold_frames} frames",
                    })

        return {
            "name": "Payoff Window Preservation",
            "status": "PASS" if not violations else "FAIL",
            "error_count": len(violations),
            "violations": violations,
        }

    def audit_timeline(
        self,
        timeline_state: Dict[str, Any],
        expected_climaxes: List[Dict[str, Any]],
        cycle_index: int = 1,
    ) -> Dict[str, Any]:
        """
        Performs a full audit across all 5 invariants.
        Returns a complete QA report dictionary conforming to qa_report.schema.json.
        """
        v1_clips = timeline_state.get("tracks", {}).get("V1", [])
        a2_clips = timeline_state.get("tracks", {}).get("A2", [])
        a4_clips = timeline_state.get("tracks", {}).get("A4", [])
        master_peak = timeline_state.get("master_true_peak_dbfs", -3.0)
        sequence_name = timeline_state.get("sequence_name", "Master_Sequence")

        inv01 = self.evaluate_inv01_zero_gaps(v1_clips)
        inv02 = self.evaluate_inv02_sfx_sync(a4_clips, expected_climaxes)
        inv03 = self.evaluate_inv03_headroom(master_peak)
        inv04 = self.evaluate_inv04_voiceover_track(a2_clips)
        inv05 = self.evaluate_inv05_payoff_window(v1_clips, expected_climaxes)

        results = {
            "INV-01": inv01,
            "INV-02": inv02,
            "INV-03": inv03,
            "INV-04": inv04,
            "INV-05": inv05,
        }

        total_errors = sum(r["error_count"] for r in results.values())
        is_pass = total_errors == 0

        if is_pass:
            overall_status = "PASS"
            recommendation = "Sequence conforms to all 5 broadcast invariants. Ready for delivery or review."
        elif cycle_index >= self.MAX_REPAIR_CYCLES:
            overall_status = "CIRCUIT_BREAKER_TRIPPED"
            recommendation = (
                f"Circuit breaker tripped after {cycle_index} iterations. "
                "Triggering soft rollback to checkpoint and planting red warning markers."
            )
        else:
            overall_status = "FAIL_REPAIRABLE"
            recommendation = f"Audit failed with {total_errors} violations. Generating micro-patch plan (Cycle {cycle_index})."

        report = {
            "report_id": f"qa_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sequence_name": sequence_name,
            "cycle_index": cycle_index,
            "overall_status": overall_status,
            "invariants_results": results,
            "review_frames_captured": timeline_state.get("review_frames_captured", []),
            "recommendation": recommendation,
        }
        return report
