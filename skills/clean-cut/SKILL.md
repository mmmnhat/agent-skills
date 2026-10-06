---
name: clean-cut
description: Precision video scene splitter and unblur engine. Automatically scans videos at high speed (over 3,000 fps in RAM), strips blurred pillarbox/letterbox margins to native aspect ratios (9:16, 1:1, 4:3), links dynamic reframes/zooms of the same incident, filters intra-video teaser duplicates and cross-video library duplicates, and snaps cuts to audio zero-crossings. Produces rich `scenes_context.json` for Premiere Pro MCP. Use when the user pastes a video file/URL or asks to "tách scene", "crop nền mờ", "bóc clip", "clean cut", "unblur video", or "khử trùng lặp video".
license: MIT
---

# Clean Cut

High-speed scene detection, native unblur crop, incident linking, 2-tier deduplication, and audio zero-crossing protection.

## When to Use

Activate this skill whenever the user:
- Pastes a video file path (`.mp4`, `.mov`, `.mkv`) or YouTube URL asking to split it.
- Says: "tách scene", "cắt cảnh", "crop nền mờ", "unblur", "clean-cut", "bóc tách footage".
- Requests deduplication across video compilation folders or within a single video.

---

## Agent Interaction Workflow

You **MUST** follow this structured 4-phase interaction protocol with the user:

### Phase 1: Pre-Execution Confirmation
When the user supplies a video path or URL:
1. Read the current settings from [`config.json`](./config.json).
2. Present a concise summary table in chat:
   - **Video Source**: `<file or URL>`
   - **Output Directory**: `<output_dir>` (default: `output_clean_cut/`)
   - **Prefix**: `<prefix>` (default: `scene_`)
   - **Unblur Cropping**: `Bật (Tự phát hiện & crop sạch viền mờ về 9:16 / 1:1 / 4:3)`
   - **Khử trùng lặp**: `Bật (Lọc Teaser <30s vào _duplicates/ & đối chiếu library_index.json)`
3. Ask the user if they wish to adjust any parameters or proceed immediately.

### Phase 2: Execution & Progress Milestones
Run the underlying script:
```bash
python .agents/skills/clean-cut/scripts/clean_cut.py "<path_to_video>" [options]
```
Briefly inform the user at key milestones:
- **Milestone 1**: Đang quét nhanh trong RAM (phát hiện số candidate shot).
- **Milestone 2**: Báo cáo số scene unblur, số clip teaser/replay trùng bị chuyển vào `_duplicates/`, và số clip trùng lặp từ library (`_cross_duplicates/`).
- **Milestone 3**: Hoàn tất render phần cứng (`h264_nvenc`) và lưu manifest [`scenes_context.json`](./scenes_context.json).

### Phase 3: Result Presentation
Format the final response with:
1. **Thống kê tổng quan**: Số scene sạch, số clip unblur, số clip trùng đã lọc.
2. **Bảng Markdown chi tiết** có link trực tiếp `file:///...`:

| Clip ID | Tên File & Link | Thời lượng | Tỉ lệ | Nhóm sự kiện (Incident) | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 01 | [`scene_001.mp4`](file:///...) | 4.2s | 16:9 | Sự kiện #1 (Shot 1/2) | Cảnh gốc |
| 02 | [`scene_002.mp4`](file:///...) | 3.1s | 9:16 | Sự kiện #1 (Shot 2/2) | Zoom cận cảnh (Linked) |
| ... | ... | ... | ... | ... | ... |

*(Nếu có clip trùng lặp, liệt kê tóm tắt các clip đã chuyển vào folder `_duplicates/` hoặc `_cross_duplicates/`).*

### Phase 4: Proactive Hand-off
Proactively ask the user via interactive options:
- **Lựa chọn 1**: *"Chạy `video-transform` để scale, rotate, flip biến đổi các clip này chống bản quyền."*
- **Lựa chọn 2**: *"Đưa các clip này vào Premiere Pro để bắt đầu dựng sequence."*
- **Lựa chọn 3**: *"Hoàn tất, tôi sẽ tự kiểm tra."*

---

## Premiere Pro MCP Integration Protocol

If the user chooses to import into Premiere Pro:
1. Check Premiere connection: `call_mcp_tool(ServerName="premiere-pro", ToolName="verify_premiere_connection")`.
2. Propose a Sequence name (e.g., `CleanCut_<VideoName>`).
3. Import the clean clips from the output folder into a dedicated Project Bin.
4. Add clips sequentially to Timeline Track V1.
5. For clips marked with `is_continuation: true` (reframe/zoom), place them directly after their parent shot or on Track V2 with markers indicating the incident link.

---

## Companion Scripts Reference

- **Main Runner**: [`scripts/clean_cut.py`](./scripts/clean_cut.py)
- **Unblur Detector**: [`scripts/unblur_detector.py`](./scripts/unblur_detector.py)
- **Audio Snapper**: [`scripts/audio_snapper.py`](./scripts/audio_snapper.py)
- **pHash & Flip Matching**: [`scripts/phash_utils.py`](./scripts/phash_utils.py)
- **Multi-folder Deduplication**: [`scripts/deduplicate.py`](./scripts/deduplicate.py)
