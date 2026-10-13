---
name: context-aware-sfx
description: Acoustic intelligence and sound design engine. Enforces authentic camera audio preservation, material-matched SFX on A4, transition SFX on A3, and strict Voiceover track A2 emptiness.
---

# Context-Aware SFX (`context-aware-sfx`)

Designs soundscapes by evaluating physical materials, acoustic environments, and genuine audio transients.

## 🎯 Directives
- **Authentic Sound First:**
  - If the source camera captured genuine physical collision sounds (breaking glass, metal slam, wood crack), BOOST Track `A1` gain by +3.0 dB to +6.0 dB.
  - DO NOT add artificial impact SFX on top of authentic camera audio.
- **Contextual Fallback SFX:**
  - For silent or muffled footage (CCTV, dashcam without audio), retrieve material-matched impacts (metal, wood, concrete, glass, cardboard) from library.
  - Place impact SFX on Track `A4` synced to `mapped_climax_frame` ($\le 1$ frame tolerance).
- **Speech Protection:**
  - If speech/dialogue is detected, attenuate SFX to -6.0 dB to prevent masking vocal reactions.
- **Track A2 Invariant (INV-04):**
  - Track `A2` is 100% RESERVED FOR VOICEOVER. NEVER place SFX, music, or clips on Track `A2`.
- **Transitions & BGM Ducking:**
  - Track `A3`: Transition Whoosh SFX at major cuts (-6.0 dB).
  - Track `A5`: Background music ducked by -12.0 dB around climaxes.
