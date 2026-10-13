---
name: source-understanding
description: Multi-modal source footage analyzer. Extracts narrative scenes, candidate cuts, acoustic transients, motion landmarks, and unblur regions. Emits state/source-manifest.json.
---

# Source Understanding (`source-understanding`)

Analyzes raw source video files across time, vision, acoustics, and physical causality.

## 🎯 Directives
- **Evidence First:** Never invent events. All timestamps, action peaks, and scene boundaries must be grounded in actual frame evidence.
- **AI Vision First:** When candidate cuts are detected, render visual contact sheets (`sheet_*.jpg`) and visually verify via `view_file`.
- **Acoustic Transients:** Detect real physical collision sounds (metal, glass, wood, concrete) and record `audio_transient_detected` and `transient_dbfs`.
- **Dynamic Bumper Dropping:** Automatically identify and drop intros, title bumpers, channel disclaimers, and countdowns.
- **Unblur Detection:** Detect 9:16 or 1:1 content padded with blurred margins and calculate crop bounding boxes.

## 📦 Output Artifact
Outputs `state/source-manifest.json` conforming to `schemas/source_manifest.schema.json`.
