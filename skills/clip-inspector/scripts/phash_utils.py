#!/usr/bin/env python3
"""
Perceptual Hash & Visual Fingerprint Utilities (Optimized)
Uses 64-bit integer representation and hardware-accelerated POPCNT (.bit_count())
for ultra-fast Hamming distance calculations in O(1) CPU time.
"""
import cv2
import numpy as np

def compute_phash(img):
    """
    Computes a 64-bit perceptual hash (DCT pHash) as a single Python integer.
    """
    if img is None:
        return None
    resized = cv2.resize(img, (32, 32), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if len(resized.shape) == 3 else resized
    dct = cv2.dct(np.float32(gray))
    dct_low = dct[:8, :8]
    med = np.median(dct_low)
    bits = (dct_low > med).flatten()
    
    # Pack 64 boolean bits into a single integer
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return val

def compute_dual_phash(img):
    """
    Returns (h_orig, h_flip) as two 64-bit integers for horizontal flip detection.
    """
    if img is None:
        return None, None
    h_orig = compute_phash(img)
    img_flipped = cv2.flip(img, 1)
    h_flip = compute_phash(img_flipped)
    return h_orig, h_flip

def hamming_dist(h1, h2):
    """
    Calculates Hamming distance in O(1) using hardware CPU POPCNT instruction.
    """
    if h1 is None or h2 is None:
        return 64
    return (h1 ^ h2).bit_count()

def match_hashes(h_cand, h_ref_orig, h_ref_flip=None, max_dist=6):
    """
    Matches candidate hash against reference hash (and its flipped counterpart).
    """
    if h_cand is None or h_ref_orig is None:
        return False, 64, 0.0, False
        
    d_orig = (h_cand ^ h_ref_orig).bit_count()
    best_dist = d_orig
    is_flipped = False
    
    if h_ref_flip is not None:
        d_flip = (h_cand ^ h_ref_flip).bit_count()
        if d_flip < best_dist:
            best_dist = d_flip
            is_flipped = True
            
    is_match = (best_dist <= max_dist)
    similarity = round((1.0 - best_dist / 64.0) * 100.0, 1)
    return is_match, best_dist, similarity, is_flipped
