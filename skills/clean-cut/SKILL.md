---
name: clean-cut
description: >-
  Precision AI video scene splitter, unblur engine, and visual narrative guard.
  Scans videos at high speed (>3,000 fps), uses AI Agent Vision (view_file) to
  inspect visual contact sheets and autonomously classify cuts (R/F/I), dynamically
  drops arbitrary intros/disclaimers without hardcoded limits, merges fragmented
  actions into complete narrative arcs, strips blurred margins (9:16, 1:1, 4:3),
  and produces verified scenes_context.json for Premiere Pro MCP.
  Use when the user pastes a video file/URL or asks to "tách scene", "crop nền mờ",
  "bóc clip", "clean cut", "unblur video", "cắt cảnh", or "khử trùng lặp video".
license: MIT
---

# 🎬 Clean Cut — Precision AI Scene Detection, Vision Verification & Unblur Engine

Hệ thống bóc tách cảnh video chính xác thế hệ mới kết hợp giữa **thuật toán quét siêu tốc trong RAM (>3.200 fps)** và **mắt AI kiểm duyệt trực quan (AI Agent Vision Review)**. 

Skill hoạt động theo chế độ **Agent Tự Chủ Hoàn Toàn (Autonomous Lead-Editor Mode)**: tự động quét, tự xem ảnh Contact Sheets, tự phán quyết ranh giới cảnh thật (`R`), tự gộp các pha hành động bị băm vụn (`F`), tự động loại bỏ Intro/Thẻ cảnh báo động (`I`) mà không cần người dùng can thiệp thủ công.

---

## ⚡ Nguyên Tắc Cốt Lõi: Agent Tự Quyết Định (Zero Manual Friction)

> [!IMPORTANT]
> **Agent là Lead Editor tự chủ — phán quyết dứt khoát bằng mắt AI nhìn vào frame thực tế!**
>
> 1. **AI Vision Thẩm Định Trực Tiếp (Bắt Buộc):**
>    - Sau khi thuật toán quét thô các điểm cắt nghi vấn, Agent **tự động dùng công cụ `view_file`** để kiểm duyệt các ảnh lưới Contact Sheets (`sheet_*.jpg`, mỗi ô gồm `frame-20 | frame-1 | vạch đỏ | frame 0 | frame+20`) hoặc Filmstrips 4-panel.
>    - Thuật toán số (luma/histogram/SSIM) chỉ là bước lọc thô. Phán quyết cắt/gộp/bỏ cuối cùng **bắt buộc dựa trên mắt AI nhìn vào hình ảnh thực tế**, giải quyết triệt để lỗi dính 2 cảnh khác nhau (under-split) hoặc cắt lửng hành động (over-split).
>
> 2. **Nhận Diện Intro Động (Dynamic Intro Detection — Không Giả Định Số Lượng):**
>    - **TUYỆT ĐỐI KHÔNG GÁN CỨNG SỐ LƯỢNG INTRO:** Intro không nhất thiết là 8 cảnh đầu, 3 cảnh đầu hay giới hạn 20s/30s! Có video có 0 cảnh intro, có video có 1 thẻ cảnh báo, có video có 12 clip teaser ngắn.
>    - **Dấu hiệu nhận biết Intro (`I`):** 
>      - Thẻ chữ cảnh báo, miễn trừ trách nhiệm ("WARNING", "DISCLAIMER", "CHÚ Ý", "FOR ENTERTAINMENT ONLY").
>      - Logo kênh đồ họa 3D, màn hình đếm ngược, bumper intro.
>      - Teaser montage dạo đầu cắt chớp nhoáng (<1.5s/shot) lấy trích đoạn từ các clip sau.
>    - **Ranh giới bắt đầu Clip #1:** Luôn là thời điểm bắt đầu của **tình huống/hành động thực tế liên tục đầu tiên**. Toàn bộ phân đoạn trước ranh giới này được gán nhãn `I` và loại bỏ sạch sẽ.
>
> 3. **Bảo Toàn Trọn Vẹn Diễn Biến Hành Động (`F` Merge):**
>    - Các hiện tượng gây nhảy ngưỡng thuật toán: lia máy nhanh (whip pan), chớp sáng (flash), cháy nổ, rung lắc camera, bọt nước tung toé, hoặc replay góc 2 / zoom cận cảnh của cùng 1 biến cố $\to$ **Agent tự động gán nhãn `F` (Merge)** để kéo dài clip trước, tạo 1 clip trọn vẹn narrative arc (setup $\to$ climax $\to$ recovery).
>
> 4. **Tự Động Cắt Phần Cứng & Chuẩn Hóa Premiere Pro MCP:**
>    - Tự động tận dụng GPU phần cứng tốt nhất (`h264_videotoolbox` trên Apple Silicon, `h264_nvenc` trên Windows) với cú pháp frame-accurate `-frames:v`.
>    - Tự động unblur crop viền mờ 9:16 / 1:1 / 4:3 về độ phân giải gốc.
>    - Tự động sinh bộ 4-Frame Filmstrips và xuất manifest `scenes_context.json` sẵn sàng import lên Premiere Pro timeline.

---

## 🔄 Quy Trình Thực Thi 4 Giai Đoạn (Autonomous Protocol)

### Giai đoạn 1: Quét Candidate Cuts & Sinh Contact Sheets
1. **Quét siêu tốc trong RAM:** Chạy phân tích proxy để thu thập toàn bộ các điểm cắt nghi vấn (candidate cuts).
2. **Sinh Contact Sheets trực quan:** Xuất các sheet dạng lưới (24 điểm cắt/sheet) hiển thị rõ ràng 4 thời điểm quanh điểm cắt: `N-20 | N-1 | [CẮT] | N+0 | N+20`.

```bash
# Phân tích sinh candidate cuts và contact sheets
python .agents/skills/clean-cut/scripts/clean_cut.py "<path_to_video>" --work-dir "_scene/<video_name>" --analyze-only
```

---

### Giai đoạn 2: 👁️ AI Agent Vision Review (Thẩm Định & Gán Nhãn)
Agent tự mở và duyệt các Contact Sheets bằng `view_file` (đọc 3-4 sheets mỗi lượt hoặc gọi subagent song song nếu video dài $\ge 50$ scenes).

Agent gán nhãn cho từng điểm cắt:
| Nhãn | Ý nghĩa | Hành động của Agent |
| :---: | :--- | :--- |
| **`R`** | **Real Cut** | Hai bên vạch đỏ là 2 cảnh/sự việc/bối cảnh/nhân vật độc lập $\to$ **Tạo điểm cắt mới**. |
| **`F`** | **False Cut (Merge)** | Hai bên vạch đỏ là cùng 1 sự việc (lia máy, flash, bọt nước, ngã tiếp đất, replay góc 2) $\to$ **Gộp vào cảnh trước**. |
| **`I`** | **Intro / Outro (Drop)** | Thẻ cảnh báo disclaimer, teaser montage dạo đầu, logo kênh, outro $\to$ **Bỏ hoàn toàn**. |

#### 🎯 Bộ quy tắc phán quyết của Agent:
- **Dò Intro:** Xem từ sheet 01 trở đi. Nếu các ô liên tiếp là chữ WARNING / disclaimer hoặc montage teaser cắt nhanh $\to$ gán `I`. Ngay khi bắt đầu cảnh quay thực tế đầu tiên $\to$ chốt kết thúc Intro. Clip 1 bắt đầu chính xác từ frame đầu tiên của cảnh này.
- **Tránh dính 2 cảnh (Under-split):** Nếu ô bên trái là cảnh A (ngoài trời, hồ bơi), ô bên phải là cảnh B (trong nhà, ẩu đả) $\to$ bắt buộc là `R`.
- **Tránh cắt lửng hành động (Over-split):** Nếu ô bên trái là người bắt đầu nhảy, ô bên phải là người đang rơi giữa không trung hoặc đang tiếp đất $\to$ bắt buộc là `F` (gộp).

---

### Giai đoạn 3: Cắt Phần Cứng Frame-Accurate & Unblur Cropping
Sau khi chốt nhãn phân đoạn:
1. **Cắt clip chuẩn từng frame:** Sử dụng `-ss` và `-frames:v` qua GPU (`videotoolbox` / `nvenc`) để xuất ra thư mục `scenes/`.
2. **Unblur Crop tự động:** Phát hiện viền mờ 9:16/1:1/4:3 bằng năng lượng biên Sobel/Laplacian variance và crop về tỉ lệ gốc nếu bật unblur.
3. **Snap audio zero-crossing:** Tránh tiếng nổ "pop/click" ở mép cắt âm thanh.

```bash
# Render phần cứng toàn bộ các scene đã được duyệt
python .agents/skills/clean-cut/scripts/clean_cut.py "<path_to_video>" \
  --output-dir "output_clean_cut" \
  --prefix "fail_" \
  --decisions "_scene/<video_name>/dec.txt" \
  --overwrite
```

---

### Giai đoạn 4: Tạo Visual Filmstrips & Xuất Manifest Premiere Pro MCP

1. **Bộ 4-Frame Filmstrips (`thumbnails/<prefix>_NNN_strip.jpg`):**
   Mỗi clip được chụp 4 mốc (0%, 33%, 66%, 100%) ghép thành ảnh ngang 1280x180 để người dùng và AI có thể nhìn lướt toàn bộ danh sách footage trong vài giây.
2. **Xuất `scenes_context.json`:**
   Chứa đầy đủ thông số kỹ thuật, mốc cao trào `temporal_landmarks` (lead-in, climax, recovery), độ phân giải, và mapping Premiere Pro timeline Track V1/V2.
3. **Báo Cáo Tổng Hợp:**
   Trình bày bảng Markdown sạch đẹp có link `file:///...` trực tiếp đến các clip và filmstrip đã hoàn tất.

---

## 🎬 Tích Hợp Premiere Pro MCP

Sau khi hoàn tất bóc tách cảnh:
1. Gọi `verify_premiere_connection` từ server `premiere-pro`.
2. Tạo Sequence mới hoặc sử dụng Sequence đang mở (hỏi người dùng tùy chọn nếu cần).
3. Import tất cả các clip sạch vào Bin chuyên biệt (VD: `Bin: Clean_Scenes`).
4. Xếp tuần tự lên Timeline Track V1, cắm Marker tại các điểm cao trào `climax_sec`.

---

## 📁 Cấu Trúc Thư Mục Chuẩn Của Clean Cut (Lean & Gọn Gàng)

Tất cả tài nguyên phân tích và kết quả được gom trọn vào **1 thư mục duy nhất** (`output_clean_cut/` hoặc thư mục chỉ định qua `--output-dir`), xóa bỏ hoàn toàn các folder trung gian rác:

```
output_clean_cut/
├── cands.json                  ← Danh sách điểm cắt nghi vấn (Stage 1)
├── dec.txt                     ← Phán quyết R/F/I của Agent Vision (Stage 2)
├── sheets/                     ← Ảnh lưới Contact Sheets kiểm duyệt (24 cuts/sheet)
├── scenes/                     ← Các clip MP4 đã cắt sạch (Stage 3)
│   ├── fail_001.mp4
│   └── ...
├── thumbnails/                 ← Filmstrip 4-panel kiểm chứng (Stage 4)
│   ├── fail_001_strip.jpg
│   └── ...
└── scenes_context.json         ← Manifest đầy đủ cho Premiere Pro MCP
```
