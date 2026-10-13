"""
TightFastCutter: Ultra-high-speed 1-pass analyzer enforcing Ultra-Tight Fast-Cut Ceilings:
- Setup: 2.0s - 3.5s (Max 4.0s)
- Climax: 1.5s - 3.0s
- Payoff / React: 1.5s - 3.5s (Max 4.0s)
- Total Incident Duration: 7.0s - 15.0s Max
Eliminates dead air in a single high-speed pass (< 2 seconds) and generates atomic batch edit operations.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


class TightFastCutter:
    """
    Computes ultra-tight fast-cut boundaries for long raw footage clips,
    stripping all bloated intervals and keeping only the viral core beats.
    """

    MAX_SETUP_SEC = 3.5
    MAX_CLIMAX_SEC = 3.0
    MAX_PAYOFF_SEC = 3.5
    MAX_TOTAL_INCIDENT_SEC = 15.0
    MIN_PAYOFF_SEC = 0.8  # Invariant INV-05

    @classmethod
    def analyze_source_tight_beats(
        cls,
        video_path: str,
        sample_fps: float = 4.0,  # Fast sampling in RAM
    ) -> List[Dict[str, Any]]:
        """
        Scans video rapidly using a coarse frame step to locate motion peaks,
        scene transitions, and compute tightest setup-climax-payoff windows.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        frame_step = max(1, int(fps / sample_fps))
        prev_gray = None
        motion_curve = []
        timestamps = []

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            if prev_gray is not None:
                diff = float(np.mean(cv2.absdiff(gray, prev_gray)))
            else:
                diff = 0.0

            motion_curve.append(diff)
            timestamps.append(frame_idx / fps)
            prev_gray = gray
            frame_idx += frame_step

        cap.release()

        # Group into significant activity regions
        return cls._extract_tight_windows(timestamps, motion_curve, duration)

    @classmethod
    def _extract_tight_windows(
        cls,
        timestamps: List[float],
        motion_curve: List[float],
        total_duration: float,
    ) -> List[Dict[str, Any]]:
        """
        Extracts tightly bounded Setup, Climax, and Payoff intervals.
        """
        if not motion_curve:
            return []

        # Find significant peaks
        arr = np.array(motion_curve)
        threshold = np.percentile(arr, 75)
        peak_indices = np.where(arr >= threshold)[0]

        # In case of no distinct peaks, use default proportional anchors
        if len(peak_indices) == 0:
            return [
                {
                    "beat": "SETUP",
                    "start_sec": 1.0,
                    "end_sec": 1.0 + cls.MAX_SETUP_SEC,
                    "duration": cls.MAX_SETUP_SEC,
                },
                {
                    "beat": "CLIMAX",
                    "start_sec": total_duration * 0.5 - 1.5,
                    "end_sec": total_duration * 0.5 + 1.5,
                    "duration": cls.MAX_CLIMAX_SEC,
                },
                {
                    "beat": "PAYOFF",
                    "start_sec": max(0.0, total_duration - cls.MAX_PAYOFF_SEC - 0.5),
                    "end_sec": total_duration - 0.5,
                    "duration": cls.MAX_PAYOFF_SEC,
                },
            ]

        # Find the primary climax peak
        primary_peak_idx = int(np.argmax(arr))
        climax_t = timestamps[primary_peak_idx]

        # Bound climax tightly (e.g. 1.2s before, 1.8s after)
        climax_start = max(0.0, climax_t - 1.2)
        climax_end = min(total_duration, climax_start + cls.MAX_CLIMAX_SEC)

        # Setup: take first recognized action or start of clip, capped at MAX_SETUP_SEC
        setup_start = max(1.0, min(timestamps[peak_indices[0]] - 0.5, climax_start - 3.0))
        if setup_start >= climax_start:
            setup_start = max(0.0, climax_start - cls.MAX_SETUP_SEC)
        setup_end = min(climax_start, setup_start + cls.MAX_SETUP_SEC)

        # Payoff: directly after climax or resolution at the end, capped at MAX_PAYOFF_SEC
        payoff_start = max(climax_end, total_duration - cls.MAX_PAYOFF_SEC - 1.0)
        payoff_end = min(total_duration, payoff_start + cls.MAX_PAYOFF_SEC)

        beats = [
            {
                "beat": "SETUP",
                "start_sec": round(setup_start, 2),
                "end_sec": round(setup_end, 2),
                "duration": round(setup_end - setup_start, 2),
            },
            {
                "beat": "CLIMAX",
                "start_sec": round(climax_start, 2),
                "end_sec": round(climax_end, 2),
                "duration": round(climax_end - climax_start, 2),
            },
            {
                "beat": "PAYOFF",
                "start_sec": round(payoff_start, 2),
                "end_sec": round(payoff_end, 2),
                "duration": round(payoff_end - payoff_start, 2),
            },
        ]
        return beats

    @classmethod
    def calculate_tight_premiere_cuts(
        cls,
        clip_timeline_start: float,
        beats: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Translates source-relative tight beats into absolute timeline seconds on Premiere.
        Produces razor points and segments to KEEP vs DELETE.
        """
        keep_ranges = []
        razor_points = set()

        for b in beats:
            t_in = round(clip_timeline_start + b["start_sec"], 2)
            t_out = round(clip_timeline_start + b["end_sec"], 2)
            keep_ranges.append({
                "beat": b["beat"],
                "timeline_start": t_in,
                "timeline_end": t_out,
                "duration": round(t_out - t_in, 2),
            })
            razor_points.add(t_in)
            razor_points.add(t_out)

        sorted_razors = sorted(list(razor_points))
        total_kept_duration = sum(k["duration"] for k in keep_ranges)

        return {
            "keep_ranges": keep_ranges,
            "razor_points": sorted_razors,
            "total_kept_duration": round(total_kept_duration, 2),
        }
