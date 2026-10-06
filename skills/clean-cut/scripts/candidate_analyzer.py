#!/usr/bin/env python3
"""
candidate_analyzer.py — Ultra-fast RAM proxy candidate cut scanner & visual contact sheet generator.
Generates candidate cuts and 24-cut contact sheets (N-20, N-1, [RED LINE], N+0, N+20) for AI Agent Vision review.
"""
import os
import sys
import json
import math
import time
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
import numpy as np

TW, TH = 64, 36       # Thumbnail analysis dimensions
SW, SH = 192, 108     # Review & sheet frame dimensions
OFFS = (-30, -20, -8, -1, 0, 8, 20, 30)

def log(*args):
    print(*args, flush=True)

def find_bin(name):
    p = shutil.which(name)
    if p:
        return p
    for candidate in [
        f"/Volumes/External/homebrew/bin/{name}",
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
        f"C:\\ffmpeg\\bin\\{name}.exe",
        f"C:\\Program Files\\ffmpeg\\bin\\{name}.exe"
    ]:
        if os.path.isfile(candidate):
            return candidate
    return name

def wjson(path, obj):
    import threading
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    for i in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1 * (i + 1))
    os.replace(tmp, path)

def progress(w_dir, step, done, total, note=""):
    try:
        wjson(os.path.join(w_dir, "progress.json"), {
            "step": step,
            "done": done,
            "total": total,
            "pct": round(100 * done / max(1, total), 1),
            "note": note,
            "t": time.time()
        })
    except OSError:
        pass

def probe_video(video_path):
    fp = find_bin("ffprobe")
    cmd = [
        fp, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,avg_frame_rate,nb_frames,width,height:format=duration,start_time",
        "-of", "json", str(video_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(res.stdout)
    stream = info["streams"][0]
    num, den = map(int, stream["r_frame_rate"].split("/"))
    an, ad = map(int, stream.get("avg_frame_rate", "0/1").split("/"))
    dur = float(info["format"].get("duration", 0))
    vfr = ad and abs(an / ad - num / den) > 0.01
    
    # Check audio
    au_cmd = [fp, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)]
    au_res = subprocess.run(au_cmd, capture_output=True, text=True).stdout.strip()
    
    return {
        "fps": [num, den],
        "duration": dur,
        "width": stream["width"],
        "height": stream["height"],
        "nb_frames": int(stream.get("nb_frames") or round(dur * num / den)),
        "has_audio": bool(au_res),
        "vfr_warning": bool(vfr)
    }

def tc(fr, fps):
    s = fr / fps
    h = int(s // 3600)
    return (f"{h}:" if h else "") + f"{int(s % 3600 // 60):02d}:{s % 60:05.2f}"

def ff_frames(ff, video, w, h, gray=False):
    pix = "gray" if gray else "bgr24"
    ch = 1 if gray else 3
    cmd = [
        ff, "-v", "error", "-hwaccel", "auto", "-skip_loop_filter", "all",
        "-i", video, "-map", "0:v:0",
        "-vf", f"scale={w}:{h}:flags=area",
        "-fps_mode", "passthrough", "-pix_fmt", pix, "-f", "rawvideo", "-"
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=w * h * ch * 64)
    n = w * h * ch
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield np.frombuffer(b, np.uint8).reshape(h, w, ch) if not gray else np.frombuffer(b, np.uint8).reshape(h, w)
    finally:
        p.kill()
        p.wait()

def ff_window(ff, video, start, n, fps, w, h, fast=False):
    cmd = [
        ff, "-v", "error", "-hwaccel", "auto"
    ]
    if fast:
        cmd.extend(["-skip_loop_filter", "all"])
    cmd.extend([
        "-ss", f"{start / fps:.6f}", "-i", video, "-map", "0:v:0",
        "-frames:v", str(n), "-vf", f"scale={w}:{h}:flags=area",
        "-fps_mode", "passthrough", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"
    ])
    res = subprocess.run(cmd, capture_output=True)
    sz = w * h * 3
    b = res.stdout
    return [np.frombuffer(b[i:i + sz], np.uint8).reshape(h, w, 3) for i in range(0, len(b) - sz + 1, sz)]

def analyze_video(video_path, work_dir=None, min_content=15.0, adaptive=1.8, max_sim=0.85, split=None, redo=False):
    ff = find_bin("ffmpeg")
    video = os.path.abspath(video_path)
    if not os.path.isfile(video):
        raise FileNotFoundError(f"Video file not found: {video}")
        
    name = Path(video).stem
    W = os.path.abspath(work_dir) if work_dir else os.path.join(os.path.dirname(video), "_scene", name)
    os.makedirs(W, exist_ok=True)
    
    info = probe_video(video)
    info.update(video=video, name=name, version="1.2.1")
    wjson(os.path.join(W, "info.json"), info)
    
    num, den = info["fps"]
    fps = num / den
    est = info["nb_frames"]
    
    log(f"\n[Clean-Cut Stage 1] Candidate Analysis: '{name}'")
    log(f"  • Resolution: {info['width']}x{info['height']} @ {fps:.3f} fps (~{info['duration']:.1f}s, {est} frames)")
    log(f"  • Work Directory: {W}")
    if info.get("vfr_warning"):
        log("  ! Warning: Variable frame rate (VFR) detected.")
        
    t0 = time.time()
    tp = os.path.join(W, "thumbs.npy")
    cp = os.path.join(W, "cval.npy")
    
    if os.path.exists(tp) and os.path.exists(cp) and not redo:
        log("  • Loading cached video proxy thumbs and HSV content values...")
        T = np.load(tp).astype(np.float32)
        cval = np.load(cp)
        N = len(T)
    else:
        nseg = split or max(1, min(8, (os.cpu_count() or 4) // 2))
        if est < 3000:
            nseg = 1
        step = math.ceil(est / nseg)
        chunks = [(i * step, min(step, est - i * step)) for i in range(nseg) if i * step < est]
        chunks[-1] = (chunks[-1][0], chunks[-1][1] + 600)
        
        log(f"  • Pass 1: Scanning {est} frames via {nseg} parallel ffmpeg decoders...")
        done = [0]
        def dec(ch):
            st, n = ch
            if nseg == 1:
                fr = list(ff_frames(ff, video, TW, TH))
            else:
                fr = ff_window(ff, video, st, n, fps, TW, TH, fast=True)
            done[0] += 1
            progress(W, "analyze-1/2", done[0], len(chunks), f"{nseg} threads · {time.time() - t0:.0f}s")
            return fr
            
        with ThreadPoolExecutor(max_workers=len(chunks)) as ex:
            parts = list(ex.map(dec, chunks))
            
        frames_all = [f for p in parts for f in p]
        vecs = []
        cval = [0.0]
        prev = None
        for fr in frames_all:
            hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV).astype(np.int16)
            if prev is not None:
                cval.append(float(np.abs(hsv - prev).mean()))
            prev = hsv
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32).ravel()
            g -= g.mean()
            g /= (np.linalg.norm(g) + 1e-6)
            vecs.append(g.astype(np.float16))
            
        del frames_all, parts
        T = np.stack(vecs).astype(np.float32)
        N = len(T)
        cval = np.array(cval[:N])
        log(f"  ✓ Pass 1 completed: {N} frames processed in {time.time() - t0:.1f}s.")
        np.save(tp, T.astype(np.float16))
        np.save(cp, cval)
        
    corr = np.r_[1.0, (T[1:] * T[:-1]).sum(1)]
    
    # Adaptive & hard candidate detection
    raw = []
    k = 2
    for f in range(k + 1, N - k):
        nb = np.r_[cval[f - k:f], cval[f + 1:f + k + 1]].mean()
        if cval[f] >= min_content and cval[f] / (nb + 1e-3) >= adaptive and (not raw or f - raw[-1] >= 8):
            raw.append(f)
            
    hard = [f for f in range(2, N - 1) if corr[f] < 0.35 and corr[f - 1] > 0.8 and corr[f + 1] > 0.8]
    
    cands = {}
    for f in sorted(set(raw + hard)):
        lo, hi = max(1, f - 8), min(N - 1, f + 8)
        r = f if corr[f] < 0.5 else int(lo + np.argmin(corr[lo:hi + 1]))
        A, B = T[max(0, r - 10):r], T[r + 1:r + 11]
        s = float((A @ B.T).max()) if len(A) and len(B) else 0.0
        if s < max_sim and not any(abs(r - x) <= 3 for x in cands):
            cands[r] = s
            
    frames = sorted(cands)
    meta = [{"n": i + 1, "frame": f, "s": round(cands[f], 3), "tc": tc(f, fps)} for i, f in enumerate(frames)]
    log(f"  • Candidate cut points identified: {len(meta)} (raw: {len(raw)}, hard: {len(hard)})")
    
    # Pass 2: Extract keyframes around candidates
    log(f"  • Pass 2: Extracting boundary keyframes for visual contact sheets...")
    need = set([8])
    for f in frames:
        for o in OFFS:
            need.add(min(N - 1, max(0, f + o)))
            
    frame_cache = {}
    import threading
    cache_lock = threading.Lock()
    
    wins = []
    for f in sorted(need):
        if wins and f - wins[-1][1] <= 15:
            wins[-1][1] = f
        else:
            wins.append([f, f])
            
    done = [0]
    def grab(wn):
        a0, b0 = wn
        local_frames = {}
        for k3, fr in enumerate(ff_window(ff, video, a0, b0 - a0 + 1, fps, SW, SH)):
            fn = a0 + k3
            if fn in need:
                local_frames[fn] = fr
        with cache_lock:
            frame_cache.update(local_frames)
        done[0] += 1
        if done[0] % 20 == 0:
            progress(W, "analyze-2/2", done[0], len(wins))
            
    with ThreadPoolExecutor(max_workers=max(2, min(8, os.cpu_count() or 4))) as ex:
        list(ex.map(grab, wins))
        
    # Render contact sheets (24 cuts per sheet)
    log(f"  • Rendering visual contact sheets (24 cuts/sheet)...")
    sd = os.path.join(W, "sheets")
    shutil.rmtree(sd, ignore_errors=True)
    os.makedirs(sd, exist_ok=True)
    
    PER, LH = 24, 20
    rows = PER // 2
    show = (-20, -1, 0, 20)
    blank = np.zeros((SH, SW, 3), np.uint8)
    
    def img(fr):
        return frame_cache.get(min(N - 1, max(0, fr)), blank)
        
    num_sheets = math.ceil(len(meta) / PER)
    for p in range(0, len(meta), PER):
        canvas = np.full((rows * (SH + LH + 6), 2 * (4 * SW + 20), 3), 30, np.uint8)
        for k2, m in enumerate(meta[p:p + PER]):
            r_, c_ = k2 % rows, k2 // rows
            x0 = c_ * (4 * SW + 20)
            y0 = r_ * (SH + LH + 6)
            cv2.putText(canvas, f"#{m['n']}  {m['tc']}  s={m['s']:.2f}", (x0 + 4, y0 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            for j, o in enumerate(show):
                x = x0 + j * SW + (4 if j >= 2 else 0)
                canvas[y0 + LH:y0 + LH + SH, x:x + SW] = img(m['frame'] + o)
            cv2.line(canvas, (x0 + 2 * SW + 2, y0 + LH), (x0 + 2 * SW + 2, y0 + LH + SH), (0, 0, 255), 3)
        sheet_path = os.path.join(sd, f"sheet_{p // PER + 1:02d}.jpg")
        cv2.imwrite(sheet_path, canvas, [cv2.IMWRITE_JPEG_QUALITY, 82])
        
    cands_path = os.path.join(W, "cands.json")
    wjson(cands_path, {"N": N, "fps": [num, den], "cands": meta})
    
    elapsed = round(time.time() - t0, 1)
    summary = {
        "frames": N,
        "raw": len(raw),
        "hard": len(hard),
        "cands": len(meta),
        "sheets": num_sheets,
        "work": W,
        "cands_file": cands_path,
        "sheets_dir": sd,
        "seconds": elapsed
    }
    progress(W, "analyze-done", 1, 1, json.dumps(summary))
    log(f"  ✓ Stage 1 complete: {len(meta)} candidate cuts, {num_sheets} contact sheets in {elapsed}s.")
    log(f"  • Contact Sheets: {sd}/sheet_*.jpg")
    log(f"  • Candidates JSON: {cands_path}")
    return summary

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: candidate_analyzer.py <video_path> [--work <work_dir>] [--redo]")
        sys.exit(1)
    vid = sys.argv[1]
    work = None
    redo = "--redo" in sys.argv
    if "--work" in sys.argv:
        idx = sys.argv.index("--work")
        if idx + 1 < len(sys.argv):
            work = sys.argv[idx + 1]
    analyze_video(vid, work_dir=work, redo=redo)
