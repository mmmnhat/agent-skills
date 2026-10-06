#!/usr/bin/env python3
"""
Pacing Editor CLI (v2.0 W-Curve & Studio 5-Track Edition)
High-retention sequencing, psychological W-Curve reordering,
hard fast-cut trimming, and automated Studio 5-Track sound design.
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
    parser = argparse.ArgumentParser(description="Pacing-Editor: High-Retention Sequencing & Sound Design Engine (v2.0)")
    parser.add_argument("--scenes-json", "-s", help="Path to scenes_context.json from clean-cut / clip-inspector")
    parser.add_argument("--input-dir", "-i", help="Directory of video clips to assemble")
    parser.add_argument("--name", default="Pacing_Master_Sequence", help="Target Sequence Name")
    parser.add_argument("--platform", default="reels_shorts", choices=["reels_shorts", "landscape_youtube"], help="Target export platform")
    parser.add_argument("--mode", default="sequential", choices=["sequential", "w-curve"], help="Sequencing mode: sequential (chronological) or w-curve (narrative retention)")
    parser.add_argument("--target-duration", "-t", type=float, default=None, help="Target total sequence duration in seconds (e.g. 30, 45, 60)")
    parser.add_argument("--cut-mode", default="fast-cut", choices=["fast-cut", "ramp"], help="Trimming mode: hard fast-cut or speed ramp")
    parser.add_argument("--no-sfx", action="store_true", help="Disable transition & climax SFX placement")
    parser.add_argument("--no-bgm", action="store_true", help="Disable BGM placement")
    parser.add_argument("--premiere-plan", action="store_true", help="Generate Premiere Pro MCP execution plan JSON")
    parser.add_argument("--render", action="store_true", help="Render standalone stitched master video via FFmpeg")
    parser.add_argument("--output", "-o", help="Output path for master video or manifest")

    args = parser.parse_args()

    input_source = args.scenes_json or args.input_dir
    if not input_source:
        parser.print_help()
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"🎬 [Pacing-Editor v2.0] Mode: '{args.mode.upper()}' | Trimming: '{args.cut_mode.upper()}'")
    if args.target_duration:
        print(f"⏱️ Target Duration: {args.target_duration}s")
    print(f"=======================================================")

    manifest = generate_pacing_plan(
        scenes_input=input_source,
        sequence_name=args.name,
        platform=args.platform,
        mode=args.mode,
        target_duration=args.target_duration,
        cut_mode=args.cut_mode,
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

    print(f"\n📊 [Pacing Blueprint Summary]")
    print(f"  ✓ Manifest saved: {manifest_file.name}")
    print(f"  ✓ Total Clips on V1: {len(manifest['tracks']['V1'])}")
    print(f"  ✓ Total Incident Bundles: {manifest.get('total_incident_bundles', len(manifest['tracks']['V1']))}")
    print(f"  ✓ Native Audio on A1: {len(manifest['tracks']['A1'])} clips")
    print(f"  ✓ Track A2: [RESERVED EXCLUSIVELY FOR VOICEOVER] (Clean)")
    print(f"  ✓ Transition SFX on A3: {len(manifest['tracks']['A3'])} assets")
    print(f"  ✓ Climax SFX on A4: {len(manifest['tracks']['A4'])} assets")
    print(f"  ✓ Ducked BGM on A5: {'Yes (-12dB Ducking)' if manifest['tracks']['A5'] else 'No'}")
    print(f"  ✓ Final Sequence Duration: {manifest['total_duration_seconds']}s")

    # Display W-Curve distribution if in w-curve mode
    if args.mode == "w-curve":
        print(f"\n🌊 [W-Curve Psychological Narrative Distribution]:")
        for sc in manifest["tracks"]["V1"]:
            role = sc.get("narrative_role", "Action")
            dur = sc.get("duration", 0)
            score = sc.get("interest_score", 0)
            print(f"  • [{role:22s}] {sc['clip_id']} ({dur}s | Score: {score}) -> {Path(sc['file_path']).name}")

    if args.premiere_plan or not args.render:
        actions = generate_premiere_mcp_actions(manifest)
        plan_file = manifest_file.with_name(f"{manifest_file.stem}_premiere_mcp_plan.json")
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(actions, f, indent=2, ensure_ascii=False)
        print(f"\n  ✓ Premiere Pro Studio 5-Track Plan ({len(actions)} actions): {plan_file.name}")

    if args.render:
        render_path = manifest_file.with_name(f"{args.name}_master.mp4")
        print(f"\n[Pacing-Editor] Rendering master sequence via FFmpeg...")
        rendered = render_standalone_master(manifest, render_path)
        print(f"  ✓ Rendered successfully: {rendered}")

    print("\n[Pacing-Editor v2.0 Finished Successfully]\n")

if __name__ == "__main__":
    main()
