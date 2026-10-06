import os
import sys

# Auto-require and self-install dependencies
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import env_bootstrap
except Exception:
    pass

import cv2
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def get_font(size):
    font_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def build_dense_vision_sheet(video_path, start_frame, total_grid_frames=64, step=5, cols=8, rows=8, output_path="dense_sheet.jpg"):
    """
    Builds a high-density Vision Sheet:
    - step=1: Full FPS (1:1 - Từng frame một liên tục, 24fps)
    - step=2: 1/2 FPS (~12 frames/sec)
    - step=5: 1/5 FPS (~4.8 frames/sec)
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 23.976
    
    thumb_w = 220
    thumb_h = 124
    header_h = 55
    label_h = 20
    pad = 8
    
    sheet_w = pad * 2 + cols * thumb_w + (cols - 1) * pad
    sheet_h = pad * 2 + header_h + rows * (thumb_h + label_h + pad)
    
    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(14, 17, 23))
    draw = ImageDraw.Draw(sheet)
    
    font_title = get_font(18)
    font_sub = get_font(12)
    font_label = get_font(10)
    font_badge = get_font(10)
    
    draw.rectangle([0, 0, sheet_w, header_h], fill=(22, 27, 36))
    
    end_frame = start_frame + total_grid_frames * step
    t_start = start_frame / fps
    t_end = end_frame / fps
    
    rate_desc = "FULL FPS (1:1 - Từng frame một)" if step == 1 else (f"1/2 FPS (~{fps/2:.1f} fps)" if step == 2 else f"1/5 FPS (~{fps/5:.1f} fps)")
    title = f"DENSE VISION SHEET — {rate_desc} — [Frame {start_frame} ➔ {end_frame}]"
    m1, s1 = divmod(t_start, 60)
    m2, s2 = divmod(t_end, 60)
    time_str = f"{int(m1):02d}:{s1:05.2f} ➔ {int(m2):02d}:{s2:05.2f} (Độ dài: {t_end - t_start:.2f}s)"
    
    draw.text((pad + 4, 8), title, fill=(255, 215, 0), font=font_title)
    draw.text((pad + 4, 32), f"Lấy mẫu: Bước nhảy step={step} frames | Grid: {cols}x{rows} ({total_grid_frames} frames) | Time: {time_str}", fill=(160, 180, 200), font=font_sub)
    
    for idx in range(total_grid_frames):
        f_num = start_frame + idx * step
        r = idx // cols
        c = idx % cols
        
        x = pad + c * (thumb_w + pad)
        y = header_h + pad + r * (thumb_h + label_h + pad)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_num)
        ret, frame = cap.read()
        if ret and frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb).resize((thumb_w, thumb_h), Image.Resampling.BILINEAR)
            sheet.paste(im, (x, y))
            
            # Border
            draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline=(45, 55, 70), width=1)
            
            # Label
            draw.rectangle([x, y + thumb_h, x + thumb_w, y + thumb_h + label_h], fill=(20, 25, 33))
            t_sec = f_num / fps
            m, s = divmod(t_sec, 60)
            tc = f"{int(m):02d}:{s:05.2f}"
            draw.text((x + 4, y + thumb_h + 3), f"F:{f_num} ({tc})", fill=(210, 225, 245), font=font_label)
            
            # Corner index
            draw.rectangle([x + thumb_w - 28, y + 2, x + thumb_w - 2, y + 16], fill=(0, 0, 0, 180))
            draw.text((x + thumb_w - 25, y + 3), f"#{idx+1}", fill=(0, 255, 180), font=font_badge)

    cap.release()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    sheet.save(output_path, quality=90)
    print(f"Saved: {output_path}")
    return output_path
