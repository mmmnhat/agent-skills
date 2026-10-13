"""
TimeMapper: Pure mathematical engine for dual-coordinate timecode translation.
Maintains invariant relationships between Source Media coordinates and Master Sequence coordinates,
compensating for conforming frame rate differences and timeline ripple shifts.
"""

from typing import Any, Dict, List, Optional, Tuple


class TimeMapper:
    """
    Translates frames and timestamps between Source Media space and Master Sequence space.
    Formula:
        Master Action Peak = Master Sequence In + round((Source Climax - Source In) * (Sequence FPS / Source FPS))
    """

    def __init__(self, default_sequence_fps: float = 23.976):
        self.default_sequence_fps = default_sequence_fps

    @staticmethod
    def source_to_sequence_frame(
        source_frame: int,
        source_in_frame: int,
        sequence_in_frame: int,
        source_fps: float = 23.976,
        sequence_fps: float = 23.976,
    ) -> int:
        """
        Converts an absolute frame index in source media to its corresponding absolute frame
        in the master sequence.
        """
        if source_fps <= 0 or sequence_fps <= 0:
            raise ValueError(f"FPS values must be positive. Got source={source_fps}, seq={sequence_fps}")

        source_offset = source_frame - source_in_frame
        timebase_ratio = sequence_fps / source_fps
        conformed_offset = round(source_offset * timebase_ratio)
        return sequence_in_frame + conformed_offset

    @staticmethod
    def sequence_to_source_frame(
        sequence_frame: int,
        sequence_in_frame: int,
        source_in_frame: int,
        sequence_fps: float = 23.976,
        source_fps: float = 23.976,
    ) -> int:
        """
        Converts a master sequence frame back to the source media absolute frame.
        """
        if source_fps <= 0 or sequence_fps <= 0:
            raise ValueError(f"FPS values must be positive. Got source={source_fps}, seq={sequence_fps}")

        seq_offset = sequence_frame - sequence_in_frame
        timebase_ratio = source_fps / sequence_fps
        source_offset = round(seq_offset * timebase_ratio)
        return source_in_frame + source_offset

    def calculate_mapped_climax(
        self,
        source_in_frame: int,
        source_climax_frame: int,
        sequence_in_frame: int,
        source_fps: float = 23.976,
        sequence_fps: Optional[float] = None,
    ) -> int:
        """
        Computes the Master Action Peak Frame given source In, source Climax, and sequence In.
        """
        target_seq_fps = sequence_fps or self.default_sequence_fps
        return self.source_to_sequence_frame(
            source_frame=source_climax_frame,
            source_in_frame=source_in_frame,
            sequence_in_frame=sequence_in_frame,
            source_fps=source_fps,
            sequence_fps=target_seq_fps,
        )

    def assemble_contiguous_timeline(
        self,
        incidents: List[Dict[str, Any]],
        start_frame: int = 0,
        sequence_fps: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Arranges a list of incidents contiguously with ZERO gaps on track V1.
        Updates master_timeline.sequence_in_frame, sequence_out_frame, and mapped_climax_frame.
        Also updates any sound_operations with sync_to_master_frame matching the new climax or in point.
        """
        target_seq_fps = sequence_fps or self.default_sequence_fps
        current_cursor = start_frame
        updated_incidents: List[Dict[str, Any]] = []

        for incident in incidents:
            inc_copy = dict(incident)
            source_ref = inc_copy.get("source_ref", {})
            src_in = source_ref.get("source_in_frame", 0)
            src_out = source_ref.get("source_out_frame", 0)
            src_climax = source_ref.get("source_climax_frame", src_in)
            src_fps = source_ref.get("source_fps", target_seq_fps)

            duration_source_frames = max(0, src_out - src_in)
            timebase_ratio = target_seq_fps / src_fps
            conformed_duration = round(duration_source_frames * timebase_ratio)

            seq_in = current_cursor
            seq_out = current_cursor + conformed_duration

            mapped_climax = self.calculate_mapped_climax(
                source_in_frame=src_in,
                source_climax_frame=src_climax,
                sequence_in_frame=seq_in,
                source_fps=src_fps,
                sequence_fps=target_seq_fps,
            )

            master_tl = {
                "track_v": inc_copy.get("master_timeline", {}).get("track_v", "V1"),
                "sequence_in_frame": seq_in,
                "sequence_out_frame": seq_out,
                "mapped_climax_frame": mapped_climax,
            }
            inc_copy["master_timeline"] = master_tl

            # Re-sync sound operations if present
            if "sound_operations" in inc_copy:
                new_sfx_ops = []
                for sfx in inc_copy["sound_operations"]:
                    sfx_copy = dict(sfx)
                    sfx_type = sfx_copy.get("type")
                    if sfx_type == "climax_sfx":
                        sfx_copy["sync_to_master_frame"] = mapped_climax
                    elif sfx_type == "transition_whoosh":
                        sfx_copy["sync_to_master_frame"] = seq_in
                    new_sfx_ops.append(sfx_copy)
                inc_copy["sound_operations"] = new_sfx_ops

            updated_incidents.append(inc_copy)
            current_cursor = seq_out

        return updated_incidents

    def apply_ripple_shift(
        self,
        incidents: List[Dict[str, Any]],
        start_index: int,
        delta_frames: int,
    ) -> List[Dict[str, Any]]:
        """
        Shifts all incidents starting from start_index downstream by delta_frames.
        Preserves relative offsets and sync targets.
        """
        if delta_frames == 0 or start_index >= len(incidents):
            return incidents

        result: List[Dict[str, Any]] = []
        for i, inc in enumerate(incidents):
            inc_copy = dict(inc)
            if i >= start_index:
                mt = dict(inc_copy.get("master_timeline", {}))
                mt["sequence_in_frame"] = mt.get("sequence_in_frame", 0) + delta_frames
                mt["sequence_out_frame"] = mt.get("sequence_out_frame", 0) + delta_frames
                mt["mapped_climax_frame"] = mt.get("mapped_climax_frame", 0) + delta_frames
                inc_copy["master_timeline"] = mt

                if "sound_operations" in inc_copy:
                    new_sfx = []
                    for sfx in inc_copy["sound_operations"]:
                        sfx_c = dict(sfx)
                        if "sync_to_master_frame" in sfx_c:
                            sfx_c["sync_to_master_frame"] += delta_frames
                        new_sfx.append(sfx_c)
                    inc_copy["sound_operations"] = new_sfx

            result.append(inc_copy)
        return result

    @staticmethod
    def verify_payoff_window(
        sequence_out_frame: int,
        mapped_climax_frame: int,
        sequence_fps: float = 23.976,
        min_reaction_sec: float = 0.8,
    ) -> Tuple[bool, int]:
        """
        Verifies INV-05: Payoff Window Preservation.
        Ensures sequence_out_frame >= mapped_climax_frame + round(min_reaction_sec * sequence_fps).
        Returns:
            (is_valid, missing_frames_count)
            If valid, missing_frames_count is 0. If invalid, missing_frames_count > 0.
        """
        required_hold_frames = round(min_reaction_sec * sequence_fps)
        actual_hold_frames = sequence_out_frame - mapped_climax_frame
        if actual_hold_frames >= required_hold_frames:
            return True, 0
        return False, required_hold_frames - actual_hold_frames
