# Kiến Trúc Mở Rộng Hệ Sinh Thái 6 Skill Biên Tập Video Tự Động

Tài liệu này quy chuẩn lộ trình mở rộng và kiến trúc kết nối giữa **6 Skill chuyên biệt**, phục vụ sản xuất video tự động từ khâu bóc tách, thẩm định kho clip, biến đổi chống bản quyền, quản lý tài nguyên, che chắn nội dung nhạy cảm đến dựng phim theo Pacing trên Adobe Premiere Pro MCP.

---

## 🗺️ Bản đồ Kiến trúc Tổng thể (Ecosystem Architecture)

```
                            [ NGUỒN DỮ LIỆU ĐẦU VÀO ]
                                      │
            ┌─────────────────────────┴────────────────────────┐
            ▼                                                  ▼
     [ Video Dài / URL ]                             [ Thư mục Clip Có Sẵn ]
            │                                                  │
            ▼                                                  ▼
   ╔═══════════════════╗                              ╔═══════════════════╗
   ║     clean-cut     ║                              ║  clip-inspector   ║
   ║ (Tách scene,      ║                              ║ (Thẩm định folder,║
   ║  unblur, dedup)   ║                              ║  filmstrip, mốc)  ║
   ╚═════════╤═════════╝                              ╚═════════╤═════════╝
             │                                                  │
             └────────────────────────┬─────────────────────────┘
                                      ▼
                        [ scenes_context.json ]
                    (Chuẩn dữ liệu đồng nhất toàn hệ thống)
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       ▼                              ▼                              ▼
╔═══════════════════╗      ╔═══════════════════╗          ╔═══════════════════╗
║  video-transform  ║      ║   asset-indexer   ║          ║  content-shield   ║
║ (Scale, Rotate,   ║      ║ (Hỏi & Nhớ kho    ║          ║ (Motion Tracking, ║
║  Flip, Speed NVENC║      ║  SFX, Meme, GIF)  ║          ║  Keyframe V2 Mask)║
╚═════════╤═════════╝      ╚═════════╤═════════╝          ╚═════════╤═════════╝
          │                          │                              │
          └──────────────────────────┼──────────────────────────────┘
                                     ▼
                          ╔═════════════════════╗
                          ║    pacing-editor    ║
                          ║ (Reasoning nhịp điệu║
                          ║  Trim / Speed-ramp  ║
                          ║  Premiere Pro MCP)  ║
                          ╚═════════════════════╝
```

---

## 🧩 Đặc tả Chi tiết 6 Skill trong Hệ sinh thái

### 1. `clean-cut` (Bóc tách cảnh & Khử viền mờ)
- **Đầu vào:** File video dài hoặc YouTube/TikTok URL.
- **Nhiệm vụ:**
  - Quét proxy siêu tốc trong RAM (>3.200 fps).
  - Tự động dò và crop sạch viền mờ (pillarbox/letterbox) về đúng tỷ lệ tự nhiên (`9:16`, `1:1`, `4:3`).
  - Liên kết các cú reframe/zoom của cùng một sự kiện trọn vẹn (`incident_id`, `is_continuation: true`).
  - Khử trùng lặp 2 tầng: Lọc Teaser mở đầu ($<30\text{s}$) vào `_duplicates/` và so khớp liên video qua `library_index.json` vào `_cross_duplicates/` (hỗ trợ cả clip lật `hflip`).
  - Bắt dính điểm cắt theo sóng âm (Audio Zero-Cut Snapping: RMS dip + zero-crossing).
  - Sinh ảnh Filmstrip 4 khung hình ngang (`thumbnails/*_strip.jpg`) cho Agent nhìn bối cảnh.
  - Trích xuất mốc cao trào (`action_peak_rel_sec`) và các pha thời gian (`lead_in`, `climax`, `recovery`).
- **Đầu ra:** Các file MP4 sạch + [`scenes_context.json`](../schemas/scenes_context.schema.json).

---

### 2. `clip-inspector` (Thẩm định & Chuẩn hóa kho clip có sẵn)
- **Đầu vào:** Thư mục bất kỳ chứa các file clip đã cắt sẵn (từ client, telegram, kho stock).
- **Nhiệm vụ:**
  - Đọc toàn bộ video trong folder, trích xuất metadata kỹ thuật (độ phân giải, thời lượng, fps).
  - Sinh Filmstrip 4 khung hình ngang cho mỗi clip (`thumbnails/`).
  - Dò mốc cao trào chuyển động `action_peak_sec` và phân chia 3 pha (`lead_in`, `climax`, `recovery`).
  - Cảnh báo nếu clip bị dính viền mờ hoặc trùng lặp với `library_index.json`.
  - **Đầu ra:** Chuẩn hóa thư mục đó thành đúng chuẩn [`scenes_context.json`](../schemas/scenes_context.schema.json) để các skill sau dùng chung.

---

### 3. `video-transform` (Biến đổi hình học & Tốc độ chống bản quyền)
- **Đầu vào:** File clip đơn lẻ, folder clip, hoặc file `scenes_context.json`.
- **Nhiệm vụ:**
  - Áp dụng Deep Crop (Scale 10% - 20%), Xoay nghiêng nhẹ ($\pm 1.5^\circ - 2.5^\circ$), Lật gương (`hflip`).
  - Thay đổi tốc độ nhẹ nhàng kết hợp `atempo` giữ nguyên cao độ giọng nói (pitch-preserved).
  - Sử dụng phần cứng NVIDIA NVENC render siêu tốc.
  - Cập nhật file `transformed_context.json` giữ nguyên liên kết sự kiện.

---

### 4. `asset-indexer` (Quản lý & Tra cứu kho tài nguyên)
- **Đầu vào:** Thư mục tài nguyên (ví dụ: `E:\Video Asset\`).
- **Nhiệm vụ:**
  - Cơ chế **"Hỏi và Nhớ"**: Hỏi người dùng đường dẫn thư mục tài nguyên lần đầu, lưu cố định vào `config.json`.
  - Quét và lập mục lục các loại tài nguyên: SFX (tiếng đấm, va chạm, cười), Music (BGM), GIF/Meme (Bonk, reaction), Animated Emojis, Brand Logos.
  - Cho phép Agent tra cứu thông minh theo từ khóa ngữ cảnh (ví dụ: query *"bonk sound"*, *"facepalm meme"*, *"whoosh transition"*) để lấy đúng file asset.

---

### 5. `content-shield` (Che chắn Logo / Chấn thương bằng Motion Tracking)
- **Đầu vào:** Clip cần che chắn + Asset che (Logo kênh, Meme GIF, Animated Emoji, Sticker).
- **Nhiệm vụ:**
  - **Che Watermark / Logo tĩnh:** Định vị 4 góc hoặc vùng chữ phụ đề.
  - **Che Chấn thương / Máu me:** Dùng mốc `action_peak_sec` để xác định thời điểm va chạm nhạy cảm, khoanh vùng đối tượng chuyển động (mặt, tay, người ngã).
  - **Motion Tracking phi hủy diệt (Non-destructive Premiere Pro MCP):**
    - Sử dụng OpenCV Tracker (CSRT/KCF) tính quỹ đạo chuyển động $(X_t, Y_t, Scale_t)$.
    - Đặt Asset che lên Track V2 trong Premiere Pro.
    - Gọi MCP `add_keyframe` đặt Keyframe Position & Scale bám sát theo chuyển động của vật thể.
    - Biên tập viên có thể tùy biến, dịch chuyển hoặc thay asset bất kỳ lúc nào trên Premiere Pro.

---

### 6. `pacing-editor` (Reasoning Pacing, Cắt tỉa & Dựng Premiere Pro)
- **Đầu vào:** `scenes_context.json` (từ `clean-cut` hoặc `clip-inspector`) + Prompt yêu cầu của người dùng.
- **Nhiệm vụ:**
  - **Linh hoạt "theo yêu cầu người dùng"**: Không áp đặt công thức cứng nhắc, tùy biến theo phong cách (Shorts dồn dập, kể chuyện tự nhiên, hay highlight kịch tính).
  - **Tối ưu Clip Dài bằng dữ liệu có sẵn:**
    - Đọc `temporal_landmarks`: Nhận diện rõ đoạn dạo đầu `lead_in` (dài lê thê), đoạn cao trào `climax` (1-2s đắt giá), và đoạn `recovery`.
    - Đưa ra quyết định:
      - *Trim dứt khoát*: Nhảy cóc thẳng vào điểm chuẩn bị cận kề hành động.
      - *Speed Ramping*: Tua nhanh đoạn đi bộ/chuẩn bị (2x - 4x) và hạ về 1x/slow-mo lúc chạm đỉnh.
      - *Fastcut*: Cắt vụn các lát cắt tạo nhịp gấp gáp.
  - **Tận dụng Optical Flow GPU trên Premiere Pro:**
    - Không render `minterpolate` FFmpeg nặng nề.
    - Khi áp dụng Slow-motion / Speed ramp trên Premiere Pro, tự động gọi MCP `set_time_interpolation(interpolation="Optical Flow")` để nhân CUDA GPU của Premiere Pro xử lý mượt mà và tức thì.
  - **Dựng Timeline đa tầng:**
    - Track V1: Clip hình chính.
    - Track V2: Overlay sticker che chắn / GIF / Meme reaction.
    - Track A1: Âm thanh tự nhiên của footage.
    - Track A2: SFX va chạm / chuyển cảnh lấy từ `asset-indexer`.
    - Track A3: Nhạc nền BGM (tự động ducking âm lượng khi có thoại).
