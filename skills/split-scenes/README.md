# 🎬 Split Scenes Skill (`split-scenes`)

> **Precision AI Scene Detection, Continuous Event Aggregation, Audio Intelligence & Multi-Video Deduplication for Antigravity & Premiere Pro.**

An agentic skill for frame-accurate video scene extraction, designed to process long compilation videos (e.g., fails, sports highlights, security feeds) with ultra-high throughput (>3,200 fps), zero boundary tail bleed (`-vframes`), background continuity aggregation (anti-over-split), comprehensive 6-class audio intelligence, and Premiere Pro MCP integration.

---

## 🚀 Key Features

1. **Ultra-Fast Frame-by-Frame Detection (`frame_by_frame_detector.py`)**
   - Scans 100% of proxy video frames in memory via OpenCV & NumPy at **>3,280 fps** (~30s for a 68-minute video).
   - **Active Center Crop (50% center window)** eliminates vertical 9:16 black pillar dilution.
   - Dual-metric trigger combining Luma disparity ($\Delta \text{Luma} \ge 18$) and color histogram correlation ($\text{HSV Corr} < 0.65$).
   - On-the-fly ORB feature caching for visual evidence.

2. **Dense Vision Sheets (`vision_sheet_engine.py`)**
   - Microscopic visual verification with 8x8 contact sheets.
   - Supports 3 sampling densities:
     - `1:1 (Full FPS)`: Every single frame (24 fps) for inspecting micro-cuts.
     - `1/2 FPS`: Fast-action analysis (capo flips, crashes).
     - `1/5 FPS`: Narrative arc & teaser montage inspection.

3. **Anti-Over-Split Aggregator (`ssim_continuity_aggregator.py`)**
   - Resolves the issue where 1 incident is shattered into 3–5 sub-clips.
   - Merges contiguous shots sharing the same environment, color palette (HSV correlation $\ge 0.68$), or structural geometry ($\text{SSIM} \ge 0.20$).
   - **Anti-Impact Splitting:** Suppresses false cuts caused by flash/smoke/airbag explosion if pre- and post-impact scenes belong to the same narrative event.

4. **Intra & Cross-Video Deduplication (`duplicate_source_detector.py`)**
   - Perceptual hash (pHash) visual fingerprinting.
   - Identifies internal duplicate clips within the same compilation and cross-compilation duplicates across $N$ videos.

5. **Audio Context Intelligence & 6-Class Taxonomy (`audio_context_engine.py`)**
   - **Audio-Assisted Zero-Cut Snapping:** Scans audio energy in a $\pm 0.25\text{s}$ window around visual cuts, snapping to local RMS energy dips and waveform zero-crossings ($y[i] \cdot y[i+1] \le 0$) to eliminate pops/clicks and protect speech.
   - **6 Standard Audio Types:**
     - 🗣️ `voice_nguoi_that`: Real human speech, emotional shouts, laughter ($\sigma(F_0) > 40\text{ Hz}$).
     - 🤖 `voice_ai`: Synthetic TTS narration (flat cadence, $\sigma(F_0) < 28\text{ Hz}$).
     - 🔇 `khong_am_thanh`: Mute / silence ($\text{Peak} \le -42\text{ dB}$, $\text{RMS} < 0.005$).
     - 💥 `co_am_thanh_sfx`: Foley, engine roar, impact crash only (no BGM, no speech).
     - 🎵 `chi_co_nhac`: BGM melody only (harmonic ratio $\ge 0.40$, regular tempo).
     - 🎛️ `hon_hop`: Multi-layer audio (BGM + voiceover, BGM + massive impact).
   - **Peak Impact Detection:** Identifies exact millisecond of peak impact transient (`peak_impact_time_sec`).
   - **Speech Transcription:** Automatic speech-to-text with `faster-whisper`.

6. **Frame-Accurate Splitting (`batch_splitter.py`)**
   - Uses multi-threaded FFmpeg with `-vframes` rather than `-to` timestamps to guarantee that the final frame never bleeds into the next scene.

7. **Interactive Preview Widget (`generate_audio_widget.py`)**
   - Standalone dark-mode HTML widget with 6-class audio filtering, speech text bubbles, impact time badges, and base64 keyframe previews.

8. **Self-Bootstrapping Auto-Installer (`env_bootstrap.py`)**
   - Zero manual setup: Scripts automatically check for all required Python packages (`opencv-python`, `scikit-image`, `numpy`, `scipy`, `librosa`, `faster-whisper`, `yt-dlp`) and CLI tools (`ffmpeg`, `ffprobe`).
   - If any dependency is missing, it is automatically installed in the background via `pip` or Homebrew with zero user friction.

---

## 📁 Repository Structure

```
.
├── SKILL.md                          # Antigravity skill specification & instructions
├── README.md                         # Project documentation
├── requirements.txt                  # Python dependencies
├── .gitignore                        # Git exclusion rules
└── scripts/
    ├── env_bootstrap.py              # Self-bootstrapping auto-installer for dependencies
    ├── frame_by_frame_detector.py    # Fast sequential frame scanner + ORB intro matching
    ├── ssim_continuity_aggregator.py # Anti-over-split event aggregator (SSIM + HSV)
    ├── intro_duplicate_resolver.py   # Intro teaser matching and clip promotion
    ├── duplicate_source_detector.py  # Intra & Cross-video deduplication engine
    ├── audio_context_engine.py       # Audio intelligence, zero-cut snapping & 6-class classifier
    ├── batch_splitter.py             # Multi-threaded -vframes FFmpeg splitter
    ├── vision_sheet_engine.py        # Dense 8x8 contact sheet generator
    ├── generate_audio_widget.py      # Interactive HTML preview widget builder
    └── test_dense_sheets.py          # Vision sheet unit tests
```

---

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/mmmnhat/split-scenes-skill.git
cd split-scenes-skill

# Install dependencies
pip install -r requirements.txt

# Ensure FFmpeg is installed
ffmpeg -version
```

---

## ⚙️ Quick Start

### 1. Detect Scene Boundaries
```bash
python scripts/frame_by_frame_detector.py \
  --video proxy_480p.mp4 \
  --output frame_detector_scenes.json \
  --frames_cache ./frames_cache
```

### 2. Aggregate Events (Anti-Over-Split)
```bash
python scripts/ssim_continuity_aggregator.py \
  --scenes frame_detector_scenes.json \
  --output scene_db.json \
  --prefix fail_87 \
  --out_dir /path/to/clips
```

### 3. Extract Clips with Frame-Accurate Precision
```bash
python scripts/batch_splitter.py \
  --db scene_db.json \
  --video original_1080p.mp4 \
  --workers 6
```

### 4. Enrich Audio Intelligence & 6-Class Classification
```bash
python scripts/audio_context_engine.py \
  --db scene_db.json \
  --model tiny
```

### 5. Generate Preview Widget
```bash
python scripts/generate_audio_widget.py
```

---

## 📄 License

Proprietary / Internal project by **mmmnhat**. All rights reserved.
