---
name: cat-scene-agent
description: >-
  Dùng khi người dùng dán đường dẫn video (.mp4/.mov/.mkv) và muốn cắt thành
  footage lẻ theo scene (cảnh). Agent tự cài công cụ, chạy phân tích, xem
  ảnh vision để dán nhãn điểm cắt, cho người dùng duyệt qua trang web, rồi
  tự xuất file — không để người dùng gõ lệnh nào. Kích hoạt khi user nói:
  "cắt scene", "băm footage", "split video", "tách cảnh", hoặc dán đường dẫn
  video kèm ý định muốn chia nhỏ.
---

# Cat-Scene Agent — Cắt scene tự động

Người dùng chỉ cần: **dán đường dẫn → chọn menu → duyệt HTML → xác nhận**.
Agent làm tất cả; không bao giờ bảo người dùng tự chạy lệnh.

> **Môi trường:** Antigravity trên Windows. Agent dùng `run_command`
> (PowerShell) để chạy mọi lệnh trên máy cục bộ. Script chính:
> [`scene_cut.py`](./scripts/scene_cut.py).

---

## 0. Kiểm tra & Cài đặt (im lặng, KHÔNG hỏi menu)

### 0a. Tìm kit đang chạy

Tìm thư mục có `scene_cut.py` + `_queue/_alive.json` trong `E:\` hoặc
Desktop — tối đa 3 cấp sâu. Dùng PowerShell:

```powershell
Get-ChildItem -Path "E:\" -Recurse -Depth 3 -Filter "_alive.json" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty DirectoryName
```

**`_alive.json` hợp lệ** = trường `t` cách hiện tại < 60s AND `version` ≥
`VERSION` trong `scene_cut.py`.

### 0b. Chưa có kit hoặc kit cũ → triển khai

1. Chọn thư mục kit: cùng thư mục với video nếu tiện, hoặc `E:\scene_cut\`.
2. Sao chép 3 file từ thư mục skill (`scripts/`) vào thư mục kit:

```powershell
$kit = "E:\scene_cut"
New-Item -ItemType Directory -Path "$kit" -Force
Copy-Item "E:\.agents\skills\cat-scene-agent\scripts\scene_cut.py" "$kit\"
Copy-Item "E:\.agents\skills\cat-scene-agent\scripts\CAI_DAT_1_LAN.bat" "$kit\"
Copy-Item "E:\.agents\skills\cat-scene-agent\scripts\CAI_DAT_1_LAN.command" "$kit\"
```

### 0c. Cài dependencies (nếu chưa alive)

Dùng `run_command` chạy:

```powershell
Start-Process -FilePath "$kit\CAI_DAT_1_LAN.bat" -WindowStyle Minimized
```

Sau đó poll `_alive.json` mỗi 15s (tối đa 3 phút):

```powershell
$alive = "$kit\_queue\_alive.json"
$deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $deadline) {
    if (Test-Path $alive) {
        $j = Get-Content $alive | ConvertFrom-Json
        if ((Get-Date) - [DateTimeOffset]::FromUnixTimeSeconds($j.t).LocalDateTime -lt [TimeSpan]::FromSeconds(60)) {
            Write-Output "ALIVE version=$($j.version)"; break
        }
    }
    Start-Sleep 15
}
```

Nếu vẫn không alive sau 3 phút → nhắn người dùng mở tay `CAI_DAT_1_LAN.bat`
trong thư mục kit.

### 0d. Version cũ hơn

Overwrite `scene_cut.py` trong kit bằng file từ skill, sau đó:

```powershell
# Dừng serve cũ
Stop-Process -Name "python*" -ErrorAction SilentlyContinue
Start-Sleep 2
# Khởi động lại
Start-Process pythonw -ArgumentList "`"$kit\scene_cut.py`" serve --root `"$kit`" --install-startup" -WindowStyle Hidden
```

---

## 1. Nhận video → gửi analyze + hỏi menu song song

Khi có đường dẫn video, **gửi job analyze ngay** rồi mới hỏi menu (dùng
`ask_question`). Máy phân tích song song với lúc người dùng trả lời.

### 1a. Viết job file

```powershell
$id    = "analyze_$(Get-Date -Format 'HHmmss')"
$name  = [IO.Path]::GetFileNameWithoutExtension($video)
$work  = "$([IO.Path]::GetDirectoryName($video))\_scene\$name"
$job   = @{ cmd="analyze"; args=@{ "_"=$video; work=$work } } | ConvertTo-Json -Compress
$job | Set-Content "$kit\_queue\$id.job.json" -Encoding UTF8
```

### 1b. Hỏi menu (4 câu, 1 lần)

Dùng `ask_question` với 4 câu đồng thời:

1. **Prefix** — `<ten>_` (từ video), prefix lần trước (nếu nhớ), Other
2. **Số bắt đầu** — số kế tiếp đã lưu cho prefix, `0001`, Other
3. **Thư mục xuất** — `<thư mục video>/footage_scene`, `<thư mục video>/footage`, Other
4. **Intro** — "Claude xem và bỏ intro/thẻ cảnh báo" *(Recommended)*, "Giữ nguyên"

---

## 2. Chờ job analyze

Poll mỗi 30s:

```powershell
$done = "$kit\_queue\$id.done.json"
if (Test-Path $done) { Get-Content $done | ConvertFrom-Json }
else {
    $prog = "$work\progress.json"
    if (Test-Path $prog) { Get-Content $prog | ConvertFrom-Json }
}
```

- `rc ≠ 0` → đọc `tail`, tự xử lý nếu được (sai đường dẫn → hỏi lại).
- Khi có `progress.json`, báo % một dòng mỗi khi thay đổi ≥ 10%.

---

## 3. Vision — xem ảnh lưới và dán nhãn

```powershell
# Lấy danh sách sheet
Get-ChildItem "$work\sheets" -Filter "*.jpg" | Select-Object -ExpandProperty FullName
```

Đọc **3–4 ảnh/lượt** bằng `view_file`. Mỗi ô trong ảnh lưới = `frame−20 |
frame−1 | vạch đỏ | frame 0 | frame+20`.

Ghi nhãn vào `dec.txt` (format: `<số|a-b> <nhãn>`):

| Nhãn | Ý nghĩa |
|------|---------|
| `R`  | Khác clip (người/bối cảnh/nguồn quay khác) |
| `F`  | Lia, zoom, flash, cháy nổ, cùng clip đổi tỉ lệ, replay cùng góc, cùng sự kiện quay bằng camera khác |
| `I`  | Intro teaser, thẻ cảnh báo, outro/subscribe *(chỉ khi chọn bỏ intro)* |
| `R?` | Không chắc, nghiêng về tách — sẽ hỏi người dùng |
| `F?` | Không chắc, nghiêng về gộp — sẽ hỏi người dùng |

Ví dụ `dec.txt`:
```
1-5 R
6 F
7 R?
8-12 R
13 I
```

Sau khi gán xong toàn bộ, commit bằng PowerShell:
```powershell
$dec | Set-Content "$work\dec.txt" -Encoding UTF8
```

---

## 4. Duyệt + Cắt trước (song song)

Gửi **2 job cùng lúc** (2 file `.job.json` riêng):

**Job review:**
```json
{ "cmd": "review", "args": { "work": "<W>", "keep_intro": true } }
```
*(bỏ `keep_intro` nếu người dùng chọn bỏ intro)*

**Job precut:**
```json
{ "cmd": "precut", "args": { "work": "<W>" } }
```

Nhắn người dùng 2 dòng:
> "Tìm thấy **N clip**, **M chỗ** cần bạn xem. Trình duyệt vừa mở trang
> duyệt — chỉ bấm vào chỗ sai, rồi bấm **Xong** và dán kết quả vào đây."

*(0 câu hỏi → nhảy thẳng bước 5)*

### 4a. Xử lý phản hồi duyệt

Người dùng dán dạng: `ten: ok` hoặc `ten: 2=tach,5=bo,sai=12+40`

- `sai=` → đọc frames quanh clip đó, tự sửa dec.txt, gửi lại job review với `answers`.
- Còn câu hỏi mới → lặp lại.

---

## 5. Xác nhận và Xuất

Đọc `segments.json`:
```powershell
Get-Content "$work\segments.json" | ConvertFrom-Json
```

Hỏi người dùng (dùng `ask_question`):
> "Xuất **N clip** `<prefix>0001` → `<prefix>000N` vào `<out>`?"
- "Xuất ngay *(Recommended)*"
- "Mở danh sách xem trước" *(gửi job review `open:true`)*
- "Huỷ"

**Job cut:**
```json
{
  "cmd": "cut",
  "args": { "work": "<W>", "prefix": "<p>", "start": 1, "out": "<out>" }
}
```

Clip có trong `cache/` → chỉ đổi tên (gần như tức thì). Còn lại cắt mới.

**Trùng tên** → hỏi: "Đánh số tiếp sau file cuối" · "Thư mục khác" · "Ghi đè".

**Sau khi xong** — đọc `cut_report.json`, báo:
- Dải tên (`first` → `last`), thư mục xuất, encoder đã dùng, số kế tiếp.
- `failed > 0` → gửi lại job `cut` với `resume: true`.
- Lưu prefix + số kế tiếp vào memory → dùng làm Recommended lần sau.

---

## Nhiều video

Dán nhiều đường dẫn → gửi **tất cả job analyze ngay**, hỏi **1 menu chung**,
vision từng video khi phân tích xong, precut từng video, **1 xác nhận xuất
chung**.

---

## Quy tắc bất biến

- ❌ Không bao giờ bảo người dùng tự gõ lệnh hay chạy `.bat` (trừ khi từ chối cấp quyền lúc cài).
- ❌ Không xuất, không ghi đè khi chưa xác nhận.
- ✅ `vfr_warning` trong `info.json` → cảnh báo người dùng trước khi cắt.
- ✅ Dịch vụ chỉ nhận lệnh qua `scene_cut.py`; không đưa shell tùy ý vào job.
- ✅ Luôn dùng `ask_question` với option Recommended; không hỏi cái đoán được.
