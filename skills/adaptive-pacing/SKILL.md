---
name: adaptive-pacing
description: High-retention narrative sequencing engine. Generates Ultra-Tight 5-beat W-Curve or Sequential Fast-Cut structures (8-15s per incident). Eliminates dead air and bundles continuous events.
---

# Adaptive Pacing (`adaptive-pacing`)

Structures clips to maximize viewer retention across short-form (15s–60s) and long-form video formats.

## ⚡ ULTRA-TIGHT RETENTION PACING

- **Hard Fast-Cut Window:**
  - Setup: $2.0\text{s} - 3.5\text{s}$
  - Climax: $2.0\text{s} - 3.0\text{s}$
  - Payoff: $2.0\text{s} - 3.5\text{s}$
  - **Mỗi incident chỉ dài từ 7s đến 12s** (tối đa 15s cho tình huống 2 nhịp).
  - Loại bỏ hoàn toàn các đoạn lê thê $> 4\text{s}$ không có hành động.

## 🎯 Pacing Modes

### 1. W-Curve Mode (Viewer Retention)
Scores each incident by Attraction Score:
$$S = 0.40 \cdot \text{Motion} + 0.35 \cdot \text{Arc} + 0.25 \cdot \text{Audio}$$
Maps incidents onto the 5-beat retention curve:
- **Hook (Peak 1):** Rank #2 clip — grabs attention in the first 3 seconds (2-4s duration).
- **Context (Valley 1):** Fast explanatory build-up (2-3s).
- **Mid-Climax (Peak 2):** Rank #3 clip — sustains mid-video engagement (3-4s).
- **Suspense (Valley 2):** Brief anticipation beat (2-3s).
- **Grand Finale (Peak 3):** Rank #1 clip — highest energy explosion (4-6s).

### 2. Sequential Fast-Cut Mode (Chronological)
- Preserves 100% original chronological order.
- Applies hard fast-cut around each climax: `Climax - 1.0s` to `Climax + 1.2s`.
- Eliminates dull setup intervals without scrambling narrative order.
