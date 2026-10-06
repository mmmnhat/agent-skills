# Antigravity Agentic Video Editorial Suite

An end-to-end autonomous video editorial workflow and skill suite for Antigravity AI, PySceneDetect, OpenCV, FFmpeg NVENC, and Adobe Premiere Pro MCP.

---

## 🚀 Core Editorial Skills

### 1. `clean-cut`
* **Zero Frame Bleed Scene Splitter & Unblur Engine**
* Scans video at high speed (>3,200 fps in RAM).
* **Quarter-Frame Centering Seek** (`-ss (s_fn - 0.25)/fps`) and **Sub-Millisecond Tail Cutoff** (`-t (N - 0.5)/fps`) ensure absolute zero frame bleed across cuts.
* **Canonical Aspect Ratio Snapping**: Strips blurred margins cleanly into native vertical (9:16), square (1:1), and standard aspect ratios.
* Groups multi-shot reframe/zoom incidents transparently into `scenes_context.json`.

### 2. `clip-inspector`
* Standardizes pre-existing clip directories into unified manifests.
* Generates 4-frame visual filmstrips (`thumbnails/*_strip.jpg`).
* Computes temporal motion landmarks (`lead_in`, `climax`, `recovery`) and pacing recommendations.

### 3. `asset-indexer`
* Indexes multimedia assets (SFX, Meme, Music, Overlay, Footage, Vlipsy).
* **"Hỏi và Nhớ" (Ask & Remember) Memory Engine**: Learns editor preferences per intent (whoosh, impact, meme, punch), boosting chosen assets in future searches.

### 4. `content-shield`
* Visual obscuration & sensitive content shielding via OpenCV Tracking and Premiere Pro V2 Blur.
* **Dual Engine**:
  * Headless FFmpeg NVENC: `delogo` (near-invisible spatial border interpolation), `gaussian_blur`, or `mosaic`.
  * Premiere Pro MCP: Generates track `V2` Adjustment Layers with `crop_clip`, `Gaussian Blur`, and animated motion keyframes.

### 5. `pacing-editor`
* High-retention video sequencing, GPU Optical Flow speed ramping, and automated sound design.
* **Timeline Architecture**:
  * `V1`: Video clips with 3-phase retention curve: Lead-In (1.0x) -> Climax (0.5x Optical Flow) -> Recovery (1.5x).
  * `A1`: Original ambient/voiceover audio.
  * `A2`: Automated SFX placement (Whooshes at cut points, Impact Hits at climax markers).
  * `A3`: Ducked Background Music (BGM).
* Exports automated Premiere Pro MCP execution plans (1,400+ timeline actions).

---

## 📦 Packaged Skills
All skills are packaged as valid `.skill` archives ready for distribution and installation in any Antigravity workspace:
* `clean-cut.skill`
* `clip-inspector.skill`
* `asset-indexer.skill`
* `content-shield.skill`
* `pacing-editor.skill`
