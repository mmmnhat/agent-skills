#!/usr/bin/env python3
"""
Content Shield CLI
Visual obscuration and watermark/logo shielding via OpenCV Tracking & Premiere Pro V2 Blur.
"""
import os
import sys
import json
import argparse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from shield_tracker import build_shield_manifest, resolve_zone_box
    from shield_renderer import render_shielded_video, generate_shield_preview
    from premiere_shield_bridge import save_premiere_plan
except ImportError:
    from .shield_tracker import build_shield_manifest, resolve_zone_box
    from .shield_renderer import render_shielded_video, generate_shield_preview
    from .premiere_shield_bridge import save_premiere_plan

def parse_roi(roi_str):
    if not roi_str:
        return None
    try:
        parts = [float(p.strip()) for p in roi_str.split(",")]
        if len(parts) == 4:
            return parts
    except Exception:
        pass
    return None

def process_single_video(video_path, args):
    v_path = Path(video_path).resolve()
    print(f"\n[Content-Shield] Processing: {v_path.name}")
    
    custom_roi = parse_roi(args.roi)
    is_static = not args.track

    manifest = build_shield_manifest(
        video_path=str(v_path),
        zone=args.zone,
        mode=args.mode,
        is_static=is_static,
        custom_box=custom_roi,
        auto_detect=args.auto_pinpoint
    )

    job = manifest["shield_jobs"][0]
    box = job["initial_box"]
    print(f"  [+] Zone: {args.zone} | Mode: {args.mode} | Box: {box}")

    # 1. Preview
    if args.preview or not (args.render or args.premiere_plan):
        preview_out = v_path.with_name(f"{v_path.stem}_shield_preview.jpg")
        generate_shield_preview(str(v_path), box, str(preview_out))
        print(f"  [+] Preview generated: {preview_out}")

    # 2. Render
    if args.render:
        out_dir = Path(args.output) if args.output else v_path.parent / "shielded"
        out_file = out_dir / f"{v_path.stem}_shielded.mp4"
        print(f"  [+] Rendering shielded video via FFmpeg ({args.mode})...")
        rendered = render_shielded_video(str(v_path), str(out_file), mode=args.mode, box=box)
        print(f"  [+] Rendered successfully: {rendered}")

    # 3. Premiere Plan
    if args.premiere_plan:
        plan_out = v_path.with_name(f"{v_path.stem}_premiere_shield_plan.json")
        save_premiere_plan(manifest, str(plan_out))
        print(f"  [+] Premiere Pro MCP Plan saved: {plan_out}")

    # Save manifest
    manifest_out = v_path.with_name(f"{v_path.stem}_shield_manifest.json")
    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  [+] Shield Manifest saved: {manifest_out}")

    return manifest

def main():
    parser = argparse.ArgumentParser(description="Content-Shield: Watermark/Logo & Sensitive Content Obscuration Engine")
    parser.add_argument("--input", "-i", help="Target video file or directory of video files")
    parser.add_argument("--scenes-json", help="Path to scenes_context.json from clean-cut / clip-inspector")
    parser.add_argument("--zone", default="top_right", choices=["top_left", "top_right", "bottom_right", "bottom_left", "bottom_center", "custom"], help="Preset zone or 'custom'")
    parser.add_argument("--roi", help="Custom ROI box: 'x,y,w,h' (in pixels or normalized 0.0-1.0)")
    parser.add_argument("--mode", default="delogo", choices=["delogo", "gaussian_blur", "mosaic", "solid_mask"], help="Obscuration method")
    parser.add_argument("--track", action="store_true", help="Enable OpenCV dynamic tracking for moving watermarks/sensitive objects")
    parser.add_argument("--auto-pinpoint", action="store_true", help="Auto-pinpoint static logo boundary via temporal edge variance")
    parser.add_argument("--render", action="store_true", help="Render output video file with mask applied via FFmpeg NVENC")
    parser.add_argument("--preview", action="store_true", help="Generate preview JPEG image showing mask coverage")
    parser.add_argument("--premiere-plan", action="store_true", help="Generate Premiere Pro MCP Adjustment Layer V2 execution plan")
    parser.add_argument("--output", "-o", help="Output directory for rendered files")

    args = parser.parse_args()

    if not args.input and not args.scenes_json:
        parser.print_help()
        sys.exit(1)

    target_files = []
    if args.scenes_json:
        s_path = Path(args.scenes_json).resolve()
        if not s_path.exists():
            print(f"Error: {s_path} not found.")
            sys.exit(1)
        with open(s_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for s in data.get("scenes", []):
            if "clip_path" in s and os.path.exists(s["clip_path"]):
                target_files.append(s["clip_path"])
    elif args.input:
        in_p = Path(args.input).resolve()
        if in_p.is_file():
            target_files.append(str(in_p))
        elif in_p.is_dir():
            for ext in [".mp4", ".mov", ".mkv", ".avi"]:
                target_files.extend([str(p) for p in in_p.glob(f"*{ext}")])

    if not target_files:
        print("No target video files found.")
        sys.exit(1)

    print(f"=== Content-Shield starting for {len(target_files)} video(s) ===")
    for vf in target_files:
        try:
            process_single_video(vf, args)
        except Exception as e:
            print(f"Error processing {vf}: {e}")

    print("\n[Content-Shield Finished]")

if __name__ == "__main__":
    main()
