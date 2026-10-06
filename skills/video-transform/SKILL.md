---
name: video-transform
description: Geometric distortion and pitch-preserving audio retiming engine for video clips. Applies scale zoom (deep crop), micro-rotation, horizontal flip, and pitch-preserved speed adjustments using NVENC hardware acceleration. Preserves scene context manifests for Premiere Pro MCP. Use when the user wants to "transform clip", "remix video", "scale rotate flip", "lật gương video", "xoay nghiêng clip", or "chống bản quyền video".
license: MIT
---

# Video Transform

Applies geometric distortion (scale, rotate, flip) and pitch-preserving audio speed shifts to make video clips unique against automated platform fingerprinting.

## When to Use

Activate this skill when the user:
- Requests to modify, remix, or transform video clips.
- Says: "transform clip", "remix video", "scale rotate flip", "lật gương video", "xoay nghiêng", "chống bản quyền".
- Wants to process clips previously extracted by `clean-cut` before importing into Premiere Pro or publishing.

---

## Agent Interaction Protocol

Follow this simple, efficient 3-step workflow:

### Step 1: Parameter Confirmation
1. Load defaults from [`config.json`](./config.json) or read the active preset.
2. Present a brief confirmation to the user:
   - **Target**: `<file, folder, or scenes_context.json>`
   - **Preset**: `standard (Crop 15%, Xoay 2.0°, Lật gương, Tốc độ 1.02x)`
   - **Output Directory**: `<output_dir>` (default: `output_transformed/`)
3. Note: If the user provided inline overrides in their prompt (e.g., *"xoay 3 độ, không lật"*), immediately apply them without asking redundant questions.

### Step 2: Execution
Run the transformation engine:
```bash
# Transform an entire manifest and preserve incident context
python .agents/skills/video-transform/scripts/transform.py "<path_to_scenes_context.json>"

# Or transform a folder of clips
python .agents/skills/video-transform/scripts/transform.py "<folder_path>" --preset standard

# Or transform a single clip with custom parameters
python .agents/skills/video-transform/scripts/transform.py "<clip.mp4>" --rotate 2.5 --scale 0.85 --speed 1.03
```

### Step 3: Result Summary & Premiere Pro Hand-off
1. Output a Markdown table listing transformed clips and updated file paths.
2. If processing a `scenes_context.json`, confirm that [`transformed_context.json`](./transformed_context.json) has been created with all incident IDs and reframe links preserved.
3. Offer to import the transformed clips into Premiere Pro if requested.

---

## Presets Reference

- **`subtle`** ([`presets/subtle.json`](./presets/subtle.json)): 8% crop, 1.0° tilt, flip, 1.01x speed.
- **`standard`** ([`presets/standard.json`](./presets/standard.json)): 15% crop, 2.0° tilt, flip, 1.02x speed (Default).
- **`aggressive`** ([`presets/aggressive.json`](./presets/aggressive.json)): 20% crop, 2.5° tilt, flip, 1.04x speed.

---

## Companion Scripts

- **Main Transformer**: [`scripts/transform.py`](./scripts/transform.py)
