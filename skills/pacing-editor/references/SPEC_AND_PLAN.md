# SPECIFICATION & IMPLEMENTATION PLAN: W-CURVE & SEQUENTIAL PACING ENGINE
**Skill:** `pacing-editor` | **Version:** 2.0.0-rc1 | **Target:** Adobe Premiere Pro MCP & Headless NVENC

---

## 1. Executive Summary & Objective

The **Pacing Editor** transforms raw video cuts into polished, high-retention video timelines on Adobe Premiere Pro. In collaboration with the editor through `/grill-me`, this specification establishes **two distinct operating modes**:

1. **Mode 1: `sequential` (Direct Order Retention Pacing)**
   - Preserves 100% of the input clip sequence (chronological / folder order).
   - Applies **Hard Fast-Cut** trimming via Premiere Pro In/Out points, eliminating sluggish lead-ins and trailing dead air to lock viewer attention onto dramatic peaks.
   - Routes audio into a professional 5-track studio layout: Original Audio (A1), Voiceover Reserve (A2), Transition SFX (A3), Climax SFX (A4), and Ducked Music (A5).

2. **Mode 2: `w-curve` (Dynamic Narrative Retention Reordering)**
   - Evaluates a multi-criteria **Interest Score** ($S$) for every clip.
   - Enforces **Incident Bundle Preservation**: shots belonging to the same incident or continuation fragments (`is_continuation: true`, `needs_continuation_stitch`) are grouped into atomic bundles and never split across disparate parts of the video.
   - Organizes clips into a psychological **W-Curve**:
     - **Hook (Peak 1 - 0s to 3s)**: High-energy opening (Rank 2 incident or signature incident opener) to stop scrolling.
     - **Valley 1 (Dip 1)**: Moderate pace incident to establish context and build curiosity.
     - **Mid-Peak (Peak 2)**: Strong tension incident (Rank 3) to prevent viewer drop-off.
     - **Valley 2 (Dip 2)**: Suspenseful build-up before the climax.
     - **Grand Finale (Peak 3)**: Maximum impact incident (Rank 1 - absolute highest score) delivering the emotional payoff and driving loops/shares.
   - Supports **`--target-duration`** filtering (e.g., 30s, 60s) to select the optimal subset of incident bundles.

---

## 2. Technical Architecture & Data Models

### 2.1 Multi-Criteria Scoring Formula (Interest Score $S$)

Each clip $c$ and incident bundle $I = \{c_1, c_2, \dots, c_k\}$ is evaluated using normalized metrics:

$$S(c) = w_m \cdot M(c) + w_n \cdot N(c) + w_a \cdot A(c)$$

Where:
- $w_m = 0.40$ (Motion Energy Weight)
- $w_n = 0.35$ (Narrative Arc Completeness Weight)
- $w_a = 0.25$ (Audio Transient / Impact Weight)

#### Scoring Components:
1. **Motion Score ($M(c) \in [0, 100]$)**:
   $$M(c) = \min\left(100, \frac{\text{peak\_motion\_diff}}{45.0} \times 100\right)$$
2. **Narrative Arc Score ($N(c) \in [0, 100]$)**:
   - Complete Arc (`Setup -> Build-up -> Climax -> Reaction`): **100 pts**
   - Shocking In-Flight Cutoff (`truncated_tail_mid_climax`): **85 pts** (high raw curiosity/hook value)
   - Mid-Action Entry (`truncated_head_mid_action`): **70 pts**
   - Incomplete Fragment (`mid_action_fragment`): **50 pts**
3. **Audio Transient Score ($A(c) \in [0, 100]$)**:
   - Measured RMS energy and spectral transient peak at the climax timestamp. Default: 75 pts if audio peak aligns with visual peak within $\pm 0.3\text{s}$.

For multi-shot incident bundles:
$$S(I) = \max_{c \in I} S(c) + 0.1 \times \sum_{c \in I \setminus \{c_{\max}\}} S(c)$$

---

### 2.2 W-Curve Slot Mapping Algorithm

Given a sorted list of incidents $I_{(1)}, I_{(2)}, \dots, I_{(K)}$ where $S(I_{(1)}) \ge S(I_{(2)}) \ge \dots$:

1. **Target Duration Fitting**:
   - If `--target-duration T` is set, select the highest-scoring set of incidents whose cumulative fast-cut duration $\sum \text{dur}(I) \le T + 2.0\text{s}$.
2. **5-Point W-Curve Assignment**:
   - **Slot 1 (Hook / Peak 1)**: $I_{(2)}$ (Second highest score, or candidate marked with `teaser_hook`).
   - **Slot 2 (Valley 1 / Context)**: $I_{(4)}, \dots$ (Lower-ranking context incidents).
   - **Slot 3 (Mid-Peak / Peak 2)**: $I_{(3)}$ (Third highest score).
   - **Slot 4 (Valley 2 / Suspense)**: $I_{(5)}, \dots$ (Build-up incidents).
   - **Slot 5 (Grand Finale / Peak 3)**: $I_{(1)}$ (The ultimate #1 highest scoring climax).

---

### 2.3 Hard Fast-Cut Trimming Specifications

Rather than stretching clips with passive lead-in/recovery, the engine applies tight In/Out boundaries:
- **`source_in`**:
  $$\text{source\_in} = \max\left(0.0, \text{climax\_time} - \Delta_{\text{pre}}\right)$$
  Where $\Delta_{\text{pre}} = 0.8\text{s} \sim 1.2\text{s}$ (based on clip lead-in phase).
- **`source_out`**:
  $$\text{source\_out} = \min\left(\text{duration}, \text{climax\_time} + \Delta_{\text{post}}\right)$$
  Where $\Delta_{\text{post}} = 0.8\text{s} \sim 1.2\text{s}$ (or end of reaction).
- **Target Clip Duration**: Between $2.0\text{s}$ and $3.5\text{s}$ per shot, ensuring brisk pacing for 9:16 mobile feeds.

---

### 2.4 Studio 5-Track Audio Layout

```
Premiere Pro Sequence Track Mapping:
===================================================================================================
[V1] Video Track       : Fast-cut video clips with action peaks aligned
---------------------------------------------------------------------------------------------------
[A1] Audio Track 1     : Original Video Clip Audio (Ambient sound / dialogue / physical impact)
[A2] Audio Track 2     : [BLANK] RESERVED EXCLUSIVELY FOR VOICEOVER (VO / Narration)
[A3] Audio Track 3     : Transition SFX (Whoosh / Swoosh synced to video cuts)
[A4] Audio Track 4     : Climax SFX (Punch / Boom / Thud synced to Action Peak Markers)
[A5] Audio Track 5     : Background Music (BGM - Automatic Ducking -12dB during Climax events)
===================================================================================================
```

---

## 3. Implementation Plan & Milestones

### Milestone 1: Pacing Engine Core Refactor (`pacing_engine.py`)
- Implement `calculate_interest_score(clip_or_incident)` computing $S(c)$ and $S(I)$.
- Implement `bundle_incidents(scenes)` enforcing incident continuity.
- Implement `map_w_curve(bundles, target_duration=None)` distributing into W-curve topology.
- Update `calculate_hard_fast_cut(scene)` calculating exact `in_point` and `out_point`.

### Milestone 2: Audio Routing & Studio 5-Track Overhaul (`timeline_assembler.py`)
- Configure track indices:
  - `track_index: 0` (V1)
  - `audio_track_index: 0` (A1 - Native Audio)
  - Audio Track 1 (A2) remains completely untouched / empty for Voiceover.
  - Audio Track 2 (A3) receives transition SFX (`woosh-1.wav`).
  - Audio Track 3 (A4) receives climax hits (`vine-boom`, punch SFX).
  - Audio Track 4 (A5) receives background music.

### Milestone 3: CLI Interface & Auto-Premiere Bridge (`pacing_cli.py`)
- Add CLI arguments:
  - `--mode {sequential,w-curve}` (default: `sequential`).
  - `--target-duration, -t <seconds>` (e.g. `30`, `45`, `60`).
  - `--cut-mode {fast-cut,ramp}` (default: `fast-cut`).
  - `--no-premiere` (flag to suppress active Premiere MCP bridge).
- Add live check for Premiere Pro connection via MCP `ping` / `verify_premiere_connection`. If connected, execute timeline construction directly on Premiere Pro.

### Milestone 4: Packaging, Testing & Git Sync
- Validate on test suite (`clean_cut_retest`).
- Package skill via `package_skill.py skills/pacing-editor .`.
- Git commit and push to `https://github.com/mmmnhat/agent-skills.git`.
