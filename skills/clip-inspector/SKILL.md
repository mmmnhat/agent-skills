---
name: clip-inspector
description: >
  Standardizes pre-existing folders of video clips into unified scenes_context.json
  manifests without running scene splitting. Automatically generates 4-frame visual
  filmstrips (thumbnails/*_strip.jpg), computes temporal motion landmarks (lead-in,
  climax, recovery) and pacing recommendations, checks for blurred letterbox/pillarbox
  margins, and matches against 64-bit integer POPCNT pHash duplicate library indices.
  Compliant with Premiere Pro MCP. Use when the user pastes a folder of clips or asks
  to "thẩm định folder clip", "chuẩn hóa kho clip", "inspect clips", "tạo filmstrip",
  "đọc folder video", or "quét thư mục footage".
---

# Clip-Inspector: Video Footage Standardization & Visual Landmark Engine

Standardizes pre-existing folders of video clips (from stock libraries, Telegram downloads, client assets, or previously cut footage) into the unified `scenes_context.json` specification used across the entire editing ecosystem.

---

## 🛠️ Core Capabilities

1. **Batch Media Ingest & Technical Metadata:**
   - Scans and naturally sorts all video formats (`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`).
   - Extracts exact duration, framerate, resolution, and aspect ratio in a single pass.
2. **4-Frame Visual Filmstrips (`thumbnails/<clip_stem>_strip.jpg`):**
   - Automatically stitches 4 keyframe panels (`Setup 12%`, `Build-up 40%`, `Climax Peak`, `Reaction 90%`) into a horizontal composite image (~60KB/clip).
   - Allows vision-enabled AI agents to inspect the visual progression of each clip with a single image read.
3. **Temporal Motion Landmarks & Pacing Recommendations:**
   - Detects the exact action climax (`action_peak_rel_sec`) via inter-frame motion diffs.
   - Segments clip timeline into narrative phases: `lead_in`, `climax`, and `recovery`.
   - Recommends cut trims and GPU Optical Flow speed ramps for Premiere Pro.
4. **Blurred Border Energy Detection:**
   - Analyzes Laplacian variance and Sobel edge energy to detect blurred letterbox/pillarbox padding and computes the tight native bounding box.
5. **64-bit Integer POPCNT Deduplication:**
   - Computes DCT perceptual hashes (both standard and `hflip` mirrored).
   - Matches against `library_index.json` in $O(1)$ hardware instructions to flag cross-project duplicate clips.
6. **Unified Manifest Output:**
   - Emits `scenes_context.json` compliant with downstream skills (`video-transform`, `pacing-editor`, `content-shield`).

---

## 📋 4-Phase Interaction Protocol

### Phase 1: Pre-Execution Confirmation
When the user specifies a folder of clips, summarize the plan before executing:
- Target clip directory and count of candidate video files.
- Unblur check status (`Enabled` by default).
- Duplicate library checking (`Enabled` by default).
- Output destination for `scenes_context.json` and `thumbnails/`.

### Phase 2: Progress Milestones
Run the inspection engine:
```powershell
python "e:\.agents\skills\clip-inspector\scripts\inspect_clips.py" "<FOLDER_PATH>" [-o "<OUTPUT_DIR>"] [--no-unblur] [--no-dedup] [-l <LIMIT>]
```
Display milestone progress:
```
[Clip-Inspector Milestone 1] Ingesting & Analyzing Media:
  • Source Directory: E:\test-dung-ai\footage_scene\dailycam_19
  • Found Video Clips: 150
  • Unblur Detection: Enabled
  • Duplicate Indexing: Enabled
  • Output Manifest: E:\test-dung-ai\footage_scene\dailycam_19\scenes_context.json

  ✓ [001] clip_001.mp4 (4.20s, 16:9, Peak @ 1.85s)
  ✓ [002] clip_002.mp4 (12.50s, 9:16, Peak @ 4.10s) [Blurred Margins Detected]
```

### Phase 3: Results Markdown Table
Present a concise summary table:
| # | Clip File | Duration | Aspect Ratio | Action Peak | Blurred Margins | Duplication Status |
|---|---|---|---|---|---|---|
| 01 | `clip_001.mp4` | 4.20s | 16:9 | 1.85s | Clean | Unique |
| 02 | `clip_002.mp4` | 12.50s | 9:16 | 4.10s | ⚠️ Blurred | Unique |

### Phase 4: Proactive Handoff
Ask the user which step to proceed with next:
1. **Chống bản quyền (`video-transform`):** Áp dụng Deep Crop, Micro-rotation, Flip và Speed Shift NVENC vào các clip vừa quét.
2. **Dựng phim tự động (`pacing-editor`):** Đọc các mốc `temporal_landmarks` và dựng sequence trên Adobe Premiere Pro với Optical Flow GPU.

---

## 💻 CLI Usage

```powershell
# Standard inspection on a folder of clips
python "e:\.agents\skills\clip-inspector\scripts\inspect_clips.py" "E:\Path\To\Clips"

# Custom output directory
python "e:\.agents\skills\clip-inspector\scripts\inspect_clips.py" "E:\Path\To\Clips" -o "E:\Path\To\Output"

# Inspect first 10 clips only
python "e:\.agents\skills\clip-inspector\scripts\inspect_clips.py" "E:\Path\To\Clips" -l 10
```
