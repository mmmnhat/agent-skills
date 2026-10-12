# Architectural Specification: Autonomous Agentic Video Editorial Suite with Closed-Loop Evaluation Harness

**Document Version:** 1.0.0  
**Date:** 2026-10-12  
**Status:** DRAFT FOR REVIEW  
**Authors:** Lead Video Editor & Systems Architect  
**Target Environment:** Antigravity / Gemini CLI / Claude Code / Cursor AI + Adobe Premiere Pro MCP (`v1.18.1`) + Python Core Engine (OpenCV / PySceneDetect / FFmpeg NVENC)

---

## 1. Executive Summary & Problem Statement

### 1.1 The Challenge
Modern AI video editing solutions typically suffer from one of two failure modes:
1. **Open-Loop Hallucination:** The AI generates an edit list or timeline script, executes commands blindly, and terminates without observing the actual rendered state or verifying synchronization, resulting in frame bleed, audio drift, black frames, and broken narrative arcs.
2. **Monolithic Overload:** A single agent tries to analyze raw video footage, infer comedic timing, select sound effects, compute keyframe coordinates, and call low-level timeline APIs simultaneously, leading to context saturation, timeline mutation errors, and unrecoverable project states.

### 1.2 The Solution
This specification establishes a **Dual-Layer Closed-Loop Autonomous Video Editorial System**.
- **Mô hình Runtime:** **Single Lead Agent tuần tự hóa qua 7 Skills** — Một Agent Tổng Biên Tập duy nhất điều phối toàn diện, nạp tuần tự từng Skill theo phase và lưu trạng thái vào `state/*.json`. Tránh tốn token và loại bỏ hoàn toàn độ trễ chuyển giao giữa các Subagents.
- **Chiến lược Intake (Dual-Phase Hybrid):** Sử dụng Python Core Engine (`clean-cut` / NVENC) quét siêu tốc ngoài RAM (>3,000 fps), khử viền mờ 9:16 và cắt frame-exact trước. Sau đó Premiere Pro chỉ import các clip sạch để dựng nhịp và âm thanh, đảm bảo Premiere luôn nhẹ và mượt.
- **Chuẩn Sequence Mục Tiêu:** **HD 1080p (1920x1080) @ 23.976 fps** (chuẩn điện ảnh / broadcast NTSC Film, khóa timebase hằng số chống trôi âm thanh).
- **Tầng Agentic Orchestration & Harness:** Điều khiển Adobe Premiere Pro thông qua 384 công cụ của `premiere-pro-mcp`.
- **Closed-Loop Test Harness:** Nghiệm thu toàn diện theo **Batch Sequence Audit** sau khi dựng xong rough cut, cưỡng chế 5 Bất Biến Kỹ Thuật (Timeline Invariants), tự sinh **Patch Plan vi mô** để tự sửa lỗi (Self-Healing). Nếu lỗi lặp lại quá 3 lần, **Circuit Breaker** thực hiện **Soft Rollback về Checkpoint an toàn + cắm Marker đỏ** và báo cáo trực quan cho Editor.

---

## 2. System Architecture & Topology

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                ORCHESTRATOR / EDITORIAL DIRECTOR                                 │
│                   Oversees narrative intent, pacing profile, and agent delegation                 │
└─────────────────────────────────┬────────────────────────────────────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ SOURCE ANALYZER  │    │ EDITING PLANNER  │    │  SOUND DESIGNER  │
│ Multi-modal view │    │ Arc segmentation │    │ Contextual SFX   │
│ Motion & Audio   │    │ Pacing & W-Curve │    │ Gain & Ducking   │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                   ┌───────────────────────────┐
                   │  STRUCTURED EDIT PLAN     │
                   │  Single Source of Truth   │
                   │  Dual-Coordinate Mapping  │
                   └─────────────┬─────────────┘
                                 ▼
                   ┌───────────────────────────┐
                   │     PREMIERE OPERATOR     │
                   │ Executes MCP Mutations    │
                   │ Checkpoints & Rollbacks   │
                   └─────────────┬─────────────┘
                                 │ Calls Tools
                                 ▼
                   ┌───────────────────────────┐
                   │     premiere-pro-mcp      │
                   │  (384 Tools ExtendScript) │
                   └─────────────┬─────────────┘
                                 │ Mutates
                                 ▼
                   ┌───────────────────────────┐
                   │    ADOBE PREMIERE PRO     │
                   │ Active Sequence Timeline  │
                   └─────────────┬─────────────┘
                                 │ Readback State
                                 ▼
               ╔═══════════════════════════════════════════╗
               ║         HARNESS QA EVALUATOR              ║
               ║ Asserts 5 Timeline Invariants             ║
               ║ Measures Frame Sync, Gaps, Headroom       ║
               ╚═════════════════┬═════════════════════════╝
                                 │
                ┌────────────────┴────────────────┐
                ▼                                 ▼
            [ PASS ]                           [ FAIL ]
     Meets all Invariants              Violates $\ge 1$ Rule
                │                                 │
                ▼                                 ▼
        [ FINAL EXPORT ]               [ SELF-HEALING LOOP ]
      Render & Human Ready             Generates `patch-plan.json`
                                       Max 3 iterations
                                       Circuit Breaker Protected
```

---

## 3. The Seven Core Editorial Skills

### Skill 01: `source-understanding`
* **Mục tiêu:** Hiểu sâu sắc source video đa phương thức qua thời gian (hình ảnh, tiếng động, lời thoại, chuyển động, quan hệ nhân quả).
* **Nhiệm vụ:**
  - Quét candidate scene cuts và sinh Contact Sheet 24 ô kiểm duyệt (`clean-cut` engine).
  - Trích xuất Motion Peaks (đỉnh hành động) và Audio Transients (tiếng va chạm/la hét).
  - Nhận diện viền mờ (blurred letterbox/pillarbox) để tự động crop khung hình sạch sẽ.
* **Output:** `state/source-manifest.json` ghi nhận chính xác frame bắt đầu, frame va chạm (`climax_frame`), và frame kết thúc kèm độ tin cậy.

### Skill 02: `comedy-timing`
* **Mục tiêu:** Tư duy dựng tình huống hài kịch, sự cố, fail compilation.
* **Nhiệm vụ:**
  - Nhận diện cấu trúc nhịp 4 thì: **Setup (Mở đầu) $\to$ Anticipation (Dự cảm) $\to$ Payoff/Climax (Va chạm) $\to$ Reaction/Recovery (Hậu quả)**.
  - Phán quyết điểm cắt:
    - *Clip hoàn chỉnh:* Giữ trọn reaction tối thiểu 0.8s - 1.5s để người xem kịp cười/cảm nhận.
    - *Hard Fast-Cut:* Cắt cúp táo bạo `Climax - 1.0s` đến `Climax + 1.0s` cho các đoạn dựng nhịp nhanh.
    - *Freeze-frame / Micro-pause:* Chèn frame dừng ngay trước khoảnh khắc va chạm để tăng kịch tính.

### Skill 03: `context-aware-sfx`
* **Mục tiêu:** Thiết kế âm thanh thông minh, phù hợp ngữ cảnh vật liệu và cảm xúc.
* **Nhiệm vụ & Ma Trận Quyết Định Âm Thanh Thích Ứng (Adaptive Audio Matrix):**
  - **Trường hợp 1 (Âm thanh thực tế rõ nét):** Nếu âm thanh gốc tại frame va chạm có transient rõ ràng (tiếng kính vỡ, sắt thép rơi, va đập thật) $\to$ **Tự động tăng gain Track A1 (+3dB đến +6dB) và KHÔNG chèn SFX giả**. Giữ trọn tính chân thực của footage fail / CCTV.
  - **Trường hợp 2 (Âm thanh câm / mờ nghẹt):** Nếu video source câm (camera giám sát không mic) hoặc âm thanh quá rè $\to$ **Tra cứu và chèn SFX đặc tả ngữ cảnh lên Track A4**.
  - **Trường hợp 3 (Có tiếng la hét / phản ứng):** Nếu âm gốc có tiếng người cười, la hét, kinh ngạc $\to$ **Giữ nguyên A1 làm trọng tâm, chèn SFX va chạm với gain thấp hơn tiếng người 3dB** để không làm lu mờ reaction tự nhiên.
  - Tra cứu kho SFX qua công cụ `asset-indexer` với cơ chế "Hỏi và Nhớ" (Affinity Ledger).

### Skill 04: `adaptive-pacing`
* **Mục tiêu:** Điều tiết nhịp thở và đường cong giữ chân người xem (Audience Retention).
* **Nhiệm vụ:**
  - Hỗ trợ 2 chế độ dựng:
    1. **Sequential Fast-Cut:** Giữ nguyên thứ tự thời gian gốc nhưng lọc bỏ 100% đoạn lê thê.
    2. **W-Curve Retention Script:** Chấm điểm Sức hút ($S = 0.40 \cdot \text{Motion} + 0.35 \cdot \text{Arc} + 0.25 \cdot \text{Audio}$) và xếp theo 5 đỉnh/đáy (Hook $\to$ Context $\to$ Mid-Climax $\to$ Suspense $\to$ Grand Finale).
  - Tự động co giãn thời lượng để vừa vặn khung mục tiêu (30s, 60s Shorts/Reels hoặc dài hơn).

### Skill 05: `visual-editing`
* **Mục tiêu:** Thao tác hình ảnh động (punch-in zoom, reframing, speed ramp, che nội dung nhạy cảm).
* **Nhiệm vụ:**
  - Tính toán keyframe co giãn tỉ lệ (Punch-in Scale 1.1x - 1.25x vào đúng chủ thể lúc cao trào).
  - Áp dụng bộ lọc `delogo` nội suy biên hoặc tạo Premiere Adjustment Layer trên track `V2` với Gaussian Blur che watermark/logo (`content-shield`).
  - Áp dụng làm mượt chuyển động Optical Flow khi thay đổi tốc độ clip.

### Skill 06: `premiere-execution`
* **Mục tiêu:** Trực tiếp điều khiển Adobe Premiere Pro thông qua 384 công cụ của `premiere-pro-mcp`.
* **Nhiệm vụ:**
  - Ánh xạ trực tiếp từng thao tác trong `edit-plan.json` sang lời gọi MCP tương ứng:
    - Tạo sequence: `create_sequence` (chuẩn HD 1080p @ 23.976 fps)
    - Dải video lên V1: `add_to_timeline_batch`
    - Cắt tỉa: `trim_clip`, `split_clip`, `ripple_delete`
    - Đặt SFX/BGM: `add_to_timeline` trên track A3, A4, A5
    - Co giãn / Vị trí: `set_clip_scale`, `set_clip_position`
    - Điều chỉnh âm lượng & Ducking: `adjust_audio_levels`, `setup_ducking`
  - Quản lý checkpoint an toàn (`create_sequence_checkpoint`) trước mọi thao tác đột biến timeline.

### Skill 07: `video-quality-control`
* **Mục tiêu:** Kiểm tra chất lượng tự động theo cơ chế **Batch Sequence Audit**, phát hiện sai sót kỹ thuật và điều phối tự sửa lỗi.
* **Nhiệm vụ:**
  - Sau khi dựng xong toàn bộ rough cut trên Timeline, gọi `get_sequence_structure`, `get_timeline_gaps` đọc ngược toàn bộ dữ liệu.
  - Chạy song song toàn bộ 5 Invariants toán học (`INV-01` đến `INV-05`).
  - Khi phát hiện vi phạm: Tạo `state/patch-plan.json` sửa đồng loạt tất cả các lỗi trong một batch.
  - Sau khi sửa xong: Chụp ảnh review frames (`export_sequence_review_frames`, `capture_frame`) để mắt AI soi visual artifacts trước khi chốt.

---

## 4. State & Memory Architecture (Single Source of Truth)

### 4.1 Mô hình Ánh Xạ Tọa Độ Thời Gian Kép (Dual-Coordinate Time Mapping)
Để giải quyết dứt điểm vấn đề lệch âm thanh (SFX drift) khi sắp xếp hoặc cắt tỉa clip, hệ thống duy trì mối liên hệ toán học bất biến giữa **Source Timeline** và **Master Sequence Timeline**:

$$\text{Master Action Peak Frame} = \text{Master Sequence In} + (\text{Source Climax Frame} - \text{Source In})$$

### 4.2 Cấu trúc `state/edit-plan.json`
```json
{
  "$schema": "../schemas/edit_plan.schema.json",
  "plan_id": "plan_funny_moments_001",
  "project_name": "IdiotsAtWork_Ep18",
  "resolution": [1920, 1080],
  "fps": 23.976,
  "target_duration_sec": 30.0,
  "audio_layout": {
    "V1": "Video Clips",
    "V2": "Adjustment Layers / Visual Shields",
    "A1": "Original Ambient Sound",
    "A2": "Voiceover (Reserved Blank)",
    "A3": "Transition Whoosh SFX",
    "A4": "Action Climax Impacts",
    "A5": "Background Music (Ducked)"
  },
  "incidents": [
    {
      "incident_id": "forklift_fail_01",
      "pacing_role": "HOOK_RANK_2",
      "source_ref": {
        "media_path": "E:/footage/cctv_01.mp4",
        "source_in_frame": 150,
        "source_climax_frame": 215,
        "source_out_frame": 290
      },
      "master_timeline": {
        "track_v": "V1",
        "sequence_in_frame": 0,
        "sequence_out_frame": 140,
        "mapped_climax_frame": 65
      },
      "visual_operations": [
        {
          "type": "punch_in_zoom",
          "start_frame": 45,
          "end_frame": 85,
          "scale_start": 1.0,
          "scale_peak": 1.15
        }
      ],
      "sound_operations": [
        {
          "type": "climax_sfx",
          "asset_id": "sfx_heavy_metal_thud_01",
          "track": "A4",
          "sync_to_master_frame": 65,
          "gain_db": -3.0
        },
        {
          "type": "transition_whoosh",
          "asset_id": "sfx_fast_whoosh_02",
          "track": "A3",
          "sync_to_master_frame": 0,
          "gain_db": -6.0
        }
      ]
    }
  ]
}
```

---

## 5. Evaluation Harness & 5 Timeline Invariants

### 5.1 Bảng Đặc Tả 5 Invariants Cốt Lõi
Hệ thống Harness chạy tự động sau mỗi phiên mutation của Premiere Operator:

```
┌──────────┬─────────────────────────────┬──────────────────────────────────────┬──────────────────────────────────┐
│ Mã Quy Tắc│ Tên Bất Biến                │ Biểu thức Logic                      │ Thao Tác Tự Khắc Phục (Self-Fix) │
├──────────┼─────────────────────────────┼──────────────────────────────────────┼──────────────────────────────────┤
│ INV-01   │ Zero Gap on V1              │ len(get_timeline_gaps('V1')) == 0    │ ripple_delete các khe hở         │
│ INV-02   │ Frame-Exact SFX Sync        │ |Frame_SFX - Frame_Climax| <= 1 frame│ move_clip trên A4 dời đúng frame │
│ INV-03   │ Audio Headroom Protection   │ TruePeak(Master) <= -1.0 dBFS        │ adjust_audio_levels hạ gain      │
│ INV-04   │ Voiceover Track Integrity   │ len(get_clips('A2')) == 0            │ move_clip_to_track dời sang A3/A4│
│ INV-05   │ Payoff Window Preservation  │ Frame_Out >= Climax + 0.8s * fps     │ trim_clip mở rộng đuôi clip      │
└──────────┴─────────────────────────────┴──────────────────────────────────────┴──────────────────────────────────┘
```

### 5.2 Bộ Ngắt Mạch Tự Động (Circuit Breaker & Rollback Policy)
* Nếu sau **3 vòng lặp tự sửa (3 iterations)** mà Harness vẫn chưa đạt trạng thái PASS 100%:
  1. **Khôi phục an toàn (Soft Rollback):** Tự động gọi `undo` hoặc nạp lại Sequence Checkpoint an toàn gần nhất trước khi bắt đầu chuỗi tự sửa, ngăn chặn timeline bị biến dạng do sửa lặp.
  2. **Cắm Marker cảnh báo:** Tự động cắm Sequence Marker màu đỏ (`add_marker` với color='Red', name='[QA_FAIL]') tại các vị trí frame vi phạm.
  3. **Xuất báo cáo chẩn đoán:** Ghi đầy đủ mã lỗi, delta frame vào `state/qa-report.json`.
  4. **Báo cáo trực quan cho Editor:** Chụp ảnh frame tại vị trí lỗi qua `capture_frame`, gửi vào khung chat và yêu cầu Editor chỉ thị tiếp theo.

---

## 6. Project Directory Scaffolding

Cấu trúc dự án tiêu chuẩn của Agentic Video Editing Suite:

```
e:/.agents/
├── AGENTS.md                  # System prompt tổng: Autonomous Video Editorial Director
├── RULES.md                   # Các quy tắc cốt lõi không thể xâm phạm
├── setup_env.py               # 1-Step Setup, dò encoder GPU, đăng ký global skills
├── config.default.json        # Cấu hình chuẩn
├── config.local.json          # Cấu hình máy cục bộ (GPU, thư mục SFX cá nhân)
│
├── agents/                    # Định nghĩa chi tiết từng Subagent
│   ├── director.md            # Tổng đạo diễn điều phối tiến độ & kịch bản
│   ├── source-analyzer.md     # Chuyên gia soi source, bóc tách sự kiện
│   ├── editing-planner.md     # Chuyên gia nhịp dựng, timing, W-Curve
│   ├── sound-designer.md      # Chuyên gia thiết kế SFX, mix nhạc, ducking
│   ├── visual-editor.md       # Chuyên gia punch-in, reframing, che logo
│   ├── premiere-operator.md   # Kỹ thuật viên gọi 384 MCP tools thao tác timeline
│   └── qa-reviewer.md         # Giám sát viên chạy Harness Invariants & Self-Healing
│
├── skills/                    # 7 Skills nghiệp vụ tiêu chuẩn
│   ├── source-understanding/  # SKILL.md + scripts phân tích sự kiện
│   ├── comedy-timing/         # SKILL.md + quy tắc cắt Setup-Payoff
│   ├── context-aware-sfx/     # SKILL.md + tra cứu SFX theo ngữ cảnh
│   ├── adaptive-pacing/       # SKILL.md + thuật toán tính W-Curve
│   ├── visual-editing/        # SKILL.md + OpenCV tracking & transform
│   ├── premiere-execution/    # SKILL.md + ánh xạ edit-plan vào MCP
│   └── video-quality-control/ # SKILL.md + bộ test Harness Invariants
│
├── harness/                   # Khung kiểm thử tự động
│   ├── evaluator.py           # Bộ kiểm tra 5 Invariants toán học
│   ├── patch_generator.py     # Bộ sinh patch-plan.json vi mô
│   └── circuit_breaker.py     # Giới hạn 3 vòng lặp tự sửa
│
├── schemas/                   # JSON Schemas chuẩn hóa dữ liệu
│   ├── source_manifest.schema.json
│   ├── edit_plan.schema.json
│   ├── patch_plan.schema.json
│   └── qa_report.schema.json
│
└── state/                     # Bộ nhớ runtime (Single Source of Truth)
    ├── source-manifest.json   # Kết quả phân tích source
    ├── edit-plan.json         # Bản kế hoạch dựng tổng thể
    ├── patch-plan.json        # Bản vá tự sửa lỗi
    ├── timeline-state.json    # Trạng thái đọc ngược từ Premiere
    └── qa-report.json         # Báo cáo đánh giá của Harness
```

---

## 7. Quy Tắc Cốt Lõi Khóa Cứng (`RULES.md`)

```markdown
# VIDEO EDITING GLOBAL RULES & INVARIANTS

## 1. Evidence First
- Không bao giờ bịa đặt sự kiện không tồn tại trong source video.
- Không suy luận âm thanh chỉ từ một bức ảnh tĩnh; phải kiểm tra audio transient thực tế.
- Luôn lưu giữ tọa độ frame gốc của source (`source_in`, `source_climax_frame`, `source_out`).

## 2. Editorial Integrity
- Hiểu rõ bản chất sự việc trước khi ra quyết định cắt gọt.
- Bảo tồn trọn vẹn thì mở đầu (Setup) và thì trả giá/hậu quả (Payoff/Reaction).
- Không tự động cắt mọi clip xuống cùng một độ dài máy móc; nhịp dựng phải phục vụ kịch tính.

## 3. Audio & Sound Design
- Ưu tiên giữ lại âm thanh gốc có giá trị (tiếng kim loại, kính vỡ, người la hét thật).
- Không nhồi nhét SFX khi không có lý do kịch bản xác đáng.
- Tiếng va đập (Impact SFX) trên Track A4 BẮT BUỘC phải khớp vào đúng frame va chạm (|offset| <= 1 frame).
- Track A2 ĐỂ TRỐNG TUYỆT ĐỐI dành riêng cho Voiceover.

## 4. Premiere Pro MCP Execution
- Luôn gọi `verify_premiere_connection` trước khi thực thi lệnh.
- Luôn tạo Checkpoint (`create_sequence_checkpoint`) trước các thao tác đột biến lớn.
- Không bao giờ sửa đè hoặc làm hỏng file source gốc.
- Không bao giờ tuyên bố "Đã dựng xong" nếu chưa chạy qua vòng kiểm thử Harness QA.

## 5. Harness Evaluation & Self-Healing
- Bắt buộc kiểm tra toàn bộ 5 Invariants (`INV-01` đến `INV-05`) sau mỗi lần cập nhật sequence.
- Tự động sinh `patch-plan.json` để sửa lỗi kỹ thuật trước khi làm mịn thẩm mỹ.
- Giới hạn tối đa 3 vòng lặp tự sửa; kích hoạt Circuit Breaker nếu lỗi lặp lại.
```

---

## 8. Lộ Trình Triển Khai (Implementation Roadmap)

1. **Giai đoạn 1: Thiết lập cấu trúc & Schemas**
   - Tạo thư mục `agents/`, `skills/`, `harness/`, `schemas/`, `state/`.
   - Viết các file JSON Schema xác thực dữ liệu cho `source-manifest`, `edit-plan`, `patch-plan`.
2. **Giai đoạn 2: Cài đặt Harness Engine & Invariants Validator**
   - Viết module `harness/evaluator.py` kết nối trực tiếp với các công cụ kiểm tra của `premiere-pro-mcp` (`get_timeline_gaps`, `analyze_loudness`, `get_sequence_structure`).
   - Xây dựng module tự sinh bản vá `harness/patch_generator.py`.
3. **Giai đoạn 3: Tích hợp 7 Skills & Định hình 7 Subagents**
   - Chuyển giao các hàm cốt lõi từ `clean-cut`, `pacing-editor`, `asset-indexer`, `content-shield` vào 7 thư mục skills mới.
   - Viết file chỉ thị system prompt cho từng Subagent trong `agents/*.md`.
4. **Giai đoạn 4: Thử nghiệm thực tế vòng lặp khép kín**
   - Chạy thử nghiệm trên video `dailycam_18.mp4` hoặc footage Funny Moments.
   - Thử cố tình tạo 1 khe hở frame đen hoặc đặt lệch 1 SFX để kiểm chứng khả năng tự phát hiện và tự sửa lỗi của Harness.
