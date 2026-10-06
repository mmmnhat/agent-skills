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
from PIL import Image, ImageDraw, ImageFont

def compute_phash(img):
    resized = cv2.resize(img, (32, 32))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if len(resized.shape) == 3 else resized
    dct = cv2.dct(np.float32(gray))
    dct_low = dct[:8, :8]
    med = np.median(dct_low)
    return (dct_low > med).flatten()

def hamming(h1, h2):
    return np.count_nonzero(h1 != h2)

def extract_video_hashes(db_path):
    db = json.load(open(db_path))
    hashes = []
    for e in db:
        p = e.get('thumb_path', '')
        if p and os.path.exists(p):
            im = cv2.imread(p)
            if im is not None:
                h = compute_phash(im)
                hashes.append({
                    'order_id': e['order_id'],
                    'file_name': e['file_name'],
                    'file_path': e['file_path'],
                    'start': e['start'],
                    'duration': e['duration'],
                    'thumb_path': p,
                    'hash': h
                })
    return hashes

def check_intra_duplicates(db_path, max_dist=4):
    hashes = extract_video_hashes(db_path)
    dups = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            d = hamming(hashes[i]['hash'], hashes[j]['hash'])
            if d <= max_dist:
                sim = round((1 - d / 64) * 100, 1)
                dups.append({
                    'clip_a': hashes[i]['file_name'],
                    'start_a': hashes[i]['start'],
                    'clip_b': hashes[j]['file_name'],
                    'start_b': hashes[j]['start'],
                    'dist': int(d),
                    'similarity': sim,
                    'thumb_a': hashes[i]['thumb_path'],
                    'thumb_b': hashes[j]['thumb_path']
                })
    print(f"Intra-Video Duplicates for {os.path.basename(db_path)}: {len(dups)} found")
    return dups

def check_cross_duplicates(db_paths, max_dist=4, out_report_path=None):
    print(f"=== Running Cross-Video Deduplication across {len(db_paths)} videos ===")
    video_hashes = {}
    for p in db_paths:
        tag = os.path.basename(os.path.dirname(p))
        video_hashes[tag] = extract_video_hashes(p)
        print(f"Loaded {len(video_hashes[tag])} clip hashes from [{tag}]")

    tags = list(video_hashes.keys())
    cross_dups = []

    for i in range(len(tags)):
        tag_a = tags[i]
        for j in range(i + 1, len(tags)):
            tag_b = tags[j]
            ha = video_hashes[tag_a]
            hb = video_hashes[tag_b]
            
            pair_count = 0
            for item_a in ha:
                for item_b in hb:
                    d = hamming(item_a['hash'], item_b['hash'])
                    if d <= max_dist:
                        sim = round((1 - d / 64) * 100, 1)
                        cross_dups.append({
                            'video_a': tag_a,
                            'clip_a': item_a['file_name'],
                            'start_a': item_a['start'],
                            'thumb_a': item_a['thumb_path'],
                            'video_b': tag_b,
                            'clip_b': item_b['file_name'],
                            'start_b': item_b['start'],
                            'thumb_b': item_b['thumb_path'],
                            'dist': int(d),
                            'similarity': sim
                        })
                        pair_count += 1
            print(f"Found {pair_count} duplicate clips between [{tag_a}] and [{tag_b}]")

    if out_report_path:
        with open(out_report_path, 'w') as f:
            json.dump(cross_dups, f, indent=2)
        print(f"Saved cross-duplicate report to {out_report_path}")

    return cross_dups

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbs", nargs="+", required=True, help="List of scene_db.json files")
    parser.add_argument("--max_dist", type=int, default=4, help="Max Hamming distance (0-64, default 4)")
    parser.add_argument("--report", default=None, help="Output json report path")
    args = parser.parse_args()

    if len(args.dbs) == 1:
        check_intra_duplicates(args.dbs[0], max_dist=args.max_dist)
    else:
        check_cross_duplicates(args.dbs, max_dist=args.max_dist, out_report_path=args.report)
