# 🎬 VisionCut — Autonomous AI Video Editorial Suite

An end-to-end autonomous video editorial workflow and skill suite for Antigravity AI, PySceneDetect, OpenCV, FFmpeg NVENC, and Adobe Premiere Pro MCP.

---

## ⚡ Hướng Dẫn Cài Đặt Cho Máy Mới (1-Step Setup)

Để AI Agent trên bất kỳ máy nào (Windows, macOS, Linux) thực thi **chính xác 100% như trên máy lead**:

### Cách 1: Đăng ký Toàn Cục (Khuyên dùng — Dùng được cho mọi project trên máy)
```bash
git clone https://github.com/mmmnhat/agent-skills.git
cd agent-skills
python setup_env.py
```
* **Tự động dò phần cứng:** Tự chọn encoder tối ưu nhất (NVIDIA NVENC, Apple Silicon VideoToolbox, Intel QSV, hoặc CPU libx264).
* **Cấu hình kho Asset:** Hỏi đường dẫn thư mục SFX & BGM của riêng bạn.
* **Tự động đăng ký Skills toàn cục:** Tự ghi vào `~/.gemini/config/skills.json` để Antigravity nhận diện skills tại bất kỳ workspace nào mở trên máy.
* **Đồng bộ đa nền tảng:** Tự động đồng bộ chỉ thị vào `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` (Claude Code) và `.cursorrules` (Cursor AI).
* **Sinh cấu hình an toàn:** Lưu vào `config.local.json` (được `.gitignore` bảo vệ, không bao giờ lo conflict khi `git pull`).

### Cách 2: Nhúng Trực Tiếp Vào Dự Án Dựng Video (Per-Project)
Nếu bạn có sẵn một thư mục video (ví dụ: `D:\MyVideoProject`):
```bash
cd D:\MyVideoProject
git clone https://github.com/mmmnhat/agent-skills.git .agents
python .agents/setup_env.py
```
Antigravity sẽ tự động nhận diện thư mục `.agents` làm customization root, kích hoạt ngay lập tức toàn bộ skills và chỉ thị Autonomous Video Editor cho dự án đó.

---

## 🤖 Trải Nghiệm Hội Thoại Với AI Agent (Agentic Workflow)

Repo này được trang bị sẵn tệp chỉ thị **[`AGENTS.md`](AGENTS.md)** & **[`GEMINI.md`](GEMINI.md)**. Bất kỳ AI Agent nào (Antigravity, Cursor, Claude Code) khi mở thư mục này sẽ **tự động đóng vai Autonomous Lead Video Editor**:

| Bạn gõ vào khung chat AI | AI Agent tự động thực hiện |
| :--- | :--- |
| *"Tách scene cho tôi video này: D:\video.mp4"* | Tự quét candidate $\to$ **Tự dùng mắt AI (`view_file`) soi Contact Sheets** $\to$ Tự loại bỏ intro/gộp cảnh $\to$ Cắt GPU $\to$ Hậu kiểm Filmstrip. |
| *"Dựng sequence các clip vừa tách theo W-Curve 30s"* | Chấm điểm Score $\to$ Đóng gói cụm sự kiện $\to$ **Dựng thẳng lên timeline Premiere Pro** (5-track layout: V1, A1, A2 trống VO, A3/A4 SFX, A5 BGM). |
| *"Soi và thẩm định folder clip này: D:\clips"* | Quét pHash trùng lặp $\to$ Sinh Filmstrip 4 ô $\to$ Phân tích cấu trúc Setup-Climax-Reaction. |
| *"Che logo ở góc trên bên phải video này"* | OpenCV tracking vùng chọn $\to$ Delogo hoặc chèn Adjustment Layer trên Premiere Pro V2. |

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
  * `V1`: Video clips with W-Curve retention reordering or chronological fast-cut.
  * `A1`: Original video clip audio.
  * `A2`: [Blank] Reserved exclusively for Voiceover.
  * `A3`: Transition SFX (Whoosh synced to cuts).
  * `A4`: Climax SFX (Punch / Impact synced to action peak markers).
  * `A5`: Ducked Background Music (-12dB during climax hits).
* Exports automated Premiere Pro MCP execution plans.

### 6. `video-transform`
* Geometric distortion and pitch-preserving audio retiming engine.
* Applies deep zoom crop, micro-rotation, horizontal flip, and pitch-preserved speed adjustments via hardware acceleration.

### 7. `split-scenes`
* Frame-accurate scene detector with AI vision sheets and narrative arc labeling.
* Deduplication and seamless multi-shot incident consolidation.

### 8. `cat-scene-agent`
* Autonomous scene splitter agent with human-in-the-loop web preview and automated export.

---

## 📦 Packaged Skills (`packages/`)
All skills are packaged as valid `.skill` archives ready for distribution and installation in any Antigravity workspace:
* `packages/clean-cut.skill`
* `packages/pacing-editor.skill`
* `packages/asset-indexer.skill`
* `packages/clip-inspector.skill`
* `packages/content-shield.skill`
* `packages/video-transform.skill`
* `packages/split-scenes.skill`
* `packages/cat-scene-agent.skill`
