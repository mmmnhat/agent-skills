---
name: content-shield
description: Visual obscuration and watermark/logo/sensitive content shielding via OpenCV Tracking and Premiere Pro V2 Blur/Adjustment Layer. Automatically detects, tracks moving ROIs, and applies delogo, heavy Gaussian blur, or mosaic censor bars headlessly via FFmpeg NVENC or on Premiere Pro timelines. Use when the user wants to "che watermark", "che logo", "xóa logo", "làm mờ logo", "che vết thương", "che mặt", "content shield", "delogo", or "blur video".
---

# Content Shield: Visual Obscuration & Watermark Shielding Engine

`content-shield` is an intelligent visual protection and obscuration engine designed for automated editing workflows. It detects, tracks, and shields intrusive watermarks, broadcast channel logos, subtitles, phone numbers, license plates, faces, or sensitive graphic content.

It operates seamlessly in two modes:
1. **Headless High-Speed NVENC**: Uses FFmpeg's spatial `delogo` interpolation or GPU-accelerated `boxblur` / `mosaic` to generate clean footage instantly.
2. **Premiere Pro MCP Timeline Integration**: Creates an Adjustment Layer on Track `V2` (directly above footage on `V1`), applies Gaussian Blur / Fast Blur / Mosaic, and sets animated keyframes matching OpenCV motion tracking.

---

## Architecture & Capabilities

```
+-------------------------------------------------------------+
|                     Video Input / Folder                    |
+-------------------------------------------------------------+
                              |
       +----------------------+----------------------+
       |                                             |
[Preset Zones: TR, TL, BR, BL, BC]           [Auto-Pinpoint / ROI]
(Broadcast bug, TikTok tag, subtitles)        (Temporal Edge Variance)
       |                                             |
       +----------------------+----------------------+
                              |
                     [OpenCV Tracking]
             (Static or Dynamic MIL Tracker)
                              |
       +----------------------+----------------------+
       |                                             |
[FFmpeg NVENC Headless]                  [Premiere Pro MCP Bridge]
 • delogo (spatial interpolation)         • Track V2 Adjustment Layer
 • gaussian_blur (heavy privacy)          • Fast Blur / Gaussian Blur
 • mosaic (pixelated censor bar)          • Crop & Motion Keyframes
 • solid_mask (blackout)                  • scenes_context.json sync
```

---

## Preset Zones & Modes

### Preset Zones
| Zone | Target Use Case | Default Relative Box `[rx, ry, rw, rh]` |
| :--- | :--- | :--- |
| `top_right` | TikTok account badge, live tag, channel icon | `[0.76, 0.02, 0.22, 0.12]` |
| `top_left` | Broadcast TV bug, news network logo | `[0.02, 0.02, 0.22, 0.12]` |
| `bottom_right` | Dashcam timestamp, recorder watermark | `[0.74, 0.86, 0.24, 0.12]` |
| `bottom_left` | Camera brand logo, device watermark | `[0.02, 0.86, 0.24, 0.12]` |
| `bottom_center` | Subtitles, ticker banner, contact hotline | `[0.10, 0.82, 0.80, 0.15]` |
| `custom` | Custom pixel or normalized `[x, y, w, h]` box | Explicit coordinates |

### Shield Modes
1. **`delogo`**: Uses border spatial interpolation. Ideal for static corner logos, TV bugs, and translucent watermarks. Near-invisible removal.
2. **`gaussian_blur`**: Heavy Gaussian blur ($r=35$). Ideal for sensitive injuries, gore, phone numbers, or license plates.
3. **`mosaic`**: Pixelated blocky censor bars. Classic aesthetic for privacy protection.
4. **`solid_mask`**: Opaque matte fill box.

---

## Quickstart & CLI Reference

### 1. Preview Watermark Mask on Single Video
```bash
python e:\.agents\skills\content-shield\scripts\shield_cli.py \
  --input "E:\path\to\clip.mp4" \
  --zone top_right \
  --preview
```
*Generates `<clip_stem>_shield_preview.jpg` showing neon bounding box and simulated blur.*

### 2. Auto-Pinpoint & Render Clean Video (Headless NVENC)
```bash
python e:\.agents\skills\content-shield\scripts\shield_cli.py \
  --input "E:\path\to\clip.mp4" \
  --zone top_right \
  --auto-pinpoint \
  --mode delogo \
  --render
```

### 3. Track Moving Object & Generate Premiere Pro Plan
```bash
python e:\.agents\skills\content-shield\scripts\shield_cli.py \
  --input "E:\path\to\clip.mp4" \
  --roi "640,360,180,180" \
  --track \
  --premiere-plan
```

### 4. Batch Shield All Clips from `scenes_context.json`
```bash
python e:\.agents\skills\content-shield\scripts\shield_cli.py \
  --scenes-json "E:\test-dung-ai\output_clean_cut_18\scenes_context.json" \
  --zone top_right \
  --mode delogo \
  --render
```

---

## Premiere Pro CLI & MCP Integration (High-Speed Channel Workflow)

When shielding watermarks and cropping blurred margins in Premiere Pro via `premiere-cli` (`http://127.0.0.1:47823/command`):
1. **Unblur & Sidebar Logo Removal (`Track V1`):**
   - Apply `Crop` (`AE.ADBE AECrop`) directly on `V1` pillarboxed clips (`Left` & `Right` `15.5% – 35%`). This simultaneously strips blurred pillarbox sidebars AND removes sidebar logos (`LA`, `FAILARMY`, `TMAX`, `REC`, `MEC`, `22`).
2. **Corner/Edge Logo Reframing (`Track V1`):**
   - Compute `fit_scale = min(1920/w, 1080/h) * 100`. For clips with corner watermarks near the top/bottom edge (`ViralHog`, `DUMPERT`, `ring`, `TMAX`, `LA`, `Reddit`), scale by `~1.15x` (`1920x1080 -> 115%`, `1080x1920 -> 65%`, `720x1280 -> 95%`, `1280x720 -> 168%`) to push edge watermarks cleanly outside the `1080p` frame.
3. **Deep In-Frame Logo Shield (`Track V2`):**
   - Call `set-item-in-out` with `V1`'s exact `inPointSeconds` and `outPointSeconds`.
   - Call `add-to-timeline` on `Track V2` (`trackIndex: 1`, which snapshots existing `A1` audio `nodeId`s and cleans up auto-linked `A2` audio so `A1` is untouched and `A2` stays 100% empty).
   - Match `V1`'s `Scale`, then apply `Gaussian Blur` (`AE.Impact_Blur_FX`, `Amount: 20`) + `Crop` (`AE.ADBE AECrop`, `Edge Feather: 15`) around the logo ROI.
