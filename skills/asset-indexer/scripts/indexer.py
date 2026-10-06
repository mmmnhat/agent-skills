#!/usr/bin/env python3
"""
High-Speed Parallel Multimedia Asset Indexer
Recursively scans multimedia repositories (SFX, Meme, Music, Overlay, Footage, Vlipsy),
extracts technical metadata and builds rich semantic tags with vibe mappings.
"""
import os
import sys
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def load_config():
    cfg_path = Path(__file__).resolve().parent.parent / "config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "asset_root": r"E:\Video Asset",
        "index_path": r"E:\Video Asset\asset_index.json",
        "supported_extensions": [".mp3", ".wav", ".m4a", ".mp4", ".mov", ".gif", ".png", ".jpg"],
        "max_workers": 16,
        "vibe_mappings": {}
    }

def probe_metadata(file_path):
    """
    Extracts duration, resolution, and stream metadata via ffprobe.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(file_path)
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=8)
        data = json.loads(proc.stdout)
        
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        
        duration = float(fmt.get("duration", 0.0))
        size_bytes = int(fmt.get("size", os.path.getsize(file_path)))
        
        media_type = "unknown"
        width = None
        height = None
        aspect_ratio = None
        has_alpha = False
        
        for st in streams:
            ctype = st.get("codec_type")
            if ctype == "video":
                media_type = "video"
                width = st.get("width")
                height = st.get("height")
                if width and height:
                    r = width / float(height)
                    if r < 0.65:
                        aspect_ratio = "9:16"
                    elif r < 0.90:
                        aspect_ratio = "4:5"
                    elif r < 1.15:
                        aspect_ratio = "1:1"
                    elif r < 1.50:
                        aspect_ratio = "4:3"
                    elif r < 1.95:
                        aspect_ratio = "16:9"
                    else:
                        aspect_ratio = "21:9"
                if "yuva" in st.get("pix_fmt", "") or st.get("codec_name") in ["png", "qtrle", "prores_ks"]:
                    has_alpha = True
                break
            elif ctype == "audio" and media_type == "unknown":
                media_type = "audio"
                
        ext = Path(file_path).suffix.lower()
        if ext in [".gif"]:
            media_type = "gif"
        elif ext in [".png", ".jpg", ".jpeg"]:
            media_type = "image"
            
        return {
            "duration": round(duration, 3),
            "size_bytes": size_bytes,
            "media_type": media_type,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "has_alpha": has_alpha
        }
    except Exception:
        size = 0
        try:
            size = os.path.getsize(file_path)
        except Exception:
            pass
        return {
            "duration": 0.0,
            "size_bytes": size,
            "media_type": "audio" if Path(file_path).suffix.lower() in [".mp3", ".wav", ".m4a"] else "video",
            "width": None,
            "height": None,
            "aspect_ratio": None,
            "has_alpha": False
        }

def normalize_text(text):
    text = re.sub(r"[^\w\s-]", " ", text.lower())
    tokens = re.split(r"[_\s-]+", text)
    return [t for t in tokens if len(t) > 1 and not t.isdigit()]

def build_tags(rel_path, vibe_mappings):
    parts = Path(rel_path).parts
    filename = Path(rel_path).stem
    
    tags = set()
    # Add folder components
    for p in parts[:-1]:
        for tok in normalize_text(p):
            tags.add(tok)
            
    # Add filename tokens
    for tok in normalize_text(filename):
        tags.add(tok)
        
    # Check green screen
    lower_rel = rel_path.lower()
    if "green screen" in lower_rel or "greenscreen" in lower_rel:
        tags.update(["green_screen", "chroma_key", "overlay"])
        
    # Map semantic vibes
    for vibe_key, vibe_words in vibe_mappings.items():
        if vibe_key in tags or any(v in tags for v in vibe_words):
            tags.add(vibe_key)
            tags.update(vibe_words)
            
    return sorted(list(tags))

def index_repository(root_dir=None, output_path=None, max_workers=16):
    cfg = load_config()
    asset_root = Path(root_dir or cfg.get("asset_root", r"E:\Video Asset")).resolve()
    out_file = Path(output_path or cfg.get("index_path", asset_root / "asset_index.json")).resolve()
    supported_exts = set(cfg.get("supported_extensions", [".mp3", ".wav", ".m4a", ".mp4", ".mov", ".gif", ".png", ".jpg"]))
    vibe_mappings = cfg.get("vibe_mappings", {})
    
    if not asset_root.exists():
        raise FileNotFoundError(f"Asset root does not exist: {asset_root}")
        
    print(f"\n[Asset-Indexer] Scanning multimedia library at: {asset_root}")
    print(f"  • Worker Threads: {max_workers}")
    print(f"  • Target Index: {out_file}")
    
    # 1. Discover all media files
    media_files = []
    for root, _, files in os.walk(asset_root):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_exts:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, asset_root).replace("\\", "/")
                media_files.append((full_p, rel_p))
                
    total_files = len(media_files)
    print(f"  • Discovered {total_files} candidate media files. Extracting metadata in parallel...")
    
    # 2. Extract metadata in parallel
    assets = []
    categories_count = {}
    
    def process_item(item):
        full_p, rel_p = item
        parts = Path(rel_p).parts
        category = parts[0] if len(parts) > 1 else "Root"
        subcategory = parts[1] if len(parts) > 2 else category
        
        meta = probe_metadata(full_p)
        tags = build_tags(rel_p, vibe_mappings)
        
        # ID generation
        stem = Path(full_p).stem
        clean_id = re.sub(r"[^\w]", "_", f"{category}_{stem}").lower()
        
        return {
            "id": clean_id,
            "file_name": Path(full_p).name,
            "rel_path": rel_p,
            "full_path": str(Path(full_p).resolve()).replace("\\", "/"),
            "category": category,
            "subcategory": subcategory,
            "media_type": meta["media_type"],
            "duration": meta["duration"],
            "size_bytes": meta["size_bytes"],
            "format": Path(full_p).suffix.lower().lstrip("."),
            "resolution": {"width": meta["width"], "height": meta["height"]} if meta["width"] else None,
            "aspect_ratio": meta["aspect_ratio"],
            "has_alpha": meta["has_alpha"],
            "tags": tags,
            "usage_count": 0,
            "affinity_score": 1.0
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_item, item): item for item in media_files}
        done_count = 0
        for future in as_completed(futures):
            res = future.result()
            assets.append(res)
            cat = res["category"]
            categories_count[cat] = categories_count.get(cat, 0) + 1
            done_count += 1
            if done_count % 200 == 0 or done_count == total_files:
                print(f"    -> Indexed {done_count}/{total_files} assets ({done_count*100//total_files}%)...", flush=True)

    # Sort assets by category and rel_path
    assets.sort(key=lambda a: (a["category"], a["rel_path"]))

    manifest = {
        "root_path": str(asset_root).replace("\\", "/"),
        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_assets": len(assets),
        "categories_summary": categories_count,
        "assets": assets
    }
    
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    print(f"\n[Asset-Indexer Succeeded]")
    print(f"  ✓ Total assets indexed: {len(assets)}")
    print(f"  ✓ Index saved at: {out_file}")
    for cat, cnt in sorted(categories_count.items()):
        print(f"     • {cat}: {cnt} files")
        
    return str(out_file)

if __name__ == "__main__":
    index_repository()
