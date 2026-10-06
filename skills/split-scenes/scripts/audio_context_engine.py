import os
import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Auto-require and self-install dependencies
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import env_bootstrap
except Exception:
    pass

import json
import argparse
import subprocess
import numpy as np
import librosa
from faster_whisper import WhisperModel

def load_audio_fast(path, sr=16000, start_sec=None, dur_sec=None):
    """
    Fast in-memory audio extraction using ffmpeg pipe.
    Decodes directly to mono float32 numpy array.
    """
    cmd = ['ffmpeg', '-nostdin', '-threads', '1']
    if start_sec is not None:
        cmd.extend(['-ss', str(start_sec)])
    if dur_sec is not None:
        cmd.extend(['-t', str(dur_sec)])
    cmd.extend(['-i', path, '-f', 's16le', '-ac', '1', '-ar', str(sr), '-'])
    
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    raw, _ = p.communicate()
    if len(raw) == 0:
        return np.array([], dtype=np.float32), sr
    y = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return y, sr

def snap_cut_boundary(video_or_audio_path, t_visual, fps=23.976, sr=44100, window_sec=0.25):
    """
    Audio-Assisted Zero-Cut Snapping (Mục 4):
    Finds the optimal natural cut point within +/- window_sec of t_visual:
    1. Evaluates short-term RMS energy dips.
    2. Snaps to the exact zero-crossing point in the local minimum valley.
    Avoids clipping voice syllables or lingering crash reverb, and eliminates DC pops.
    """
    t_start = max(0.0, t_visual - window_sec)
    t_dur = window_sec * 2.0
    
    y, _ = load_audio_fast(video_or_audio_path, sr=sr, start_sec=t_start, dur_sec=t_dur)
    f_visual = int(round(t_visual * fps))
    
    if len(y) < int(sr * 0.05):
        return {
            'snapped_time': t_visual,
            'snapped_frame': f_visual,
            'shift_ms': 0.0,
            'shift_frames': 0,
            'status': 'fallback_too_short'
        }
    
    hop = int(sr * 0.005) # 5ms hop
    frame_len = int(sr * 0.015) # 15ms window
    rms = librosa.feature.rms(y=y, frame_length=frame_len, hop_length=hop)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop) + t_start
    
    valid_mask = np.abs(times - t_visual) <= (window_sec * 0.85)
    if not np.any(valid_mask):
        valid_mask = np.ones(len(times), dtype=bool)
        
    valid_times = times[valid_mask]
    valid_rms = rms[valid_mask]
    min_idx = np.argmin(valid_rms)
    best_time = valid_times[min_idx]
    
    best_sample_idx = int((best_time - t_start) * sr)
    search_r = range(max(0, best_sample_idx - 250), min(len(y) - 1, best_sample_idx + 250))
    zc = [s for s in search_r if y[s] * y[s+1] <= 0]
    if zc:
        closest = min(zc, key=lambda s: abs(s - best_sample_idx))
        snapped_t = t_start + closest / float(sr)
    else:
        snapped_t = best_time
        
    snapped_f = int(round(snapped_t * fps))
    shift_ms = round((snapped_t - t_visual) * 1000.0, 1)
    shift_frames = snapped_f - f_visual
    
    return {
        'snapped_time': round(snapped_t, 3),
        'snapped_frame': snapped_f,
        'shift_ms': shift_ms,
        'shift_frames': shift_frames,
        'rms_before': round(float(rms[np.argmin(np.abs(times - t_visual))]), 5),
        'rms_snapped': round(float(valid_rms[min_idx]), 5),
        'status': 'snapped_ok'
    }

def classify_audio_track(clip_path, whisper_model=None, sr=16000, fps=23.976):
    """
    6-Class Standard Audio Classification:
    1. khong_am_thanh (Mute/Silence)
    2. voice_nguoi_that (Real Human Voice / Screams / Reactions)
    3. voice_ai (AI / Synthetic TTS / Robot Narrator)
    4. co_am_thanh_sfx (SFX / Impacts / Foley / Mechanical only)
    5. chi_co_nhac (Music / BGM only)
    6. hon_hop (Mixed: Music+Voice, Music+SFX, Voice+SFX)
    """
    y, _ = load_audio_fast(clip_path, sr=sr)
    dur = len(y) / sr if len(y) > 0 else 0
    
    if len(y) == 0:
        return {
            'audio_type': 'khong_am_thanh',
            'has_speech': False,
            'speech_text': '',
            'speech_language': '',
            'sound_class': 'silent_track',
            'mood': 'mute',
            'peak_impact_time_sec': 0.0,
            'peak_impact_frame_relative': 0,
            'loudness_peak_db': -100.0,
            'dynamic_range': 1.0,
            'harmonic_ratio': 0.0,
            'percussive_ratio': 0.0
        }
    
    rms = librosa.feature.rms(y=y)[0]
    peak_rms = float(np.max(rms)) if len(rms) > 0 else 0.0
    mean_rms = float(np.mean(rms)) if len(rms) > 0 else 0.0
    peak_db = round(float(librosa.amplitude_to_db([peak_rms])[0]), 1) if peak_rms > 0 else -100.0
    dynamic_range = round(peak_rms / max(1e-5, mean_rms), 2)
    
    # 1. Silence check
    if mean_rms < 0.005 or peak_db < -42.0:
        return {
            'audio_type': 'khong_am_thanh',
            'has_speech': False,
            'speech_text': '',
            'speech_language': '',
            'sound_class': 'silence_mute',
            'mood': 'mute',
            'peak_impact_time_sec': 0.0,
            'peak_impact_frame_relative': 0,
            'loudness_peak_db': peak_db,
            'dynamic_range': dynamic_range,
            'harmonic_ratio': 0.0,
            'percussive_ratio': 0.0
        }

    # 2. HPSS & Rhythm
    y_harm, y_perc = librosa.effects.hpss(y)
    tot_energy = np.mean(y**2) + 1e-9
    harm_ratio = round(float(np.mean(y_harm**2) / tot_energy), 2)
    perc_ratio = round(float(np.mean(y_perc**2) / tot_energy), 2)
    
    tempo, beats = librosa.beat.beat_track(y=y_perc, sr=sr)
    tempo_val = float(np.squeeze(tempo)) if len(np.atleast_1d(tempo)) > 0 else 0.0
    beat_count = len(beats)
    has_rhythm = (beat_count >= int(dur * 0.75)) and (55 <= tempo_val <= 210)
    
    # 3. Peak Impact Onset
    onset_strengths = librosa.onset.onset_strength(y=y, sr=sr)
    peak_onset_frame = int(np.argmax(onset_strengths))
    peak_onset_time = round(float(librosa.frames_to_time([peak_onset_frame], sr=sr)[0]), 2)
    impact_frame_relative = int(round(peak_onset_time * fps))
    
    # 4. Speech transcription & VAD
    has_speech = False
    speech_text = ""
    speech_lang = ""
    speech_dur = 0.0
    lang_prob = 0.0
    
    if whisper_model is not None and dur >= 0.8:
        try:
            segments, info = whisper_model.transcribe(clip_path, vad_filter=True)
            valid_texts = []
            for s in segments:
                t = s.text.strip()
                if t and not t.startswith('[') and not t.startswith('(') and t not in ['♪', '...']:
                    valid_texts.append(t)
                    speech_dur += (s.end - s.start)
            if valid_texts:
                speech_text = " ".join(valid_texts)
                speech_lang = info.language
                lang_prob = info.language_probability
                has_speech = (len(speech_text) >= 4 and speech_dur >= 0.4) or (speech_dur >= 0.25 * dur)
        except Exception:
            pass

    # 5. Audio Type Decision Tree
    if has_speech:
        is_bgm = (harm_ratio >= 0.38 and has_rhythm)
        is_heavy_sfx = (dynamic_range >= 3.6 or perc_ratio >= 0.42)
        
        if is_bgm or is_heavy_sfx:
            audio_type = 'hon_hop'
            sound_class = 'mixed_voice_bgm' if is_bgm else 'mixed_voice_impact'
            mood = 'active'
        else:
            # Distinguish AI Voice vs Real Human Voice
            try:
                f0, voiced_flag, _ = librosa.pyin(y, fmin=60, fmax=500, sr=sr)
                v_f0 = f0[voiced_flag] if voiced_flag is not None else []
                std_f0 = float(np.std(v_f0)) if len(v_f0) > 10 else 0.0
            except Exception:
                std_f0 = 35.0
                
            shout_keywords = ['oh', 'shit', 'watch', 'throw', 'whoa', 'no', 'god', 'hey', 'stop', 'damn', 'wtf', 'fuck']
            has_shout = any(w in speech_text.lower() for w in shout_keywords)
            
            if std_f0 > 45.0 or dynamic_range >= 2.5 or has_shout:
                audio_type = 'voice_nguoi_that'
                sound_class = 'human_speech_reaction'
                mood = 'dramatic' if has_shout else 'neutral'
            elif std_f0 < 28.0 and lang_prob > 0.90 and len(speech_text.split()) >= 4:
                audio_type = 'voice_ai'
                sound_class = 'synthetic_tts_narration'
                mood = 'informative'
            else:
                audio_type = 'voice_nguoi_that'
                sound_class = 'human_speech_dialogue'
                mood = 'neutral'
    else:
        # No speech
        is_music = (harm_ratio >= 0.40 and (has_rhythm or perc_ratio < 0.25))
        is_sfx = (dynamic_range >= 2.2 or perc_ratio >= 0.32 or harm_ratio < 0.32)
        
        if is_music and dynamic_range >= 3.5:
            audio_type = 'hon_hop'
            sound_class = 'music_with_heavy_impact'
            mood = 'intense'
        elif is_music:
            audio_type = 'chi_co_nhac'
            sound_class = 'bgm_melody_track'
            mood = 'melodic'
        else:
            audio_type = 'co_am_thanh_sfx'
            if dynamic_range >= 3.5:
                sound_class = 'shocking_crash_foley'
                mood = 'shocking'
            elif perc_ratio > 0.45:
                sound_class = 'percussive_impact_thud'
                mood = 'funny'
            else:
                sound_class = 'ambient_machinery_foley'
                mood = 'ambient'

    return {
        'audio_type': audio_type,
        'has_speech': has_speech,
        'speech_text': speech_text,
        'speech_language': speech_lang,
        'sound_class': sound_class,
        'mood': mood,
        'peak_impact_time_sec': peak_onset_time,
        'peak_impact_frame_relative': impact_frame_relative,
        'loudness_peak_db': peak_db,
        'dynamic_range': dynamic_range,
        'harmonic_ratio': harm_ratio,
        'percussive_ratio': perc_ratio
    }

def process_database(db_path, out_db_path=None, whisper_model_size="tiny", skip_whisper=False):
    db = json.load(open(db_path))
    out_db_path = out_db_path or db_path
    
    print(f"\n==================================================")
    print(f"  AUDIO CONTEXT INTELLIGENCE & 6-CLASS CLASSIFIER")
    print(f"==================================================")
    print(f"Target DB: {db_path} ({len(db)} clips)")
    
    whisper_model = None
    if not skip_whisper:
        print(f"Loading Whisper model ({whisper_model_size}) on CPU...")
        try:
            whisper_model = WhisperModel(whisper_model_size, device="cpu", compute_type="int8")
            print("Whisper ready!")
        except Exception as e:
            print(f"Whisper initialization warning: {e}")
            
    stats = {
        'voice_nguoi_that': 0,
        'voice_ai': 0,
        'khong_am_thanh': 0,
        'co_am_thanh_sfx': 0,
        'chi_co_nhac': 0,
        'hon_hop': 0
    }
    
    enriched = 0
    for idx, clip in enumerate(db):
        fpath = clip.get('file_path')
        if not fpath or not os.path.exists(fpath):
            continue
            
        res = classify_audio_track(fpath, whisper_model=whisper_model)
        
        clip['audio_context'] = res
        atype = res['audio_type']
        stats[atype] = stats.get(atype, 0) + 1
        enriched += 1
        
        if (idx + 1) % 25 == 0 or (idx + 1) == len(db):
            print(f"Processed {idx + 1}/{len(db)} clips... (Current stats: {stats})")
            
    with open(out_db_path, 'w') as f:
        json.dump(db, f, indent=2)
        
    print(f"\n✅ Finished! Enriched {enriched} clips in: {out_db_path}")
    print("\nSummary Statistics by Audio Type:")
    for k, v in stats.items():
        pct = (v / max(1, enriched)) * 100
        print(f"  - {k:<20}: {v:>4} clips ({pct:>5.1f}%)")
        
    return db, stats

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Audio Context Intelligence & Classification")
    parser.add_argument("--db", required=True, help="Path to scene_db.json")
    parser.add_argument("--output", default=None, help="Output path (default: overwrite db)")
    parser.add_argument("--no_whisper", action="store_true", help="Disable Whisper transcription")
    parser.add_argument("--model", default="tiny", help="Whisper model size (tiny, base, small)")
    parser.add_argument("--test_snap", default=None, help="Video path to test zero-cut snapping")
    parser.add_argument("--t", type=float, default=23.315, help="Timestamp for test_snap")
    args = parser.parse_args()
    
    if args.test_snap:
        snap_res = snap_cut_boundary(args.test_snap, args.t)
        print("Snap Result:", json.dumps(snap_res, indent=2))
    else:
        process_database(args.db, out_db_path=args.output, whisper_model_size=args.model, skip_whisper=args.no_whisper)
