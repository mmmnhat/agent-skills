#!/usr/bin/env python3
"""
Asset Indexer & Retrieval CLI with "Hỏi và Nhớ" Memory Engine
"""
import sys
import json
import argparse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


try:
    from indexer import index_repository
    from search_engine import search_assets, format_search_results
    from memory_manager import remember_choice, load_memory
except ImportError:
    from .indexer import index_repository
    from .search_engine import search_assets, format_search_results
    from .memory_manager import remember_choice, load_memory

def main():
    parser = argparse.ArgumentParser(description="Asset-Indexer: Multimedia Library with 'Hỏi và Nhớ' Memory Engine")
    parser.add_argument("--scan", action="store_true", help="Scan repository and build/update asset_index.json")
    parser.add_argument("--root", default=None, help="Root directory of asset repository (default: E:\\Video Asset)")
    parser.add_argument("--output", default=None, help="Output path for asset_index.json")
    
    # Search arguments
    parser.add_argument("-q", "--query", default=None, help="Text query, sound description, or emotional vibe")
    parser.add_argument("-c", "--category", default=None, help="Filter by category (SFX, Meme, Music, Footage, Overlay, Vlipsy, Brand)")
    parser.add_argument("-t", "--type", default=None, help="Filter by media type (audio, video, gif, image)")
    parser.add_argument("--max-dur", type=float, default=None, help="Maximum duration in seconds")
    parser.add_argument("--min-dur", type=float, default=None, help="Minimum duration in seconds")
    parser.add_argument("--green-screen", action="store_true", help="Only return green screen / transparent assets")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Number of results to return (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    
    # Memory "Hỏi và Nhớ" arguments
    parser.add_argument("--remember", action="store_true", help="Record user/agent preference pairing")
    parser.add_argument("--intent", default=None, help="Intent tag to remember (e.g. 'action_punch', 'cut_transition')")
    parser.add_argument("--asset", default=None, help="Relative path of chosen asset to remember")
    parser.add_argument("--list-memories", action="store_true", help="List all remembered affinity pairings")

    args = parser.parse_args()

    if args.scan:
        out_file = index_repository(root_dir=args.root, output_path=args.output)
        sys.exit(0)
        
    if args.remember:
        if not args.intent or not args.asset:
            print("Error: --remember requires both --intent and --asset.")
            sys.exit(1)
        remember_choice(args.intent, args.asset)
        print(f"✓ Đã ghi nhớ: Lần sau intent '{args.intent}' sẽ ưu tiên asset: '{args.asset}'")
        sys.exit(0)
        
    if args.list_memories:
        mem = load_memory()
        print(f"=== BẢNG KÝ ỨC ĐÃ GHI NHỚ ('Hỏi và Nhớ') ===")
        print(f"Tổng số liên kết: {mem.get('total_memories', 0)}")
        for intent, records in mem.get("intent_bindings", {}).items():
            print(f"\n  • Intent: '{intent}'")
            for r in records:
                print(f"      - {r['rel_path']} (Score: {r['score']}, Đã chọn: {r['times_chosen']} lần)")
        sys.exit(0)
        
    if args.query:
        results = search_assets(
            query=args.query,
            category=args.category,
            media_type=args.type,
            max_duration=args.max_dur,
            min_duration=args.min_dur,
            green_screen_only=args.green_screen,
            top_k=args.top_k
        )
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(format_search_results(results))
        sys.exit(0)

    parser.print_help()

if __name__ == "__main__":
    main()
