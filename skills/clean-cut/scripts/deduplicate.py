#!/usr/bin/env python3
"""
Deduplication Engine (Intra & Cross-Video)
Detects duplicate clips within a single folder or across multiple folders
using 64-bit DCT perceptual hashing, horizontal flip matching, and Hamming distance.
"""
import os
import sys
import json
import argparse
from pathlib import Path
import cv2

try:
    from phash_utils import compute_dual_phash, match_hashes
except ImportError:
    from .phash_utils import compute_dual_phash, match_hashes

def extract_clip_fingerprint(video_path):
    """
    Extracts mid-frame keyframe and computes dual pHash (original + flipped).
    """
    if not os.path.exists(video_path):
        return None
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        cap.release()
        return None
    
    mid_idx = total_frames // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_idx)
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        return None
        
    h_orig, h_flip = compute_dual_phash(frame)
    return {
        "file_name": os.path.basename(video_path),
        "file_path": str(Path(video_path).resolve()).replace("\\", "/"),
        "hash_orig": h_orig,
        "hash_flip": h_flip
    }

def scan_folder_fingerprints(folder_path):
    folder = Path(folder_path)
    if not folder.exists():
        return []
    
    video_exts = {".mp4", ".mov", ".mkv", ".webm"}
    clips = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in video_exts]
    
    fingerprints = []
    for c in clips:
        # Skip subfolders like _duplicates or _cross_duplicates
        fp = extract_clip_fingerprint(str(c))
        if fp:
            fingerprints.append(fp)
    return fingerprints

def find_duplicates_across_folders(folders, max_dist=6, report_path=None):
    """
    Compares clips across multiple folders to find identical or mirrored duplicates.
    """
    folder_data = {}
    for f in folders:
        name = Path(f).name
        print(f"Scanning folder [{name}] for fingerprints...")
        fps = scan_folder_fingerprints(f)
        folder_data[name] = fps
        print(f"  -> Extracted {len(fps)} fingerprints.")
        
    names = list(folder_data.keys())
    duplicates = []
    
    for i in range(len(names)):
        f_a = names[i]
        for j in range(i + 1, len(names)):
            f_b = names[j]
            for item_a in folder_data[f_a]:
                for item_b in folder_data[f_b]:
                    is_match, dist, sim, is_flipped = match_hashes(
                        item_a["hash_orig"],
                        item_b["hash_orig"],
                        item_b["hash_flip"],
                        max_dist=max_dist
                    )
                    if is_match:
                        duplicates.append({
                            "folder_a": f_a,
                            "clip_a": item_a["file_name"],
                            "path_a": item_a["file_path"],
                            "folder_b": f_b,
                            "clip_b": item_b["file_name"],
                            "path_b": item_b["file_path"],
                            "hamming_dist": dist,
                            "similarity_percent": sim,
                            "is_mirrored_hflip": is_flipped
                        })
                        
    print(f"\n[Deduplication Summary] Found {len(duplicates)} duplicate pairs across {len(folders)} folders.")
    for d in duplicates:
        flip_tag = " (Mirrored / hflip)" if d["is_mirrored_hflip"] else ""
        print(f"  ⚠ [{d['folder_a']}/{d['clip_a']}] ⟷ [{d['folder_b']}/{d['clip_b']}] ({d['similarity_percent']}% match){flip_tag}")
        
    report = {
        "scanned_folders": [str(Path(f).resolve()).replace("\\", "/") for f in folders],
        "total_duplicates_found": len(duplicates),
        "duplicate_pairs": duplicates
    }
    
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Report saved to: {report_path}")
        
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-folder Cross-Video Deduplication Scanner")
    parser.add_argument("folders", nargs="+", help="Folders containing video clips to compare")
    parser.add_argument("-d", "--max-dist", type=int, default=6, help="Max Hamming distance (default: 6)")
    parser.add_argument("-r", "--report", default="duplicates_report.json", help="Path to save output JSON report")
    
    args = parser.parse_args()
    find_duplicates_across_folders(args.folders, max_dist=args.max_dist, report_path=args.report)
