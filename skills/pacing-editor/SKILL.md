---
name: pacing-editor
description: Automated high-retention video sequencing, GPU Optical Flow speed ramping, and automated SFX/BGM sound design for Adobe Premiere Pro. Reads scenes_context.json or footage folders, builds multi-track timelines (V1 video, A2 transitions/impacts, A3 ducked BGM), sets optical flow time interpolation, and syncs audio hits to action peaks. Use when the user asks to "dựng timeline", "tạo sequence", "optical flow", "dựng premiere", "speed ramping", "ghép clip", "pacing editor", "lắp sfx", or "auto edit".
---

# Pacing Editor: High-Retention Sequencing & Sound Design Engine

`pacing-editor` turns isolated scene cuts into fully-scored, high-retention video sequences ready for social media (TikTok, YouTube Shorts, Reels) or broadcast.

It integrates seamlessly with:
1. **`clean-cut` & `clip-inspector`**: Reads scene landmarks (`lead_in`, `climax`, `recovery`) from `scenes_context.json`.
2. **`asset-indexer`**: Automatically queries the asset repository for matching whoosh transitions and climax impact hits, boosting choices based on learned preferences ("Hỏi và Nhớ").
3. **Premiere Pro MCP**: Programmatically orchestrates timeline creation, clip placement, Optical Flow time interpolation, marker tagging, and audio routing.
4. **Hardware NVENC Concat**: Optionally renders an instant stitched master MP4 without needing Premiere Pro open.

---

## Multi-Track Studio Architecture (5-Track Layout)

```
Premiere Pro Timeline Layout:
===================================================================================================
[V1] Video Track       : Fast-cut video clips with action peaks aligned
---------------------------------------------------------------------------------------------------
[A1] Audio Track 1     : Original Video Clip Audio (Ambient sound / dialogue / physical impact)
[A2] Audio Track 2     : [BLANK] RESERVED EXCLUSIVELY FOR VOICEOVER (VO / Narration)
[A3] Audio Track 3     : Transition SFX (Whoosh / Swoosh synced to video cuts)
[A4] Audio Track 4     : Climax SFX (Punch / Boom / Thud synced to Action Peak Markers)
[A5] Audio Track 5     : Background Music (BGM - Automatic Ducking -12dB during Climax events)
===================================================================================================
```

---

## Operating Modes

1. **Sequential Mode (`--mode sequential`)**:
   - Preserves 100% of the input clip sequence (chronological / folder order).
   - Applies **Hard Fast-Cut** trimming via Premiere Pro In/Out points, eliminating sluggish lead-ins and trailing dead air.

2. **W-Curve Reordering Mode (`--mode w-curve`)**:
   - Scores clips using: $\text{Score} = 0.40 \cdot \text{Motion} + 0.35 \cdot \text{Arc} + 0.25 \cdot \text{Audio}$.
   - Preserves **Incident Bundles** (multi-shot clips stay connected).
   - Maps into psychological W-curve:
     - **Hook (Peak 1)**: Rank 2 incident (or signature opening).
     - **Valley 1 (Dip 1)**: Context & curiosity.
     - **Mid-Peak (Peak 2)**: Rank 3 incident.
     - **Valley 2 (Dip 2)**: Suspense build-up.
     - **Grand Finale (Peak 3)**: Rank 1 incident (maximum impact payoff).
   - Optional `--target-duration` (e.g., `-t 30` or `-t 60`) selects top incident bundles to fit the duration.

See full engineering specification in [`references/SPEC_AND_PLAN.md`](references/SPEC_AND_PLAN.md).

---

## Agent Interaction Workflow

> [!CAUTION]
> **QUY TẮC BẮT BUỘC: KHÔNG TỰ ĐỘNG DỰNG TIMELINE KHI CHƯA HỎI NGƯỜI DÙNG**
> Khi người dùng yêu cầu dựng timeline hoặc chạy pacing editor, Agent **TUYỆT ĐỐI KHÔNG** tự ý chạy với tham số mặc định.
> Agent **PHẢI DỪNG LẠI** và sử dụng công cụ `ask_question` (hoặc hiển thị menu câu hỏi) để xác nhận các thông số sau:
> 1. **Tuỳ chọn Sequence Premiere (`--seq-mode`)**:
>    - `active`    : Dùng sequence đang mở sẵn trong Premiere (mặc định)
>    - `new_clone` : Tạo sequence mới sạch (nhân bản cấu hình độ phân giải/fps từ sequence hiện có - Khuyên dùng)
>    - `preset`    : Tạo sequence theo Preset chuẩn của Premiere (VD: HD 1080p 59.94 fps)
> 2. **Tên Bin lưu trữ footage (`--bin-name`)**: Mặc định `Scenes` (Nghiêm cấm để footage rải rác ngoài thư mục gốc Root của Project Panel).
> 3. **Chế độ dựng nhịp (`--mode`)**:
>    - `w-curve`: Đảo cảnh kích thích giữ chân người xem theo mô hình tâm lý W-Curve (Khuyên dùng)
>    - `sequential`: Giữ nguyên thứ tự thời gian gốc
> 4. **Thời lượng mong muốn (`--target-duration`)**: 30s, 60s hay dựng toàn bộ clips?
> 5. **Đích xuất**: Nạp trực tiếp vào Premiere Pro qua MCP (`--premiere-plan`) hay render ra file MP4 (`--render`)?

---

## Quickstart & CLI Reference

### 1. Sequential Fast-Cut Assembly (Default)
```bash
python e:\.agents\skills\pacing-editor\scripts\pacing_cli.py \
  --scenes-json "E:\test-dung-ai\test_skills_run\inspected\scenes_context.json" \
  --name "Sequential_Master" \
  --mode sequential \
  --premiere-plan
```

### 2. W-Curve Dynamic Reordering (Target 30s)
```bash
python e:\.agents\skills\pacing-editor\scripts\pacing_cli.py \
  --scenes-json "E:\test-dung-ai\test_skills_run\inspected\scenes_context.json" \
  --name "W_Curve_Master" \
  --mode w-curve \
  --target-duration 30 \
  --premiere-plan
```bash
python .agents/skills/pacing-editor/scripts/pacing_cli.py \
  --scenes-json "output_clean_cut/manifests/scenes_context.json" \
  --name "Dailycam_Preview" \
  --render
```

### 3. Assemble Folder of Clips with Custom SFX & BGM
```bash
python .agents/skills/pacing-editor/scripts/pacing_cli.py \
  --input-dir "output_clean_cut/scenes" \
  --platform reels_shorts \
  --premiere-plan
```

---

## Premiere Pro MCP Execution (High-Speed Batch Architecture)

⚡️ **CRITICAL PERFORMANCE RULE**:
**NEVER execute per-clip `add_to_timeline` in a sequential loop!** Calling 60+ individual tool calls across CEP bridge takes 90–120 seconds. ALWAYS use atomic batch execution:

### 🚀 Method 1: Atomic Batch MCP (`add_to_timeline_batch`) — [0.9s Speed]
1. **Import Media**: Import required unique clips via `import_media` (or `import_folder`).
2. **Prepare Target Sequence**: Call `duplicate_sequence(sequenceId=..., newName="...", clearContents=true)` to create a blank target sequence inheriting exact resolution and framerate.
3. **Batch Video Track (V1) + Linked Audio (A1)**:
   - Call `add_to_timeline_batch` once with all clips containing `projectItemId`, `trackIndex: 0`, `time`, `sourceInPoint`, `sourceOutPoint`, `linkAudio: true`.
   - Places 15–50 clips with sub-frame precision in **under 1 second**.
4. **Batch Audio Design (A3, A4, A5)**:
   - Call `add_to_timeline_batch` once for SFX Whoosh (`trackIndex: 2`), Climax Hits (`trackIndex: 3`), and BGM (`trackIndex: 4`).
   - Track `A2` (index 1) is kept clean for voiceover.
5. **Key Climax Markers**:
   - Call `add_marker` only for the top 3–5 dramatic peaks.

### ⚡ Method 2: Final Cut Pro 7 XML Import (`import_fcp_xml`) — [Single-Shot Import]
1. `pacing_cli.py` automatically generates a standardized `manifests/<sequence_name>_manifest.xml`.
2. Call `import_fcp_xml(filePath="path/to/manifest.xml")` — exactly **ONE tool call**.
3. Premiere Pro imports all 5 tracks, source trims, and markers natively.
