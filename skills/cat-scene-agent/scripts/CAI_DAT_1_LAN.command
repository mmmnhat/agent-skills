#!/bin/bash
cd "$(dirname "$0")"
PY=$(command -v python3)
if [ -z "$PY" ]; then echo "Cài Python 3 từ python.org rồi chạy lại"; read; exit 1; fi
"$PY" scene_cut.py check || { echo "Lỗi kiểm tra requirements"; read; exit 1; }
nohup "$PY" scene_cut.py serve > _queue_serve.log 2>&1 &
echo "XONG. Dịch vụ đang chạy nền. Từ giờ chỉ cần dán đường dẫn video cho Claude."
read
