---
name: asset-indexer
description: Multi-modal multimedia asset indexer and retrieval engine for SFX, Meme clips, Background Music, Overlays, and Vlipsy reactions. Features the "Hỏi và Nhớ" (Ask & Remember) adaptive affinity ledger to learn editor preferences for specific scene actions (punches, transitions, emotional beats). Use when the user wants to search sound effects, find memes, pick music, index E:\Video Asset, or mentions "tìm sfx", "tìm sound", "tìm meme", "kho asset", "asset indexer", or "hỏi và nhớ asset".
---

# Asset-Indexer: Smart Multimedia Vault with "Hỏi và Nhớ"

Kỹ năng quản trị, lập chỉ mục và truy vấn thông minh kho tài nguyên multimedia (`E:\Video Asset\`) bao gồm: **SFX** (hiệu ứng âm thanh), **Meme** (video hài/cắt cảnh/green screen), **Music** (nhạc nền), **Overlay** (chèn đè), **Brand Packs** (ITV, Bonk, YIKES) và **Vlipsy Reactions** (celebrate, funny, omg, sad, sports...).

Tích hợp cơ chế **"Hỏi và Nhớ" (Ask & Remember)**: Tự động ghi nhớ sở thích ghép âm thanh / meme của biên tập viên cho từng loại tình huống để ưu tiên đề xuất chính xác ở các lần dựng tiếp theo.

---

## 🚀 1. Lập Chỉ Mục Kho Tài Nguyên (Scan & Index)

Để quét toàn bộ kho tài nguyên `E:\Video Asset\` (1.700+ tệp) đa luồng trong vài giây:

```bash
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py --scan
```

Kết quả lập chỉ mục được lưu trữ tại `E:\Video Asset\asset_index.json` gồm:
- Thời lượng chính xác (`duration`).
- Độ phân giải & tỷ lệ khung hình (`resolution`, `aspect_ratio`).
- Kênh trong suốt (`has_alpha`, `green_screen`).
- Bộ thẻ từ khóa ngữ nghĩa tiếng Việt & tiếng Anh (`tags`, `vibe_mappings`).

---

## 🔍 2. Truy Vấn Thông Minh (Search by Intent & Vibe)

Tìm kiếm theo mô tả âm thanh, tình huống, cảm xúc hoặc định dạng:

### Tìm hiệu ứng âm thanh (SFX)
```bash
# Tìm tiếng chuyển cảnh / lướt nhanh
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py -q "whoosh chuyen canh" -c SFX

# Tìm tiếng đấm / va chạm mạnh
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py -q "punch va cham" -c SFX --max-dur 2.0
```

### Tìm Meme & Video Cắt Cảnh (Meme / Vlipsy)
```bash
# Tìm meme hài hước / cười troll
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py -q "cuoi hai huoc funny" -c Meme

# Tìm meme phông xanh (Green Screen) để chèn đè lên video
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py -q "cat" --green-screen

# Tìm reaction bất ngờ (OMG)
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py -q "bat ngo kinh ngac" -c Vlipsy
```

### Tìm Nhạc Nền (Music)
```bash
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py -q "soi dong hype" -c Music
```

---

## 🧠 3. Cơ Chế "Hỏi và Nhớ" (Ask & Remember Engine)

Khi dựng video, mỗi khi người dùng hoặc agent chọn một sound hoặc meme cụ thể cho một hành động (ví dụ: hành động té ngã $\rightarrow$ chọn `punch_01.mp3`, điểm chuyển cảnh $\rightarrow$ chọn `whoosh_fast.wav`), kỹ năng sẽ ghi nhớ vào `asset_memory.json`:

### Ghi nhớ sự lựa chọn:
```bash
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py --remember --intent "action_peak_punch" --asset "SFX/05_Impacts_Hits/Punch_01.mp3"
```

### Hiển thị bảng ký ức đã nhớ:
```bash
python e:\.agents\skills\asset-indexer\scripts\asset_cli.py --list-memories
```

Ở các lần tìm kiếm tiếp theo với từ khóa liên quan (`"punch"`, `"đấm"`, `"va chạm"`), asset đã được nhớ sẽ được tăng điểm số (Affinity Boost $\times 1.5 \sim \times 2.0$) và được gắn nhãn sao vàng `🌟 [Được Nhớ Thường Dùng]`.

---

## 🔌 4. Lập Trình Python API (Dành cho Pacing-Editor)

Các kỹ năng dựng phim (như `pacing-editor`) có thể trực tiếp import và truy vấn asset:

```python
from search_engine import search_assets
from memory_manager import remember_choice

# Lấy 1 tiếng whoosh ngắn nhất cho edit point
matches = search_assets(query="whoosh", category="SFX", max_duration=1.5, top_k=1)
if matches:
    best_sfx_path = matches[0]["asset"]["full_path"]
    # Import vào Premiere Pro track A2 qua MCP...
```
