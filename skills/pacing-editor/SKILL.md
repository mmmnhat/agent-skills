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
> Agent **PHẢI DỪNG LẠI** và sử dụng công cụ `ask_question` (hoặc hiển thị menu câu hỏi) để xác nhận:
> 1. **Tên Sequence Premiere**: Mặc định `W_Curve_Master` hay tên tùy chỉnh?
> 2. **Chế độ dựng (`--mode`)**:
>    - `w-curve`: Đảo cảnh kích thích giữ chân người xem theo mô hình W-Curve (Khuyên dùng)
>    - `sequential`: Giữ nguyên thứ tự thời gian gốc
> 3. **Thời lượng mong muốn (`--target-duration`)**: 30s, 60s hay dựng toàn bộ clips?
> 4. **Đích xuất**: Nạp trực tiếp vào Premiere Pro qua MCP (`--premiere-plan`) hay render ra file MP4 (`--render`)?

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
```
  --scenes-json "E:\test-dung-ai\output_clean_cut_18\scenes_context.json" \
  --name "Dailycam_Preview" \
  --render
```

### 3. Assemble Folder of Clips with Custom SFX & BGM
```bash
python e:\.agents\skills\pacing-editor\scripts\pacing_cli.py \
  --input-dir "E:\test-dung-ai\output_clean_cut_18" \
  --platform reels_shorts \
  --premiere-plan
```

---

## Premiere Pro MCP Execution

When executing via Premiere Pro MCP:
1. `create_sequence(name="Dailycam_Reels_Master")`
2. `import_media(file_path=...)` for footage, SFX, and BGM assets.
3. For each video clip on Track `V1`:
   - `add_to_timeline(item_id=clip, track_index=0, audio_track_index=0, start_seconds=in_time)`
   - `set_time_interpolation(node_id=clip, interpolation_type=2)` (Optical Flow)
   - `add_marker(name="Climax: scene_001", time_seconds=climax_time)`
4. For sound design:
   - Transition Whooshes placed at edit cuts on Audio Track `1` (`A2`).
   - Climax Hits placed at peak timestamps on Audio Track `1` (`A2`).
   - BGM placed on Audio Track `2` (`A3`) with volume ducking.
