# 📜 VIDEO EDITING GLOBAL RULES

These rules are universally binding and take precedence over individual skill variations.

---

## 1. Evidence First
- **Never invent source events:** All edits, labels, and cuts must be grounded in physical frame and audio data.
- **Never infer sound from visual content alone:** Do not assume a sound exists without checking acoustic transient energy.
- **Record uncertainty:** When evidence is ambiguous, record confidence scores in `source-manifest.json`.
- **Preserve original source timestamps:** Keep raw timecodes traceable via `TimeMapper` dual-coordinate bindings.

---

## 2. Editorial Reasoning & Ultra-Tight Pacing
- **Understand the event before editing:** Complete narrative comprehension takes priority over fast cutting.
- **Ultra-Tight Fast-Cut Ceilings (Bắt buộc):**
  - Setup / Hook: $2.0\text{s} - 3.5\text{s}$ (tối đa 4.0s). Bỏ 100% các đoạn máy lắc lư, lia chưa cố định.
  - Anticipation: $1.0\text{s} - 2.0\text{s}$.
  - Climax: $1.5\text{s} - 3.0\text{s}$ (quanh đỉnh va chạm/thót tim).
  - Payoff / Reaction: $1.5\text{s} - 3.5\text{s}$ (tối đa 4.0s, tối thiểu 0.8s theo INV-05). Khán giả thấy kết quả là cắt ngay!
  - **TỔNG MỖI INCIDENT: CHỈ 7s – 15s.** Tuyệt đối không để từng đoạn kéo dài 10s-21s làm loãng video.
- **Zero Dead Air:** Mọi đoạn trườn bò quẩn quanh, loay hoay lặp lại $> 2\text{s}$ đều phải gọt sạch.
- **Prefer intentional edits over decorative effects:** Do not add transitions, zooms, or SFX unless they enhance narrative impact.

---

## 3. Audio Integrity & Track Layout
- **Preserve valuable original audio:** If camera audio has genuine collision transients, BOOST Track `A1` by +3dB to +6dB and FORBID artificial SFX.
- **Contextual SFX on Track A4:** Use material-specific impact SFX only when footage is silent or muffled.
- **Frame-Exact SFX Alignment (INV-02):** Impact SFX must align with the visual collision frame within $\le 1$ frame.
- **Voiceover Track Integrity (INV-04):** Track `A2` is 100% RESERVED FOR VOICEOVER. Never place SFX, music, or video clips on Track `A2`.
- **Headroom Protection (INV-03):** Master audio True Peak must never exceed $-1.0\text{ dBFS}$.
- **Background Music Ducking:** Duck Track `A5` BGM by $-12\text{ dBFS}$ during action climaxes and speech.

---

## 4. Premiere Execution & High-Speed Batch Processing
- **High-Speed Batch Execution:** Phải gom toàn bộ các điểm cắt, markers, hoặc edits thành **1 batch duy nhất** (hoặc 1 kịch bản thực thi tự động). Tuyệt đối không gọi từng công cụ MCP lẻ tẻ nhiều lượt làm tắc nghẽn và làm chậm tiến độ người dùng.
- **Never modify original source files:** All mutations occur on trimmed exports or inside Premiere sequence instances.
- **Standard Sequence Timebase:** Output sequences must strictly conform to Full HD 1080p (1920x1080) at 23.976 fps constant frame rate.
- **Checkpoints Before Mutations:** Always call `create_sequence_checkpoint` before executing timeline changes.
- **Zero Gaps on Video Track (INV-01):** Unintended black frames on Track `V1` are strictly prohibited.
- **Closed-Loop Verification:** Never declare success based on tool call returns alone; always audit the resulting timeline state via `HarnessEvaluator`.

---

## 5. Quality & Human Escalation
- **Fix technical invariants before aesthetic polish:** Ensure gaps, sync, and audio headroom pass before fine-tuning transitions.
- **Circuit Breaker Policy:** If automated repairs fail after 3 iterations, execute a soft rollback to checkpoint, plant red markers (`[QA_FAIL]`), and present review frame captures in chat for human guidance.
