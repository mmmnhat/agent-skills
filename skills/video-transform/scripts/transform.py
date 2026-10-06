#!/usr/bin/env python3
"""
Video Transform Engine
Applies geometric distortion (scale / deep crop, micro-rotation, horizontal flip)
and pitch-preserved audio retiming with hardware acceleration (NVENC).
"""
import os
import sys
import json
import random
import functools
import argparse
import subprocess
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "scale_crop_ratio": 0.85,
        "rotate_deg": 2.0,
        "enable_flip": True,
        "speed_range": [0.98, 1.02],
        "preserve_pitch": True,
        "output_dir": "output_transformed",
        "prefix": "remix_",
        "encoder": "auto"
    }

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to save config: {e}")

def load_preset(name):
    p_file = PRESETS_DIR / f"{name}.json"
    if p_file.exists():
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

@functools.lru_cache(maxsize=1)
def get_best_encoder(user_choice="auto"):
    if user_choice != "auto":
        return user_choice
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        out = res.stdout
        if "h264_nvenc" in out:
            return "h264_nvenc"
        if "h264_videotoolbox" in out:
            return "h264_videotoolbox"
        if "h264_amf" in out:
            return "h264_amf"
        if "h264_mf" in out:
            return "h264_mf"
    except Exception:
        pass
    return "libx264"

def transform_single_clip(input_path, output_path, crop_ratio=0.85, rotate_deg=2.0, enable_flip=True, speed=1.02, encoder="auto"):
    encoder_name = get_best_encoder(encoder)
    rad = rotate_deg * 3.14159265 / 180.0
    
    vf_filters = []
    if enable_flip:
        vf_filters.append("hflip")
        
    if abs(rotate_deg) > 0.01:
        vf_filters.append(f"rotate={rad:.5f}:ow=rotw({rad:.5f}):oh=roth({rad:.5f}):fillcolor=black")
        
    # Deep crop with even dimensions for H.264
    vf_filters.append(f"crop=trunc(iw*{crop_ratio:.4f}/2)*2:trunc(ih*{crop_ratio:.4f}/2)*2")
    
    # Speed adjustment
    if abs(speed - 1.0) > 0.005:
        vf_filters.append(f"setpts=PTS/{speed:.4f}")
        
    filter_complex = f"[0:v]{','.join(vf_filters)}[v]"
    
    # Audio pitch-preserving filter
    audio_filter = f"[0:a]atempo={speed:.4f}[a]" if abs(speed - 1.0) > 0.005 else "[0:a]anull[a]"
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-filter_complex", f"{filter_complex};{audio_filter}",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", encoder_name,
        "-preset", "p4" if "nvenc" in encoder_name else "medium",
        "-b:v", "4000k",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path)
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_path

def run_transform(input_target, output_dir=None, prefix=None, preset=None, scale=None, rotate=None, no_flip=False, speed=None):
    cfg = load_config()
    
    # Apply preset if specified
    if preset:
        p_data = load_preset(preset)
        if p_data:
            cfg["scale_crop_ratio"] = p_data.get("crop_ratio", cfg["scale_crop_ratio"])
            cfg["rotate_deg"] = p_data.get("rotate_deg", cfg["rotate_deg"])
            cfg["enable_flip"] = p_data.get("enable_flip", cfg["enable_flip"])
            if "speed" in p_data:
                cfg["speed_range"] = [p_data["speed"], p_data["speed"]]
                
    # Overrides
    if scale is not None:
        cfg["scale_crop_ratio"] = scale
    if rotate is not None:
        cfg["rotate_deg"] = rotate
    if no_flip:
        cfg["enable_flip"] = False
    if speed is not None:
        cfg["speed_range"] = [speed, speed]
    if output_dir:
        cfg["output_dir"] = output_dir
    if prefix:
        cfg["prefix"] = prefix
        
    save_config(cfg)
    
    out_dir = Path(cfg.get("output_dir", "output_transformed"))
    out_dir.mkdir(parents=True, exist_ok=True)
    pfx = cfg.get("prefix", "remix_")
    encoder = get_best_encoder(cfg.get("encoder", "auto"))
    
    crop_r = cfg.get("scale_crop_ratio", 0.85)
    rot_d = cfg.get("rotate_deg", 2.0)
    flip_e = cfg.get("enable_flip", True)
    spd_min, spd_max = cfg.get("speed_range", [0.98, 1.02])
    
    print(f"\n[Video-Transform] Initialized")
    print(f"  • Preset: {preset or 'Custom'}")
    print(f"  • Scale/Crop Ratio: {crop_r} (Crop: {(1-crop_r)*100:.1f}%)")
    print(f"  • Rotation: {rot_d}° | Flip: {'Enabled' if flip_e else 'Disabled'}")
    print(f"  • Speed Shift: {spd_min}x - {spd_max}x (Pitch Preserved)")
    print(f"  • Encoder: {encoder}")
    print(f"  • Destination: {out_dir}")

    target_path = Path(input_target)
    
    # Scenario A: Manifest JSON input
    if target_path.is_file() and target_path.suffix.lower() == ".json":
        print(f"\nProcessing from context manifest: {target_path}")
        with open(target_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        scenes = manifest.get("scenes", [])
        transformed_scenes = []
        
        for idx, sc in enumerate(scenes, start=1):
            src_file = Path(sc["file_path"])
            if not src_file.exists():
                continue
                
            cur_speed = random.uniform(spd_min, spd_max)
            cur_rot = random.choice([-rot_d, rot_d]) if abs(rot_d) > 0.01 else 0.0
            
            out_name = f"{pfx}{src_file.name}"
            out_file = out_dir / out_name
            
            transform_single_clip(
                src_file, out_file,
                crop_ratio=crop_r,
                rotate_deg=cur_rot,
                enable_flip=flip_e,
                speed=cur_speed,
                encoder=encoder
            )
            
            new_sc = dict(sc)
            new_sc["file_name"] = out_name
            new_sc["file_path"] = str(out_file.resolve()).replace("\\", "/")
            new_sc["duration"] = round(sc["duration"] / cur_speed, 2)
            new_sc["transform"] = {
                "crop_ratio": crop_r,
                "rotate_deg": cur_rot,
                "flipped": flip_e,
                "speed": round(cur_speed, 3)
            }
            transformed_scenes.append(new_sc)
            print(f"  ✓ [{idx:02d}] {out_name} (rot={cur_rot}°, spd={cur_speed:.2f}x, Inc #{sc['incident_id']})")
            
        # Save updated manifest
        out_manifest_path = out_dir / "transformed_context.json"
        out_manifest = dict(manifest)
        out_manifest["output_directory"] = str(out_dir.resolve()).replace("\\", "/")
        out_manifest["scenes"] = transformed_scenes
        with open(out_manifest_path, "w", encoding="utf-8") as f:
            json.dump(out_manifest, f, indent=2, ensure_ascii=False)
            
        print(f"\n[Video-Transform Complete] Manifest updated: {out_manifest_path}")
        return str(out_manifest_path)

    # Scenario B: Single Video File
    elif target_path.is_file():
        out_name = f"{pfx}{target_path.name}"
        out_file = out_dir / out_name
        cur_speed = random.uniform(spd_min, spd_max)
        cur_rot = rot_d
        
        transform_single_clip(
            target_path, out_file,
            crop_ratio=crop_r,
            rotate_deg=cur_rot,
            enable_flip=flip_e,
            speed=cur_speed,
            encoder=encoder
        )
        print(f"  ✓ Transformed single clip -> {out_file}")
        return str(out_file)

    # Scenario C: Folder of clips
    elif target_path.is_dir():
        video_exts = {".mp4", ".mov", ".mkv"}
        clips = [f for f in target_path.iterdir() if f.is_file() and f.suffix.lower() in video_exts]
        print(f"\nFound {len(clips)} clips in folder: {target_path}")
        
        results = []
        for idx, c in enumerate(clips, start=1):
            out_name = f"{pfx}{c.name}"
            out_file = out_dir / out_name
            cur_speed = random.uniform(spd_min, spd_max)
            cur_rot = random.choice([-rot_d, rot_d]) if abs(rot_d) > 0.01 else 0.0
            
            transform_single_clip(
                c, out_file,
                crop_ratio=crop_r,
                rotate_deg=cur_rot,
                enable_flip=flip_e,
                speed=cur_speed,
                encoder=encoder
            )
            results.append(str(out_file))
            print(f"  ✓ [{idx:02d}] {out_name} (rot={cur_rot}°, spd={cur_speed:.2f}x)")
            
        print(f"\n[Video-Transform Complete] {len(results)} clips transformed in {out_dir}")
        return str(out_dir)
        
    else:
        raise FileNotFoundError(f"Target path not found: {input_target}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Transform: Anti-Fingerprint Geometric & Speed Transformation")
    parser.add_argument("target", help="Input clip file, directory of clips, or scenes_context.json")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory")
    parser.add_argument("-p", "--prefix", default=None, help="Prefix for transformed filenames (default: remix_)")
    parser.add_argument("--preset", choices=["subtle", "standard", "aggressive"], default=None, help="Transformation preset")
    parser.add_argument("--scale", type=float, default=None, help="Crop ratio (e.g. 0.85 = 15%% crop)")
    parser.add_argument("--rotate", type=float, default=None, help="Rotation angle in degrees (e.g. 2.0)")
    parser.add_argument("--no-flip", action="store_true", help="Disable horizontal flip")
    parser.add_argument("--speed", type=float, default=None, help="Speed factor (e.g. 1.02)")
    
    args = parser.parse_args()
    run_transform(
        input_target=args.target,
        output_dir=args.output_dir,
        prefix=args.prefix,
        preset=args.preset,
        scale=args.scale,
        rotate=args.rotate,
        no_flip=args.no_flip,
        speed=args.speed
    )
