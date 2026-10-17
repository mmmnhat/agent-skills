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
  - Premiere Pro mode: Places an Adjustment Layer or cropped shield clip on Track `V2` (or Masked `AE.Impact_Blur_FX` on `V3`) with Gaussian Blur and keyframed motion.
- **Animated Emoji Impact Shields (`Track V4` in ITV 10-Track Template):**
  - Covers strong physical impacts (`🙈` `512 (1).gif` for groin/crotch hits, `😵‍💫` `mnhat_emoji_37.gif` for direct head/face hits, `💥` `512 (4).gif` for heavy slams/explosions, `💨⭐` `512 (7).gif` for chaotic tumbles, `😹` `512 (6).gif` / `🐱` `512 (5).gif` for slapstick slips).
  - **Mandatory AI Vision & `premiere-cli` Verification:** Never guess impact timestamps or `(x, y)` coordinates from unscaled source thumbnails. Scan dense frames (`0.08s–0.10s` step) to find exact physical contact onset (`0.35s–0.50s` duration), read normalized `(x, y)` coordinates on the `1920x1080` sequence canvas after `Scale`/`Crop`, set Emoji `InPoint = 0`, apply 4 `AE.ADBE Motion -> Position` keyframes, and verify placement via `premiere-cli export-frame` + `view_file`.
- **Subject Preservation:**
  - Never crop out the primary subject or essential reaction during reframing.
