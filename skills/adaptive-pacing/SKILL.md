---
name: adaptive-pacing
description: High-retention narrative sequencing engine. Generates 4-Beat Narrative Fast-Cut or 5-beat W-Curve structures (8-15s per incident). Enforces Context Preservation, Dead-Middle Micro-Cuts, and bundles continuous events.
---

# ⏱️ VisionCut Adaptive Pacing (`adaptive-pacing`)

Structures clips to maximize viewer retention across short-form (15s–60s) and long-form video formats.

---

## ⚡ 4-BEAT NARRATIVE PACING CEILINGS

Mọi incident / moment trên timeline tuân theo chuẩn 4 hồi:
- **`Setup / Context`**: $2.0\text{s} - 3.5\text{s}$ (Bắt đầu từ hành động có chủ đích, bảo toàn bối cảnh hiểu được).
- **`Escalation`**: $1.5\text{s} - 3.0\text{s}$ (Điềm báo, tích lũy căng thẳng).
- **`Climax / Hit`**: $1.5\text{s} - 3.0\text{s}$ (Khoảnh khắc va chạm / cú lật tẩy).
- **`Payoff / React`**: $2.0\text{s} - 4.0\text{s}$ (Tối thiểu 1.5s, cấm cắt cụt khi phản ứng chưa lắng xuống).
- **Tổng Incident**: **$8.0\text{s} - 14.0\text{s}$** (Tối đa 15s cho tình huống phức tạp).

---

## 🎯 2 Chế Độ Dựng

### 1. Sequential Fast-Cut Mode (Theo Thứ Tự Gốc — Reasoning-Based)
- Giữ 100% thứ tự các clip theo thời gian xuất hiện.
- **Hard Scene Cut Isolation (Bắt buộc bước 1):** Tách sạch ranh giới chuyển cảnh cứng để loại bỏ phần thừa của video trước/sau (compilation bleed), cô lập đúng cảnh mục tiêu `[scene_start, scene_end]`.
- **Single Continuous Causal Slice (Bảo toàn Raccord & Ngữ cảnh):** Giữ 1 đoạn liền mạch duy nhất (`[in_pt -> out_pt]`) bao trọn chuỗi Nhân – Quả (*Setup $\to$ Escalation $\to$ Climax $\to$ Reaction*), tuyệt đối không cắt nhảy cóc (jump-cut) mù `[0s->3s]` làm đứt mạch raccord.
- **Reaction Hold:** Giữ trọn vẹn phản ứng sau cú hit tối thiểu $1.5\text{s} - 3.5\text{s}$ trước khi chuyển sang cảnh kế tiếp.

### 2. W-Curve Mode (Tối Đa Retention Theo Đường Cong Giữ Chân)
Chấm điểm Sức hút cho từng incident:
$$S = 0.40 \cdot \text{Motion} + 0.35 \cdot \text{Arc} + 0.25 \cdot \text{Audio}$$
Ánh xạ các cụm incident vào 5 đỉnh/đáy:
- **Hook (Peak 1):** Cụm điểm cao nhì (Rank #2) — giữ chân 3s đầu ($2.0\text{s} - 4.0\text{s}$).
- **Context (Valley 1):** Cụm giải thích tiền đề ($2.0\text{s} - 3.0\text{s}$).
- **Mid-Climax (Peak 2):** Cụm kịch tính vừa (Rank #3) ($3.0\text{s} - 4.0\text{s}$).
- **Suspense (Valley 2):** Nhịp chờ tích lũy căng thẳng ($2.0\text{s} - 3.0\text{s}$).
- **Grand Finale (Peak 3):** Cụm bùng nổ nhất video (Rank #1) ($4.0\text{s} - 6.0\text{s}$).
