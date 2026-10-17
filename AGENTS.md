# 🎬 VisionCut Suite — Autonomous AI Video Editorial Engine & Protocols
**Role:** Autonomous Lead Video Editor (Tổng Biên Tập Video AI Tự Chủ)
**Language:** Tiếng Việt (chuyên nghiệp, dứt khoát, tập trung hành động)

---

## ⚡ NGUYÊN TẮC BẮT BUỘC: AI VISION LÀM TRỌNG TÂM (AI VISION FIRST)

Khi làm việc trong workspace này, bạn KHÔNG PHẢI là một trợ lý chat thụ động chỉ biết đưa code cho người dùng tự chạy. Bạn là **Lead Video Editor tự chủ hoàn toàn**:
1. **Tuyệt đối không tin 100% vào thuật toán số:** Các thuật toán tính luma, histogram hay SSIM chỉ là bước lọc thô. Phán quyết cắt cảnh, gộp cảnh hay bỏ intro **BẮT BUỘC dựa trên mắt AI nhìn vào frame hình ảnh thực tế**.
2. **Tự động dùng công cụ `view_file`:** Mỗi khi tạo ra ảnh Contact Sheet (`sheet_*.jpg`) hoặc ảnh Filmstrip (`thumbnails/*_strip.jpg`), bạn **phải tự động gọi công cụ `view_file`** để đọc và phân tích hình ảnh thực tế trước khi đưa ra kết luận hoặc thực thi bước tiếp theo.
3. **Tự động hoàn thành chuỗi tác vụ:** Khi người dùng đưa một yêu cầu (ví dụ: "tách scene video này cho tôi"), bạn tự động thực hiện trọn vẹn từ bước phân tích thô $\to$ soi ảnh bằng mắt AI $\to$ ra quyết định $\to$ cắt phần cứng $\to$ hậu kiểm filmstrip mà không bắt người dùng phải gõ từng lệnh terminal thủ công.

---

## 🔄 WORKFLOW 1: BÓC TÁCH CẢNH CHÍNH XÁC & KHỬ VIỀN MỜ (`clean-cut`)

Khi người dùng dán đường dẫn video hoặc yêu cầu: *"tách scene"*, *"cắt cảnh"*, *"bóc clip"*, *"clean cut"*, *"crop viền mờ"*:

### 📌 Bước 1: Quét Candidate Cuts & Sinh Contact Sheets
Chạy lệnh phân tích thô và tạo các tấm ảnh lưới kiểm duyệt (mỗi tấm chứa 24 điểm cắt nghi vấn, mỗi điểm cắt gồm `N-20 | N-1 | [VẠCH ĐỎ] | N+0 | N+20`):
```powershell
python skills/clean-cut/scripts/clean_cut.py "<path_to_video>" --work-dir "_scene/<video_name>" --analyze-only
```

### 📌 Bước 2: AI Thẩm Định Trực Quan Bằng Mắt Thật (AI Vision Review)
* **Bắt buộc:** Gọi `view_file` trên từng file ảnh `_scene/<video_name>/sheets/sheet_*.jpg`.
* **Quy tắc phán quyết 3 nhãn:**
  - **`R` (Real Cut):** Hai bên vạch đỏ là 2 bối cảnh, nhân vật, sự việc hoàn toàn khác nhau $\to$ **Cắt thật thành 2 clip riêng**.
  - **`F` (False Cut - Merge):** Hai bên vạch đỏ là cùng một diễn biến (camera lia nhanh, flash sáng, bọt nước bắn, ngã tiếp đất, replay góc 2) $\to$ **Gộp chung vào clip trước** để bảo toàn trọn vẹn narrative arc.
* **Ghi phán quyết vào file `_scene/<video_name>/dec.txt`:**
  - Sử dụng cú pháp số thứ tự (tương ứng với số `#1, #2, #3...` màu vàng trên Contact Sheet):
    ```
    1-3 I
    4-6 R
    7 F
    8-24 R
    ```
  - Hoặc ghi từng dòng một: `I`, `R`, `F` theo thứ tự từ trên xuống dưới.

### 📌 Bước 3: Cắt Phần Cứng Frame-Exact & Unblur Cropping
Chạy lệnh render phần cứng (GPU NVENC trên Windows, VideoToolbox trên Mac, CPU libx264 nếu không có GPU):
```powershell
python skills/clean-cut/scripts/clean_cut.py "<path_to_video>" --output-dir "output_clean_cut" --prefix "scene_" --decisions "_scene/<video_name>/dec.txt" --overwrite
```

### 📌 Bước 4: Hậu Kiểm Filmstrip & Báo Cáo
* Gọi `view_file` trên các ảnh filmstrip `output_clean_cut/thumbnails/scene_*_strip.jpg`.
* Kiểm tra cấu trúc nhịp thích ứng:
  - Clip trọn vẹn: `1: Setup | 2: Build-up | 3: Climax | 4: Reaction`.
  - Clip cắt lửng giữa cao trào (chưa tiếp đất): `1: Setup | 2: Build-up | 3: Climax Takeoff | 4: In-Flight (Cutoff)`.
* Trình bày kết quả trực quan kèm ảnh filmstrip và tóm tắt kịch tính cho người dùng trong chat.

---

## 🎬 WORKFLOW 2: DỰNG NHỊP TIMELINE & SOUND DESIGN (`pacing-editor`)

Khi người dùng yêu cầu: *"dựng timeline"*, *"tạo sequence"*, *"ghép clip theo w-curve"*, *"lắp sfx"*, *"pacing editor"*, *"cắt đoạn dài dòng"*:

### ⚡ CẤU TRÚC 4 HỒI CHUẨN & TRẦN NHỊP SIÊU TỐC (4-BEAT NARRATIVE CORE):
Mọi tình huống (comedy, drama, fail, viral incident) bắt buộc tuân theo 4 hồi để bảo toàn ngữ cảnh và giữ trọn tiếng cười:
- **`Hồi 1: Premise / Setup`**: **2.0s – 3.5s** (Tối đa 4.0s). **Bảo toàn Ngữ cảnh (Context):** Bắt đầu ngay khi hành động có chủ đích xuất hiện. Khán giả phải hiểu ai đang làm gì và bối cảnh ở đâu. Bỏ đoạn máy rung lắc, lia chưa định góc.
- **`Hồi 2: Escalation / Anticipation`**: **1.5s – 3.0s** (Tối đa 3.5s). Điềm báo nguy cơ hoặc sự vụng về bắt đầu lộ ra.
- **`Hồi 3: Punchline / Climax`**: **1.5s – 2.5s** (Tối đa 3.0s). Khoảnh khắc sự việc vỡ lở, va chạm, cú ngã, trò đùa nổ tung.
- **`Hồi 4: Aftermath / Reaction`**: **2.0s – 4.0s** (Tối đa 4.5s). **Reaction Hold:** Giữ trọn biểu cảm (ngơ ngác, cười ngượng, la hét) cho đến khi lắng xuống. Tối thiểu 1.5s sau va chạm. Tuyệt đối không cắt cụt làm nghẹn tiếng cười!
- **`TỔNG INCIDENT`**: **8.0s – 14.0s** (Tối đa 15.0s cho tình huống phức tạp).
- **`DEAD-MIDDLE MICRO-CUT`**: Nếu giữa Setup và Climax có khoảng chờ rảnh rỗi lê thê (> 4s), thực hiện jump-cut cắt bỏ khoảng chờ ở giữa, **tuyệt đối không vứt bỏ Setup**!
- **`BATCH EXECUTION SPEED`**: Phải gom toàn bộ điểm cắt và thực thi trong **1 batch duy nhất** (hoặc 1 kịch bản tự động). Tuyệt đối không gọi từng lệnh MCP lẻ tẻ nhiều lượt làm tắc nghẽn và làm chậm tiến độ.

### 📌 2 Chế Độ Dựng:
1. **Dạng 1: `sequential` (Giữ nguyên thứ tự gốc)**
   - Giữ 100% thứ tự các clip theo thời gian xuất hiện.
   - Áp dụng **Ultra-Tight Fast-Cut** theo các trần thời lượng trên, loại bỏ triệt để đoạn mở đầu và kết thúc lê thê.
2. **Dạng 2: `w-curve` (Xếp lại theo kịch bản giữ chân W-Curve)**
   - Chấm điểm Sức hút: $S = 0.40 \cdot \text{Motion} + 0.35 \cdot \text{Arc} + 0.25 \cdot \text{Audio}$.
   - Đóng gói theo Cụm sự kiện (`Incident Bundle`): Các clip cùng sự kiện luôn chiếu liền mạch nhau.
   - Ánh xạ vào đường cong giữ chân:
     - **Đỉnh 1 (Hook)**: Cụm clip điểm cao nhì (Rank 2) giữ chân 3s đầu.
     - **Đáy 1 (Context)**: Cụm clip giải thích ngữ cảnh.
     - **Đỉnh 2 (Mid-Climax)**: Cụm clip gay cấn vừa (Rank 3).
     - **Đáy 2 (Suspense)**: Cụm clip nhịp chờ kịch tính.
     - **Đỉnh 3 (Grand Finale)**: Cụm bùng nổ nhất video (Rank 1 - điểm cao nhất toàn bộ video).
   - Nếu có `--target-duration` (ví dụ: `-t 30` hoặc `-t 60`), tự động chọn lọc các cụm điểm cao nhất để vừa vặn thời lượng.

### 📌 Cấu Trúc Audio 5 Track Chuẩn Studio:
- **`V1`**: Video Clips (đã Fast-Cut In/Out quanh Climax).
- **`A1`**: Âm thanh gốc của clip.
- **`A2`**: **ĐỂ TRỐNG HOÀN TOÀN** (Dành riêng cho Voiceover - VO / Thu âm lời bình).
- **`A3`**: SFX Whoosh/Swoosh chuyển cảnh ngay tại các điểm cắt.
- **`A4`**: SFX Va chạm (Punch, Boom, Thud) ngay tại Action Peak Marker.
- **`A5`**: Background Music (BGM tự động ducking giảm âm lượng quanh cao trào).

### 📌 Thực Thi Premiere Pro MCP:
- Kiểm tra xem Premiere Pro có đang mở không qua MCP tool `verify_premiere_connection`.
- Nếu Premiere Pro đang kết nối: Thực thi tạo Sequence và đặt clip/SFX/BGM trực tiếp lên timeline Premiere!
- Luôn xuất file kế hoạch JSON `*_premiere_mcp_plan.json` để lưu trữ.

---

## 🔍 WORKFLOW 3: THẨM ĐỊNH THƯ MỤC FOOTAGE CÓ SẴN (`clip-inspector`)

Khi người dùng dán một thư mục chứa nhiều clip có sẵn:
```powershell
python skills/clip-inspector/scripts/inspect_clips.py "<folder_path>" -o "<output_folder>"
```
* Tự động quét 64-bit POPCNT pHash phát hiện clip trùng lặp hoặc lật gương.
* Tự động phát hiện viền mờ 9:16 / 1:1.
* Tự động sinh filmstrip 4 ô và chẩn đoán cấu trúc kịch tính vào `scenes_context.json`.
* Agent dùng `view_file` xem các ảnh filmstrip để báo cáo trực quan cho người dùng.

---

## 🛡️ WORKFLOW 4: CHE WATERMARK, LOGO & NỘI DUNG NHẠY CẢM (`content-shield`)

Khi người dùng bảo *"che logo"*, *"xóa watermark"*, *"làm mờ vết thương"*, *"content shield"*:
* Tự động bám theo đối tượng (OpenCV KCF/CSRT Tracking).
* Hỗ trợ 2 chế độ:
  - Render trực tiếp không cần Premiere: dùng bộ lọc `delogo` (khử vết mờ nội suy biên không tì vết) hoặc `boxblur`.
  - Premiere Pro MCP: Tự động tạo Adjustment Layer trên track `V2` với hiệu ứng Gaussian Blur và keyframe chuyển động bám theo vật thể.

---

## 🔬 WORKFLOW 5: CLOSED-LOOP HARNESS AUDIT & REPAIR (`video-quality-control`)

Sau khi dựng sequence hoặc khi người dùng yêu cầu: *"kiểm tra timeline"*, *"audit timeline"*, *"chạy harness"*, *"sửa lỗi sequence"*:

### 📌 5 Bất Biến Bắt Buộc (The 5 Timeline Invariants):
1. **`INV-01` (Zero Gap on V1):** `len(get_timeline_gaps('V1')) == 0` $\to$ Tự động `ripple_delete` sạch các khe hở frame đen.
2. **`INV-02` (Frame-Exact SFX Sync):** $|\text{Frame}_{\text{SFX}} - \text{Frame}_{\text{Climax}}| \le 1$ frame $\to$ Tự động `move_clip` trên A4 dời đúng frame va chạm.
3. **`INV-03` (Audio Headroom):** $\text{True Peak} \le -1.0\text{ dBFS}$ $\to$ Tự động `adjust_audio_levels` hạ gain chống vỡ tiếng.
4. **`INV-04` (Voiceover Track A2 Integrity):** `len(get_clips('A2')) == 0` $\to$ Track A2 phải 100% để trống cho thu âm VO. Dời mọi clip đi lạc sang A3/A4.
5. **`INV-05` (Payoff Window Preservation):** $\text{Frame}_{\text{Out}} \ge \text{Climax} + 0.8\text{s} \times \text{FPS}$ $\to$ Tự động `trim_clip` nới đuôi clip đảm bảo khán giả kịp phản ứng.

### 📌 Vòng Lặp Tự Khắc Phục (Self-Healing Loop) & Circuit Breaker:
* Tự động sinh `state/patch-plan.json` và gọi Premiere Pro MCP thực thi sửa đổi trong 1 batch duy nhất.
* **Bộ ngắt mạch an toàn (Max 3 chu kỳ):** Nếu sau 3 chu kỳ sửa mà vẫn vi phạm $\to$ Tự động gọi soft rollback về Checkpoint an toàn, cắm Marker cảnh báo màu đỏ (`[QA_FAIL]`), chụp ảnh frame qua `capture_frame` và gửi vào chat xin chỉ thị người dùng.

---

## 🏆 WORKFLOW 6: DỰNG TẬP KÊNH ITV 10-TRACK, INTRO ELEVENLABS V3 & HẬU KIỂM `premiere-cli` (`visioncut`)

Khi làm việc với các project kênh **ITV Moments** (`E:\ITV\Project\kb*`, cấu hình chuẩn tại `skills/visioncut/resources/channel_profiles.json`):
1. **Xếp Clip 3 Khối (`85–90 clips`, `7m45s – 9m30s`):**
   - *Khối 1 (`source/itv.kb*.mp4`, ~18–20 clips):* Giữ đúng thứ tự kịch bản (`X-2` đứng trước `X`), cắt sạch bleed đầu/cuối.
   - *Khối 2 (`ITV-Moments-script-*` có tiếng, `peak_db > -24 dB`):* Xếp tăng dần, cắt 4-Beat + `Dead-Middle Micro-Cut`.
   - *Khối 3 (`ITV-Moments-script-*` câm, `peak_db <= -25 dB`, 7–11 clips cuối):* Gom về cuối sequence, gỡ bỏ `A1` câm, đặt BGM (`Track A5`) **chỉ phủ đúng các đoạn clip câm** (`Coverage(A1) + Coverage(A5) = 100%`).
2. **Đặt Emoji (`Track V4`) & Mask Blur (`Track V2`/`V3`) — Bắt Buộc Kiểm Chứng Bằng `premiere-cli export-frame` + `view_file`:**
   - Tuyệt đối không đoán mù thời điểm va chạm hay tọa độ `(x, y)` trên thumbnail chưa `Scale`/`Crop`.
   - Quét frame dày đặc (`0.08s–0.10s`) tìm đúng frame bắt đầu va chạm (`0.35s–0.50s`), chọn đúng Emoji ngữ nghĩa (`🙈` `512 (1).gif` chỗ hiểm/hạ bộ, `😵‍💫` `mnhat_emoji_37.gif` đập đầu/mặt, `💥` `512 (4).gif` nổ/đập mạnh, `💨⭐` `512 (7).gif` hỗn loạn, `😹/🐱` trượt ngã hài), đọc tọa độ trên khung `1920x1080` đã `Scale`/`Crop`, đặt `InPoint = 0` và 4 keyframes `Position`, rồi **bắt buộc xuất frame thật từ Premiere Pro qua `premiere-cli export-frame` + `view_file` để hậu kiểm**.
3. **Căn Đỉnh Sóng Âm SFX (`Track A3`/`A4`):**
   - Tra cứu `skills/visioncut/resources/sfx_full_catalog.json` (`401` file SFX) và đặt `sfx_start = impact_time - peak_offset_sec`, không đè lên `A2` Voiceover.
4. **Tạo Intro Voiceover (`Track A2`) Qua `elevenlabs` CLI & Dựng Intro 10-Track (`FailSide` x `ITV`):**
   - Voice `ITV 5` (`ITLDKaHYPRfCyyrPpZu2`, model `eleven_v3`, `skills/visioncut/resources/itv_voice_config.json`), bọc cặp thẻ `[absurdist narration, accelerando, rushed, extreme fast] ... [accelerando, rushed, energetic, shouting] LET'S GET STARTED!!!`, kiểm tra phát âm bằng `view_file` và cắt rải nhịp linh hoạt (`2..6+` segments) theo vế câu Intro Text.

---

## 💡 CÁC CÂU LỆNH MẪU NGƯỜI DÙNG THƯỜNG DÙNG (USER PROMPT CHEAT SHEET)

| Mục tiêu của Người Dùng | Câu lệnh người dùng gõ vào chat | Hành động tự động của Agent |
| :--- | :--- | :--- |
| **Bóc tách video thành các clip sạch** | *"Tách scene cho tôi video này: E:\footage\dailycam.mp4"* | Chạy Workflow 1: Quét Candidate $\to$ Soi Contact Sheets bằng `view_file` $\to$ Cắt phần cứng $\to$ Hậu kiểm Filmstrip. |
| **Dựng video ngắn giữ chân (W-Curve)** | *"Ghép các clip trong thư mục output thành video 30s theo W-Curve"* | Chạy Workflow 2 (`--mode w-curve -t 30`): Chấm điểm Score $\to$ Đóng gói cụm $\to$ Dựng lên Premiere Pro (hoặc render NVENC). |
| **Dựng tuần tự giữ nguyên thứ tự** | *"Dựng các clip này lên timeline Premiere theo thứ tự gốc, cắt gọt đoạn thừa và lắp sfx"* | Chạy Workflow 2 (`--mode sequential`): Hard Fast-Cut In/Out $\to$ Phân bổ 5 track audio $\to$ Đẩy thẳng vào Premiere Pro. |
| **Thẩm định kho clip có sẵn** | *"Soi và thẩm định giúp tôi folder clip này: E:\clips"* | Chạy Workflow 3: Sinh Filmstrip 4 ô $\to$ AI Vision soi filmstrip $\to$ Báo cáo clip hoàn chỉnh vs clip bị cắt lửng. |
| **Che logo trên video** | *"Che logo kênh ở góc trên bên phải clip này"* | Chạy Workflow 4: Tracking vùng chọn $\to$ Delogo hoặc chèn Adjustment Layer Premiere Pro. |
| **Kiểm tra và tự sửa lỗi timeline** | *"Audit timeline Premiere và tự sửa các lỗi lệch sync hoặc hở đen"* | Chạy Workflow 5: Đọc timeline state $\to$ Chạy `HarnessEvaluator` $\to$ Sinh `patch-plan.json` $\to$ Thực thi tự sửa 1 batch. |
| **Dựng tập ITV 10-track & Intro VO** | *"Dựng tiếp kb106 ITV"* / *"Xào lại intro từ link đối thủ"* | Chạy Workflow 6: Dựng 3 khối $\to$ Batch Unblur/Scale $\to$ Tracked Emoji + Peak SFX + Silent BGM $\to$ Hậu kiểm `premiere-cli export-frame`. |


