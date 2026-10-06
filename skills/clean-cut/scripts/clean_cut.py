#!/usr/bin/env python3
"""
Clean-Cut Main Engine (High-Performance Lean Edition)
Fast-proxy scene detection, unblur cropping, dynamic reframe linking,
single-pass RAM audio zero-cut snapping, 64-bit integer POPCNT deduplication,
and unified single-pass filmstrip & temporal landmark generation.
"""
import os
import sys
import json
import functools
import argparse
import subprocess
import shutil
import concurrent.futures
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Import companion modules
try:
    from unblur_detector import detect_unblur_box
    from audio_snapper import load_audio_buffer, snap_audio_cut_in_ram
    from phash_utils import compute_dual_phash, match_hashes
    from temporal_analyzer import analyze_and_generate_filmstrip
    from scene_context_engine import synthesize_scene_context
except ImportError:
    from .unblur_detector import detect_unblur_box
    from .audio_snapper import load_audio_buffer, snap_audio_cut_in_ram
    from .phash_utils import compute_dual_phash, match_hashes
    from .temporal_analyzer import analyze_and_generate_filmstrip
    from .scene_context_engine import synthesize_scene_context

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "output_dir": "output_clean_cut",
        "prefix": "scene_",
        "unblur_enabled": True,
        "min_scene_duration_sec": 1.2,
        "detector_threshold": 27.0,
        "audio_snap_window_sec": 0.25,
        "deduplication": {
            "enable_intra_dedup": True,
            "intro_cutoff_sec": 30.0,
            "similarity_threshold": 0.70,
            "max_phash_distance": 6,
            "enable_cross_dedup": True,
            "library_index_file": "library_index.json",
            "move_duplicates": True
        },
        "encoder": "auto",
        "premiere_pro": {
            "auto_import": False,
            "sequence_name": "CleanCut_Timeline"
        }
    }

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to save config.json: {e}")

def resolve_library_index_path(cfg):
    dedup_cfg = cfg.get("deduplication", {})
    idx_name = dedup_cfg.get("library_index_file", "library_index.json")
    skill_dir = Path(__file__).resolve().parent.parent
    return skill_dir / idx_name

def load_library_index(index_path):
    if index_path.exists():
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"clips": []}

def save_library_index(index_path, data):
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to save library index: {e}")

@functools.lru_cache(maxsize=1)
def get_best_encoder(user_choice="auto"):
    if user_choice != "auto":
        return user_choice
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        out = res.stdout
        if "h264_nvenc" in out:
            return "h264_nvenc"
        if "h264_videotoolbox" in out:
            return "h264_videotoolbox"
        if "h264_amf" in out:
            return "h264_amf"
        if "h264_mf" in out:
            return "h264_mf"
    except Exception:
        pass
    return "libx264"

def get_hsv_hist(frame):
    if frame is None:
        return None
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    return cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

_sift_engine = None
_bf_matcher = None

def get_geometric_inliers(f1, f2):
    global _sift_engine, _bf_matcher
    if f1 is None or f2 is None:
        return 0
    if _sift_engine is None:
        _sift_engine = cv2.SIFT_create(nfeatures=600)
        _bf_matcher = cv2.BFMatcher()
    s1 = cv2.resize(f1, (640, 360))
    s2 = cv2.resize(f2, (640, 360))
    mask = np.zeros((360, 640), dtype=np.uint8)
    mask[int(360 * 0.15):int(360 * 0.85), :] = 255
    kp1, des1 = _sift_engine.detectAndCompute(s1, mask)
    kp2, des2 = _sift_engine.detectAndCompute(s2, mask)
    if des1 is None or des2 is None or len(des1) < 8 or len(des2) < 8:
        return 0
    matches = _bf_matcher.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return 0
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    _, h_mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    return int(np.sum(h_mask)) if h_mask is not None else 0

def resolve_video_input(src):
    if src.startswith("http://") or src.startswith("https://"):
        print(f"Downloading stream via yt-dlp: {src}")
        out_name = "downloaded_input.mp4"
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
            "-o", out_name, src
        ]
        subprocess.check_call(cmd)
        return out_name
    return src

def generate_fast_proxy(video_path, proxy_path, height=240):
    """
    Generates an ultra-fast hardware-accelerated proxy (240p at NATIVE video framerate H.264)
    using CUVID/CUDA (on NVIDIA) or VideoToolbox (on Apple Silicon) or ultrafast CPU.
    Preserves exact 1:1 frame alignment with master video to eliminate boundary bleed.
    """
    p_path = Path(proxy_path)
    if p_path.exists() and p_path.stat().st_size > 10000:
        print(f"  • Using existing hardware proxy: {p_path.name}")
        return str(p_path)
        
    print(f"  • Generating fast hardware proxy ({height}p @ native FPS)...")
    
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        codec = subprocess.check_output(probe_cmd, text=True).strip().lower()
    except Exception:
        codec = ""
        
    cuvid_decoders = {
        "av1": "av1_cuvid",
        "h264": "h264_cuvid",
        "hevc": "hevc_cuvid"
    }
    cuvid_dec = cuvid_decoders.get(codec)
    
    enc = get_best_encoder()
    cmd = ["ffmpeg", "-y"]
    if "nvenc" in enc:
        if cuvid_dec:
            cmd.extend(["-c:v", cuvid_dec])
        else:
            cmd.extend(["-hwaccel", "cuda"])
        cmd.extend([
            "-i", str(video_path),
            "-vf", f"scale=-2:{height}",
            "-c:v", "h264_nvenc",
            "-preset", "p1",
            "-an",
            str(p_path)
        ])
    elif "videotoolbox" in enc:
        cmd.extend([
            "-i", str(video_path),
            "-vf", f"scale=-2:{height}",
            "-c:v", "h264_videotoolbox",
            "-b:v", "1000k",
            "-an",
            str(p_path)
        ])
    else:
        cmd.extend([
            "-i", str(video_path),
            "-vf", f"scale=-2:{height}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-an",
            str(p_path)
        ])
    
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(f"  ✓ Fast hardware proxy ready: {p_path.name}")
        return str(p_path)
    except Exception as e:
        print(f"  ! Warning: Hardware proxy failed ({e}), falling back to master video.")
        return str(video_path)

def run_clean_cut(video_path, output_dir=None, prefix=None, threshold=None, min_duration=None, unblur=None, limit=None):
    cfg = load_config()
    out_dir = output_dir or cfg.get("output_dir", "output_clean_cut")
    pfx = prefix if prefix is not None else cfg.get("prefix", "scene_")
    det_thresh = threshold if threshold is not None else cfg.get("detector_threshold", 27.0)
    min_dur = min_duration if min_duration is not None else cfg.get("min_scene_duration_sec", 1.2)
    do_unblur = unblur if unblur is not None else cfg.get("unblur_enabled", True)
    snap_window = cfg.get("audio_snap_window_sec", 0.25)
    
    dedup_cfg = cfg.get("deduplication", {})
    enable_intra = dedup_cfg.get("enable_intra_dedup", True)
    intro_cutoff = dedup_cfg.get("intro_cutoff_sec", 30.0)
    max_phash_dist = dedup_cfg.get("max_phash_distance", 6)
    enable_cross = dedup_cfg.get("enable_cross_dedup", True)
    move_duplicates = dedup_cfg.get("move_duplicates", True)

    cfg["output_dir"] = out_dir
    cfg["prefix"] = pfx
    cfg["detector_threshold"] = det_thresh
    cfg["min_scene_duration_sec"] = min_dur
    cfg["unblur_enabled"] = do_unblur
    save_config(cfg)
    
    # Clean previous run clips, thumbnails, duplicates, and manifests (preserving proxy cache)
    if os.path.exists(out_dir):
        for sub in ["scenes", "thumbnails", "manifests", "duplicates", "exports"]:
            sub_p = os.path.join(out_dir, sub)
            if os.path.exists(sub_p):
                try:
                    shutil.rmtree(sub_p)
                except Exception:
                    pass
        for fname in os.listdir(out_dir):
            fpath = os.path.join(out_dir, fname)
            if fname.endswith("_proxy240p.mp4") or fname == "cache":
                continue
            if os.path.isfile(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
        print(f"  🧹 Cleaned previous run artifacts in '{out_dir}'.")

    os.makedirs(out_dir, exist_ok=True)
    scenes_dir = os.path.join(out_dir, "scenes")
    os.makedirs(scenes_dir, exist_ok=True)
    thumb_dir = os.path.join(out_dir, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    manifest_dir = os.path.join(out_dir, "manifests")
    os.makedirs(manifest_dir, exist_ok=True)
    cache_dir = os.path.join(out_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    exports_dir = os.path.join(out_dir, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    
    dup_dir = os.path.join(out_dir, "duplicates", "intra")
    cross_dup_dir = os.path.join(out_dir, "duplicates", "cross")
    if move_duplicates:
        os.makedirs(dup_dir, exist_ok=True)
        os.makedirs(cross_dup_dir, exist_ok=True)

    real_video = resolve_video_input(video_path)
    video_stem = Path(real_video).stem
    
    if not os.path.exists(real_video):
        raise FileNotFoundError(f"Video file not found: {real_video}")
        
    encoder = get_best_encoder(cfg.get("encoder", "auto"))
    print(f"\n[Clean-Cut Milestone 1] Initializing & Fast-Proxy Scanning: '{real_video}'")
    print(f"  • Hardware Encoder: {encoder}")
    print(f"  • Detector Threshold: {det_thresh} | Min Duration: {min_dur}s")
    print(f"  • Unblur Detection: {'Enabled' if do_unblur else 'Disabled'}")
    print(f"  • Deduplication: Intra-video={'ON' if enable_intra else 'OFF'} | Cross-video={'ON' if enable_cross else 'OFF'}")

    # Generate hardware proxy in cache/ for ultra-fast scene detection & visual landmark extraction
    proxy_path = os.path.join(cache_dir, f"{video_stem}_proxy240p.mp4")
    # Check if legacy proxy existed in out_dir root and reuse it
    legacy_proxy = os.path.join(out_dir, f"{video_stem}_proxy240p.mp4")
    if os.path.exists(legacy_proxy) and not os.path.exists(proxy_path):
        try:
            shutil.move(legacy_proxy, proxy_path)
        except Exception:
            pass
    scan_video = generate_fast_proxy(real_video, proxy_path, height=240)

    # 1. Fast-Proxy Scene Detection via PySceneDetect in RAM
    from scenedetect import open_video, SceneManager, ContentDetector
    video = open_video(scan_video)
    proxy_fps = video.frame_rate
    proxy_total_frames = video.duration.frame_num
    
    sm = SceneManager()
    sm.auto_downscale = False  # Proxy is already 240p
    min_frames = max(5, int(min_dur * proxy_fps))
    sm.add_detector(ContentDetector(threshold=det_thresh, min_scene_len=min_frames))
    
    sm.detect_scenes(video, frame_skip=0)
    raw_scenes = sm.get_scene_list()
    
    if not raw_scenes:
        from scenedetect import FrameTimecode
        raw_scenes = [(FrameTimecode(0, proxy_fps), FrameTimecode(proxy_total_frames, proxy_fps))]
    
    print(f"  -> Detected {len(raw_scenes)} raw candidate cut points in RAM (Native 60fps frame-exact).")

    # 2. Extract Keyframes & Analyze Unblur, Continuity & Fingerprints (Directly on 1080p Master)
    cap_info = cv2.VideoCapture(real_video)
    master_fps = cap_info.get(cv2.CAP_PROP_FPS) or proxy_fps
    master_w = int(cap_info.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    master_h = int(cap_info.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    cap_info.release()

    cap = cv2.VideoCapture(scan_video)

    shots = []
    for idx, (s, e) in enumerate(raw_scenes):
        s_sec = s.get_seconds() if not hasattr(s, "seconds") else s.seconds
        e_sec = e.get_seconds() if not hasattr(e, "seconds") else e.seconds
        s_fn = s.frame_num if hasattr(s, "frame_num") else int(round(s_sec * master_fps))
        e_fn = e.frame_num if hasattr(e, "frame_num") else int(round(e_sec * master_fps))
        dur = e_sec - s_sec
        if dur < (min_dur * 0.7):
            continue
        # Read frames from proxy in RAM (<5ms seek) with multi-checkpoint unblur check
        mid_frame_fn = int(((s_fn + e_fn) / 2))
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_fn)
        ret, frame_proxy = cap.read()
        if not ret or frame_proxy is None:
            continue

        sample_fns = [
            int(s_fn + dur * 0.25 * master_fps),
            mid_frame_fn,
            int(s_fn + dur * 0.75 * master_fps)
        ]
        has_blur = False
        detected_boxes = []
        for s_fn_sample in sample_fns:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(proxy_total_frames - 1, s_fn_sample)))
            ret_s, frame_s = cap.read()
            if ret_s and frame_s is not None and do_unblur:
                b_blur, b_box, b_ratio = detect_unblur_box(frame_s, target_res=(master_w, master_h))
                if b_blur:
                    has_blur = True
                    detected_boxes.append((b_box, b_ratio))

        if has_blur and detected_boxes:
            min_bw = min(b[0][2] for b in detected_boxes)
            min_bh = min(b[0][3] for b in detected_boxes)
            cx, cy = master_w // 2, master_h // 2
            x1 = max(0, ((cx - min_bw // 2) // 2) * 2)
            y1 = max(0, ((cy - min_bh // 2) // 2) * 2)
            box_master = (x1, y1, min_bw, min_bh)
            ratio = min_bw / float(min_bh)
            if ratio < 0.65:
                aspect_ratio = "9:16"
            elif ratio < 0.88:
                aspect_ratio = "4:5"
            elif ratio < 1.15:
                aspect_ratio = "1:1"
            elif ratio < 1.45:
                aspect_ratio = "4:3"
            else:
                aspect_ratio = "16:9"
        else:
            aspect_ratio = "16:9" if (master_w / master_h >= 1.5) else "9:16"
            box_master = (0, 0, master_w, master_h)
            
        bx, by, bw, bh = box_master
        # Scale crop box to proxy dimensions for scale-invariant pHash and HSV histogram
        scale_x = frame_proxy.shape[1] / float(master_w)
        scale_y = frame_proxy.shape[0] / float(master_h)
        pbx = int(bx * scale_x)
        pby = int(by * scale_y)
        pbw = max(10, int(bw * scale_x))
        pbh = max(10, int(bh * scale_y))
        clean_crop_p = frame_proxy[pby:pby+pbh, pbx:pbx+pbw]
        # Boundary frames for temporal continuity stitching
        head_fn = min(proxy_total_frames - 1, s_fn + 2)
        tail_fn = max(0, min(proxy_total_frames - 1, e_fn - 2))
        cap.set(cv2.CAP_PROP_POS_FRAMES, head_fn)
        ret_h, frame_head = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, tail_fn)
        ret_t, frame_tail = cap.read()

        head_crop = frame_head[pby:pby+pbh, pbx:pbx+pbw] if (ret_h and frame_head is not None) else clean_crop_p
        tail_crop = frame_tail[pby:pby+pbh, pbx:pbx+pbw] if (ret_t and frame_tail is not None) else clean_crop_p

        head_hist = get_hsv_hist(head_crop)
        tail_hist = get_hsv_hist(tail_crop)
        
        shots.append({
            "raw_start": s_sec,
            "raw_end": e_sec,
            "raw_start_fn": s_fn,
            "raw_end_fn": e_fn,
            "dur": dur,
            "mid_frame": cv2.resize(frame_proxy, (320, 180)),
            "head_frame": cv2.resize(frame_head, (320, 180)) if (ret_h and frame_head is not None) else None,
            "tail_frame": cv2.resize(frame_tail, (320, 180)) if (ret_t and frame_tail is not None) else None,
            "hist": hist,
            "head_hist": head_hist,
            "tail_hist": tail_hist,
            "hash_orig": h_orig,
            "hash_flip": h_flip,
            "has_blur": has_blur,
            "box": box_master,
            "box_proxy": (pbx, pby, pbw, pbh),
            "aspect_ratio": aspect_ratio
        })

    # 3. Incident Grouping & Continuous Action Unification
    incidents = []
    current_incident_id = 1
    
    for i, s in enumerate(shots):
        if not incidents:
            s["incident_id"] = current_incident_id
            s["shot_index"] = 1
            s["is_continuation"] = False
            s["continuation_of"] = None
            s["variation_type"] = "base"
            incidents.append(s)
            continue
            
        prev = incidents[-1]

        # A. Boundary continuity (tail of prev vs head of current shot)
        boundary_corr = 0.0
        if prev.get("tail_hist") is not None and s.get("head_hist") is not None:
            boundary_corr = float(cv2.compareHist(prev["tail_hist"], s["head_hist"], cv2.HISTCMP_CORREL))

        mid_corr = 0.0
        if prev.get("hist") is not None and s.get("hist") is not None:
            mid_corr = float(cv2.compareHist(prev["hist"], s["hist"], cv2.HISTCMP_CORREL))

        is_hard_stitch = False
        is_linked_reframe = False

        # Case 1: Hard Stitch (Single action false split by flash, rapid motion blur, or lighting change)
        if (boundary_corr >= 0.58) or (mid_corr >= 0.62 and prev["aspect_ratio"] == s["aspect_ratio"]):
            is_hard_stitch = True
        elif (boundary_corr >= 0.35 or mid_corr >= 0.35) and prev["aspect_ratio"] == s["aspect_ratio"]:
            inl = get_geometric_inliers(prev.get("tail_frame", prev.get("mid_frame")), s.get("head_frame", s.get("mid_frame")))
            if inl >= 10:
                is_hard_stitch = True

        if is_hard_stitch:
            # Merge seamlessly into prev shot so the action stays unbroken
            prev["raw_end"] = s["raw_end"]
            prev["raw_end_fn"] = s["raw_end_fn"]
            prev["dur"] = round(prev["raw_end"] - prev["raw_start"], 2)
            prev["hist"] = s["hist"]
            prev["tail_hist"] = s["tail_hist"]
            prev["tail_frame"] = s.get("tail_frame")
            prev["mid_frame"] = s["mid_frame"]
            if prev["has_blur"] or s["has_blur"]:
                prev["has_blur"] = True
                bw_prev = prev["box"][2] if prev["has_blur"] else master_w
                bh_prev = prev["box"][3] if prev["has_blur"] else master_h
                bw_curr = s["box"][2] if s["has_blur"] else master_w
                bh_curr = s["box"][3] if s["has_blur"] else master_h
                min_bw = min(bw_prev, bw_curr)
                min_bh = min(bh_prev, bh_curr)
                cx, cy = master_w // 2, master_h // 2
                x1 = max(0, ((cx - min_bw // 2) // 2) * 2)
                y1 = max(0, ((cy - min_bh // 2) // 2) * 2)
                prev["box"] = (x1, y1, min_bw, min_bh)
                ratio = min_bw / float(min_bh)
                if ratio < 0.65:
                    prev["aspect_ratio"] = "9:16"
                elif ratio < 0.88:
                    prev["aspect_ratio"] = "4:5"
                elif ratio < 1.15:
                    prev["aspect_ratio"] = "1:1"
                elif ratio < 1.45:
                    prev["aspect_ratio"] = "4:3"
                else:
                    prev["aspect_ratio"] = "16:9"
            continue

        # Case 2: Multi-shot Incident Linking (Different angle, zoom reframe, or replay of the SAME incident)
        is_hash_match, dist, sim, is_flipped = match_hashes(
            prev["hash_orig"], s["hash_orig"], s["hash_flip"], max_dist=12
        )
        if is_hash_match or (mid_corr >= 0.40 and s["aspect_ratio"] != prev["aspect_ratio"]):
            is_linked_reframe = True
        elif mid_corr >= 0.35:
            inl = get_geometric_inliers(prev.get("mid_frame"), s.get("mid_frame"))
            if inl >= 12:
                is_linked_reframe = True

        if is_linked_reframe:
            # Separate file, but grouped under the same incident_id
            s["incident_id"] = prev["incident_id"]
            s["shot_index"] = prev["shot_index"] + 1
            s["is_continuation"] = True
            s["continuation_of"] = prev["incident_id"]
            s["variation_type"] = "reframe" if s["aspect_ratio"] != prev["aspect_ratio"] else "angle_b"
            incidents.append(s)
            continue

        # Case 3: Completely new independent incident
        current_incident_id += 1
        s["incident_id"] = current_incident_id
        s["shot_index"] = 1
        s["is_continuation"] = False
        s["continuation_of"] = None
        s["variation_type"] = "base"
        incidents.append(s)

    if limit and limit > 0:
        incidents = incidents[:limit]

    # 4. Intra-Video Deduplication (Fast 64-bit bit_count POPCNT)
    intra_duplicate_indices = set()
    intra_matches = {}
    
    if enable_intra and len(incidents) > 1:
        for i in range(len(incidents)):
            for j in range(i + 1, len(incidents)):
                if j in intra_duplicate_indices:
                    continue
                cand_a = incidents[i]
                cand_b = incidents[j]
                
                is_match, dist, sim, is_flipped = match_hashes(
                    cand_a["hash_orig"],
                    cand_b["hash_orig"],
                    cand_b["hash_flip"],
                    max_dist=max_phash_dist
                )
                
                if is_match:
                    a_is_intro = cand_a["raw_start"] < intro_cutoff
                    b_is_intro = cand_b["raw_start"] < intro_cutoff
                    
                    if a_is_intro and not b_is_intro:
                        dup_idx, master_idx = i, j
                        dup_type = "intro_teaser"
                    elif b_is_intro and not a_is_intro:
                        dup_idx, master_idx = j, i
                        dup_type = "intro_teaser"
                    else:
                        if cand_a["dur"] >= cand_b["dur"]:
                            dup_idx, master_idx = j, i
                        else:
                            dup_idx, master_idx = i, j
                        dup_type = "replay"
                        
                    intra_duplicate_indices.add(dup_idx)
                    intra_matches[dup_idx] = {
                        "master_idx": master_idx,
                        "dup_type": dup_type,
                        "similarity": sim,
                        "is_flipped": is_flipped
                    }

    # 5. Cross-Video Deduplication against Library Index
    lib_path = resolve_library_index_path(cfg)
    lib_index = load_library_index(lib_path)
    existing_lib_clips = lib_index.get("clips", [])
    
    cross_duplicates = {}
    new_lib_entries = []
    
    if enable_cross and existing_lib_clips:
        for idx, inc in enumerate(incidents):
            if idx in intra_duplicate_indices:
                continue
            for entry in existing_lib_clips:
                if entry.get("source_video") == video_stem:
                    continue
                is_match, dist, sim, is_flipped = match_hashes(
                    inc["hash_orig"],
                    entry.get("hash_orig"),
                    entry.get("hash_flip"),
                    max_dist=max_phash_dist
                )
                if is_match:
                    cross_duplicates[idx] = {
                        "matched_source_video": entry.get("source_video"),
                        "matched_clip": entry.get("file_name"),
                        "similarity": sim,
                        "is_flipped": is_flipped
                    }
                    break

    print(f"\n[Clean-Cut Milestone 2] Deduplication & Temporal Extraction:")
    print(f"  • Total scenes detected: {len(incidents)}")
    print(f"  • Intra-video duplicates (Teaser/Replay): {len(intra_duplicate_indices)} clips filtered")
    print(f"  • Cross-video duplicates from library: {len(cross_duplicates)} clips matched")

    # 6. Unified Temporal/Filmstrip Generation & Sub-frame Boundary Enforcement
    if limit is not None and limit > 0:
        incidents = incidents[:limit]
        print(f"  • Limiting export to first {len(incidents)} scenes per --limit {limit}", flush=True)
        
    final_scenes = []
    
    for idx, inc in enumerate(incidents, start=1):
        zero_idx = idx - 1
        s_fn = inc.get("raw_start_fn", int(round(inc["raw_start"] * master_fps)))
        e_fn = inc.get("raw_end_fn", int(round(inc["raw_end"] * master_fps)))
        
        # Absolute frame-exact boundary enforcement: ZERO frame bleed!
        # Head seeks to (s_fn - 0.25) / master_fps (25% before s_fn, safely past s_fn - 1)
        # Tail cuts off half a frame before e_fn to prevent decoding the first frame of the next shot
        num_frames = max(5, e_fn - s_fn)
        s_seek = max(0.0, (s_fn - 0.25) / float(master_fps)) if s_fn > 0 else 0.0
        s_exact = s_fn / float(master_fps)
        final_dur = max(0.2, (num_frames - 0.5) / float(master_fps))
        e_exact = (s_fn + num_frames) / float(master_fps)
        s_delta = 0.0
        e_delta = 0.0
        
        is_intra_dup = (zero_idx in intra_duplicate_indices)
        is_cross_dup = (zero_idx in cross_duplicates)
        
        file_name = f"{pfx}{idx:03d}.mp4"
        stem = f"{pfx}{idx:03d}"
        
        if is_intra_dup and move_duplicates:
            target_dir = dup_dir
            folder_tag = "duplicates/intra"
        elif is_cross_dup and move_duplicates:
            target_dir = cross_dup_dir
            folder_tag = "duplicates/cross"
        else:
            target_dir = scenes_dir
            folder_tag = "scenes"
            
        out_path = os.path.join(target_dir, file_name)
        strip_file_name = f"{stem}_strip.jpg"
        strip_path = os.path.join(thumb_dir, strip_file_name)
        
        # Unified single-pass temporal analysis and filmstrip generation using existing cap handle
        action_peak_rel, phases, pacing_rec = analyze_and_generate_filmstrip(
            cap, proxy_fps, s_exact, s_exact + final_dur, out_strip_path=strip_path,
            crop_box=inc.get("box_proxy") if inc.get("has_blur") else None
        )
        
        scene_info = {
            "scene_id": idx,
            "incident_id": inc["incident_id"],
            "shot_index": inc["shot_index"],
            "is_continuation": inc["is_continuation"],
            "continuation_of": inc["continuation_of"],
            "variation_type": inc["variation_type"],
            "file_name": file_name,
            "target_folder": folder_tag,
            "file_path": str(Path(out_path).resolve()).replace("\\", "/"),
            "filmstrip_path": str(Path(strip_path).resolve()).replace("\\", "/"),
            "start_time": round(s_exact, 4),
            "end_time": round(e_exact, 4),
            "duration": round(final_dur, 3),
            "seek_time": round(s_seek, 5),
            "total_frames": num_frames,
            "has_blur": inc["has_blur"],
            "crop_box": {
                "x": inc["box"][0],
                "y": inc["box"][1],
                "w": inc["box"][2],
                "h": inc["box"][3]
            },
            "aspect_ratio": inc["aspect_ratio"],
            "native_resolution": {
                "width": inc["box"][2],
                "height": inc["box"][3]
            },
            "audio": {
                "start_snap_delta": round(s_delta, 3),
                "end_snap_delta": round(e_delta, 3)
            },
            "temporal_landmarks": {
                "action_peak_rel_sec": action_peak_rel,
                "phases": phases,
                "pacing_recommendations": pacing_rec
            },
            "deduplication": {
                "is_intra_duplicate": is_intra_dup,
                "intra_details": intra_matches.get(zero_idx),
                "is_cross_duplicate": is_cross_dup,
                "cross_details": cross_duplicates.get(zero_idx)
            },
            "premiere_pro": {
                "suggested_track": "V1" if not (is_intra_dup or is_cross_dup) else "V2",
                "in_point": 0.0,
                "out_point": round(final_dur, 2),
                "action_peak_marker_sec": action_peak_rel,
                "optical_flow_ready": True,
                "clip_name": f"Scene_{idx:03d} (Inc_{inc['incident_id']})"
            }
        }
        final_scenes.append(scene_info)
        
        if not is_intra_dup and not is_cross_dup:
            new_lib_entries.append({
                "source_video": video_stem,
                "file_name": file_name,
                "duration": round(final_dur, 2),
                "aspect_ratio": inc["aspect_ratio"],
                "hash_orig": inc["hash_orig"],
                "hash_flip": inc["hash_flip"]
            })

    # Release VideoCapture handle once all keyframes, unblur, and filmstrips are finished
    cap.release()

    # 7. Hardware Export (Parallel Multi-Worker Engine)
    print(f"\n[Clean-Cut Milestone 3] Exporting {len(final_scenes)} clean clips via {encoder} (Parallel x4)...")
    
    def export_clip(item):
        cb = item["crop_box"]
        filters = []
        if item["has_blur"]:
            filters.append(f"crop={cb['w']}:{cb['h']}:{cb['x']}:{cb['y']}")
            
        safe_start = item["start_time"] + 0.12 if item["duration"] > 0.8 else item["start_time"]
        safe_end = item["end_time"] - 0.12 if item["duration"] > 0.8 else item["end_time"]
        safe_dur = max(0.2, safe_end - safe_start)

        cmd = ["ffmpeg", "-y"]
        if "nvenc" in encoder:
            cmd.extend(["-hwaccel", "cuda"])
        cmd.extend([
            "-ss", f"{safe_start:.3f}",
            "-t", f"{safe_dur:.3f}",
            "-i", real_video
        ])
        
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
            
        fade_d = min(0.015, safe_dur / 4.0)
        af_fade = f"afade=t=in:st=0:d={fade_d:.3f},afade=t=out:st={max(0.0, safe_dur-fade_d):.3f}:d={fade_d:.3f}"
        
        cmd.extend([
            "-af", af_fade,
            "-c:v", encoder,
            "-c:a", "aac",
            "-b:a", "192k",
            item["file_path"]
        ])
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        item["duration"] = round(safe_dur, 3)
        tag_str = ""
        if item["deduplication"]["is_intra_duplicate"]:
            tag_str = " [Intra-Dup -> _duplicates/]"
        elif item["deduplication"]["is_cross_duplicate"]:
            tag_str = f" [Cross-Dup -> _cross_duplicates/ (Matched {item['deduplication']['cross_details']['matched_source_video']})]"
        elif item["is_continuation"]:
            tag_str = f" [Reframe linked to Inc #{item['incident_id']}]"
            
        print(f"    ✓ [{item['scene_id']:02d}] {item['file_name']} ({safe_dur:.2f}s, {item['aspect_ratio']}, Peak @ {item['temporal_landmarks']['action_peak_rel_sec']}s){tag_str}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(export_clip, final_scenes))

    # 8. Update Portable Library Index
    if new_lib_entries:
        existing_lib_clips.extend(new_lib_entries)
        lib_index["clips"] = existing_lib_clips
        save_library_index(lib_path, lib_index)
        print(f"  ✓ Added {len(new_lib_entries)} new fingerprints to library index ({lib_path.name}).")

    # 9. Group Multi-Shot Incidents & Build Rich Context Manifest
    incident_groups_map = {}
    for item in final_scenes:
        inc_id = item["incident_id"]
        if inc_id not in incident_groups_map:
            incident_groups_map[inc_id] = {
                "incident_id": inc_id,
                "is_multi_shot": False,
                "total_shots": 0,
                "total_duration": 0.0,
                "shots": [],
                "editorial_status": "single_shot",
                "explanation": ""
            }
        group = incident_groups_map[inc_id]
        group["total_shots"] += 1
        group["total_duration"] = round(group["total_duration"] + item["duration"], 2)
        group["shots"].append({
            "scene_id": item["scene_id"],
            "file_name": item["file_name"],
            "variation_type": item["variation_type"],
            "aspect_ratio": item["aspect_ratio"],
            "duration": item["duration"],
            "is_continuation": item["is_continuation"]
        })
        if group["total_shots"] > 1:
            group["is_multi_shot"] = True
            group["editorial_status"] = "multi_shot_same_event"
            group["explanation"] = f"CÙNG CẢNH / SỰ KIỆN: Đoạn này diễn ra cùng một tình huống, được chia thành {group['total_shots']} clip do đổi góc máy/zoom/tỷ lệ khung hình."

    # Embed same_scene_group metadata into every scene
    for item in final_scenes:
        inc_id = item["incident_id"]
        grp = incident_groups_map[inc_id]
        all_clip_names = [s["file_name"] for s in grp["shots"]]
        other_clips = [name for name in all_clip_names if name != item["file_name"]]
        item["same_scene_group"] = {
            "incident_id": inc_id,
            "is_multi_shot": grp["is_multi_shot"],
            "shot_index": item["shot_index"],
            "total_shots_in_incident": grp["total_shots"],
            "all_incident_clips": all_clip_names,
            "note": f"CÙNG CẢNH với {', '.join(other_clips)}" if grp["is_multi_shot"] else "Cảnh độc lập (đơn cú máy)"
        }
        item["context"] = synthesize_scene_context(item, source_title=video_stem)

    multi_shot_incidents = [g for g in incident_groups_map.values() if g["is_multi_shot"]]

    context_manifest = {
        "source_video": str(Path(real_video).resolve()).replace("\\", "/"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_scenes": len(final_scenes),
        "total_incidents": current_incident_id,
        "multi_shot_incidents_count": len(multi_shot_incidents),
        "clean_master_scenes": len(final_scenes) - len(intra_duplicate_indices) - len(cross_duplicates),
        "intra_duplicates_count": len(intra_duplicate_indices),
        "cross_duplicates_count": len(cross_duplicates),
        "output_directory": str(Path(out_dir).resolve()).replace("\\", "/"),
        "multi_shot_scene_groups": multi_shot_incidents,
        "scenes": final_scenes
    }
    
    def json_default(o):
        if isinstance(o, (np.bool_, bool)):
            return bool(o)
        if isinstance(o, (np.integer, int)):
            return int(o)
        if isinstance(o, (np.floating, float)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    manifest_path = os.path.join(manifest_dir, "scenes_context.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(context_manifest, f, indent=2, ensure_ascii=False, default=json_default)
        
    # Also mirror at root of out_dir for quick CLI access
    root_manifest = os.path.join(out_dir, "scenes_context.json")
    try:
        shutil.copy2(manifest_path, root_manifest)
    except Exception:
        pass
        
    print(f"\n[Clean-Cut Execution Succeeded]")
    print(f"  ✓ Context manifest ready at: {manifest_path} (mirrored to root)")
    print(f"  ✓ Clean footage saved in: {scenes_dir}")
    print(f"  ✓ Visual filmstrips saved in: {thumb_dir}")

    if multi_shot_incidents:
        print(f"\n=======================================================")
        print(f"🔗 CÁC CẢNH ĐƯỢC GỘP CHUNG SỰ KIỆN (MULTI-SHOT INCIDENTS):")
        for g in multi_shot_incidents:
            clip_list = " + ".join([f"{s['file_name']} ({s['variation_type']}, {s['aspect_ratio']})" for s in g["shots"]])
            print(f"  • Incident #{g['incident_id']} ({g['total_duration']}s, {g['total_shots']} clips): {clip_list}")
        print(f"=======================================================")
    return manifest_path

def interactive_setup():
    print("\n=======================================================")
    print("🎬 [CLEAN-CUT] MENU CẤU HÌNH THỰC THI (INTERACTIVE SETUP)")
    print("=======================================================")
    cfg = load_config()
    
    # 1. Video source
    video_in = input("📹 Đường dẫn video hoặc link YouTube: ").strip().strip('"').strip("'")
    while not video_in:
        print("  ! Lỗi: Vui lòng nhập đường dẫn video hợp lệ.")
        video_in = input("📹 Đường dẫn video hoặc link YouTube: ").strip().strip('"').strip("'")
        
    # 2. Output directory
    def_out = cfg.get("output_dir", "output_clean_cut")
    out_in = input(f"📁 Thư mục lưu trữ output [{def_out}]: ").strip()
    out_dir = out_in if out_in else def_out
    
    # 3. Prefix
    def_pfx = cfg.get("prefix", "scene_")
    pfx_in = input(f"🏷️ Tiền tố đặt tên clip (Prefix) [{def_pfx}]: ").strip()
    prefix = pfx_in if pfx_in else def_pfx
    
    # 4. Unblur
    def_unblur = cfg.get("unblur_enabled", True)
    unblur_in = input(f"✨ Tự động bóc tách & khử viền mờ (Unblur) [{'Y/n' if def_unblur else 'y/N'}]: ").strip().lower()
    if unblur_in:
        unblur = (unblur_in in ["y", "yes", "1", "true"])
    else:
        unblur = def_unblur
        
    # 5. Limit
    limit_in = input("🔢 Giới hạn số cảnh xuất (Enter để lấy toàn bộ): ").strip()
    limit = int(limit_in) if limit_in.isdigit() else None
    
    print("=======================================================\n")
    return video_in, out_dir, prefix, unblur, limit

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean-Cut: Precision Scene Splitter with Unblur, Deduplication, and Pacing Landmarks")
    parser.add_argument("video", nargs="?", default=None, help="Path to video file or YouTube URL")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory")
    parser.add_argument("-p", "--prefix", default=None, help="Filename prefix (e.g. scene_)")
    parser.add_argument("-t", "--threshold", type=float, default=None, help="Detector sensitivity threshold (default: 27.0)")
    parser.add_argument("-m", "--min-duration", type=float, default=None, help="Minimum scene duration in seconds (default: 1.2)")
    parser.add_argument("--no-unblur", action="store_true", help="Disable automatic unblur cropping")
    parser.add_argument("-l", "--limit", type=int, default=None, help="Limit number of output scenes")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run interactive configuration menu")
    
    args = parser.parse_args()
    
    if not args.video or args.interactive:
        v_in, o_in, p_in, unblur_val, lim_val = interactive_setup()
        run_clean_cut(
            video_path=v_in,
            output_dir=o_in,
            prefix=p_in,
            threshold=args.threshold,
            min_duration=args.min_duration,
            unblur=unblur_val,
            limit=lim_val
        )
    else:
        run_clean_cut(
            video_path=args.video,
            output_dir=args.output_dir,
            prefix=args.prefix,
            threshold=args.threshold,
            min_duration=args.min_duration,
            unblur=not args.no_unblur,
            limit=args.limit
        )
