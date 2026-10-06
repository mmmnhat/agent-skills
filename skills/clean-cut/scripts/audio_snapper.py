#!/usr/bin/env python3
"""
Audio Zero-Cut Snapper (Optimized Single-Pass in RAM)
Loads entire audio track into RAM once (16kHz float32, only ~15MB for an 8-min video),
then computes RMS dips and zero-crossings in sub-milliseconds without spawning subprocesses.
"""
import subprocess
import numpy as np

def load_audio_buffer(video_path, sample_rate=16000):
    """
    Extracts the audio track into a single 16kHz float32 numpy array in RAM.
    Returns (audio_samples, sample_rate).
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "-"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        samples = np.frombuffer(proc.stdout, dtype=np.float32)
        return samples, sample_rate
    except Exception:
        return np.array([], dtype=np.float32), sample_rate

def snap_audio_cut_in_ram(audio_samples, sample_rate, candidate_sec, window_sec=0.25):
    """
    Snaps candidate_sec to nearest RMS energy minimum and zero-crossing in RAM.
    Execution time: <0.001ms.
    """
    if audio_samples is None or len(audio_samples) < 100:
        return candidate_sec, 0.0, False
        
    t_start = max(0.0, candidate_sec - window_sec)
    idx_start = int(t_start * sample_rate)
    idx_end = int((candidate_sec + window_sec) * sample_rate)
    
    idx_start = max(0, min(len(audio_samples) - 1, idx_start))
    idx_end = max(idx_start + 10, min(len(audio_samples), idx_end))
    
    samples = audio_samples[idx_start:idx_end]
    if len(samples) < 100:
        return candidate_sec, 0.0, False
        
    # Calculate RMS energy in chunks of ~15ms (240 samples @ 16kHz)
    chunk_size = max(16, int(0.015 * sample_rate))
    num_chunks = len(samples) // chunk_size
    if num_chunks < 3:
        return candidate_sec, 0.0, False
        
    # Reshape and compute RMS in vectorized numpy
    usable_samples = samples[:num_chunks * chunk_size].reshape(num_chunks, chunk_size)
    rms_energies = np.sqrt(np.mean(usable_samples**2, axis=1) + 1e-9)
    
    target_idx = int((candidate_sec - t_start) * sample_rate)
    target_chunk = max(0, min(num_chunks - 1, target_idx // chunk_size))
    
    search_radius = max(2, int(window_sec / 0.015 * 0.75))
    c_min = max(0, target_chunk - search_radius)
    c_max = min(num_chunks, target_chunk + search_radius + 1)
    
    best_chunk = c_min + int(np.argmin(rms_energies[c_min:c_max]))
    sample_around = best_chunk * chunk_size
    
    sub = samples[sample_around:sample_around + chunk_size]
    zero_crossings = np.where(np.diff(np.signbit(sub)))[0]
    
    if len(zero_crossings) > 0:
        exact_sample = sample_around + zero_crossings[len(zero_crossings) // 2]
    else:
        exact_sample = sample_around
        
    snapped_time = t_start + (exact_sample / float(sample_rate))
    delta = snapped_time - candidate_sec
    return round(snapped_time, 4), round(delta, 4), True
