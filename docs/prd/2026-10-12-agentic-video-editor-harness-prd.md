# Product Requirements Document (PRD): Autonomous Agentic Video Editorial Suite with Closed-Loop Evaluation Harness

**Status:** Ready for Agent  
**Date:** 2026-10-12  
**Target Platform:** Adobe Premiere Pro MCP (`v1.18.1`) + Antigravity / Gemini CLI / Claude Code / Cursor AI  

---

## Problem Statement

When video creators and editors use AI to assist in video assembly, existing tools operate as passive script generators or open-loop planners. The AI creates a timeline cut list or sends commands to an editing tool, but it never observes the actual timeline state, verifies frame synchronization, or detects visual and acoustic defects. 

As a result:
- **Audio and visual drift:** Impact sound effects frequently miss physical collision frames by 3–10 frames when clips are trimmed or reordered.
- **Accidental black gaps:** Subtle rounding errors in timebase calculations introduce 1–2 black frames between clips on the primary video track.
- **Loss of narrative payoffs:** Blind fast-cut algorithms truncate reaction windows (the fall, laughter, shock) immediately after collision, ruining comedic or dramatic payoffs.
- **Runaway corruption:** When an AI attempts to edit a timeline and encounters an unexpected track state, it makes repeated blind adjustments that mangle the project without any rollback mechanism.
- **Performance bottlenecks:** Importing massive raw footage files directly into Premiere Pro causes severe UI lag, memory bloat, and timeline freezing.

Editors need an autonomous, closed-loop Video Editing Director that can ingest footage at high speed, plan pacing intelligently, execute mutations deterministically in Premiere Pro, read back the resulting timeline state, and enforce mathematical quality invariants before human delivery.

---

## Solution

The Autonomous Agentic Video Editorial Suite provides a closed-loop system layered directly on top of Adobe Premiere Pro MCP (384 tools). 

Key solution elements from the user's perspective:
1. **Dual-Layer Execution:** Heavy frame scanning, candidate cut detection, and blurred margin stripping happen at hardware speeds (>3,000 fps via NVENC outside RAM). Premiere Pro only receives clean, frame-exact clips, keeping the timeline ultra-responsive.
2. **Single Lead Agent Workflow:** A unified Editorial Director coordinates sequentially across 7 specialized Skills (`source-understanding`, `comedy-timing`, `context-aware-sfx`, `adaptive-pacing`, `visual-editing`, `premiere-execution`, `video-quality-control`), maintaining shared state in standardized JSON files without token-heavy subagent handoffs.
3. **Bi-directional Time Mapping Model:** Every clip maintains a mathematical binding between its source timecode and its sequence timeline timecode. If a clip is moved from the end of the video to become the opening Hook, all associated SFX and punch-in keyframes automatically track to the new action peak frame.
4. **Adaptive Audio Decision Matrix:** The system preserves authentic sound: if the camera captured real glass shattering or metal crashing, it boosts the original audio (+3dB to +6dB) and forbids artificial sound effects. It only adds contextual SFX on Track A4 for silent or muffled CCTV footage, and leaves Track A2 100% blank for voiceover recording.
5. **Closed-Loop Evaluation Harness:** After timeline assembly, an automated harness audits 5 core technical invariants (Zero Gap on V1, Frame-Exact SFX Sync $\le 1$ frame, Audio Headroom $\le -1.0$ dBFS, Empty Voiceover Track A2, and Payoff Window Preservation $\ge 0.8$s). If any invariant fails, it generates a surgical micro-patch plan to fix the errors in a single batch.
6. **Circuit Breaker Protection:** If self-healing cannot resolve an invariant after 3 attempts, the system automatically rolls back the sequence to a pre-fix checkpoint, plants red review markers on the problematic edit points, and presents a visual frame capture in chat for human direction.
7. **Broadcast Standard Timeline:** All output sequences conform to Full HD 1080p (1920x1080) at 23.976 fps constant frame rate, eliminating variable frame rate audio desynchronization.

---

## User Stories

1. As an editor, I want raw video pre-scanned in RAM at over 3,000 fps, so that I can process 30-minute videos in under 2 minutes without bogging down my workstation.
2. As an editor, I want candidate cuts rendered into 24-cut visual contact sheets with red separator lines, so that the AI can visually verify scene boundaries with human-level accuracy.
3. As an editor, I want false cuts caused by fast camera whip pans, water splashes, and light flashes automatically merged, so that complete narrative arcs remain intact within a single clip.
4. As an editor, I want disclaimers, channel logos, and countdown bumpers automatically dropped from the start of videos, so that the first clip always opens immediately on real action.
5. As a mobile video creator, I want blurred pillarbox margins (9:16 content inside 16:9) automatically detected and cropped, so that my clips fill the full canvas natively.
6. As a comedy editor, I want the system to identify Setup, Anticipation, Climax, and Payoff phases, so that comedic moments are never cut prematurely before the audience can react.
7. As a short-form video creator, I want clips scored and arranged according to a 5-beat W-Curve (Hook $\to$ Context $\to$ Mid-Climax $\to$ Suspense $\to$ Grand Finale), so that viewer retention is maximized within a 30-second window.
8. As an editor, I want clips from the same event bundled together atomically, so that chronological narrative continuations are never scrambled across disparate parts of the timeline.
9. As a documentary editor, I want a sequential fast-cut mode that preserves original chronological order while eliminating dead lead-in air, so that continuous real-life events feel tight and punchy.
10. As a sound designer, I want audio transients analyzed at the collision point, so that genuine physical sounds (breaking glass, metal impact) are boosted rather than covered by fake SFX.
11. As an editor working with silent CCTV footage, I want appropriate material-specific impact sounds (metal, wood, cardboard, concrete) retrieved from my sound library and synced to the impact frame, so that silent falls feel tactile and impactful.
12. As a voiceover narrator, I want Track A2 kept completely empty of all audio, so that I can record voiceover tracks directly without cleaning up misallocated sound effects.
13. As an editor, I want impact sound effects synchronized to within 1 frame of physical collision, so that there is zero perceptible lag between picture and sound.
14. As an editor, I want transition whoosh sounds automatically placed at cuts between major incident bundles on Track A3, so that scene transitions feel dynamic and fluid.
15. As a sound engineer, I want background music automatically ducked during action peaks and dialogue, so that high-energy collisions and speech remain perfectly audible.
16. As an editor, I want subtle punch-in zooms (1.10x–1.20x scale) keyframed around dramatic action peaks, so that the viewer's eye is guided straight to the point of impact.
17. As an editor, I want watermarks and logos tracked and shielded via OpenCV delogo filters or Premiere Track V2 Adjustment Layers, so that unwanted branding is cleanly obscured.
18. As an operator, I want edit operations translated into verified Premiere Pro MCP tool calls, so that timelines are created and populated programmatically.
19. As an editor, I want a sequence checkpoint created before any timeline mutation, so that any failure can be reverted cleanly without project corruption.
20. As a quality reviewer, I want timeline gaps on Track V1 automatically flagged and ripple-deleted, so that rendered videos never contain blank black frames.
21. As a sound engineer, I want master audio loudness audited to enforce a $-1.0$ dBFS True Peak headroom, so that the audio track never clips or distorts on mobile speakers.
22. As an editor, I want self-healing patch plans applied in a single batch, so that minor sync and gap errors are repaired in seconds without rebuilding the entire sequence.
23. As an editor, I want a 3-iteration circuit breaker on automated repairs, so that the system never enters an infinite loop of timeline mutations when facing ambiguous geometry.
24. As an editor, I want visual review frames captured and displayed in chat when a repair requires human decision, so that I can see exactly what went wrong without scrubbing Premiere manually.
25. As a content publisher, I want output sequences standardized to Full HD 1080p at 23.976 fps, so that my final exports conform to cinematic broadcast standards with zero audio drift.
26. As a team lead, I want all agent directives synchronized across AGENTS.md, GEMINI.md, CLAUDE.md, and .cursorrules, so that any team member using any AI editor gets identical autonomous behavior.

---

## Implementation Decisions

### Modular Architecture (Deep Modules)
The system decomposes into four deep, isolated modules with minimal, unchanging interfaces:
1. **`TimeMapper`**: A pure mathematical engine that converts bidirectional coordinates between source media timestamps and master sequence frames. It encapsulates frame rate conformation, ripple shift compensation, and fast-cut offsets.
2. **`AudioDecisionEngine`**: A pure functional decision matrix that accepts audio transient energy, speech confidence, and material metadata, returning explicit track routing instructions (boost A1 gain vs. insert A4 SFX vs. duck A5 music).
3. **`HarnessEvaluator`**: An assertion runner that reads sequence state dictionaries from `premiere-pro-mcp` and validates the 5 Timeline Invariants, producing structured error records with exact frame offsets.
4. **`PatchGenerator`**: A deterministic reducer that takes failed invariant records and emits an atomic list of corrective MCP operations (`ripple_delete`, `move_clip`, `adjust_audio_levels`) without touching healthy clips.

### Single Lead Agent Orchestration Model
- The system runs as a single Lead Editorial Director sequentially loading 7 specialized skills (`source-understanding` $\to$ `comedy-timing` $\to$ `context-aware-sfx` $\to$ `adaptive-pacing` $\to$ `visual-editing` $\to$ `premiere-execution` $\to$ `video-quality-control`).
- Inter-stage communication is mediated exclusively through typed JSON state files in the `state/` directory (`source-manifest.json`, `edit-plan.json`, `patch-plan.json`, `qa-report.json`).
- Subagents are NOT spawned for individual skills; this avoids context fragmentation, reduces token consumption by over 60%, and guarantees complete conversational awareness.

### Dual-Phase Ingest Strategy
- **Phase 1 (Outside Premiere):** The Python Core Engine scans raw footage using PySceneDetect and OpenCV, renders 24-cut contact sheets, receives AI Vision review decisions, and uses FFmpeg NVENC hardware acceleration to export cropped, unblurred, frame-exact scene clips to a dedicated directory.
- **Phase 2 (Inside Premiere):** Premiere Pro only imports the trimmed scene clips and required SFX assets into a dedicated project bin. Timeline assembly is fast and lightweight, preventing Premiere UI lag.

### Audio Layout Standard
- `V1`: Primary video clips.
- `V2`: Adjustment layers for visual shielding, blur, and color treatment.
- `A1`: Original clip ambient audio (normalized, boosted when real transients exist).
- `A2`: Reserved strictly blank for Voiceover narration.
- `A3`: Transition sound effects (whoosh, swipe, whip).
- `A4`: Climax impact sound effects (thud, punch, crash, metallic hits).
- `A5`: Background music bed (automatically ducked by $-12$ dBFS during action peaks).

### Invariant & Circuit Breaker Logic
```json
{
  "invariants": {
    "INV-01": "len(get_timeline_gaps('V1')) == 0",
    "INV-02": "abs(sfx_frame - impact_frame) <= 1",
    "INV-03": "master_true_peak_dbfs <= -1.0",
    "INV-04": "len(get_track_clips('A2')) == 0",
    "INV-05": "clip_out_frame >= climax_frame + int(0.8 * fps)"
  },
  "circuit_breaker": {
    "max_repair_cycles": 3,
    "on_breach": "rollback_to_checkpoint_and_flag_markers"
  }
}
```

---

## Testing Decisions

### What Makes a Good Test
- Tests must verify external contract behavior and mathematical invariants rather than internal implementation details.
- Tests must be runnable headlessly without requiring an active Adobe Premiere Pro GUI instance wherever possible, using mock timeline state dictionaries.
- Every assertion corresponds directly to an invariant defined in the specification.

### Module Test Scope
1. **`test_time_mapper.py`**:
   - Tests coordinate translation under frame rate shifts (conforming 29.33 fps source into 23.976 fps master sequence).
   - Tests action peak tracking when a clip is trimmed on the left or relocated on the timeline.
2. **`test_audio_decision_engine.py`**:
   - Tests that real impact transients above threshold suppress artificial SFX generation and boost Track A1 gain.
   - Tests that silent or low-confidence audio triggers Track A4 SFX selection with appropriate gain.
   - Tests that detected speech preserves Track A1 and attenuates Track A4 impacts.
3. **`test_harness_evaluator.py`**:
   - Tests gap detection against synthetic sequence structures with 1-frame, 5-frame, and zero gaps.
   - Tests SFX alignment checks with on-time, late (+4 frames), and early (-3 frames) sound placements.
   - Tests headroom verification with clipping (+0.5 dBFS) and compliant (-1.5 dBFS) audio signals.
4. **`test_patch_generator.py`**:
   - Verifies that a detected gap produces an exact `ripple_delete` operation.
   - Verifies that an SFX offset produces an exact `move_clip` operation with signed delta frame compensation.
   - Verifies that multiple errors in one sequence produce a consolidated, non-conflicting patch plan.

### Prior Art
- Existing test patterns in `tests/test_candidate_analyzer.py` and `tests/test_unblur_detector.py` demonstrating headlessly mocked video frame synthesis and PySceneDetect validation.

---

## Out of Scope

- Cloud-based remote rendering farms or multi-machine rendering pipelines (all rendering targets the local machine's GPU).
- Generative AI video synthesis (e.g., generating new video pixels via Sora or Runway); the system edits, trims, and designs sound for authentic source footage.
- Automated subtitle generation and animated motion graphics captions (reserved for a subsequent sprint).
- Multicamera angle switching and live switcher simulation (handled by separate multicam skills).

---

## Further Notes

- The system directly utilizes `premiere-pro-mcp` v1.18.1 located at `C:\Users\AMZ-HUY\AppData\Local\premiere-mcp\premiere-pro-mcp`, communicating via ExtendScript and UXP bridges.
- Verified on Windows 11 with NVIDIA NVENC hardware acceleration and Adobe Premiere Pro 2026.
