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
import numpy as np
import time
import json
import argparse
from PIL import Image, ImageDraw, ImageFont

def detect_and_match_scenes(video_path, min_scene_len_sec=1.5, threshold_delta=18.0, intro_cutoff_sec=15.0, output_json=None, save_frames=True):
    start_time = time.time()
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 23.976
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    min_scene_frames = int(round(min_scene_len_sec * fps))
    intro_cutoff_frame = int(intro_cutoff_sec * fps)

    video_dir = os.path.dirname(os.path.abspath(output_json)) if output_json else os.path.dirname(os.path.abspath(video_path))
    frames_cache_dir = os.path.join(video_dir, "frames_cache")
    if save_frames:
        os.makedirs(frames_cache_dir, exist_ok=True)

    print(f"=== Starting Frame-by-Frame Scene Detection & On-The-Fly Intro Match ===")
    print(f"Video: {video_path}")
    print(f"Total frames: {total_frames} @ {fps:.3f} fps ({total_frames/fps/60:.1f} min)")
    print(f"Intro cutoff: {intro_cutoff_sec}s ({intro_cutoff_frame} frames)")

    small_w, small_h = 160, 90
    prev_gray_center = None
    prev_hist = None
    raw_cuts = []
    
    frame_idx = 0
    t0 = time.time()
    
    # Pass 1: Ultra-fast sequential cut trigger detection (>3,200 fps)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        h, w = frame.shape[:2]
        crop_center = frame[:, int(w * 0.25):int(w * 0.75)]
        small_center = cv2.resize(crop_center, (small_w, small_h))
        gray_center = cv2.cvtColor(small_center, cv2.COLOR_BGR2GRAY)
        
        hsv_center = cv2.cvtColor(small_center, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv_center], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        
        if prev_gray_center is not None:
            diff_luma = float(np.mean(np.abs(gray_center.astype(np.float32) - prev_gray_center.astype(np.float32))))
            hist_corr = float(cv2.compareHist(hist, prev_hist, cv2.HISTCMP_CORREL))
            
            is_candidate_cut = (diff_luma >= threshold_delta and hist_corr < 0.65) or (diff_luma >= 35.0)
            if is_candidate_cut:
                raw_cuts.append((frame_idx, diff_luma, hist_corr))
                
        prev_gray_center = gray_center
        prev_hist = hist
        frame_idx += 1
        
    scan_elapsed = time.time() - t0
    print(f"Fast scan complete in {scan_elapsed:.2f}s ({frame_idx/scan_elapsed:.1f} fps). Raw cuts: {len(raw_cuts)}")

    # Filter cuts
    confirmed_cut_frames = []
    last_cut = 0
    for f_cut, diff, corr in raw_cuts:
        if f_cut - last_cut >= min_scene_frames:
            confirmed_cut_frames.append(f_cut)
            last_cut = f_cut

    all_scene_bounds = sorted(list(set([0] + confirmed_cut_frames + [total_frames])))
    print(f"Confirmed distinct scenes: {len(all_scene_bounds) - 1}")

    # Pass 2: Extract keyframe info and match Intro on-the-fly using ORB descriptors
    orb = cv2.ORB_create(400)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    scenes = []
    intro_buffer = []  # list of (intro_scene_id, keyframe_img, kp, des, mid_f, start, dur)

    print("Extracting keyframes, frame_info, and matching Intro...")
    for s_idx in range(len(all_scene_bounds) - 1):
        s_f = all_scene_bounds[s_idx]
        e_f = all_scene_bounds[s_idx + 1]
        mid_f = (s_f + e_f) // 2
        dur = round((e_f - s_f) / fps, 3)
        st = round(s_f / fps, 3)
        en = round(e_f / fps, 3)
        
        # Read mid frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_f)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
            
        h, w = frame.shape[:2]
        crop_clean = frame[int(h * 0.25):int(h * 0.75), int(w * 0.2):int(w * 0.8)]
        kp, des = orb.detectAndCompute(crop_clean, None)

        is_intro = s_f < intro_cutoff_frame
        matched_intro_id = None
        match_inliers = 0

        if is_intro:
            # Add to intro buffer
            intro_buffer.append({
                "intro_id": s_idx + 1,
                "frame": frame,
                "kp": kp,
                "des": des,
                "mid_f": mid_f,
                "start": st,
                "dur": dur
            })
        else:
            # Match against intro buffer using ORB inliers
            if des is not None and len(des) >= 10:
                best_inliers = 0
                best_intro = None
                for item in intro_buffer:
                    i_des = item['des']
                    if i_des is not None and len(i_des) >= 10:
                        matches = bf.match(i_des, des)
                        good = [m for m in matches if m.distance < 35]
                        if len(good) > best_inliers:
                            best_inliers = len(good)
                            best_intro = item['intro_id']
                if best_inliers >= 20:  # Confirmed structural match
                    matched_intro_id = best_intro
                    match_inliers = best_inliers
                    print(f"  🎯 Found Intro Match! Body Scene #{s_idx + 1} ({st}s) ⟷ Intro #{best_intro} with {best_inliers} ORB inliers!")

        # Save thumbnail in frames_cache if requested
        thumb_path = ""
        if save_frames:
            thumb_path = os.path.join(frames_cache_dir, f"scene_{s_idx + 1:04d}.jpg")
            thumb_img = cv2.resize(frame, (320, 180))
            cv2.imwrite(thumb_path, thumb_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

        scenes.append({
            "scene_id": s_idx + 1,
            "start_f": s_f,
            "end_f": e_f,
            "start": st,
            "end": en,
            "duration": dur,
            "total_frames": e_f - s_f,
            "mid_f": mid_f,
            "is_intro": is_intro,
            "matched_intro_id": matched_intro_id,
            "orb_inliers": match_inliers,
            "thumb_path": thumb_path
        })

    cap.release()

    if output_json:
        with open(output_json, 'w') as f:
            json.dump(scenes, f, indent=2)
        print(f"Saved {len(scenes)} scenes to {output_json}")

    # Generate side-by-side verification sheet for matches
    matched_scenes = [s for s in scenes if s.get('matched_intro_id')]
    print(f"\nTotal verified intro matches: {len(matched_scenes)}")
    
    total_time = time.time() - start_time
    print(f"Finished in {total_time:.2f}s!")
    return scenes

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min_len", type=float, default=1.5)
    parser.add_argument("--threshold", type=float, default=18.0)
    parser.add_argument("--cutoff", type=float, default=15.0)
    args = parser.parse_args()
    
    detect_and_match_scenes(args.video, min_scene_len_sec=args.min_len, threshold_delta=args.threshold, intro_cutoff_sec=args.cutoff, output_json=args.output)
