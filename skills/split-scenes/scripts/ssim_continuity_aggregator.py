import os
import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Auto-require and self-install dependencies
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import env_bootstrap
except Exception:
    pass

import cv2
import json
import argparse
import numpy as np
from skimage.metrics import structural_similarity as ssim

def aggregate_events(scenes_json_path, output_db_path, prefix="fail_87", out_clips_dir="/Volumes/External/clips/work_87", intro_count=7):
    scenes = json.load(open(scenes_json_path))
    
    # 1. Promoted clean scenes (from intro resolution)
    promoted_scenes = [s for s in scenes if s.get('is_promoted', False) or s.get('matched_intro_id') is not None]
    # Deduplicate promoted
    seen_ids = set()
    unique_promoted = []
    for p in promoted_scenes:
        if p['scene_id'] not in seen_ids and p['scene_id'] > intro_count:
            seen_ids.add(p['scene_id'])
            unique_promoted.append(p)

    # 2. Body scenes (skip intro_count and skip already promoted)
    body_scenes = [s for s in scenes[intro_count:] if s['scene_id'] not in seen_ids]
    
    print(f"=== Running SSIM & Palette Continuity Aggregator ===")
    print(f"Total raw shots in body: {len(body_scenes)} | Promoted highlight clips: {len(unique_promoted)}")

    merged_events = []
    curr = None

    for s in body_scenes:
        thumb = s.get('thumb_path', '')
        im = cv2.imread(thumb) if (thumb and os.path.exists(thumb)) else None
        
        if im is not None:
            gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
            gray_small = cv2.resize(gray, (160, 90))
            hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
            h = cv2.calcHist([hsv], [0, 1], None, [12, 12], [0, 180, 0, 256])
            cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
        else:
            gray_small = None
            h = None

        if curr is None:
            curr = {
                'start_f': s['start_f'],
                'end_f': s['end_f'],
                'start': s['start'],
                'end': s['end'],
                'duration': s['duration'],
                'shots_count': 1,
                'shot_ids': [s['scene_id']],
                'thumb_path': thumb,
                'last_gray': gray_small,
                'last_hist': h
            }
        else:
            is_same_event = False
            if curr['last_gray'] is not None and gray_small is not None:
                s_val = ssim(curr['last_gray'], gray_small)
                corr = cv2.compareHist(curr['last_hist'], h, cv2.HISTCMP_CORREL)
                
                # Rule 1: High structural similarity (same camera / background)
                # Rule 2: Moderate structural similarity + High palette correlation (angle switch in same room/car)
                # Rule 3: Very short shot (< 2.5s) following a high luma flash/impact
                is_same_event = (s_val > 0.22) or (s_val > 0.15 and corr > 0.68) or (s['duration'] < 2.5 and corr > 0.50)
                
            if is_same_event:
                curr['end_f'] = s['end_f']
                curr['end'] = s['end']
                curr['duration'] = round(curr['end'] - curr['start'], 3)
                curr['shots_count'] += 1
                curr['shot_ids'].append(s['scene_id'])
                curr['last_gray'] = gray_small
                curr['last_hist'] = h
            else:
                merged_events.append(curr)
                curr = {
                    'start_f': s['start_f'],
                    'end_f': s['end_f'],
                    'start': s['start'],
                    'end': s['end'],
                    'duration': s['duration'],
                    'shots_count': 1,
                    'shot_ids': [s['scene_id']],
                    'thumb_path': thumb,
                    'last_gray': gray_small,
                    'last_hist': h
                }

    if curr:
        merged_events.append(curr)

    # 3. Assemble final sequence: Promoted on top, followed by merged events
    final_db = []
    
    # Add promoted
    for idx, p in enumerate(unique_promoted, start=1):
        fn = f"{prefix}_{idx:03d}.mp4"
        final_db.append({
            "order_id": idx,
            "file_name": fn,
            "file_path": os.path.join(out_clips_dir, fn),
            "start_f": p['start_f'],
            "end_f": p['end_f'],
            "total_frames": p['total_frames'],
            "start": p['start'],
            "end": p['end'],
            "duration": p['duration'],
            "is_promoted": True,
            "shots_count": 1,
            "thumb_path": p.get('thumb_path', '')
        })

    # Add merged events
    start_order = len(final_db) + 1
    for idx, e in enumerate(merged_events, start=start_order):
        fn = f"{prefix}_{idx:03d}.mp4"
        final_db.append({
            "order_id": idx,
            "file_name": fn,
            "file_path": os.path.join(out_clips_dir, fn),
            "start_f": e['start_f'],
            "end_f": e['end_f'],
            "total_frames": e['end_f'] - e['start_f'],
            "start": e['start'],
            "end": e['end'],
            "duration": e['duration'],
            "is_promoted": False,
            "shots_count": e['shots_count'],
            "merged_shot_ids": e['shot_ids'],
            "thumb_path": e['thumb_path']
        })

    os.makedirs(os.path.dirname(os.path.abspath(output_db_path)), exist_ok=True)
    with open(output_db_path, 'w') as f:
        json.dump(final_db, f, indent=2)

    durations = [e['duration'] for e in final_db]
    print(f"\n✅ Aggregation Complete! {len(body_scenes)} raw shots merged into {len(final_db)} Complete Story Events!")
    print(f"Output database: {output_db_path}")
    print(f"Average event duration: {np.mean(durations):.1f}s | Median: {np.median(durations):.1f}s | Min: {np.min(durations):.1f}s | Max: {np.max(durations):.1f}s")
    return final_db

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prefix", default="fail_87")
    parser.add_argument("--clips_dir", default="/Volumes/External/clips/work_87")
    parser.add_argument("--intro_count", type=int, default=7)
    args = parser.parse_args()
    
    aggregate_events(args.scenes, args.output, prefix=args.prefix, out_clips_dir=args.clips_dir, intro_count=args.intro_count)
