---
name: split-scenes
description: >-
  Skill bóc tách cảnh video chính xác từng frame (-vframes), quét siêu tốc (>3.200 fps),
  Agent tự xem Vision Sheets bằng mắt AI để gán nhãn R/F/I từng điểm cắt,
  gộp tình huống trọn vẹn (SSIM), hiểu ngữ cảnh âm thanh,
  khử trùng lặp Intro / Liên video và tích hợp Premiere Pro MCP.
  Trigger: "split-scenes", "tách cảnh", "cắt cảnh", "split video", "scene detect", "premiere pro".
---

# 🎬 Split Scenes — Precision AI Scene Detection & Splitting

Skill bóc tách cảnh video chuẩn xác từng frame: quét proxy siêu tốc (>3.200 fps), **Agent tự xem Vision Sheets bằng `view_file` để hiểu ngữ cảnh và gán nhãn R/F/I từng điểm cắt**, gộp tình huống trọn vẹn (SSIM & Palette), hiểu ngữ cảnh âm thanh & bắt đỉnh va chạm, khử trùng lặp Intro & Liên video, cắt sạch đuôi bằng `-vframes` và hỗ trợ dựng Premiere Pro MCP.

---

## 🛑 Nguyên tắc Tương tác Bắt buộc: Không tự tiện mặc định ở bất kỳ khâu nào!

> [!IMPORTANT]
> **Agent KHÔNG ĐƯỢC tự ý gán cứng đường dẫn lưu hay cách đặt tên file ở bất kỳ giai đoạn nào!**
>
> 1. **Trước khi TẢI video (Phase 1):** Bắt buộc hỏi User:
>    * 📁 **Thư mục lưu video gốc:** Tải về lưu vào đâu? (Gợi ý đường dẫn, nhưng để User quyết định).
>    * 🏷️ **Tên thư mục & Tên file:** Đặt tên là gì? (Tên gọn theo chủ đề của User hay giữ nguyên Title/ID dài ngoằng của YouTube).
>
> 2. **Ngay đầu PHASE 2 (Trước khi lập `scene_db.json`):** Bắt buộc hỏi User về quy chuẩn xuất clip:
>    * 📁 **Thư mục lưu clips:** Sau khi split sẽ lưu vào đâu? (VD: thư mục con `scenes/`, ổ cứng khác, Desktop...).
>    * 🏷️ **Tiền tố tên file (Prefix):** Bắt đầu bằng gì? (VD: `fail_`, `clip_`, `<channel>_<id>_`, hoặc tên tùy chỉnh theo dự án).
>    * 🔢 **Quy cách đánh số:** Đánh số kiểu gì? (2 chữ số `01`, 3 chữ số `001`, 4 chữ số `0001`, bắt đầu từ số mấy)
>    * 📝 **Hậu tố ngữ nghĩa (Suffix):** User muốn tên file vật lý là `prefix_số.mp4` (VD: `fail_001.mp4` — chuẩn khuyến nghị để tránh lỗi đường dẫn và ký tự tiếng Việt) hay có kèm Title tiếng Việt vào tên file (VD: `fail_001_xe_tai_dam_cao_toc.mp4`)?
>
> 3. **Tự động Require & Tự Cài Đặt Môi Trường (Zero Manual Setup):**
>    * Khi chạy bất kỳ tác vụ nào, hệ thống **tự động kiểm tra 100% các package cần thiết**: `opencv-python`, `scikit-image`, `numpy`, `scipy`, `librosa`, `faster-whisper`, `yt-dlp` và các công cụ CLI (`ffmpeg`, `ffprobe`).
>    * Nếu máy tính thiếu bất kỳ thư viện hay công cụ nào, script **TỰ ĐỘNG CÀI ĐẶT NGAY LẬP TỨC** trong nền, **tuyệt đối không bắt User phải gõ lệnh cài đặt thủ công!**

---

## Cấu trúc thư mục & Ánh xạ `scene_db.json`

```
<User_Chosen_Download_Dir>/
├── <User_Chosen_Name>.mp4           ← 1. Video gốc (1080p)
├── proxy_480p.mp4                   ← 2. Proxy H.264 ultrafast (dùng để detect)
└── frames_cache/                    ← 3. Keyframes & Cut-context sheets (tạm)
    ├── kf_0000000.jpg               ← Keyframe đầu scene
    └── cut_sheets/
        ├── cut_sheet_001.jpg        ← Vision sheet: N-20|N-1|CUT|N+1|N+20
        └── ...

<User_Chosen_Output_Dir>/
├── fail_001.mp4                     ← Tên file vật lý ngắn gọn
├── fail_002.mp4
└── scene_db.json                    ← Database với metadata đã phân tích
```

### Chuẩn cấu trúc một bản ghi trong `scene_db.json`:
```json
{
  "scene_id": 1,
  "file_name": "fail_001.mp4",
  "file_path": "/Volumes/External/clips/fail_001.mp4",
  "start_f": 3348,
  "end_f": 3470,
  "duration": 5.09,
  "keyframe": "/path/frames_cache/kf_0003348.jpg",
  "label": "R",
  "title": "Xe tải mất lái đâm dải phân cách cao tốc",
  "action": "Xe tải chạy tốc độ cao đâm rào chắn, nắp capo vàng bung lên hất vỡ kính",
  "category": "Traffic Accident",
  "mood": "shocking",
  "tags": ["highway", "truck", "dashcam"]
}
```
> Khi import vào **Premiere Pro MCP**: File vật lý được import là `fail_001.mp4`, nhưng MCP sẽ gán Clip Display Name trên Timeline bằng `title`. Người dựng phim nhìn vào Timeline vẫn thấy ngay tên tiếng Việt rõ ràng!

---

## 🧹 Chính sách Tự động Dọn dẹp & Chống Tràn Ổ Đĩa (Auto-Purge Policy)

> [!CAUTION]
> **Không để file tạm tích tụ làm đầy ổ cứng!** Quy tắc tự động dọn rác nghiêm ngặt:

1. **Tự động xóa sau từng Phase (Post-Phase Auto-Purge):**
   * **Vision Sheets & Frames tạm:** Ngay sau khi kết thúc Phase 2.3 (Agent đã xem xong và ghi nhãn) → **Tự động xóa ngay lập tức 100% ảnh Vision Sheet**. Chỉ giữ lại file text `scene_db.json` siêu nhẹ (~300 KB).
   * **File Proxy 480p:** Sau khi hoàn thành Phase 3 → Agent hỏi User có muốn xóa proxy_480p.mp4 không.

2. **Giới hạn trần Cache (Max Cap 3 GB & TTL 48h):** File tạm tối đa 3 GB, tự động FIFO purge.

3. **Lệnh một chạm dọn sạch:** Khi User gõ *"dọn dẹp"*, *"xóa rác"*, *"clean cache"* → xóa sạch tất cả file tạm.

---

## Phase 1 — Tải video & Tạo Proxy Siêu Tốc

> ⚠️ Trước khi tải, Agent **phải hỏi User** về Thư mục lưu và Tên file/thư mục mong muốn!

### 1. Tải video YouTube và chuẩn hóa về 23.976 fps ngay lập tức

```bash
# Bước 1: tải về
yt-dlp -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]" \
  --merge-output-format mp4 --write-info-json \
  -o "<DIR>/<NAME>_raw.%(ext)s" "<URL>"

# Bước 2: normalize fps về 23.976 (mặc định bắt buộc)
ffmpeg -y -i "<DIR>/<NAME>_raw.mp4" \
  -vf "fps=24000/1001" \
  -c:v libx264 -crf 16 -preset fast -c:a copy \
  "<DIR>/<NAME>.mp4"

# Xóa file raw
Remove-Item "<DIR>/<NAME>_raw.mp4"
```

> [!IMPORTANT]
> **Mọi video đều phải normalize 23.976fps trước khi làm gì khác.**
> - Source 60fps → 23.976fps: scan nhanh hơn **2.5×**
> - Frame index proxy = frame index source = **khớp tuyệt đối, không cần convert**
> - Mọi thứ trong `scene_db.json` dùng **23.976fps thống nhất**: `start_f / 23.976 = start_sec`

### 2. Tạo Proxy 480p (kế thừa fps đã chuẩn)

```bash
ffmpeg -y -i "<DIR>/<NAME>.mp4" \
  -vf "scale=-2:480" \
  -c:v libx264 -crf 28 -preset ultrafast -an \
  "<DIR>/proxy_480p.mp4"
```

Proxy kế thừa 23.976fps từ source — **không cần `-vf fps=...` ở bước này.**

---

## Phase 2 — Dò Cảnh Bằng Thuật Toán + Agent Vision

Phase 2 gồm **3 bước bắt buộc theo thứ tự**:

```
Phase 2.1: Quét frame (thuật toán)  →  danh sách raw cut points
Phase 2.2: Sinh Cut-Context Vision Sheets  →  ảnh N-20|N-1|CUT|N+1|N+20
Phase 2.3: Agent XEM ảnh bằng view_file  →  gán nhãn R/F/I + điền metadata
```

> [!IMPORTANT]
> **Phase 2.3 là BẮT BUỘC và KHÔNG THỂ BỎ QUA.**
> Agent phải tự xem từng vision sheet bằng `view_file` để hiểu ngữ cảnh thực tế của từng điểm cắt trước khi chốt `scene_db.json`. Thuật toán số (luma/HSV/SSIM) chỉ là bước lọc thô — quyết định cắt/gộp cuối cùng phải dựa trên **mắt AI nhìn vào frame thực tế**.

---

### Phase 2.1 — Quét Frame Tuần Tự (Algorithmic Pre-Filter)

Quét **100% từng khung hình** của file proxy qua OpenCV & NumPy để lấy danh sách **raw cut candidates**:

* **Adaptive Luma Threshold:** Tự động calibrate `luma_thresh = clamp(0.40 × std_luma, 16, 35)` thay vì hardcode.
* **Vùng trung tâm kích hoạt (Active Center Crop):** Cắt lấy 50% chiều rộng ở giữa (`[w*0.25 : w*0.75]`) để triệt tiêu viền đen 9:16.
* **Sliding Window (N vs N-K):** So sánh frame N với frame N-3 thay vì N-1 để bắt cả fade/dissolve chậm, không chỉ hard-cut.
* **Composite Metric:** $\Delta\text{Luma} \ge \text{luma\_thresh}$ AND $\text{HSV Corr} < 0.60$
* **SSIM Anti-Over-Split:** Nếu $\text{SSIM} > 0.25$ → hủy cut candidate (cùng cảnh).
* **Cooldown 0.5s:** Bỏ qua triggers trong 0.5s ngay sau mỗi cut → tránh flash/flicker.
* **min_scene_sec = 2.0s:** Không tạo scene ngắn hơn 2 giây.

**Kết quả:** File `frames_cache/` chứa keyframe đầu mỗi scene (dùng cho Phase 2.2).

---

### Phase 2.2 — Sinh Dense Vision Sheets (Mật Độ Cao Per-Scene)

> [!NOTE]
> Sinh lưới **8×8 = 64 frames** cho mỗi scene, lấy mẫu đều theo toàn bộ độ dài scene.
> Agent nhìn vào 1 sheet duy nhất để đọc toàn bộ narrative arc (chuẩn bị → biến cố → hậu quả).

**3 chế độ sampling:**

| Mode | Lệnh | Tốc độ mẫu | Dùng khi |
|------|------|-----------|----------|
| `--auto` | 1 sheet/scene, 64 frame trải đều | Tự tính theo độ dài | **Mặc định** — xem tất cả nhanh |
| `--step 2` | 1 frame / 2 frames gốc = **½ fps gốc** | ~12fps (25fps) / ~30fps (60fps) | Scenes ngắn < 10s cần chi tiết |
| `--step 5` | 1 frame / 5 frames gốc = **⅕ fps gốc** | ~5fps (25fps) / ~12fps (60fps) | Scenes dài > 30s xem narrative tổng |

Mỗi thumbnail có timecode `MM:SS.s` và frame number. Header bar: `Scene #XXXX | 01:23.4 → 01:45.6 | 22.2s`.

```bash
# Auto (1 sheet/scene — dùng mặc định)
python vision_dense.py <proxy> <scene_db.json> <out_dir> --auto

# Step=2 cho scenes cụ thể cần xem kỹ hơn
python vision_dense.py <proxy> <scene_db.json> <out_dir> --step 2 --ids 13 20 25

# Step=5 cho scenes dài > 60s
python vision_dense.py <proxy> <scene_db.json> <out_dir> --step 5
```

Output: `<out_dir>/dense_sheets_stepauto/scene_NNNN_sheet01.jpg`

---

### Phase 2.3 — 🤖 Agent Vision Review (BẮT BUỘC)

> [!IMPORTANT]
> **Agent PHẢI thực hiện bước này bằng `view_file` tool.** Đây là bước Agent dùng mắt AI để đọc hiểu nội dung video — thuật toán không thể thay thế bước này.

---

#### ⚡ Chiến lược SONG SONG: Dùng Subagents (KHUYẾN NGHỊ MẠNH)

> [!TIP]
> Nếu video có **≥ 50 scenes**, **KHÔNG xem tuần tự** — rất chậm (1-2 giờ).
> Thay vào đó: **spawn song song nhiều subagents**, mỗi agent xem 1 batch ~60-70 sheets.
> Kết quả: **400+ sheets trong ~10 phút** — nhanh hơn 10-15× so với tuần tự.

**Bước 1: Define subagent `vision-reviewer` (chỉ làm 1 lần/session)**

```python
define_subagent(
    name="vision-reviewer",
    description="Views dense vision sheets and returns R/F/I labels as Python dict.",
    enable_write_tools=True,
    system_prompt="""
You are a vision review agent for a video scene detection system.
Your job is to view dense vision sheets (8x8 grid = 64 frames per scene)
and assign labels:

- R (Real/Keep): Scene is one coherent, continuous clip. Keep as output.
- F (Fragment/Merge): Scene is under-split (multiple sub-scenes glued together) OR
  is a very short continuation of the previous scene. Merge with previous.
- I (Intro/Drop): Title screen, watermark animation, branding. Drop entirely.

For R-labeled scenes also provide:
- title: Short Vietnamese description <= 10 words
- category: Home | Animal | Crash | Funny | Sport | Security | Street | Nature
- mood: funny | shocking | cute | heartwarming | calm | inspiring | clumsy | scary
- tags: 2-4 descriptive English tags

Return ONLY a Python dict literal — no markdown fences, no explanation text:
{
  1: ("R", "Người chạy qua đường bị xe tông", "Crash", "shocking", ["car", "pedestrian", "dashcam"]),
  2: ("F", None, None, None, []),
  3: ("I", None, None, None, []),
}

KEY DECISION RULES:
- Sheet shows 2+ clearly different backgrounds/cameras in same scene → F (under-split)
- Sheet shows ONE consistent environment with continuous action → R
- Scene is 2-5s AND visually continues the same action as prior → F
- ALL frames are dark / logo watermark / text overlay only → I
- Scene > 60s: check BOTH first rows AND last rows — often under-split → may be F
- When uncertain R vs F: if 2+ distinct camera angles/environments exist → F

PROCESS: View ALL sheets before outputting. View exactly 6 sheets per tool call.
After viewing all, output the complete dict for your assigned scene ID range.
"""
)
```

**Bước 2: Spawn parallel subagents — tất cả cùng 1 lần invoke**

Chia scenes thành batches ~60-70, spawn tất cả đồng thời. Có thể mix nhiều videos:

```python
invoke_subagent([
    # Video A — 195 scenes → 3 subagents
    {
        "TypeName": "vision-reviewer",
        "Role": "VideoA scenes 1-65",
        "Prompt": (
            "View dense vision sheets for scenes 1-65. "
            "Location: E:\\project\\videoA_v2\\dense_sheets_stepauto\\ "
            "Files: scene_0001_sheet01.jpg through scene_0065_sheet01.jpg. "
            "View 6 sheets at a time. Return Python dict for scene IDs 1-65."
        )
    },
    {
        "TypeName": "vision-reviewer",
        "Role": "VideoA scenes 66-130",
        "Prompt": (
            "View sheets scene_0066_sheet01.jpg through scene_0130_sheet01.jpg "
            "in E:\\project\\videoA_v2\\dense_sheets_stepauto\\ "
            "Return Python dict for scene IDs 66-130."
        )
    },
    {
        "TypeName": "vision-reviewer",
        "Role": "VideoA scenes 131-195",
        "Prompt": "... scene_0131 through scene_0195 ... Return dict IDs 131-195."
    },
    # Video B — 119 scenes → 2 subagents
    {
        "TypeName": "vision-reviewer",
        "Role": "VideoB scenes 1-60",
        "Prompt": "View E:\\project\\videoB_v2\\dense_sheets_stepauto\\scene_0001 through scene_0060... Return dict IDs 1-60."
    },
    {
        "TypeName": "vision-reviewer",
        "Role": "VideoB scenes 61-119",
        "Prompt": "... scene_0061 through scene_0119 ... Return dict IDs 61-119."
    },
    # Video C — có thể thêm tùy ý, không giới hạn
])
```

> **Sau khi invoke**, KHÔNG cần poll hay chờ — system tự notify khi từng subagent xong.
> Trong lúc chờ, agent cha có thể tiếp tục công việc khác (apply labels video đã xong, v.v.)

**Bước 3: Nhận kết quả & lưu vào scratch ngay lập tức**

Khi subagent gửi dict về, lưu ngay vào scratch để không mất:

```
C:\Users\..\brain\<conv-id>\scratch\<video>_labels_<range>.py
```

**Bước 4: Merge các batches thành dict hoàn chỉnh**

```python
ALL_LABELS = {}
ALL_LABELS.update(BATCH_1_65)
ALL_LABELS.update(BATCH_66_130)
ALL_LABELS.update(BATCH_131_195)
# Tổng: 195 scenes phủ đủ
```

---

#### 📖 Cách đọc Dense Vision Sheet để phán đoán R/F/I

Mỗi sheet là JPG **8 cột × 8 hàng = 64 thumbnails**, trải đều theo toàn bộ độ dài scene.

**Header bar:** `Scene #NNNN | HH:MM.S → HH:MM.S | XXXs | sheet 1/1`

**Bảng phán đoán nhanh:**

| Pattern quan sát trong sheet | → Label | Lý do |
|------------------------------|---------|-------|
| Tất cả 64 frames — cùng background, cùng nhân vật | **R** | 1 cảnh thực |
| Rows 1-4: môi trường A; Rows 5-8: môi trường B khác hẳn | **F** | Under-split |
| Ngày (rows 1-4) → đêm (rows 5-8) | **F** | Under-split |
| Camera A (rows 1-4) → Camera B khác chất lượng (rows 5-8) | **F** | Under-split |
| Scene ngắn ≤ 5s + bối cảnh giống scene ngay trước | **F** | Tiếp tục |
| Scene dài > 60s — đầu/cuối khác nhau | **F** | Khả năng under-split cao |
| Tất cả frames: logo / tối đen / text overlay / watermark | **I** | Drop |

---

#### Apply Labels → `scene_db_labeled.json`

Sau khi có đủ labels, chạy apply script (dùng lại cho mọi video, chỉ đổi params):

```python
import json, pathlib

def apply_labels(db_path, labels, out_path, prefix):
    """
    Áp labels vào scene_db.json:
    - R: giữ lại
    - F: merge end_f vào scene trước (kéo dài scene trước)
    - I: bỏ hoàn toàn
    Output: scene_db_labeled.json đã renumber
    """
    db = json.loads(pathlib.Path(db_path).read_text(encoding='utf-8'))
    kept, merged, dropped = 0, 0, 0
    new_scenes = []

    for sc in db['scenes']:
        sid = sc['scene_id']
        if sid not in labels:
            sc['label'] = '?'
            new_scenes.append(sc)
            continue
        lbl, title, cat, mood, tags = labels[sid]
        sc.update({'label': lbl, 'title': title, 'category': cat,
                   'mood': mood, 'tags': tags or []})
        if lbl == 'I':
            dropped += 1                  # bỏ hoàn toàn
        elif lbl == 'F':
            merged += 1
            if new_scenes:                # kéo dài end_f của scene trước
                new_scenes[-1]['end_f'] = sc['end_f']
                new_scenes[-1]['duration'] = round(
                    (new_scenes[-1]['end_f'] - new_scenes[-1]['start_f']) / db['fps'], 2)
        else:                             # R — giữ lại
            kept += 1
            new_scenes.append(sc)

    # Renumber 1..N và cập nhật file_path
    orig_dir = None
    for i, sc in enumerate(new_scenes, 1):
        sc['scene_id'] = i
        fname = "{}{:04d}.mp4".format(prefix, i)
        sc['file_name'] = fname
        if orig_dir is None:
            orig_dir = str(pathlib.Path(sc['file_path']).parent)
        sc['file_path'] = orig_dir + '\\' + fname
    db['scenes'] = new_scenes

    pathlib.Path(out_path).write_text(
        json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')
    print("kept={} R, merged={} F, dropped={} I → {} final clips".format(
        kept, merged, dropped, len(new_scenes)))

# Ví dụ chạy:
apply_labels(
    db_path  = r'E:\project\dc19_v2\scene_db.json',
    labels   = DC19_LABELS,   # dict đã merge từ các batches
    out_path = r'E:\project\dc19_v2\scene_db_labeled.json',
    prefix   = 'dc19_'
)
```

> [!NOTE]
> `scene_db_labeled.json` là **đầu vào duy nhất của Phase 3**.
> Phase 3 chỉ xuất scenes có `"label": "R"`.
> F-scenes đã được merge vào scene trước (kéo dài `end_f`), không còn tồn tại riêng.

---

#### Quy trình tuần tự (khi < 50 scenes hoặc không dùng subagent)

Nếu số scenes nhỏ, xem trực tiếp **6 sheets / lượt** bằng `view_file`, gán label ngay:

```python
# Lượt 1: view 6 cùng lúc (parallel tool calls)
view_file("scene_0001_sheet01.jpg")
view_file("scene_0002_sheet01.jpg")
view_file("scene_0003_sheet01.jpg")
view_file("scene_0004_sheet01.jpg")
view_file("scene_0005_sheet01.jpg")
view_file("scene_0006_sheet01.jpg")
# → Gán nhãn ngay, ghi vào dict
# Lượt 2: tiếp theo 6 sheets...
```

---

### Phase 2.4 — Khử Trùng Lặp Intro & Cross-Video

* **ORB Inliers > 60:** Ngưỡng cao tránh false positive từ logo/watermark chung
* **Chỉ chạy khi có ≥ 1 cut thực sự trong 15s đầu** (không phải chỉ frame 0)
* Cross-video dedup: pHash fingerprint, phát hiện clip tái sử dụng liên video

---

## 🛑 Step 2.5 (Bắt buộc) — Preview Widget & Human-in-the-Loop Approval

> [!IMPORTANT]
> **Tuyệt đối KHÔNG ĐƯỢC tự ý chạy lệnh cắt (Phase 3 Split) ngay sau khi vừa detect xong!**
> Hệ thống bắt buộc phải dừng lại và thực thi quy trình Human-in-the-Loop:
>
> 1. **Dựng Preview Widget Trực Quan:** HTML widget với thumbnail keyframe thực tế, timecode, duration, **label badge màu (R/F/I)**, title và category đã phân tích.
>
> 2. **Chờ User Phê Duyệt (Human Confirmation):**
>    * Trình bày bảng xem trước và dừng lại hỏi: *"Bạn đã duyệt danh sách các tình huống ở trên chưa? Có cần tinh chỉnh ranh giới điểm cắt nào không trước khi tiến hành cắt thật?"*
>    * Chỉ khi User xác nhận đồng ý (`ok`, `tiến hành cắt`, `proceed`), Agent mới được phép kích hoạt Phase 3.

---

## Phase 3 — Frame-Accurate Splitting (`-vframes`)

> Agent **chỉ việc đọc trực tiếp danh sách từ `scene_db_labeled.json`** (đã có sẵn `file_name` và `file_path` chuẩn chỉnh). Chỉ xuất các scene có `label = "R"` (bỏ qua `F`, `I`, `is_intro`).

Khi xuất video clip thật từ video gốc 1080p, **tuyệt đối không dùng `-to <timecode>`** vì thuật toán làm tròn của FFmpeg có thể kéo theo 1 frame của cảnh kế tiếp.

### Cú pháp cắt chuẩn xác 100% không dính đuôi:
```bash
ffmpeg -y -ss <START_SECONDS> -i original_video.mp4 \
  -vframes <TOTAL_FRAMES> \
  -c:v libx264 -crf 18 -preset ultrafast -c:a aac \
  "<file_path_from_scene_db>"
```

*Công thức tính:*
* $\text{START\_SECONDS} = \text{start\_f} / \text{FPS}$
* $\text{TOTAL\_FRAMES} = \text{end\_f} - \text{start\_f}$

---

## Phase 4 — Premiere Pro MCP Bridge

Sau khi các clip sạch được xuất:
1. **Lọc kịch bản thông minh:** Lọc các clip theo `category`, `mood`, `tags`, tự động loại bỏ các clip bị trùng lặp liên video.
2. **Gọi MCP Tools để dựng Timeline:**
   * `createSequence`: Tạo sequence theo độ phân giải và fps mong muốn.
   * `importFiles`: Import các clips, gán Clip Display Name = `title` từ DB.
   * `insertClipToTimeline`: Xếp clips lên timeline theo thứ tự kịch bản.
   * **`addMarker` (Impact Marker):** Cắm Marker màu đỏ tại `peak_impact_frame`.
   * **Tự động gắn phụ đề:** Đọc `speech_text` để tạo caption tự động.
   * `addTransition`: Thêm chuyển cảnh mượt mà.
