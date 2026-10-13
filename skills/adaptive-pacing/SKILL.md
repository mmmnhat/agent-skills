---
name: adaptive-pacing
description: High-retention narrative sequencing engine. Generates 5-beat W-Curve or Sequential Fast-Cut structures. Eliminates dead air and bundles continuous events.
---

# Adaptive Pacing (`adaptive-pacing`)

Structures clips to maximize viewer retention across short-form (15s–60s) and long-form video formats.

## 🎯 Pacing Modes

### 1. W-Curve Mode (Viewer Retention)
Scores each incident by Attraction Score:
$$S = 0.40 \cdot \text{Motion} + 0.35 \cdot \text{Arc} + 0.25 \cdot \text{Audio}$$
Maps incidents onto the 5-beat retention curve:
- **Hook (Peak 1):** Rank #2 clip — grabs attention in the first 3 seconds.
- **Context (Valley 1):** Explanatory build-up clips.
- **Mid-Climax (Peak 2):** Rank #3 clip — sustains mid-video engagement.
- **Suspense (Valley 2):** Anticipation clips building tension.
- **Grand Finale (Peak 3):** Rank #1 clip — highest energy payoff of the video.

### 2. Sequential Fast-Cut Mode (Chronological)
- Preserves 100% original chronological order.
- Applies hard fast-cut around each climax: `Climax - 1.0s` to `Climax + 1.2s`.
- Eliminates dull setup intervals without scrambling narrative order.
