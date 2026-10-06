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
    from timeline_assembler import generate_premiere_mcp_actions, generate_fcp_xml, render_standalone_master
except ImportError:
    from .pacing_engine import generate_pacing_plan
    from .timeline_assembler import generate_premiere_mcp_actions, generate_fcp_xml, render_standalone_master

def interactive_setup():
    print("\n=======================================================")
    print("🌊 [PACING-EDITOR] MENU CẤU HÌNH DỰNG TIMELINE (INTERACTIVE)")
    print("=======================================================")
    
    # 1. Source
    candidates = [
        "output_clean_cut/manifests/scenes_context.json",
        "output_clean_cut/scenes_context.json",
        "output_clean_cut/scenes"
    ]
    def_source = ""
    for c in candidates:
        if os.path.exists(c):
            def_source = c
            break
            
    prompt_str = f" [{def_source}]" if def_source else ""
    src_in = input(f"📋 Đường dẫn scenes_context.json hoặc thư mục footage{prompt_str}: ").strip().strip('"').strip("'")
    source = src_in if src_in else def_source
    while not source or not os.path.exists(source):
        print(f"  ! Lỗi: Không tìm thấy nguồn footage '{source}'.")
        src_in = input("📋 Nhập lại đường dẫn: ").strip().strip('"').strip("'")
        source = src_in
        
    # 2. Sequence Mode
    print("\n🎬 Tuỳ chọn Sequence Premiere:")
    print("   1. active    : Dùng sequence đang mở sẵn trong Premiere (Mặc định)")
    print("   2. new_clone : Tạo sequence mới sạch (Clone từ sequence hiện có - Khuyên dùng)")
    print("   3. preset    : Tạo sequence theo Preset chuẩn (.sqpreset)")
    seq_opt = input("   Lựa chọn [1/2/3, mặc định 1]: ").strip()
    
    seq_mode_prem = "active"
    preset_path = None
    if seq_opt == "2":
        seq_mode_prem = "new_clone"
        name_in = input("🎬 Tên Sequence mới [W_Curve_Master]: ").strip()
        name = name_in if name_in else "W_Curve_Master"
    elif seq_opt == "3":
        seq_mode_prem = "preset"
        name_in = input("🎬 Tên Sequence [W_Curve_Master]: ").strip()
        name = name_in if name_in else "W_Curve_Master"
        print("   Chọn preset:")
        print("     1. HD 1080p 59.94 fps (Khuyên dùng cho Reels/Shorts/Action)")
        print("     2. HD 1080p 29.97 fps")
        print("     3. Đường dẫn custom .sqpreset")
        p_opt = input("     Lựa chọn [1/2/3, mặc định 1]: ").strip()
        if p_opt == "2":
            preset_path = "/Applications/Adobe Premiere Pro 2025/Adobe Premiere Pro 2025.app/Contents/Settings/SequencePresets/HD 1080p/HD 1080p 29.97 fps.sqpreset"
        elif p_opt == "3":
            preset_path = input("     Nhập đường dẫn .sqpreset: ").strip().strip('"').strip("'")
        else:
            preset_path = "/Applications/Adobe Premiere Pro 2025/Adobe Premiere Pro 2025.app/Contents/Settings/SequencePresets/HD 1080p/HD 1080p 59.94 fps.sqpreset"
    else:
        seq_mode_prem = "active"
        name_in = input("🎬 Tên Sequence hiển thị [Active_Sequence]: ").strip()
        name = name_in if name_in else "Active_Sequence"

    # 3. Dedicated Footage Bin
    bin_in = input("\n📁 Tên Bin lưu trữ footage trong Premiere [Scenes]: ").strip()
    bin_name = bin_in if bin_in else "Scenes"

    # 4. Pacing Narrative Mode
    print("\n🎯 Chế độ dựng nhịp (Pacing Mode):")
    print("   1. w-curve    : Đảo cảnh nhịp tâm lý W-Curve (Hook -> Context -> Climax -> Ending)")
    print("   2. sequential : Giữ nguyên thứ tự thời gian gốc")
    mode_in = input("   Lựa chọn [1/2, mặc định 1]: ").strip()
    mode = "sequential" if mode_in == "2" else "w-curve"
    
    # 5. Target Duration
    dur_in = input("\n⏱️ Thời lượng mục tiêu (giây, VD: 30, 45, 60. Enter để lấy hết): ").strip()
    try:
        target_dur = float(dur_in) if dur_in else None
    except ValueError:
        target_dur = None
        
    # 6. Output options
    plan_in = input("\n🚀 Sinh Premiere Pro MCP Plan? [Y/n]: ").strip().lower()
    prem_plan = (plan_in not in ["n", "no"])
    
    render_in = input("🎥 Render luôn master video qua FFmpeg? [y/N]: ").strip().lower()
    do_render = (render_in in ["y", "yes"])
    
    print("=======================================================\n")
    return source, name, seq_mode_prem, preset_path, bin_name, mode, target_dur, prem_plan, do_render

def main():
    parser = argparse.ArgumentParser(description="Pacing-Editor: High-Retention Sequencing & Sound Design Engine (v2.0)")
    parser.add_argument("--scenes-json", "-s", help="Path to scenes_context.json from clean-cut / clip-inspector")
    parser.add_argument("--input-dir", "-d", help="Directory of video clips to assemble")
    parser.add_argument("--name", default="Pacing_Master_Sequence", help="Target Sequence Name")
    parser.add_argument("--seq-mode", default="active", choices=["active", "new_clone", "preset"], help="Sequence creation strategy: active, new_clone, or preset")
    parser.add_argument("--preset-path", default=None, help="Path to installed Premiere .sqpreset (for --seq-mode preset)")
    parser.add_argument("--bin-name", default="Scenes", help="Destination bin name for imported footage inside Premiere")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive configuration wizard")
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
    seq_name = args.name
    seq_mode = args.mode
    seq_target_dur = args.target_duration
    seq_prem_plan = args.premiere_plan
    seq_render = args.render
    seq_mode_prem = args.seq_mode
    preset_path = args.preset_path
    bin_name = args.bin_name

    if not input_source or args.interactive:
        input_source, seq_name, seq_mode_prem, preset_path, bin_name, seq_mode, seq_target_dur, seq_prem_plan, seq_render = interactive_setup()

    print(f"\n=======================================================")
    print(f"🎬 [Pacing-Editor v2.0] Mode: '{seq_mode.upper()}' | Trimming: '{args.cut_mode.upper()}'")
    if seq_target_dur:
        print(f"⏱️ Target Duration: {seq_target_dur}s")
    print(f"=======================================================")

    manifest = generate_pacing_plan(
        scenes_input=input_source,
        sequence_name=seq_name,
        platform=args.platform,
        mode=seq_mode,
        target_duration=seq_target_dur,
        cut_mode=args.cut_mode,
        add_sfx=not args.no_sfx,
        add_bgm=not args.no_bgm
    )

    out_base = Path(args.output or (Path(input_source).parent if Path(input_source).is_file() else Path(input_source)))
    if out_base.is_dir():
        manifests_dir = out_base / "manifests" if (out_base / "manifests").exists() or (out_base / "scenes").exists() else out_base
        manifests_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = manifests_dir / f"{args.name}_manifest.json"
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
    if seq_mode == "w-curve":
        print(f"\n🌊 [W-Curve Psychological Narrative Distribution]:")
        for sc in manifest["tracks"]["V1"]:
            role = sc.get("narrative_role", "Action")
            dur = sc.get("duration", 0)
            score = sc.get("interest_score", 0)
            print(f"  • [{role:22s}] {sc['clip_id']} ({dur}s | Score: {score}) -> {Path(sc['file_path']).name}")

    if seq_prem_plan or not seq_render:
        actions = generate_premiere_mcp_actions(
            pacing_manifest=manifest,
            sequence_mode=seq_mode_prem,
            sequence_name=seq_name,
            preset_path=preset_path,
            bin_name=bin_name
        )
        plan_file = manifest_file.with_name(f"{manifest_file.stem}_premiere_mcp_plan.json")
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(actions, f, indent=2, ensure_ascii=False)
        print(f"\n  ✓ Premiere Pro Batch MCP Plan ({len(actions)} atomic calls): {plan_file.name}")

        xml_file = manifest_file.with_name(f"{manifest_file.stem}.xml")
        generate_fcp_xml(manifest, xml_file)
        print(f"  ✓ Premiere Pro FCP7 XML Sequence (Single-shot import): {xml_file.name}")

    if seq_render:
        exports_dir = out_base / "exports" if out_base.is_dir() else out_base.parent / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        render_path = exports_dir / f"{seq_name}_master.mp4"
        print(f"\n[Pacing-Editor] Rendering master sequence via FFmpeg...")
        rendered = render_standalone_master(manifest, render_path)
        print(f"  ✓ Rendered successfully: {rendered}")

    print("\n[Pacing-Editor v2.0 Finished Successfully]\n")

if __name__ == "__main__":
    main()
