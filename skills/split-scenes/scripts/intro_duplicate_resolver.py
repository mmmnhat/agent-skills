import os
import sys

# Auto-require and self-install dependencies
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import env_bootstrap
except Exception:
    pass

import cv2
import json
import numpy as np
import time
import argparse

def resolve_intro_duplicates(video_path, scenes_json_path, intro_cutoff_sec=20.0, similarity_threshold=0.68):
    t0 = time.time()
    with open(scenes_json_path, 'r') as f:
        scenes = json.load(f)
        
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 23.976
    
    # 1. Identify teaser scenes (scenes that occur before intro_cutoff_sec)
    intro_scenes = [s for s in scenes if s['start'] < intro_cutoff_sec]
    body_scenes = [s for s in scenes if s['start'] >= intro_cutoff_sec]
    
    print(f"=== Intro Duplicate Resolver ===")
    print(f"Video: {video_path}")
    print(f"Total scenes: {len(scenes)} | Intro teaser candidates: {len(intro_scenes)} (cutoff: {intro_cutoff_sec}s)")
    
    # 2. Extract feature fingerprints for all scenes in a single forward pass
    # We sample 3 points per scene: 25%, 50%, 75%
    print("Extracting visual fingerprints...")
    
    def extract_fingerprint(frame):
        h, w = frame.shape[:2]
        # Crop center 50% width and bottom 65% height (to avoid top teaser titles)
        crop = frame[int(h * 0.35):, int(w * 0.25):int(w * 0.75)]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    scene_features = {}
    
    # Single forward pass through video
    for s in scenes:
        mid_f = (s['start_f'] + s['end_f']) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_f)
        ret, frame = cap.read()
        if ret and frame is not None:
            scene_features[s['scene_id']] = extract_fingerprint(frame)
            
    cap.release()
    print(f"Extracted {len(scene_features)} scene fingerprints in {time.time() - t0:.2f}s")
    
    # 3. Match each intro scene with body scenes
    matches = []
    matched_body_scene_ids = set()
    
    for intro_s in intro_scenes:
        i_id = intro_s['scene_id']
        i_feat = scene_features.get(i_id)
        if i_feat is None:
            continue
            
        best_match = None
        best_score = -1.0
        
        for body_s in body_scenes:
            b_id = body_s['scene_id']
            b_feat = scene_features.get(b_id)
            if b_feat is None:
                continue
                
            score = float(cv2.compareHist(i_feat, b_feat, cv2.HISTCMP_CORREL))
            if score > best_score:
                best_score = score
                best_match = body_s
                
        if best_match and best_score >= similarity_threshold:
            matches.append({
                "intro_scene_id": i_id,
                "intro_start": intro_s['start'],
                "intro_dur": intro_s['duration'],
                "full_scene_id": best_match['scene_id'],
                "full_start": best_match['start'],
                "full_dur": best_match['duration'],
                "similarity": round(best_score, 3)
            })
            matched_body_scene_ids.add(best_match['scene_id'])
            
    print(f"\nFound {len(matches)} Teaser Intro matches:")
    for m in matches:
        print(f"  • Intro #{m['intro_scene_id']} ({m['intro_start']}s, {m['intro_dur']}s) ⟷ Full #{m['full_scene_id']} ({m['full_start']}s, {m['full_dur']}s) [Similarity: {m['similarity']*100:.1f}%]")
        
    return {
        "intro_scene_count": len(intro_scenes),
        "matches": matches,
        "matched_body_scene_ids": list(matched_body_scene_ids)
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--scenes", required=True)
    parser.add_argument("--cutoff", type=float, default=20.0)
    parser.add_argument("--threshold", type=float, default=0.65)
    args = parser.parse_args()
    
    resolve_intro_duplicates(args.video, args.scenes, intro_cutoff_sec=args.cutoff, similarity_threshold=args.threshold)
