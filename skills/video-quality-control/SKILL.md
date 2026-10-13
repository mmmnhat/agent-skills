---
name: video-quality-control
description: Closed-loop QA and evaluation harness runner. Audits the 5 Timeline Invariants, generates atomic micro-patch plans, and enforces the 3-cycle circuit breaker.
---

# Video Quality Control (`video-quality-control`)

Audits the assembled sequence using `HarnessEvaluator` and orchestrates self-healing repairs.

## 🎯 Directives
- **Audit Against the 5 Invariants:**
  1. `INV-01 (Zero Gaps on V1)`: Ripple-deletes black gaps.
  2. `INV-02 (SFX Sync <= 1 frame)`: Moves misaligned SFX clips on A4.
  3. `INV-03 (Headroom <= -1.0 dBFS)`: Attenuates master audio to prevent clipping.
  4. `INV-04 (Voiceover Track A2 Empty)`: Moves misplaced audio off A2 to A3/A4.
  5. `INV-05 (Payoff Window >= 0.8s)`: Extends truncated reaction clip tails on V1.
- **Micro-Patch Generation:**
  - Emits `state/patch-plan.json` containing atomic corrective actions.
  - Passes patch plan to `premiere-execution` for single-batch application.
- **Circuit Breaker Policy:**
  - Maximum repair cycles: 3.
  - If invariants fail on cycle 3:
    1. Soft rollback to pre-fix sequence checkpoint.
    2. Plant Red sequence markers (`[QA_FAIL]`) at problem frame positions.
    3. Capture review frame (`capture_frame`) and present in chat for editor intervention.
- **Final Visual Verification:**
  - Export sequence review frames (`export_sequence_review_frames`) and verify visual integrity with AI Vision (`view_file`).
