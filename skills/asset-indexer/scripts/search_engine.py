#!/usr/bin/env python3
"""
Asset Search Engine with "Hỏi và Nhớ" (Ask & Remember) Ranking
Provides fast fuzzy, semantic vibe, category, and duration-aware asset lookup.
"""
import os
import sys
import json
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from memory_manager import get_affinity_boost
except ImportError:
    from .memory_manager import get_affinity_boost

ROOT_LOCAL_CONFIG = Path(__file__).resolve().parent.parent.parent.parent / "config.local.json"
SKILL_CONFIG = Path(__file__).resolve().parent.parent / "config.json"
DEFAULT_INDEX_FILE = r"E:\Video Asset\asset_index.json"

def resolve_index_path(index_path=None):
    if index_path and Path(index_path).exists():
        return Path(index_path)
    if ROOT_LOCAL_CONFIG.exists():
        try:
            with open(ROOT_LOCAL_CONFIG, "r", encoding="utf-8") as f:
                l_cfg = json.load(f)
                ad = l_cfg.get("asset_directories", {})
                cand = ad.get("asset_root") or ad.get("sfx_dir")
                if cand:
                    p = Path(cand)
                    if p.name.lower() == "sfx":
                        p = p.parent
                    idx = p / "asset_index.json"
                    if idx.exists():
                        return idx
        except Exception:
            pass
    if SKILL_CONFIG.exists():
        try:
            with open(SKILL_CONFIG, "r", encoding="utf-8") as f:
                sc = json.load(f)
                p = Path(sc.get("index_path", ""))
                if p.exists():
                    return p
        except Exception:
            pass
    local_copy = Path(__file__).resolve().parent.parent / "asset_index.json"
    if local_copy.exists():
        return local_copy
    if Path(DEFAULT_INDEX_FILE).exists():
        return Path(DEFAULT_INDEX_FILE)
    return None

def load_index(index_path=None):
    i_path = resolve_index_path(index_path)
    if not i_path or not i_path.exists():
        return {"total_assets": 0, "assets": []}
            
    with open(i_path, "r", encoding="utf-8") as f:
        return json.load(f)

def tokenize_query(query):
    normalized = re.sub(r"[^\w\s-]", " ", query.lower())
    return [t for t in re.split(r"[_\s-]+", normalized) if len(t) > 1]

def search_assets(query, category=None, media_type=None, max_duration=None, min_duration=None, 
                  green_screen_only=False, top_k=5, index_path=None, memory_path=None):
    """
    Searches multimedia asset library by text intent, vibe, category and duration constraints.
    Returns ranked list of matching asset dicts.
    """
    index_data = load_index(index_path)
    assets = index_data.get("assets", [])
    query_tokens = tokenize_query(query)
    
    results = []
    
    for item in assets:
        # Category filter
        if category and item["category"].lower() != category.lower():
            continue
            
        # Media type filter
        if media_type and item["media_type"] != media_type:
            continue
            
        # Green screen / alpha filter
        if green_screen_only and not (item["has_alpha"] or "green_screen" in item["tags"]):
            continue
            
        # Duration constraints
        dur = item.get("duration", 0.0)
        if max_duration and dur > max_duration:
            continue
        if min_duration and dur < min_duration:
            continue
            
        # Calculate relevance score
        tags_set = set(item.get("tags", []))
        filename_lower = item["file_name"].lower()
        subcat_lower = item.get("subcategory", "").lower()
        
        score = 0.0
        matched_tags = []
        
        for q_tok in query_tokens:
            if q_tok in tags_set:
                score += 2.0
                matched_tags.append(q_tok)
            elif any(q_tok in t for t in tags_set):
                score += 1.0
                matched_tags.append(q_tok)
                
            if q_tok in filename_lower:
                score += 3.0
                matched_tags.append(f"filename:{q_tok}")
                
            if q_tok in subcat_lower:
                score += 1.5
                matched_tags.append(f"subcat:{q_tok}")
                
        # If query is completely empty, rank by usage/affinity
        if not query_tokens:
            score = 1.0
            
        if score > 0.0:
            # Apply "Hỏi và Nhớ" affinity boost from past selections
            affinity = get_affinity_boost(query, item["rel_path"], memory_path=memory_path)
            total_score = round(score * affinity, 2)
            
            results.append({
                "score": total_score,
                "affinity_boost": affinity,
                "matched_terms": list(set(matched_tags)),
                "asset": item
            })
            
    # Sort descending by total_score
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]

def format_search_results(results):
    if not results:
        return "Không tìm thấy asset phù hợp."
        
    lines = [f"Tìm thấy {len(results)} asset phù hợp nhất:"]
    for i, r in enumerate(results, 1):
        a = r["asset"]
        mem_tag = f" 🌟 [Được Nhớ Thường Dùng (x{r['affinity_boost']})]" if r["affinity_boost"] > 1.0 else ""
        dur_str = f"{a['duration']}s" if a['duration'] > 0 else "N/A"
        res_str = f"{a['resolution']['width']}x{a['resolution']['height']}" if a.get('resolution') else a['format']
        lines.append(f"  {i}. [{a['category']}] {a['file_name']} ({dur_str}, {res_str}) - Score: {r['score']}{mem_tag}")
        lines.append(f"     Path: {a['full_path']}")
        if r['matched_terms']:
            lines.append(f"     Matches: {', '.join(r['matched_terms'])}")
    return "\n".join(lines)
