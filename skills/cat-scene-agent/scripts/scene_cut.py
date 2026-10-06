#!/usr/bin/env python3
"""scene_cut.py — băm video compilation thành footage lẻ theo scene.

Chạy trên máy người dùng (Windows / macOS / Linux). Agent (Claude) gọi các lệnh này;
người dùng không cần tự chạy. Thiếu thư viện hay ffmpeg thì script tự cài.

  python scene_cut.py check
  python scene_cut.py analyze "<video>" [--work <thư mục>]
  python scene_cut.py review  --work <W> [--keep-intro] [--answers "2=tach,5=bo"] [--no-open]
  python scene_cut.py cut     --work <W> --prefix fsm_ --start 1 --out "<thư mục xuất>" [--jobs 4] [--pad 4]
  python scene_cut.py serve   [--root <thư mục>] [--install-startup]
      Chạy nền, nhận việc từ Claude qua <root>/_queue/<id>.job.json {"cmd":..,"args":{..}}
      -> ghi <id>.log, <id>.done.json, _alive.json. Chỉ nhận check/analyze/review/cut.

Tệp trong thư mục làm việc W (mặc định: <thư mục video>/_scene/<tên video>/):
  info.json        fps, số frame, thời lượng
  progress.json    tiến độ bước đang chạy (agent đọc để biết khi nào xong)
  cands.json       điểm cắt nghi vấn    sheets/*.jpg  ảnh lưới cho agent xem
  dec.txt          nhãn agent ghi: "<số|a-b> R|F|I|R?|F?"
  review.html      trang duyệt cho người dùng     segments.json  danh sách clip cuối
  cut_report.json  kết quả cắt (file thiếu / lệch frame)
"""
import argparse, base64, html, json, math, os, platform, shutil, subprocess, sys, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

VERSION = '1.2.1'
HOME_TOOLS = os.path.join(os.path.expanduser('~'), '.scene_cut', 'tools')
TW, TH = 64, 36            # thumb phân tích
SW, SH = 192, 108          # frame ảnh lưới / review
OFFS = (-30, -20, -8, -1, 0, 8, 20, 30)
IS_WIN = platform.system() == 'Windows'
EXE = '.exe' if IS_WIN else ''


# =============================================================== requirements
def log(*a):
    print(*a, flush=True)


def ensure_py_packages():
    need = []
    try:
        import numpy  # noqa
    except ImportError:
        need.append('numpy')
    try:
        import cv2  # noqa
    except ImportError:
        need.append('opencv-python-headless')
    if need:
        log(f'[cài đặt] pip install {" ".join(need)}')
        cmd = [sys.executable, '-m', 'pip', 'install', '--user', '--disable-pip-version-check', *need]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            subprocess.run(cmd + ['--break-system-packages'], check=True)
        import site, importlib
        site.main(); importlib.invalidate_caches()


def _which_ff(name):
    cands = [os.path.join(HOME_TOOLS, name + EXE), shutil.which(name)]
    if IS_WIN:
        cands += [rf'C:\ffmpeg\bin\{name}.exe', rf'C:\Program Files\ffmpeg\bin\{name}.exe',
                  os.path.expandvars(rf'%LOCALAPPDATA%\Microsoft\WinGet\Links\{name}.exe'),
                  os.path.expandvars(rf'%USERPROFILE%\scoop\shims\{name}.exe'), rf'C:\ProgramData\chocolatey\bin\{name}.exe']
    else:
        cands += [f'/opt/homebrew/bin/{name}', f'/usr/local/bin/{name}', f'/usr/bin/{name}']
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def _download(url, dst):
    log(f'[cài đặt] tải {url}')
    with urllib.request.urlopen(url, timeout=120) as r, open(dst, 'wb') as f:
        shutil.copyfileobj(r, f)


def ensure_ffmpeg():
    ff, fp = _which_ff('ffmpeg'), _which_ff('ffprobe')
    if ff and fp:
        return ff, fp
    os.makedirs(HOME_TOOLS, exist_ok=True)
    sysname = platform.system()
    if sysname == 'Windows':
        z = os.path.join(HOME_TOOLS, 'ff.zip')
        _download('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', z)
        with zipfile.ZipFile(z) as zf:
            for m in zf.namelist():
                b = os.path.basename(m)
                if b in ('ffmpeg.exe', 'ffprobe.exe'):
                    with zf.open(m) as s, open(os.path.join(HOME_TOOLS, b), 'wb') as d:
                        shutil.copyfileobj(s, d)
        os.remove(z)
    elif sysname == 'Darwin':
        if shutil.which('brew'):
            subprocess.run(['brew', 'install', 'ffmpeg'], check=False)
        if not (_which_ff('ffmpeg') and _which_ff('ffprobe')):
            for n in ('ffmpeg', 'ffprobe'):
                z = os.path.join(HOME_TOOLS, n + '.zip')
                _download(f'https://evermeet.cx/ffmpeg/getrelease/{n}/zip', z)
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(HOME_TOOLS)
                os.remove(z); os.chmod(os.path.join(HOME_TOOLS, n), 0o755)
    else:
        sys.exit('Thiếu ffmpeg. Cài bằng: sudo apt install ffmpeg  (hoặc trình quản lý gói của máy)')
    ff, fp = _which_ff('ffmpeg'), _which_ff('ffprobe')
    if not (ff and fp):
        sys.exit('Không cài được ffmpeg tự động.')
    return ff, fp


def cmd_check(a):
    rows = [('python', f'{sys.version.split()[0]}', sys.version_info >= (3, 8))]
    ensure_py_packages()
    import numpy, cv2
    rows += [('numpy', numpy.__version__, True), ('opencv', cv2.__version__, True)]
    ff, fp = ensure_ffmpeg()
    v = subprocess.run([ff, '-version'], capture_output=True, text=True).stdout.split('\n')[0]
    rows += [('ffmpeg', v, True), ('ffprobe', fp, True), ('encoder', pick_encoder(ff), True),
             ('cpu', str(os.cpu_count()), True), ('disk_free_GB', f'{shutil.disk_usage(os.path.expanduser("~")).free / 1e9:.0f}', True)]
    for n, v, ok in rows:
        log(f'{"OK " if ok else "LỖI"} {n:12s} {v}')
    log(json.dumps({'ok': all(r[2] for r in rows), 'version': VERSION, 'ffmpeg': ff}))


# =============================================================== helpers
def wjson(path, obj):
    import threading
    tmp = f'{path}.{os.getpid()}.{threading.get_ident()}.tmp'   # tmp riêng mỗi luồng
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    for i in range(20):                                        # Windows: file đang bị đọc/khóa → thử lại
        try:
            os.replace(tmp, path); return
        except PermissionError:
            time.sleep(0.1 * (i + 1))
    os.replace(tmp, path)


def progress(W, step, done, total, note=''):
    try:
        _progress(W, step, done, total, note)
    except OSError:
        pass                                                   # tiến độ không được làm hỏng job


def _progress(W, step, done, total, note=''):
    wjson(os.path.join(W, 'progress.json'), {'step': step, 'done': done, 'total': total,
                                            'pct': round(100 * done / max(1, total), 1), 'note': note, 't': time.time()})


def probe(fp, video):
    r = subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=r_frame_rate,avg_frame_rate,nb_frames,width,height:format=duration,start_time',
                        '-of', 'json', video], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout); s = j['streams'][0]
    num, den = map(int, s['r_frame_rate'].split('/'))
    an, ad = map(int, s.get('avg_frame_rate', '0/1').split('/'))
    au = subprocess.run([fp, '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', video],
                        capture_output=True, text=True).stdout.strip()
    dur = float(j['format'].get('duration', 0))
    vfr = ad and abs(an / ad - num / den) > 0.01
    return {'fps': [num, den], 'duration': dur, 'width': s['width'], 'height': s['height'],
            'nb_frames': int(s.get('nb_frames') or round(dur * num / den)), 'has_audio': bool(au), 'vfr_warning': bool(vfr)}


def tc(fr, fps):
    s = fr / fps
    h = int(s // 3600)
    return (f'{h}:' if h else '') + f'{int(s % 3600 // 60):02d}:{s % 60:05.2f}'


def ff_frames(ff, video, w, h, gray=False):
    """Giải mã tuần tự; yield từng frame numpy."""
    import numpy as np
    pix = 'gray' if gray else 'bgr24'; ch = 1 if gray else 3
    p = subprocess.Popen([ff, '-v', 'error', '-hwaccel', 'auto', '-skip_loop_filter', 'all', '-i', video, '-map', '0:v:0',
                          '-vf', f'scale={w}:{h}:flags=area',
                          '-fps_mode', 'passthrough', '-pix_fmt', pix, '-f', 'rawvideo', '-'],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=w * h * ch * 64)
    n = w * h * ch
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield np.frombuffer(b, np.uint8).reshape(h, w, ch) if not gray else np.frombuffer(b, np.uint8).reshape(h, w)
    finally:
        p.kill(); p.wait()


def ff_window(ff, video, start, n, fps, w, h, fast=False):
    """Giải mã đúng n frame bắt đầu từ frame `start` (tua nhanh tới keyframe gần nhất)."""
    import numpy as np
    r = subprocess.run([ff, '-v', 'error', '-hwaccel', 'auto', *(['-skip_loop_filter', 'all'] if fast else []),
                        '-ss', f'{start / fps:.6f}', '-i', video, '-map', '0:v:0',
                        '-frames:v', str(n), '-vf', f'scale={w}:{h}:flags=area', '-fps_mode', 'passthrough',
                        '-pix_fmt', 'bgr24', '-f', 'rawvideo', '-'], capture_output=True)
    sz = w * h * 3; b = r.stdout
    return [np.frombuffer(b[i:i + sz], np.uint8).reshape(h, w, 3) for i in range(0, len(b) - sz + 1, sz)]


ENC_CACHE = os.path.join(os.path.expanduser('~'), '.scene_cut', 'encoder.json')
ENCODERS = {   # chất lượng tương đương x264 crf18 cho footage
    'nvenc': ['-c:v', 'h264_nvenc', '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', '19', '-b:v', '0', '-pix_fmt', 'yuv420p'],
    'qsv': ['-c:v', 'h264_qsv', '-preset', 'faster', '-global_quality', '20', '-pix_fmt', 'nv12'],
    'amf': ['-c:v', 'h264_amf', '-quality', 'balanced', '-rc', 'cqp', '-qp_i', '19', '-qp_p', '21', '-pix_fmt', 'yuv420p'],
    'videotoolbox': ['-c:v', 'h264_videotoolbox', '-q:v', '65', '-pix_fmt', 'yuv420p'],
    'x264': ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p'],
}


def pick_encoder(ff, want='auto'):
    """auto: thử GPU (NVIDIA/Intel/AMD/Apple) → lỗi thì x264 veryfast. Kết quả lưu cache."""
    if want != 'auto':
        return want
    try:
        c = json.load(open(ENC_CACHE))
        if c.get('ff') == ff:
            return c['enc']
    except Exception:
        pass
    enc = 'x264'
    order = ['videotoolbox'] if platform.system() == 'Darwin' else ['nvenc', 'qsv', 'amf']
    for e in order:
        r = subprocess.run([ff, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:d=0.5', *ENCODERS[e], '-f', 'null', '-'],
                           capture_output=True)
        if r.returncode == 0:
            enc = e; break
    os.makedirs(os.path.dirname(ENC_CACHE), exist_ok=True)
    wjson(ENC_CACHE, {'ff': ff, 'enc': enc})
    return enc


def encode_segment(ff, video, s, fps, path, enc, overwrite=False):
    nf = s['end'] - s['start']
    cmd = [ff, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y' if overwrite else '-n',
           '-ss', f"{s['start'] / fps:.6f}", '-i', video, '-t', f'{nf / fps:.6f}', '-frames:v', str(nf),
           '-map', '0:v:0', '-map', '0:a:0?', *ENCODERS[enc], '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = os.path.exists(path) and os.path.getsize(path) > 0
    if not ok and enc != 'x264':                      # GPU lỗi giữa chừng → làm lại bằng CPU
        return encode_segment(ff, video, s, fps, path, 'x264', overwrite=True)
    return ok, (r.stderr.strip()[-300:] if not ok else '')


# =============================================================== analyze
def cmd_analyze(a):
    ensure_py_packages()
    import numpy as np, cv2
    ff, fp = ensure_ffmpeg()
    video = os.path.abspath(a.video)
    if not os.path.isfile(video):
        sys.exit(f'Không thấy video: {video}')
    name = os.path.splitext(os.path.basename(video))[0]
    W = a.work or os.path.join(os.path.dirname(video), '_scene', name)
    os.makedirs(W, exist_ok=True)
    info = probe(fp, video); info.update(video=video, name=name, version=VERSION)
    wjson(os.path.join(W, 'info.json'), info)
    num, den = info['fps']; fps = num / den; est = info['nb_frames']
    log(f'{name}: {info["width"]}x{info["height"]} {fps:.3f}fps {info["duration"]:.0f}s ~{est} frame'
        + ('  [CẢNH BÁO: VFR]' if info['vfr_warning'] else ''))
    # ---- lượt 1: thumb + chỉ số nội dung (HSV) -----------------------------
    t0 = time.time(); tp, cp = os.path.join(W, 'thumbs.npy'), os.path.join(W, 'cval.npy')
    if os.path.exists(tp) and os.path.exists(cp) and not a.redo:
        T = np.load(tp).astype(np.float32); cval = np.load(cp); N = len(T)
    else:
        # chia video thành nhiều đoạn, mỗi đoạn 1 tiến trình ffmpeg giải mã song song
        nseg = a.split or max(1, min(8, (os.cpu_count() or 4) // 2))
        if est < 3000:
            nseg = 1
        step = math.ceil(est / nseg)
        chunks = [(i * step, min(step, est - i * step)) for i in range(nseg) if i * step < est]
        chunks[-1] = (chunks[-1][0], chunks[-1][1] + 600)     # đoạn cuối đọc dư để không sót frame
        done = [0]
        def dec(ch):
            st, n = ch
            if nseg == 1:
                fr = list(ff_frames(ff, video, TW, TH))
            else:
                fr = ff_window(ff, video, st, n, fps, TW, TH, fast=True)
            done[0] += 1
            progress(W, 'analyze-1/2', done[0], len(chunks), f'{nseg} luồng · {time.time() - t0:.0f}s')
            return fr
        with ThreadPoolExecutor(max_workers=len(chunks)) as ex:
            parts = list(ex.map(dec, chunks))
        frames_all = [f for p in parts for f in p]
        vecs = []; cval = [0.0]; prev = None
        for fr in frames_all:
            hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV).astype(np.int16)
            if prev is not None:
                cval.append(float(np.abs(hsv - prev).mean()))
            prev = hsv
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32).ravel()
            g -= g.mean(); g /= (np.linalg.norm(g) + 1e-6); vecs.append(g.astype(np.float16))
        del frames_all, parts
        T = np.stack(vecs).astype(np.float32); N = len(T); cval = np.array(cval[:N])
        log(f'lượt 1: {N} frame, {nseg} luồng, {time.time() - t0:.0f}s')
        np.save(tp, T.astype(np.float16)); np.save(cp, cval)
    corr = np.r_[1.0, (T[1:] * T[:-1]).sum(1)]          # corr[f] = tương quan(f-1, f)
    # ---- dò: adaptive (kiểu PySceneDetect) + cắt cứng ------------------------
    raw = []
    k = 2
    for f in range(k + 1, N - k):
        nb = np.r_[cval[f - k:f], cval[f + 1:f + k + 1]].mean()
        if cval[f] >= a.min_content and cval[f] / (nb + 1e-3) >= a.adaptive and (not raw or f - raw[-1] >= 8):
            raw.append(f)
    hard = [f for f in range(2, N - 1) if corr[f] < 0.35 and corr[f - 1] > 0.8 and corr[f + 1] > 0.8]
    cands = {}
    for f in sorted(set(raw + hard)):
        lo, hi = max(1, f - 8), min(N - 1, f + 8)
        r = f if corr[f] < 0.5 else int(lo + np.argmin(corr[lo:hi + 1]))   # cắt rõ thì giữ nguyên
        A, B = T[max(0, r - 10):r], T[r + 1:r + 11]
        s = float((A @ B.T).max()) if len(A) and len(B) else 0.0
        if s < a.max_sim and not any(abs(r - x) <= 3 for x in cands):
            cands[r] = s
    frames = sorted(cands)
    meta = [{'n': i + 1, 'frame': f, 's': round(cands[f], 3), 'tc': tc(f, fps)} for i, f in enumerate(frames)]
    # ---- lượt 2: lấy frame cho ảnh lưới + review ---------------------------
    need = set([8])
    for f in frames:
        for o in OFFS:
            need.add(min(N - 1, max(0, f + o)))
    fd = os.path.join(W, 'frames'); os.makedirs(fd, exist_ok=True)
    # gộp các frame cần thành cửa sổ liền nhau, đọc song song bằng tua (không giải mã lại cả video)
    wins = []
    for f in sorted(need):
        if wins and f - wins[-1][1] <= 15:
            wins[-1][1] = f
        else:
            wins.append([f, f])
    done = [0]
    def grab(wn):
        a0, b0 = wn
        for k3, fr in enumerate(ff_window(ff, video, a0, b0 - a0 + 1, fps, SW, SH)):
            if a0 + k3 in need:
                cv2.imwrite(os.path.join(fd, f'{a0 + k3}.jpg'), fr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        done[0] += 1
        if done[0] % 20 == 0:
            progress(W, 'analyze-2/2', done[0], len(wins))
    with ThreadPoolExecutor(max_workers=max(2, min(8, os.cpu_count() or 4))) as ex:
        list(ex.map(grab, wins))
    # ---- ảnh lưới cho agent -----------------------------------------------
    sd = os.path.join(W, 'sheets'); shutil.rmtree(sd, ignore_errors=True); os.makedirs(sd)
    PER, LH = 24, 20; rows = PER // 2; show = (-20, -1, 0, 20)
    blank = np.zeros((SH, SW, 3), np.uint8)
    def img(fr):
        im = cv2.imread(os.path.join(fd, f'{min(N - 1, max(0, fr))}.jpg'))
        return blank if im is None else im
    for p in range(0, len(meta), PER):
        canvas = np.full((rows * (SH + LH + 6), 2 * (4 * SW + 20), 3), 30, np.uint8)
        for k2, m in enumerate(meta[p:p + PER]):
            r_, c_ = k2 % rows, k2 // rows; x0 = c_ * (4 * SW + 20); y0 = r_ * (SH + LH + 6)
            cv2.putText(canvas, f"#{m['n']}  {m['tc']}  s={m['s']:.2f}", (x0 + 4, y0 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            for j, o in enumerate(show):
                x = x0 + j * SW + (4 if j >= 2 else 0)
                canvas[y0 + LH:y0 + LH + SH, x:x + SW] = img(m['frame'] + o)
            cv2.line(canvas, (x0 + 2 * SW + 2, y0 + LH), (x0 + 2 * SW + 2, y0 + LH + SH), (0, 0, 255), 3)
        cv2.imwrite(os.path.join(sd, f'sheet_{p // PER + 1:02d}.jpg'), canvas, [cv2.IMWRITE_JPEG_QUALITY, 82])
    wjson(os.path.join(W, 'cands.json'), {'N': N, 'fps': [num, den], 'cands': meta})
    summary = {'frames': N, 'raw': len(raw), 'hard': len(hard), 'cands': len(meta),
               'sheets': math.ceil(len(meta) / PER), 'work': W, 'seconds': round(time.time() - t0)}
    progress(W, 'analyze-done', 1, 1, json.dumps(summary))
    log(json.dumps(summary, ensure_ascii=False))


# =============================================================== review
def read_dec(W):
    d = {}
    for ln in open(os.path.join(W, 'dec.txt'), encoding='utf-8'):
        ln = ln.split('#')[0].strip()
        if not ln:
            continue
        rng, lab = ln.split()[:2]
        lo, hi = (rng.split('-') + [rng])[:2]
        for i in range(int(lo), int(hi) + 1):
            d[i] = lab
    return d


def b64file(p):
    try:
        return base64.b64encode(open(p, 'rb').read()).decode()
    except OSError:
        return ''


def cmd_review(a):
    W = a.work; C = json.load(open(os.path.join(W, 'cands.json'))); info = json.load(open(os.path.join(W, 'info.json')))
    num, den = C['fps']; fps = num / den; N = C['N']; d = read_dec(W)
    miss = [m['n'] for m in C['cands'] if m['n'] not in d]
    if miss:
        sys.exit(f'dec.txt thiếu nhãn: {miss[:30]}')
    qp = os.path.join(W, 'questions.json'); prev = json.load(open(qp)) if os.path.exists(qp) else []
    sap = os.path.join(W, 'short_answers.json'); short_ans = json.load(open(sap)) if os.path.exists(sap) else {}
    if a.answers is not None:
        given = {}
        for tok in a.answers.replace(' ', '').split(','):
            if '=' in tok:
                k, v = tok.split('=', 1)
                given[k] = v
        extra = []
        for q in prev:
            v = given.get(str(q['q']), q['rec'])            # không đổi = đồng ý đề xuất
            if q['kind'] == 'boundary':
                extra.append(f"{q['n']} {'R' if v == 'tach' else 'F'}  # nguoi dung\n")
            else:
                short_ans[str(q['start'])] = v
        with open(os.path.join(W, 'dec.txt'), 'a', encoding='utf-8') as f:
            f.writelines(extra)
        wjson(sap, short_ans); d = read_dec(W)
    bym = {m['n']: m for m in C['cands']}
    labs = {n: d[n] for n in bym}
    if a.keep_intro:
        labs = {n: ('F' if l == 'I' else l) for n, l in labs.items()}
    cut = sorted((bym[n]['frame'], n) for n in bym if labs[n] in ('R', 'R?'))
    intro_end = max([bym[n]['frame'] for n in bym if labs[n] == 'I'] + [0])
    if intro_end == 0:
        cut = [(0, 0)] + [c for c in cut if c[0] > 0]
    segs = []
    for i, (f, n) in enumerate(cut):
        e = cut[i + 1][0] if i + 1 < len(cut) else N
        if f >= intro_end:
            segs.append({'start': f, 'end': e, 'dur': round((e - f) / fps, 2)})
    keep = [s for s in segs if s['dur'] >= a.min_clip and short_ans.get(str(s['start'])) != 'bo']
    for i, s in enumerate(keep, 1):
        s['id'] = i
    qs = [{'kind': 'boundary', 'n': n, 'frame': bym[n]['frame'], 'rec': 'tach' if labs[n] == 'R?' else 'gop'}
          for n in sorted(bym) if labs[n] in ('R?', 'F?')]
    qs += [{'kind': 'short', 'start': s['start'], 'end': s['end'], 'frame': s['start'], 'rec': 'giu'}
           for s in keep if s['dur'] < 2.5 and str(s['start']) not in short_ans]
    qs.sort(key=lambda q: q['frame'])
    for i, q in enumerate(qs, 1):
        q['q'] = i
    wjson(qp, qs)
    wjson(os.path.join(W, 'segments.json'), {'fps': [num, den], 'video': info['video'], 'segments': keep})
    page = render_review(W, info['name'], keep, qs, fps, N)
    out = os.path.join(W, 'review.html'); open(out, 'w', encoding='utf-8').write(page)
    summ = {'clips': len(keep), 'questions': len(qs), 'total_s': round(sum(s['dur'] for s in keep), 1), 'review': out}
    log(json.dumps(summ, ensure_ascii=False))
    if (qs or a.open) and not a.no_open:
        try:
            if IS_WIN:
                os.startfile(out)
            else:
                subprocess.run(['open' if platform.system() == 'Darwin' else 'xdg-open', out])
        except Exception:
            pass


def render_review(W, title, keep, qs, fps, N):
    fd = os.path.join(W, 'frames')
    def im(fr):
        b = b64file(os.path.join(fd, f'{min(N - 1, max(0, fr))}.jpg'))
        return f'<img src="data:image/jpeg;base64,{b}">' if b else '<span class="ph"></span>'
    cards = []
    for q in qs:
        f = q['frame']
        strip = ''.join(im(f + o) + ('<i class="cut"></i>' if o == -1 else '') for o in (-30, -8, -1, 0, 8, 30))
        if q['kind'] == 'boundary':
            ask = f'Ở <b>{tc(f, fps)}</b>: hai bên vạch đỏ là 2 clip khác nhau?'
            opts = [('tach', 'Tách – 2 clip'), ('gop', 'Gộp – cùng 1 clip')]
        else:
            ask = f'Clip ngắn <b>{(q["end"] - q["start"]) / fps:.1f}s</b> ở {tc(f, fps)} – có giữ không?'
            opts = [('giu', 'Giữ'), ('bo', 'Bỏ')]
        btn = ''.join(f'<button data-v="{v}" class="{"on" if v == q["rec"] else ""}">{t}'
                      f'{" <small>· Claude chọn</small>" if v == q["rec"] else ""}</button>' for v, t in opts)
        cards.append(f'<section class="q" data-q="{q["q"]}" data-rec="{q["rec"]}"><div class="t"><b>{q["q"]}.</b> {ask}</div>'
                     f'<div class="strip">{strip}</div><div class="b">{btn}</div></section>')
    grid = ''.join(f'<div class="c" data-id="{s["id"]}">{im(s["start"] + 8)}<span>{s["id"]} · {tc(s["start"], fps)} · {s["dur"]}s</span></div>'
                   for s in keep)
    return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} – duyệt scene</title><style>
:root{{--bg:#131417;--card:#1f2125;--fg:#ececec;--mut:#9aa0a6;--acc:#2f6fe4;--ok:#1f9d55;--cut:#e5484d;--chg:#f0a020}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif}}
header{{position:sticky;top:0;z-index:3;background:#0c0d0f;padding:12px 16px;border-bottom:1px solid #2a2c31}}
h1{{font-size:17px;margin:0 0 4px}}.mut{{color:var(--mut);font-size:13px}}
.bar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px}}
button{{font:inherit;border:1px solid #3a3d44;background:#2a2c31;color:var(--fg);border-radius:6px;padding:8px 12px;cursor:pointer}}
button.on{{background:var(--acc);border-color:var(--acc)}}#copy{{background:var(--ok);border-color:var(--ok);font-weight:600}}
main{{padding:12px 16px;max-width:1150px;margin:auto}}.q{{background:var(--card);border-radius:8px;padding:10px;margin-bottom:10px}}
.q.chg{{outline:2px solid var(--chg)}}.strip{{display:flex;align-items:center;overflow-x:auto;margin:8px 0}}
.strip img,.ph{{height:99px;width:176px;object-fit:cover;margin-right:3px;border-radius:3px;background:#000;display:inline-block}}
.cut{{display:inline-block;width:4px;height:99px;background:var(--cut);margin-right:5px;border-radius:2px;flex:none}}
.b{{display:flex;gap:8px;flex-wrap:wrap}}#out{{flex:1;min-width:200px;background:#000;color:#7CFC7C;border:1px solid #333;padding:8px;border-radius:6px;font:13px monospace}}
details{{margin-top:18px}}summary{{cursor:pointer;color:var(--mut)}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:6px;margin-top:10px}}
.c{{background:var(--card);border-radius:6px;padding:4px;cursor:pointer;font-size:12px;border:2px solid transparent}}.c img{{width:100%;height:auto;display:block;border-radius:4px}}
.c.bad{{border-color:var(--cut);opacity:.6}}#msg{{color:#7CFC7C}}
</style></head><body><header><h1>{html.escape(title)}: {len(keep)} clip · {len(qs)} chỗ cần bạn xem</h1>
<div class="mut">Nút xanh là lựa chọn của Claude. Chỉ bấm khi thấy sai. Xong bấm nút xanh lá rồi dán vào Claude.</div>
<div class="bar"><button id="copy">Xong – Copy kết quả</button><input id="out" readonly><span id="msg"></span></div></header>
<main>{''.join(cards) or '<p>Không có chỗ nào cần hỏi.</p>'}
<details><summary>Xem toàn bộ {len(keep)} clip (không bắt buộc) – bấm vào clip bị cắt sai</summary><div class="grid">{grid}</div></details></main>
<script>
const T={json.dumps(title)},bad=new Set();
function res(){{const ch=[];document.querySelectorAll('.q').forEach(q=>{{const v=q.querySelector('button.on').dataset.v;q.classList.toggle('chg',v!==q.dataset.rec);if(v!==q.dataset.rec)ch.push(q.dataset.q+'='+v)}});
if(bad.size)ch.push('sai='+[...bad].sort((a,b)=>a-b).join('+'));return T+': '+(ch.length?ch.join(','):'ok')}}
function upd(){{document.getElementById('out').value=res()}}
document.querySelectorAll('.q').forEach(q=>q.querySelectorAll('button').forEach(b=>b.onclick=()=>{{q.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');upd()}}));
document.querySelectorAll('.c').forEach(c=>c.onclick=()=>{{const i=+c.dataset.id;bad.has(i)?bad.delete(i):bad.add(i);c.classList.toggle('bad');upd()}});
document.getElementById('copy').onclick=async()=>{{upd();const t=document.getElementById('out');t.select();try{{await navigator.clipboard.writeText(t.value)}}catch(e){{document.execCommand('copy')}}document.getElementById('msg').textContent='Đã copy – dán vào Claude'}};upd();
</script></body></html>'''


# =============================================================== cut
def cmd_cut(a):
    ff, fp = ensure_ffmpeg()
    W = a.work; S = json.load(open(os.path.join(W, 'segments.json')))
    num, den = S['fps']; fps = num / den; video = a.source or S['video']; K = S['segments']
    if not os.path.isfile(video):
        sys.exit(f'Không thấy video nguồn: {video}')
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    jobs = []
    for i, s in enumerate(K):
        name = f'{a.prefix}{a.start + i:0{a.pad}d}'
        jobs.append({'name': name, 'path': os.path.join(out, name + '.mp4'), 'nf': s['end'] - s['start'],
                     'ss': f"{s['start'] / fps:.6f}", 't': f"{(s['end'] - s['start']) / fps:.6f}", 'seg': s})
    clash = [j['name'] for j in jobs if os.path.exists(j['path'])]
    if a.resume:
        jobs = [j for j in jobs if not os.path.exists(j['path'])]
        clash = []
        if not jobs:
            log('Không còn file nào cần cắt.'); return
    if clash and not a.overwrite:
        wjson(os.path.join(W, 'cut_report.json'), {'error': 'exists', 'clash': clash[:50], 'n_clash': len(clash)})
        sys.exit(f'Đã có {len(clash)} file trùng tên trong {out} (vd {clash[0]}). Dùng --overwrite hoặc đổi số/thư mục.')
    done = [0]; t0 = time.time(); enc = pick_encoder(ff, a.encoder); cache = os.path.join(W, 'cache'); reused = [0]
    log(f'encoder: {enc}')
    def run(j):
        cp = os.path.join(cache, f"{j['seg']['start']}_{j['seg']['end']}.mp4")
        err = ''
        if os.path.isfile(cp) and os.path.getsize(cp) > 0 and (a.overwrite or not os.path.exists(j['path'])):
            shutil.move(cp, j['path']); reused[0] += 1          # đã cắt trước trong lúc chờ duyệt → chỉ đổi tên
        else:
            _, err = encode_segment(ff, video, j['seg'], fps, j['path'], enc, a.overwrite)
        ok = os.path.exists(j['path']) and os.path.getsize(j['path']) > 0
        r = type('R', (), {'stderr': err})
        got = None
        if ok:
            pr = subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                                 'stream=nb_read_packets', '-of', 'csv=p=0', j['path']], capture_output=True, text=True).stdout.strip()
            got = int(pr) if pr.isdigit() else None
        done[0] += 1
        if done[0] % 5 == 0 or done[0] == len(jobs):
            progress(W, 'cut', done[0], len(jobs), f'{time.time() - t0:.0f}s')
        return {'name': j['name'], 'ok': ok, 'frames': got, 'expect': j['nf'], 'err': r.stderr.strip()[-300:] if not ok else ''}
    progress(W, 'cut', 0, len(jobs))
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        res = list(ex.map(run, jobs))
    bad = [r for r in res if not r['ok']]
    off = [r for r in res if r['ok'] and r['frames'] is not None and abs(r['frames'] - r['expect']) > 1]
    rep = {'first': jobs[0]['name'], 'last': jobs[-1]['name'], 'count': len(jobs), 'next': f'{a.prefix}{a.start + len(jobs):0{a.pad}d}',
           'out': out, 'failed': bad, 'frame_mismatch': off, 'seconds': round(time.time() - t0), 'encoder': enc, 'reused_precut': reused[0]}
    wjson(os.path.join(W, 'cut_report.json'), rep)
    shutil.rmtree(cache, ignore_errors=True)
    with open(os.path.join(out, f'_plan_{a.prefix.rstrip("_")}.txt'), 'w', encoding='utf-8') as f:
        f.write(f"Nguồn: {video}\n{rep['first']} → {rep['last']} ({len(jobs)} file). Số kế tiếp: {rep['next']}\n\n")
        for j in jobs:
            f.write(f"{j['name']}  {tc(j['seg']['start'], fps)} → {tc(j['seg']['end'], fps)}  {j['seg']['dur']:.2f}s\n")
    progress(W, 'cut-done', 1, 1, json.dumps({k: rep[k] for k in ('first', 'last', 'next')}))
    log(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()}, ensure_ascii=False))


def cmd_precut(a):
    """Cắt trước các clip vào <W>/cache trong lúc người dùng duyệt. Không ghi gì ra thư mục xuất.
    Khi `cut` chạy, clip nào trùng khoảng frame sẽ chỉ được đổi tên (gần như tức thì)."""
    ff, fp = ensure_ffmpeg()
    W = a.work; S = json.load(open(os.path.join(W, 'segments.json')))
    num, den = S['fps']; fps = num / den; video = S['video']
    cache = os.path.join(W, 'cache'); os.makedirs(cache, exist_ok=True)
    qs = json.load(open(os.path.join(W, 'questions.json'))) if os.path.exists(os.path.join(W, 'questions.json')) else []
    risky = {q['frame'] for q in qs}                    # clip chạm vào chỗ đang hỏi → để sau
    segs = [s for s in S['segments'] if s['start'] not in risky and s['end'] not in risky]
    segs = [s for s in segs if not os.path.isfile(os.path.join(cache, f"{s['start']}_{s['end']}.mp4"))]
    enc = pick_encoder(ff, a.encoder); done = [0]; t0 = time.time()
    def run(s):
        p = os.path.join(cache, f"{s['start']}_{s['end']}.mp4")
        encode_segment(ff, video, s, fps, p + '.part.mp4', enc, True)
        if os.path.isfile(p + '.part.mp4'):
            os.replace(p + '.part.mp4', p)
        done[0] += 1
        if done[0] % 5 == 0:
            progress(W, 'precut', done[0], len(segs), f'{enc} {time.time() - t0:.0f}s')
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        list(ex.map(run, segs))
    progress(W, 'precut-done', 1, 1, json.dumps({'encoded': len(segs), 'encoder': enc, 'seconds': round(time.time() - t0)}))
    log(json.dumps({'encoded': len(segs), 'encoder': enc, 'seconds': round(time.time() - t0)}))


# =============================================================== serve (hàng đợi cho agent)
ALLOWED = {'check', 'analyze', 'review', 'precut', 'cut'}


def job_argv(job):
    """Chỉ cho phép 4 lệnh của script này, tham số dạng key/value — không chạy shell tuỳ ý."""
    cmd = job.get('cmd')
    if cmd not in ALLOWED:
        raise ValueError(f'lệnh không được phép: {cmd}')
    argv = [sys.executable, os.path.abspath(__file__), cmd]
    for k, v in (job.get('args') or {}).items():
        k = str(k)
        if k == '_':
            argv.append(str(v)); continue
        if not k.replace('-', '').replace('_', '').isalnum():
            raise ValueError(f'tham số lạ: {k}')
        flag = '--' + k.replace('_', '-')
        if v is True:
            argv.append(flag)
        elif v not in (False, None):
            argv += [flag, str(v)]
    return argv


def install_startup(root):
    if not IS_WIN:
        log('Tự khởi động hiện chỉ hỗ trợ Windows.'); return
    st = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
    py = sys.executable.replace('python.exe', 'pythonw.exe')
    if not os.path.exists(py):
        py = sys.executable
    with open(os.path.join(st, 'scene_cut_agent.bat'), 'w', encoding='utf-8') as f:
        f.write(f'@echo off\r\nstart "scene_cut" /min "{py}" "{os.path.abspath(__file__)}" serve --root "{root}"\r\n')
    log(f'Đã thêm vào Startup: {st}')


def cmd_serve(a):
    root = os.path.abspath(a.root or os.path.dirname(os.path.abspath(__file__)))
    q = os.path.join(root, '_queue'); os.makedirs(q, exist_ok=True)
    if a.install_startup:
        install_startup(root)
    log(f'scene_cut {VERSION} đang chờ việc từ Claude tại {q}  (Ctrl+C để dừng)')
    import queue as _q, threading
    lanes = {'light': _q.Queue(), 'heavy': _q.Queue()}      # review/check không phải chờ precut/cut

    def worker(lane):
        while True:
            jid, job, argv = lanes[lane].get()
            run_job(q, jid, job, argv)
    for ln in lanes:
        threading.Thread(target=worker, args=(ln,), daemon=True).start()
    last = 0
    while True:
        now = time.time()
        if now - last > 5:
            wjson(os.path.join(q, '_alive.json'), {'t': now, 'version': VERSION, 'python': sys.executable, 'pid': os.getpid()})
            last = now
        for fn in sorted(os.listdir(q)):
            if not fn.endswith('.job.json'):
                continue
            jp = os.path.join(q, fn); jid = fn[:-9]
            taken = jp + '.taken'
            try:
                os.replace(jp, taken)
                job = json.load(open(taken, encoding='utf-8-sig'))
                argv = job_argv(job)
            except Exception as e:
                wjson(os.path.join(q, jid + '.done.json'), {'id': jid, 'rc': -1, 'error': str(e)}); continue
            wjson(os.path.join(q, jid + '.queued.json'), {'id': jid, 'cmd': job['cmd'], 't': time.time()})
            lanes['light' if job['cmd'] in ('check', 'review') else 'heavy'].put((jid, job, argv))
        time.sleep(2)


def run_job(q, jid, job, argv):
    if True:
        if True:
            try:
                os.remove(os.path.join(q, jid + '.queued.json'))
            except OSError:
                pass
            log(f'[{time.strftime("%H:%M:%S")}] chạy {job["cmd"]} ({jid})')
            wjson(os.path.join(q, jid + '.running.json'), {'id': jid, 'cmd': job['cmd'], 't': time.time()})
            with open(os.path.join(q, jid + '.log'), 'w', encoding='utf-8') as lf:
                env = dict(os.environ, PYTHONIOENCODING='utf-8')
                rc = subprocess.run(argv, stdout=lf, stderr=subprocess.STDOUT, env=env).returncode
            tail = open(os.path.join(q, jid + '.log'), encoding='utf-8', errors='replace').read()[-3000:]
            wjson(os.path.join(q, jid + '.done.json'), {'id': jid, 'cmd': job['cmd'], 'rc': rc, 'tail': tail, 't': time.time()})
            try:
                os.remove(os.path.join(q, jid + '.running.json'))
            except OSError:
                pass
            log(f'    xong rc={rc}')


# =============================================================== main
if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='Băm video theo scene (Claude điều khiển).')
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('check')
    p = sp.add_parser('analyze'); p.add_argument('video'); p.add_argument('--work'); p.add_argument('--redo', action='store_true')
    p.add_argument('--split', type=int, default=0, help='số đoạn giải mã song song (0 = tự chọn theo CPU)')
    p.add_argument('--adaptive', type=float, default=2.5); p.add_argument('--min-content', type=float, default=6.0)
    p.add_argument('--max-sim', type=float, default=0.8)
    p = sp.add_parser('review'); p.add_argument('--work', required=True); p.add_argument('--answers')
    p.add_argument('--keep-intro', action='store_true'); p.add_argument('--min-clip', type=float, default=1.2); p.add_argument('--no-open', action='store_true'); p.add_argument('--open', action='store_true')
    p = sp.add_parser('cut'); p.add_argument('--work', required=True); p.add_argument('--prefix', required=True)
    p.add_argument('--start', type=int, default=1); p.add_argument('--pad', type=int, default=4); p.add_argument('--out', required=True)
    p.add_argument('--source'); p.add_argument('--jobs', type=int, default=max(2, min(6, (os.cpu_count() or 4) // 2)))
    p.add_argument('--encoder', default='auto', choices=['auto', *ENCODERS]); p.add_argument('--overwrite', action='store_true'); p.add_argument('--resume', action='store_true')
    p = sp.add_parser('precut'); p.add_argument('--work', required=True); p.add_argument('--encoder', default='auto', choices=['auto', *ENCODERS])
    p.add_argument('--jobs', type=int, default=max(2, min(6, (os.cpu_count() or 4) // 2)))
    p = sp.add_parser('serve'); p.add_argument('--root'); p.add_argument('--install-startup', action='store_true')
    a = ap.parse_args()
    {'check': cmd_check, 'analyze': cmd_analyze, 'review': cmd_review, 'precut': cmd_precut, 'cut': cmd_cut, 'serve': cmd_serve}[a.cmd](a)
