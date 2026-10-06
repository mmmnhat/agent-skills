#!/usr/bin/env python3
"""
Pacing Editor CLI
High-retention video sequencing, speed ramping (Optical Flow), and automated SFX/BGM sound design.
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
    from pacing_engine import generate_pacing_plan
    from timeline_assembler import generate_premiere_mcp_actions, render_standalone_master
except ImportError:
    from .pacing_engine import generate_pacing_plan
    from .timeline_assembler import generate_premiere_mcp_actions, render_standalone_master

def main():
    parser = argparse.ArgumentParser(description="Pacing-Editor: High-Retention Sequencing & Sound Design Engine")
    parser.add_argument("--scenes-json", "-s", help="Path to scenes_context.json from clean-cut / clip-inspector")
    parser.add_argument("--input-dir", "-i", help="Directory of video clips to assemble")
    parser.add_argument("--name", default="Pacing_Master_Sequence", help="Target Sequence Name")
    parser.add_argument("--platform", default="reels_shorts", choices=["reels_shorts", "landscape_youtube"], help="Target export platform")
    parser.add_argument("--no-sfx", action="store_true", help="Disable transition & climax SFX placement")
    parser.add_argument("--no-bgm", action="store_true", help="Disable BGM placement")
    parser.add_argument("--premiere-plan", action="store_true", help="Generate Premiere Pro MCP execution plan JSON")
    parser.add_argument("--render", action="store_true", help="Render standalone stitched master video via FFmpeg NVENC")
    parser.add_argument("--output", "-o", help="Output path for master video or manifest")

    args = parser.parse_args()

    input_source = args.scenes_json or args.input_dir
    if not input_source:
        parser.print_help()
        sys.exit(1)

    print(f"\n[Pacing-Editor] Analyzing scenes and generating pacing blueprint...")
    manifest = generate_pacing_plan(
        scenes_input=input_source,
        sequence_name=args.name,
        platform=args.platform,
        add_sfx=not args.no_sfx,
        add_bgm=not args.no_bgm
    )

    out_base = Path(args.output or (Path(input_source).parent if Path(input_source).is_file() else Path(input_source)))
    if out_base.is_dir():
        manifest_file = out_base / f"{args.name}_manifest.json"
    else:
        manifest_file = out_base.with_suffix(".json")

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"  [+] Pacing Manifest saved: {manifest_file}")
    print(f"  [+] Total Clips on V1: {len(manifest['tracks']['V1'])}")
    print(f"  [+] Total SFX on A2: {len(manifest['tracks']['A2'])}")
    print(f"  [+] BGM on A3: {'Yes' if manifest['tracks']['A3'] else 'No'}")
    print(f"  [+] Total Sequence Duration: {manifest['total_duration_seconds']}s")

    if args.premiere_plan or not args.render:
        actions = generate_premiere_mcp_actions(manifest)
        plan_file = manifest_file.with_name(f"{manifest_file.stem}_premiere_mcp_plan.json")
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(actions, f, indent=2, ensure_ascii=False)
        print(f"  [+] Premiere Pro MCP Plan generated ({len(actions)} actions): {plan_file}")

    if args.render:
        render_path = manifest_file.with_name(f"{args.name}_master.mp4")
        print(f"\n[Pacing-Editor] Rendering master sequence via FFmpeg NVENC...")
        rendered = render_standalone_master(manifest, render_path)
        print(f"  [+] Rendered successfully: {rendered}")

    print("\n[Pacing-Editor Finished]")

if __name__ == "__main__":
    main()
