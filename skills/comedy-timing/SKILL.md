---
name: comedy-timing
description: Narrative arc and comedic timing controller. Identifies Setup, Anticipation, Climax, and Payoff phases. Enforces the 0.8s reaction window rule.
---

# Comedy Timing (`comedy-timing`)

Manages comedic and dramatic timing for funny moments, fail compilations, and reaction videos.

## 🎯 Directives
- **4-Phase Narrative Arc:** Every incident must be evaluated across:
  1. `Setup`: Establishing subject and context.
  2. `Anticipation`: Build-up of tension or mistake initiation.
  3. `Climax / Collision`: The instant of physical impact or realization.
  4. `Payoff / Reaction`: The aftermath (the fall, laughter, shock, freeze frame, or replay).
- **Payoff Window Preservation (INV-05):** The reaction phase must NEVER be cut prematurely. Minimum reaction window is $0.8\text{s} \times \text{FPS}$ (e.g. 19 frames at 23.976 fps).
- **No Uniform Trimming:** Avoid cutting every clip to the same duration. Pacing expands for dramatic pauses and contracts for rapid chaos.
- **Incident Bundling:** If an incident has an immediate follow-up angle or continuous reaction, bundle them contiguously as an atomic incident unit.
