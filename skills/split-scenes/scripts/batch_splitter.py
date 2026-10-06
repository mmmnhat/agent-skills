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

import json
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

def split_single_clip(clip_info, video_src):
    out_file = clip_info['file_path']
    # If already exists and valid size (> 50KB), skip
    if os.path.exists(out_file) and os.path.getsize(out_file) > 50000:
        return clip_info['order_id'], True, "already_exists"
        
    start_sec = clip_info['start']
    total_frames = clip_info['total_frames']
    
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_sec),
        '-i', video_src,
        '-vframes', str(total_frames),
        '-c:v', 'libx264', '-crf', '18', '-preset', 'ultrafast',
        '-c:a', 'aac',
        out_file
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return clip_info['order_id'], True, "ok"
    except Exception as e:
        return clip_info['order_id'], False, str(e)

def batch_split(scene_db_path, video_src, max_workers=6):
    t0 = time.time()
    with open(scene_db_path, 'r') as f:
        clips = json.load(f)
        
    total_clips = len(clips)
    tag = os.path.basename(os.path.dirname(scene_db_path))
    print(f"=== Starting Batch Split for [{tag}] ===")
    print(f"Total clips to split: {total_clips}")
    print(f"Source video: {video_src}")
    print(f"Workers: {max_workers}")
    
    completed_count = 0
    errors = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(split_single_clip, c, video_src): c for c in clips}
        
        for future in as_completed(futures):
            order_id, success, status = future.result()
            if success:
                completed_count += 1
            else:
                errors += 1
                print(f"Error splitting clip #{order_id}: {status}")
                
            if completed_count % 50 == 0 or completed_count == total_clips:
                elapsed = time.time() - t0
                speed = completed_count / max(0.1, elapsed)
                print(f"[{tag}] Progress: {completed_count}/{total_clips} clips ({completed_count/total_clips*100:.1f}%) | {speed:.1f} clips/s | Elapsed: {elapsed:.1f}s")
                
    total_time = time.time() - t0
    print(f"\n[{tag}] Batch Split Completed in {total_time:.2f}s ({total_time/60:.1f} min)!")
    print(f"Successfully created: {completed_count}/{total_clips} clips (Errors: {errors})")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to scene_db.json")
    parser.add_argument("--video", required=True, help="Path to source original video")
    parser.add_argument("--workers", type=int, default=6, help="Number of concurrent ffmpeg workers")
    args = parser.parse_args()
    
    batch_split(args.db, args.video, max_workers=args.workers)
