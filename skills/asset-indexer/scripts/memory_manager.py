#!/usr/bin/env python3
"""
Asset Memory Manager: "Hỏi và Nhớ" (Ask & Remember) Affinity Engine
Tracks editorial preferences, pairs event intents (e.g. 'action_peak', 'transition', 'funny_fall')
with specific chosen assets, and boosts them in future searches.
"""
import os
import json
from datetime import datetime
from pathlib import Path

ROOT_LOCAL_CONFIG = Path(__file__).resolve().parent.parent.parent.parent / "config.local.json"
SKILL_CONFIG = Path(__file__).resolve().parent.parent / "config.json"
DEFAULT_MEMORY_FILE = r"E:\Video Asset\asset_memory.json"

def resolve_memory_path(memory_path=None):
    if memory_path:
        return Path(memory_path)
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
                    return p / "asset_memory.json"
        except Exception:
            pass
    if SKILL_CONFIG.exists():
        try:
            with open(SKILL_CONFIG, "r", encoding="utf-8") as f:
                sc = json.load(f)
                p = Path(sc.get("memory_path", ""))
                if p:
                    return p
        except Exception:
            pass
    if Path(DEFAULT_MEMORY_FILE).parent.exists():
        return Path(DEFAULT_MEMORY_FILE)
    return Path(__file__).resolve().parent.parent / "asset_memory.json"

def load_memory(memory_path=None):
    m_path = resolve_memory_path(memory_path)
    if m_path.exists():
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "version": "1.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_memories": 0,
        "intent_bindings": {},
        "asset_usage": {}
    }

def save_memory(memory_data, memory_path=None):
    m_path = resolve_memory_path(memory_path)
    m_path.parent.mkdir(parents=True, exist_ok=True)
    memory_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memory_data["total_memories"] = len(memory_data.get("intent_bindings", {}))
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2, ensure_ascii=False)

def remember_choice(intent_tag, asset_rel_path, score_boost=1.0, memory_path=None):
    """
    Records an affinity link between an editorial intent (e.g. 'punch', 'whoosh_fast', 'sad_violin')
    and a specific asset.
    """
    mem = load_memory(memory_path)
    intent_key = intent_tag.strip().lower().replace(" ", "_")
    
    bindings = mem.setdefault("intent_bindings", {})
    intent_records = bindings.setdefault(intent_key, [])
    
    # Check if asset already remembered for this intent
    found = False
    for rec in intent_records:
        if rec["rel_path"] == asset_rel_path:
            rec["score"] = round(rec.get("score", 1.0) + score_boost, 2)
            rec["times_chosen"] = rec.get("times_chosen", 0) + 1
            rec["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            found = True
            break
            
    if not found:
        intent_records.append({
            "rel_path": asset_rel_path,
            "score": round(1.0 + score_boost, 2),
            "times_chosen": 1,
            "last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    usage = mem.setdefault("asset_usage", {})
    usage[asset_rel_path] = usage.get(asset_rel_path, 0) + 1
    
    save_memory(mem, memory_path)
    return True

def get_affinity_boost(intent_query, asset_rel_path, memory_path=None):
    """
    Returns an affinity multiplier (1.0 = neutral, >1.0 = remembered preference)
    for a given query/intent and asset.
    """
    mem = load_memory(memory_path)
    bindings = mem.get("intent_bindings", {})
    normalized_q = intent_query.strip().lower().replace(" ", "_")
    
    boost = 1.0
    for intent_key, records in bindings.items():
        if intent_key in normalized_q or normalized_q in intent_key:
            for rec in records:
                if rec.get("rel_path") == asset_rel_path:
                    boost += rec.get("score", 1.0) * 0.5
                    
    # Usage count minor boost
    usage = mem.get("asset_usage", {})
    times = usage.get(asset_rel_path, 0)
    boost += min(0.5, times * 0.05)
    return round(boost, 2)
