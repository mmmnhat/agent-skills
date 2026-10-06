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

## Multi-Track Architecture

```
Timeline Layout:
--------------------------------------------------------------------------------------
[V2]  (Optional) Meme Overlays / Shield Adjustment Layers / Zoom Motion
[V1]  [Scene 01 (1.0x -> 0.5x Optical Flow -> 1.5x)] [Scene 02] [Scene 03] ...
--------------------------------------------------------------------------------------
[A1]  [Original Ambient / Voiceover Audio Track]
[A2]  |Whoosh|   *Impact Hit*   |Whoosh|   *Bonk Hit*   |Whoosh|
[A3]  [-------------------- Background Music (Ducked BGM) ---------------------------]
--------------------------------------------------------------------------------------
```

---

## Speed Ramping & Retention Curve

For each scene:
- **Lead-In (Hook)**: Runs at $1.0\times$ (or snappy $1.1\times$) to establish the scene without wasting viewer time.
- **Action Peak (Climax)**: Ramps down to $0.5\times$ slow-motion with **Optical Flow** (`interpolation_type: 2`) for dramatic visual tension.
- **Recovery / Outro**: Speeds up to $1.5\times$ to eliminate dead air before the next cut.
- **Climax Marker**: Places a timeline marker exactly at the impact peak and syncs an impact sound effect on track `A2`.

---

## Quickstart & CLI Reference

### 1. Generate Pacing Blueprint & Premiere Pro MCP Plan
```bash
python e:\.agents\skills\pacing-editor\scripts\pacing_cli.py \
  --scenes-json "E:\test-dung-ai\output_clean_cut_18\scenes_context.json" \
  --name "Dailycam_Reels_Master" \
  --platform reels_shorts \
  --premiere-plan
```
*Outputs:*
- `Dailycam_Reels_Master_manifest.json` (Structured timeline tracks)
- `Dailycam_Reels_Master_premiere_mcp_plan.json` (Executable MCP tool calls)

### 2. Render Instant Stitched Video (Headless NVENC)
```bash
python e:\.agents\skills\pacing-editor\scripts\pacing_cli.py \
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
