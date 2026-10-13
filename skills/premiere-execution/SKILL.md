---
name: premiere-execution
description: Adobe Premiere Pro MCP execution engine. Translates edit and patch plans into verified ExtendScript/UXP mutations. Manages checkpoints, timebases, and tracks.
---

# Premiere Execution (`premiere-execution`)

Translates abstract editorial plans (`edit-plan.json` and `patch-plan.json`) into concrete Adobe Premiere Pro MCP tool calls.

## 🎯 Directives
- **Conforming Timebase:**
  - Sequences must strictly conform to Full HD 1080p (1920x1080) at 23.976 fps constant frame rate.
- **Dedicated Project Bins:**
  - Import pre-trimmed source clips into `_Clips` bin and SFX assets into `_SFX` bin.
- **Track Layout Mapping:**
  - `V1`: Primary Video Clips
  - `V2`: Adjustment Layers / Visual Shields
  - `A1`: Original Ambient Sound (Gain boosted if authentic transient)
  - `A2`: **RESERVED 100% EMPTY FOR VOICEOVER**
  - `A3`: Transition Whoosh SFX
  - `A4`: Action Climax Impacts
  - `A5`: Ducked Background Music
- **Atomic Operations & Checkpoints:**
  - Always create a sequence checkpoint (`create_sequence_checkpoint`) before major mutations.
  - Apply mutations using batch tools (`add_to_timeline_batch`, `set_clip_properties_batch`).
  - Read back timeline state via `get_sequence_structure` and `get_track_info` for closed-loop evaluation.
