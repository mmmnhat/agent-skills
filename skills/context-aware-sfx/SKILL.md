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
- **Contextual & Peak-Aligned SFX (`Track A3`/`A4`):**
  - Look up `dur_sec` and `peak_offset_sec` in `E:\.agents\skills\visioncut\resources\sfx_full_catalog.json` (401 indexed SFX files in `E:\Video Asset\SFX`).
  - Align the acoustic peak to the physical impact frame: `sfx_start_sec = timeline_impact_sec - peak_offset_sec` ($\le 1$ frame tolerance). Cap long SFX ($>3.2\text{s}$) to a tight `2.5s–3.2s` window around `peak_offset_sec`.
- **Speech & Voiceover Protection (INV-04):**
  - Track `A2` is 100% RESERVED FOR VOICEOVER (or ElevenLabs `ITV 5` Intro VO). NEVER place SFX or BGM overlapping active `A2` Voiceover segments.
- **Silent-Clip-Only BGM Policy (`Track A5` in ITV Studio Profile):**
  - Place Background Music on Track `A5` **exclusively** over clips that have no audible original sound (`peak_db <= -25 dB` or missing `A1` stream), and remove dead-silent `A1` items under `A5` BGM intervals so `Coverage(A1) + Coverage(A5) = 100%`.
