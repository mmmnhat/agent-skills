---
name: comedy-timing
description: Narrative arc and comedic timing controller. Enforces Ultra-Tight Fast-Cut ceilings (Setup 2-4s, Climax 2-3.5s, Payoff 2-4s, Total 8-15s) and the 0.8s reaction window rule.
---

# Comedy Timing (`comedy-timing`)

Manages comedic, dramatic, and high-retention timing for funny moments, fail compilations, and viral reaction videos.

## ⚡ ULTRA-TIGHT FAST-CUT CEILINGS (QUY TẮC NHỊP SIÊU TỐC - BẮT BUỘC)

Tuyệt đối KHÔNG ĐƯỢC để các đoạn setup, climax, payoff kéo dài lê thê 10-21 giây. Khán giả short-form/viral sẽ lướt qua nếu nhịp chậm quá 3-4 giây không có chuyển biến:

| Pha Kịch Tính | Thời Lượng Chuẩn | Trần Thời Lượng Tối Đa | Mô Tả & Ranh Giới Cắt |
| :--- | :---: | :---: | :--- |
| **`Setup / Hook`** | **2.0s – 3.0s** | **Tối đa 4.0s** | Cắt ngay tại khoảnh khắc nhận diện bất thường/mối nguy. Bỏ 100% các frame máy lắc lư, lia tìm góc. |
| **`Anticipation`** | **1.0s – 2.0s** | **Tối đa 2.5s** | Tích lũy căng thẳng hoặc bắt đầu sai lầm. |
| **`Climax / Hit`** | **1.5s – 3.0s** | **Tối đa 3.5s** | Đúng khoảnh khắc va chạm/thót tim (`Peak - 0.8s` đến `Peak + 1.2s`). |
| **`Payoff / React`** | **1.5s – 3.5s** | **Tối đa 4.0s** | Tối thiểu 0.8s (theo INV-05). Khán giả thấy kết quả/phản ứng là cắt ngay, cấm kéo dài! |
| **TỔNG INCIDENT** | **7.0s – 12.0s** | **Tối đa 15.0s** | Toàn bộ 1 tình huống chỉ gói gọn trong 8-15 giây cô đọng nhất. |

## 🎯 Directives
- **Zero Dead Air:** Mọi khoảng lặng không tạo kịch tính hoặc chuyển động lặp lại $> 2.0\text{s}$ phải bị gọt sạch.
- **Fast Action Peak Snapping:** Thuật toán tự động snap vào tâm Action Peak và chỉ lấy cửa sổ đối xứng siêu hẹp quanh đỉnh.
- **Incident Bundling:** Nếu một tình huống có nhiều cú hit hoặc góc quay phụ, mỗi góc chỉ được xuất hiện 2-3s liền mạch rồi chuyển cảnh ngay.
- **Batch Execution:** Không thực thi từng nhát cắt lẻ tẻ; gộp toàn bộ các điểm cắt thành 1 batch ExtendScript duy nhất để tránh nghẽn.
