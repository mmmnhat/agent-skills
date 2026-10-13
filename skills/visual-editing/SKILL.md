---
name: visual-editing
description: Visual treatments, punch-in zooms, speed ramping, and sensitive content shielding. Manages Track V1 clips and Track V2 adjustment layers.
---

# Visual Editing (`visual-editing`)

Applies optical enhancements and shielding treatments to maintain visual engagement and content compliance.

## 🎯 Directives
- **Action Peak Punch-In:**
  - Keyframes subtle zooms (1.10x–1.20x scale) around the action climax (`mapped_climax_frame - 0.5s` to `mapped_climax_frame + 0.3s`).
  - Anchor point focused on the point of impact or subject face.
- **Content Shielding (Watermarks, Logos, Sensitive Content):**
  - Uses OpenCV KCF/CSRT tracking to track moving ROIs.
  - Headless mode: Renders via FFmpeg `delogo` or `boxblur`.
  - Premiere Pro mode: Places an Adjustment Layer on Track `V2` with Gaussian Blur and keyframed motion.
- **Subject Preservation:**
  - Never crop out the primary subject or essential reaction during reframing.
