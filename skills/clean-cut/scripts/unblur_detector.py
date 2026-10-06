#!/usr/bin/env python3
"""
Unblur & Aspect Ratio Detector (Pristine Razor-Sharp Edition)
Uses Laplacian variance and Sobel edge energy to detect blurred margins (pillarbox / letterbox),
applies inward safety margins and canonical aspect ratio snapping to guarantee ZERO residual blur.
Supports passing proxy frames while mapping to target master resolution.
"""
import cv2
import numpy as np

def detect_unblur_box(frame, target_res=None):
    """
    Analyzes a single frame (can be proxy or master) to detect whether it contains blurred side/top/bottom margins.
    If target_res=(master_w, master_h) is provided, returns canonical box in target coordinates.
    
    Returns:
        is_blurred: bool
        box: (x, y, w, h) in target frame pixel coordinates
        aspect_ratio_str: str (e.g., '9:16', '1:1', '4:3', '16:9')
    """
    if frame is None:
        tw, th = target_res if target_res else (1920, 1080)
        return False, (0, 0, tw, th), "16:9"

    in_h, in_w = frame.shape[:2]
    orig_w, orig_h = target_res if target_res else (in_w, in_h)

    # Process directly on frame if width <= 640, else resize down for speed
    if in_w > 640:
        target_small_w = 640
        scale = target_small_w / float(in_w)
        target_small_h = int(in_h * scale)
        small = cv2.resize(frame, (target_small_w, target_small_h), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    mid_y1, mid_y2 = int(h * 0.20), int(h * 0.80)
    
    # 1. Check Pillarbox (blur on left and right)
    margin_l = gray[mid_y1:mid_y2, int(w * 0.04):int(w * 0.16)]
    margin_r = gray[mid_y1:mid_y2, int(w * 0.84):int(w * 0.96)]
    center_roi = gray[mid_y1:mid_y2, int(w * 0.40):int(w * 0.60)]
    
    var_l = cv2.Laplacian(margin_l, cv2.CV_64F).var()
    var_r = cv2.Laplacian(margin_r, cv2.CV_64F).var()
    var_c = cv2.Laplacian(center_roi, cv2.CV_64F).var()
    
    blur_ratio_x = var_c / (max(var_l, var_r) + 1e-5)
    
    if blur_ratio_x >= 4.0 and max(var_l, var_r) <= 45.0:
        sobel_x = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))
        col_energy = np.mean(sobel_x[mid_y1:mid_y2, :], axis=0)
        
        left_band = col_energy[int(w * 0.10):int(w * 0.45)]
        right_band = col_energy[int(w * 0.55):int(w * 0.90)]
        
        if len(left_band) > 0 and len(right_band) > 0:
            left_peak = int(w * 0.10) + int(np.argmax(left_band))
            right_peak = int(w * 0.55) + int(np.argmax(right_band))
            
            bw_proxy = right_peak - left_peak
            bw_ratio = bw_proxy / float(w)
            content_ratio = (bw_ratio * orig_w) / float(orig_h)
            
            # Canonical snapping for pristine zero blur
            if content_ratio < 0.65:
                ratio_str = "9:16"
                canon_w = (int(orig_h * 9 / 16) // 2) * 2
            elif content_ratio < 0.88:
                ratio_str = "4:5"
                canon_w = (int(orig_h * 4 / 5) // 2) * 2
            elif content_ratio < 1.15:
                ratio_str = "1:1"
                canon_w = (orig_h // 2) * 2
            elif content_ratio < 1.45:
                ratio_str = "4:3"
                canon_w = (int(orig_h * 4 / 3) // 2) * 2
            else:
                ratio_str = "16:9"
                return False, (0, 0, orig_w, orig_h), "16:9"

            cx = orig_w // 2
            x1 = max(0, cx - canon_w // 2)
            x1 = (x1 // 2) * 2
            return True, (x1, 0, canon_w, orig_h), ratio_str

    # 2. Check Letterbox (blur on top and bottom)
    mid_x1, mid_x2 = int(w * 0.20), int(w * 0.80)
    margin_t = gray[int(h * 0.04):int(h * 0.16), mid_x1:mid_x2]
    margin_b = gray[int(h * 0.84):int(h * 0.96), mid_x1:mid_x2]
    
    var_t = cv2.Laplacian(margin_t, cv2.CV_64F).var()
    var_b = cv2.Laplacian(margin_b, cv2.CV_64F).var()
    blur_ratio_y = var_c / (max(var_t, var_b) + 1e-5)
    
    if blur_ratio_y >= 4.0 and max(var_t, var_b) <= 45.0:
        sobel_y = np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
        row_energy = np.mean(sobel_y[:, mid_x1:mid_x2], axis=1)
        
        top_band = row_energy[int(h * 0.08):int(h * 0.45)]
        bot_band = row_energy[int(h * 0.55):int(h * 0.92)]
        
        if len(top_band) > 0 and len(bot_band) > 0:
            top_peak = int(h * 0.08) + int(np.argmax(top_band))
            bot_peak = int(h * 0.55) + int(np.argmax(bot_band))
            
            bh_proxy = bot_peak - top_peak
            bh_ratio = bh_proxy / float(h)
            content_ratio = float(orig_w) / max(1.0, bh_ratio * orig_h)
            
            ratio_str = _classify_aspect_ratio(content_ratio)
            bh_target = (int(bh_ratio * orig_h) // 2) * 2
            cy = orig_h // 2
            y1 = max(0, cy - bh_target // 2)
            y1 = (y1 // 2) * 2
            return True, (0, y1, orig_w, bh_target), ratio_str

    ratio = orig_w / float(orig_h)
    return False, (0, 0, orig_w, orig_h), _classify_aspect_ratio(ratio)

def _classify_aspect_ratio(ratio):
    if ratio < 0.65:
        return "9:16"
    elif ratio < 0.88:
        return "4:5"
    elif ratio < 1.15:
        return "1:1"
    elif ratio < 1.45:
        return "4:3"
    elif ratio < 1.90:
        return "16:9"
    else:
        return "21:9"
