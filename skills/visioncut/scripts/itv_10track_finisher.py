import copy
import gzip
import json
import os
import re
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

TICKS_PER_SEC = 254016000000
SCRATCH = r"C:\Users\AMZ-HUY\.gemini\antigravity\brain\3f487483-4d7b-4954-8bee-9a95da3752bd\scratch"

KB99_PATH  = r"E:\ITV\Project\kb99\kb99.prproj"
KB100_PATH = r"E:\ITV\Project\kb100\kb100.prproj"
KB101_PATH = r"E:\ITV\Project\kb101\kb101.prproj"
KB102_PATH = r"E:\ITV\Project\kb102\kb102.prproj"
KB104_PATH = r"E:\ITV\Project\kb104\kb104.prproj"
KB105_PATH = r"E:\ITV\Project\kb105\kb105.prproj"
KB106_PATH = r"E:\ITV\Project\kb106\kb106.prproj"


def load_xml(path):
    with gzip.open(path, "rb") as f:
        root = ET.fromstring(f.read())
    by_id = {el.attrib["ObjectID"]: el for el in root if "ObjectID" in el.attrib}
    by_uid = {el.attrib["ObjectUID"]: el for el in root if "ObjectUID" in el.attrib}
    return root, by_id, by_uid


# Restore clean original backups of kb105..kb110 BEFORE reading templates
for kb in ["kb105", "kb106", "kb107", "kb108", "kb109", "kb110"]:
    p = rf"E:\ITV\Project\{kb}\{kb}.prproj"
    orig_bak = p + ".orig_bak"
    if not os.path.exists(orig_bak):
        shutil.copy2(p, orig_bak)
    else:
        shutil.copy2(orig_bak, p)

root99, id99, uid99 = load_xml(KB99_PATH)
root100, id100, uid100 = load_xml(KB100_PATH)
root101, id101, uid101 = load_xml(KB101_PATH)
root102, id102, uid102 = load_xml(KB102_PATH)
root104, id104, uid104 = load_xml(KB104_PATH)
root105_tmpl, id105_tmpl, uid105_tmpl = load_xml(KB105_PATH + ".orig_bak")
root106_tmpl, id106_tmpl, uid106_tmpl = load_xml(KB106_PATH + ".orig_bak")

SRC_PROJECTS = {
    "kb99":  (root99, id99, uid99),
    "kb100": (root100, id100, uid100),
    "kb101": (root101, id101, uid101),
    "kb102": (root102, id102, uid102),
    "kb104": (root104, id104, uid104),
    "kb105": (root105_tmpl, id105_tmpl, uid105_tmpl),
    "kb106": (root106_tmpl, id106_tmpl, uid106_tmpl),
}

GLOBAL_BH_POOL = {}
for _r, _, _ in SRC_PROJECTS.values():
    for _e in _r.iter():
        _bh = _e.attrib.get("BinaryHash")
        if _bh and (_e.text or "").strip():
            GLOBAL_BH_POOL[_bh] = _e.text

AUDIO_ANALYSIS = json.load(open(os.path.join(SCRATCH, "kb105_110_audio_analysis.json"), encoding="utf-8"))
SFX_CATALOG_DATA = json.load(open(r"E:\.agents\skills\visioncut\resources\sfx_full_catalog.json", encoding="utf-8"))["catalog"]

# Build lookup of MasterClips in kb104 for any SFX in the 425-file SFX vault
KB104_SFX_MASTERCLIPS = {}
for _mc in root104.iter("MasterClip"):
    _nm = (_mc.findtext("Name") or "").strip()
    _c_ref = _mc.find(".//Clip")
    if _nm and _c_ref is not None and _c_ref.attrib.get("ObjectRef") in id104:
        _ac = id104[_c_ref.attrib["ObjectRef"]]
        _s_ref = _ac.find(".//Source")
        if _s_ref is not None and _s_ref.attrib.get("ObjectRef") in id104:
            KB104_SFX_MASTERCLIPS[_nm] = (_mc.attrib["ObjectUID"], _s_ref.attrib["ObjectRef"])


def iter_no_pvs(el):
    if el.tag == "ProjectViewState.List":
        return
    yield el
    for c in el:
        yield from iter_no_pvs(c)


def iter_for_clone(el):
    if el.tag in ("ProjectViewState.List", "HeadTransition", "TailTransition", "Links"):
        return
    yield el
    for c in el:
        yield from iter_for_clone(c)


def collect_subgraph(start_kind, start_key, by_id, by_uid, stop_ids=None, stop_uids=None):
    stop_ids = stop_ids or set()
    stop_uids = stop_uids or set()
    visited_id = []
    visited_uid = []
    seen_id = set()
    seen_uid = set()
    queue = [(start_kind, start_key)]
    while queue:
        kind, key = queue.pop(0)
        if kind == "id":
            if key in seen_id or key in stop_ids or key not in by_id:
                continue
            seen_id.add(key)
            visited_id.append(key)
            el = by_id[key]
        else:
            if key in seen_uid or key in stop_uids or key not in by_uid:
                continue
            seen_uid.add(key)
            visited_uid.append(key)
            el = by_uid[key]
        for sub in iter_for_clone(el):
            if "ObjectRef" in sub.attrib:
                queue.append(("id", sub.attrib["ObjectRef"]))
            if "ObjectURef" in sub.attrib:
                queue.append(("uid", sub.attrib["ObjectURef"]))
    return visited_id, visited_uid


def clone_subgraph_into(start_kind, start_key, src_id, src_uid, dst_root, next_oid_fn, stop_ids=None, stop_uids=None):
    vis_ids, vis_uids = collect_subgraph(start_kind, start_key, src_id, src_uid, stop_ids, stop_uids)
    id_map = {old_id: str(next_oid_fn()) for old_id in vis_ids}
    uid_map = {old_uid: str(uuid.uuid4()) for old_uid in vis_uids}

    cloned_els = []
    for old_id in vis_ids:
        el = copy.deepcopy(src_id[old_id])
        el.attrib["ObjectID"] = id_map[old_id]
        cloned_els.append(el)
    for old_uid in vis_uids:
        el = copy.deepcopy(src_uid[old_uid])
        el.attrib["ObjectUID"] = uid_map[old_uid]
        cloned_els.append(el)

    for el in cloned_els:
        if el.tag in ("VideoClipTrackItem", "AudioClipTrackItem"):
            cti = el.find("ClipTrackItem")
            if cti is not None:
                for t in list(cti):
                    if t.tag in ("HeadTransition", "TailTransition"):
                        cti.remove(t)
                    elif t.tag == "Links":
                        t.clear()
                        t.attrib["Version"] = "1"
        for sub in iter_no_pvs(el):
            if "ObjectRef" in sub.attrib and sub.attrib["ObjectRef"] in id_map:
                sub.attrib["ObjectRef"] = id_map[sub.attrib["ObjectRef"]]
            if "ObjectURef" in sub.attrib and sub.attrib["ObjectURef"] in uid_map:
                sub.attrib["ObjectURef"] = uid_map[sub.attrib["ObjectURef"]]
            if sub.tag == "ClipID" and (sub.text or "").strip():
                sub.text = str(uuid.uuid4())
            if el.tag in ("VideoClipTrackItem", "AudioClipTrackItem") and sub.tag == "ID" and "-" in (sub.text or ""):
                sub.text = str(uuid.uuid4())
        dst_root.append(el)

    root_new_key = id_map[start_key] if start_kind == "id" else uid_map[start_key]
    return root_new_key, id_map, uid_map


def canonicalize_prproj(root, bh_pool):
    for e in root.iter():
        bh = e.attrib.get("BinaryHash")
        if bh and (e.text or "").strip():
            bh_pool[bh] = e.text

    els = list(root)[1:]
    by_key = {}
    for e in els:
        if "ObjectID" in e.attrib:
            by_key[("id", e.attrib["ObjectID"])] = e
        elif "ObjectUID" in e.attrib:
            by_key[("uid", e.attrib["ObjectUID"])] = e

    queue = [("id", "1")]
    seen = {
        ("id", "1"),
        ("id", "0"),
        ("uid", "00000000-0000-0000-0000-000000000000"),
    }
    bfs_order = []
    id_discovery_order = ["1"]

    while queue:
        k = queue.pop(0)
        if k not in by_key:
            raise KeyError(f"Missing referenced object in PremiereData: {k}")
        bfs_order.append(k)
        e = by_key[k]
        for sub in iter_no_pvs(e):
            if "ObjectRef" in sub.attrib:
                nk = ("id", sub.attrib["ObjectRef"])
                if nk not in seen:
                    seen.add(nk)
                    queue.append(nk)
                    id_discovery_order.append(sub.attrib["ObjectRef"])
            if "ObjectURef" in sub.attrib:
                nk = ("uid", sub.attrib["ObjectURef"])
                if nk not in seen:
                    seen.add(nk)
                    queue.append(nk)

    id_map = {"1": "1"}
    next_id = 3
    for old_id in id_discovery_order[1:]:
        id_map[old_id] = str(next_id)
        next_id += 1

    new_root = ET.Element("PremiereData", {"Version": "3"})
    ET.SubElement(new_root, "Project", {"ObjectRef": "1"})

    for k in bfs_order:
        e = by_key[k]
        if k[0] == "id":
            e.attrib["ObjectID"] = id_map[k[1]]
        for sub in iter_no_pvs(e):
            if "ObjectRef" in sub.attrib and sub.attrib["ObjectRef"] in id_map:
                sub.attrib["ObjectRef"] = id_map[sub.attrib["ObjectRef"]]
        new_root.append(e)

    all_node_ids = [
        int(n.findtext("ID"))
        for n in new_root.iter("Node")
        if n.findtext("ID") and n.findtext("ID").strip().isdigit()
    ]
    next_node_id = max(all_node_ids, default=1000000) + 1
    seen_node_ids = set()
    for n in new_root.iter("Node"):
        id_el = n.find("ID")
        if id_el is not None and id_el.text and id_el.text.strip().isdigit():
            val = int(id_el.text.strip())
            if val in seen_node_ids:
                id_el.text = str(next_node_id)
                seen_node_ids.add(next_node_id)
                next_node_id += 1
            else:
                seen_node_ids.add(val)
    proj_next_id_el = new_root.find("./Project[@ObjectID='1']/NextID")
    if proj_next_id_el is not None:
        proj_next_id_el.text = str(max(seen_node_ids, default=1000000) + 1)

    seen_uuids = set()
    for e in new_root.iter():
        if e.tag in ("ID", "ClipID") and e.text and "-" in e.text and len(e.text.strip()) == 36:
            uval = e.text.strip()
            if uval in seen_uuids:
                new_u = str(uuid.uuid4())
                e.text = new_u
                seen_uuids.add(new_u)
            else:
                seen_uuids.add(uval)

    seen_bh = set()
    for e in new_root.iter():
        bh = e.attrib.get("BinaryHash")
        if bh:
            if bh not in seen_bh:
                if bh not in bh_pool:
                    raise KeyError(f"Missing BinaryHash payload for {bh}")
                e.text = bh_pool[bh]
                seen_bh.add(bh)
            else:
                e.text = None

    return new_root, id_map


def serialize_prproj_bytes(root):
    ET.indent(root, space="\t")
    xml_str = '<?xml version="1.0" encoding="UTF-8" ?>\n' + ET.tostring(root, encoding="unicode") + "\n\n"
    xml_str = re.sub(
        r"<Project\.Metadata\.Schema>(.*?)</Project\.Metadata\.Schema>",
        lambda m: "<Project.Metadata.Schema>" + m.group(1).replace("\n", "&#10;") + "</Project.Metadata.Schema>",
        xml_str,
        flags=re.S,
    )
    xml_str = xml_str.replace(" />", "/>")
    raw_bytes = xml_str.encode("utf-8")
    comp = gzip.compress(raw_bytes, compresslevel=6, mtime=0)
    return comp[:8] + b"\x00\x0a" + comp[10:]


def set_trackitem_timing(ti_el, dst_by_id, start_ticks, end_ticks, preserve_inpoint=True, explicit_in_ticks=None):
    ti_inner = ti_el.find("./ClipTrackItem/TrackItem")
    st_el = ti_inner.find("Start")
    en_el = ti_inner.find("End")
    if start_ticks > 0:
        if st_el is None:
            st_el = ET.Element("Start")
            en_idx = list(ti_inner).index(en_el) if en_el is not None else 0
            ti_inner.insert(en_idx, st_el)
        st_el.text = str(int(start_ticks))
    else:
        if st_el is not None:
            ti_inner.remove(st_el)
    if en_el is None:
        en_el = ET.SubElement(ti_inner, "End")
    en_el.text = str(int(end_ticks))

    sc_ref = ti_el.find(".//SubClip")
    if sc_ref is not None and sc_ref.attrib.get("ObjectRef") in dst_by_id:
        sc_el = dst_by_id[sc_ref.attrib["ObjectRef"]]
        c_ref = sc_el.find(".//Clip")
        if c_ref is not None and c_ref.attrib.get("ObjectRef") in dst_by_id:
            c_el = dst_by_id[c_ref.attrib["ObjectRef"]]
            ip_el = c_el.find(".//InPoint")
            op_el = c_el.find(".//OutPoint")
            if explicit_in_ticks is not None:
                in_val = int(explicit_in_ticks)
            else:
                in_val = int(ip_el.text) if (preserve_inpoint and ip_el is not None and ip_el.text) else 0
            if ip_el is not None:
                ip_el.text = str(in_val)
            if op_el is not None:
                op_el.text = str(in_val + int(end_ticks - start_ticks))


def set_emoji_motion_keyframes(ti_el, dst_by_id, dur_ticks, scale_val, points):
    """
    Set AE.ADBE Motion Position 4-keyframe trajectory and Scale on an Emoji VideoClipTrackItem.
    points = [(x0, y0), (x1, y1), (x2, y2), (x3, y3)] in normalized [0..1] 1920x1080 sequence coordinates.
    Requires VideoClip InPoint = 0 so keyframe ticks start at 0.
    """
    chain_ref = ti_el.find(".//Components").attrib["ObjectRef"]
    chain_el = dst_by_id[chain_ref]
    for cref in chain_el.findall("./ComponentChain/Components/Component"):
        comp = dst_by_id.get(cref.attrib["ObjectRef"])
        if comp is None or comp.findtext("MatchName") != "AE.ADBE Motion":
            continue
        for pref in comp.findall("./Component/Params/Param"):
            prm = dst_by_id.get(pref.attrib["ObjectRef"])
            if prm is None:
                continue
            nm = prm.findtext("Name")
            if nm == "Position":
                x0, y0 = points[0]
                skf_el = prm.find("StartKeyframe")
                if skf_el is not None:
                    skf_el.text = f"-91445760000000000,{x0:.6f}:{y0:.6f},0,0,0,0,0,0,5,4,0,0,0,0"
                kfs_el = prm.find("Keyframes")
                if kfs_el is None:
                    kfs_el = ET.SubElement(prm, "Keyframes")
                n_pts = len(points)
                kf_parts = []
                for i, (px, py) in enumerate(points):
                    t_tick = int(round(i * dur_ticks / max(1, n_pts - 1)))
                    kf_parts.append(
                        f"{t_tick},{px:.6f}:{py:.6f},0,0,0,0.16666666666666666,0,0.16666666666666666,5,4,0,0,0,0;"
                    )
                kfs_el.text = "".join(kf_parts)
            elif nm == "Scale":
                skf_el = prm.find("StartKeyframe")
                if skf_el is not None:
                    skf_el.text = f"-91445760000000000,{float(scale_val):.2f},0,0,0,0,0,0"
                kfs_el = prm.find("Keyframes")
                if kfs_el is not None:
                    kfs_el.text = None


def strip_lumetri_from_ti(ti_el, dst_by_id):
    chain_ref = ti_el.find(".//Components").attrib["ObjectRef"]
    chain_el = dst_by_id[chain_ref]
    comps_el = chain_el.find("./ComponentChain/Components")
    if comps_el is None:
        return
    kept = []
    for c in comps_el.findall("Component"):
        cid = c.attrib["ObjectRef"]
        comp = dst_by_id.get(cid)
        if comp is not None and comp.findtext("MatchName") == "AE.ADBE Lumetri":
            continue
        kept.append(cid)
    comps_el.clear()
    comps_el.attrib["Version"] = "1"
    for idx, cid in enumerate(kept):
        sub = ET.SubElement(comps_el, "Component")
        sub.attrib["Index"] = str(idx)
        sub.attrib["ObjectRef"] = cid


# ==============================================================================
# 1. EMOJI TEMPLATES & VISION-TRACKED IMPACT PLANS (Track V4)
# ==============================================================================
# Semantic Emoji mapping:
# - "monkey_eyes" (512 (1).gif 🙈): Groin/crotch hits, sensitive body spot shield
# - "bang"        (512 (4).gif 💥): Strong crashes, hard slams, explosions, heavy hits
# - "dizzy"       (mnhat_emoji_37.gif 😵‍💫): Direct head/face hits, dizzy knockdowns
# - "fight_cloud" (512 (7).gif 💨⭐): Chaotic group tumbles, multi-hit collisions
# - "laugh_cat"   (512 (6).gif 😹): Hilarious slapstick fails, comical slips
# - "orange_cat"  (512 (5).gif 🐱): Cute/funny awkward moments
EMOJI_TEMPLATES = {
    "monkey_eyes": ("kb99",  "7881"), # 512 (1).gif 🙈
    "bang":        ("kb99",  "7880"), # 512 (4).gif 💥
    "fight_cloud": ("kb101", "7725"), # 512 (7).gif 💨⭐
    "dizzy":       ("kb105", "2309"), # mnhat_emoji_37.gif 😵‍💫
    "laugh_cat":   ("kb105", "2310"), # 512 (6).gif 😹
    "orange_cat":  ("kb105", "2311"), # 512 (5).gif 🐱
}

# Format: (clip_idx, rel_start_sec, dur_sec, emoji_type, scale_pct, [(x0,y0), (x1,y1), (x2,y2), (x3,y3)])
VISION_EMOJI_PLANS = {
    "kb105": [
        # (Preserves user's 4 existing emojis in 0..160s, adds 5 vision-tracked emojis in 160..419s)
        # #38 (18.mp4): Welder torch explodes with sparks right behind his head
        (38, 0.65, 0.42, "bang", 26.0, [(0.51, 0.25), (0.51, 0.24), (0.50, 0.23), (0.50, 0.22)]),
        # #41 (22.mp4): Woman dancing on bar chair slips and falls backward off chair
        (41, 2.82, 0.42, "laugh_cat", 24.0, [(0.44, 0.56), (0.45, 0.65), (0.46, 0.73), (0.47, 0.78)]),
        # #55 (39.mp4): Guy in green hoodie gets smacked in the back of the head
        (55, 0.45, 0.42, "dizzy", 25.0, [(0.44, 0.48), (0.45, 0.52), (0.45, 0.55), (0.46, 0.57)]),
        # #62 (48.mp4): Doorway pull-up bar detaches; person slams onto back/head on floor
        (62, 2.60, 0.42, "bang", 26.0, [(0.48, 0.55), (0.49, 0.73), (0.50, 0.82), (0.51, 0.85)]),
        # #72 (61.mp4): Skateboarder slips off rail and lands on groin/pelvis
        (72, 2.60, 0.42, "monkey_eyes", 22.0, [(0.54, 0.56), (0.56, 0.58), (0.58, 0.60), (0.59, 0.62)]),
    ],
    "kb106": [
        # #03 (itv.kb106.4-2): Person on balance beam flips over and hits head/chest on beam
        (3,  3.92, 0.42, "dizzy", 24.0, [(0.47, 0.54), (0.46, 0.57), (0.45, 0.60), (0.44, 0.62)]),
        # #26 (08 (2).mp4): Two people carrying friend tumble into a heap on patio (HAHAHA!!)
        (26, 1.60, 0.45, "laugh_cat", 25.0, [(0.48, 0.42), (0.48, 0.52), (0.49, 0.62), (0.50, 0.68)]),
        # #33 (16 (2).mp4): Person slips on snow/ice and slams flat onto back/head
        (33, 2.35, 0.42, "bang", 26.0, [(0.43, 0.45), (0.43, 0.58), (0.44, 0.70), (0.45, 0.74)]),
        # #64 (51 (2).mp4): Person slips and wipes out on yellow indoor gym court (HOHOHO)
        (64, 2.95, 0.42, "orange_cat", 24.0, [(0.53, 0.49), (0.50, 0.52), (0.47, 0.53), (0.45, 0.54)]),
        # #81 (11 (2).mp4): Man on blue ladder falls down as ladder collapses
        (81, 1.65, 0.45, "fight_cloud", 45.0, [(0.44, 0.35), (0.46, 0.50), (0.49, 0.65), (0.52, 0.75)]),
    ],
    "kb107": [
        # #15 (itv.kb107.16): Guy doing indoor backflip lands upside-down on head/neck
        (15, 0.20, 0.42, "dizzy", 25.0, [(0.52, 0.52), (0.52, 0.58), (0.53, 0.62), (0.53, 0.65)]),
        # #30 (12 (2).mp4): Person jumping in living room crashes onto coffee table
        (30, 2.10, 0.45, "bang", 26.0, [(0.48, 0.38), (0.46, 0.52), (0.45, 0.64), (0.44, 0.68)]),
        # #47 (35 (2).mp4): Woman in red jacket slips on treadmill and falls onto belt
        (47, 1.60, 0.42, "laugh_cat", 24.0, [(0.47, 0.45), (0.48, 0.52), (0.50, 0.58), (0.52, 0.63)]),
        # #51 (39 (2).mp4): Trampoline jump into pool straddles pool edge right in groin
        (51, 2.35, 0.42, "monkey_eyes", 23.0, [(0.45, 0.48), (0.47, 0.46), (0.49, 0.48), (0.51, 0.52)]),
        # #74 (67 (2).mp4): Weightlifter collapses backward under heavy barbell
        (74, 3.40, 0.45, "bang", 26.0, [(0.58, 0.55), (0.60, 0.65), (0.62, 0.74), (0.63, 0.78)]),
    ],
    "kb108": [
        # #06 (itv.kb108.7): Construction worker carrying drywall falls backward onto board
        (6,  2.20, 0.45, "bang", 26.0, [(0.48, 0.52), (0.49, 0.60), (0.50, 0.67), (0.50, 0.70)]),
        # #24 (05 (2).mp4): Guy on gym weight bench tips over backward upside-down
        (24, 5.50, 0.45, "dizzy", 25.0, [(0.45, 0.52), (0.42, 0.62), (0.39, 0.72), (0.37, 0.78)]),
        # #32 (13 (2).mp4): Person wading by waterfall slips into water
        (32, 3.25, 0.42, "laugh_cat", 24.0, [(0.58, 0.64), (0.59, 0.68), (0.60, 0.72), (0.61, 0.74)]),
        # #49 (39 (2).mp4): Woman on playground balance pods slips & straddles pod in groin (ROFL)
        (49, 3.40, 0.45, "monkey_eyes", 24.0, [(0.52, 0.56), (0.50, 0.62), (0.48, 0.66), (0.45, 0.68)]),
        # #62 (55 (2).mp4): Horse & rider crash through show-jumping obstacle bars
        (62, 3.40, 0.42, "fight_cloud", 45.0, [(0.50, 0.52), (0.47, 0.54), (0.44, 0.56), (0.41, 0.58)]),
    ],
    "kb109": [
        # #05 (itv.kb109.6): Go-kart crashes into track barrier
        (5,  2.50, 0.45, "bang", 26.0, [(0.48, 0.56), (0.50, 0.58), (0.52, 0.60), (0.53, 0.62)]),
        # #17 (itv.kb109.16): People on bamboo raft capsize into river
        (17, 7.90, 0.45, "fight_cloud", 45.0, [(0.52, 0.62), (0.55, 0.58), (0.58, 0.54), (0.60, 0.50)]),
        # #26 (06 (2).mp4): Delivery guy on Ring doorbell camera slips on porch steps
        (26, 3.75, 0.42, "laugh_cat", 24.0, [(0.43, 0.48), (0.43, 0.54), (0.44, 0.60), (0.44, 0.64)]),
        # #49 (35 (2).mp4): Cyclist in woods crashes onto dirt trail
        (49, 2.45, 0.45, "dizzy", 25.0, [(0.48, 0.50), (0.50, 0.55), (0.52, 0.60), (0.53, 0.63)]),
        # #57 (44 (2).mp4): Rope swing in forest drops person onto dirt slope
        (57, 2.10, 0.42, "orange_cat", 24.0, [(0.45, 0.50), (0.48, 0.55), (0.52, 0.60), (0.55, 0.64)]),
    ],
    "kb110": [
        # #01 (itv.kb110.2): Truck tire explodes next to pickup & launches worker
        (1,  4.05, 0.42, "bang", 28.0, [(0.39, 0.25), (0.40, 0.28), (0.41, 0.34), (0.42, 0.42)]),
        # #09 (itv.kb110.9): Firefighter knocked down by high-pressure hose
        (9,  2.20, 0.42, "dizzy", 24.0, [(0.35, 0.64), (0.37, 0.68), (0.39, 0.72), (0.41, 0.75)]),
        # #23 (03 (2).mp4): Guy in swim trunks by lake gets hit/slipped in groin/legs
        (23, 3.40, 0.42, "monkey_eyes", 23.0, [(0.60, 0.64), (0.61, 0.66), (0.63, 0.68), (0.64, 0.70)]),
        # #39 (21 (2).mp4): Guy in indoor turf gym jumps high & slams flat onto back/head
        (39, 2.90, 0.42, "bang", 26.0, [(0.42, 0.45), (0.43, 0.62), (0.45, 0.78), (0.46, 0.84)]),
        # #54 (40 (2).mp4): Guy rolling inside giant black pipe tumbles out on face (HAHAHA!)
        (54, 3.65, 0.42, "laugh_cat", 25.0, [(0.45, 0.60), (0.46, 0.64), (0.47, 0.67), (0.48, 0.69)]),
    ],
}


# ==============================================================================
# 2. FULL SFX LIBRARY TEMPLATES & CONTEXT-MATCHED SFX PLANS (Track A3)
# ==============================================================================
PLACED_SFX_TEMPLATES = {
    "metal-gear-solid.mp3":        ("kb100", "7714", 2.21),
    "censor-beep-1.mp3":           ("kb100", "7715", 0.21),
    "oof.mp3":                     ("kb100", "7717", 1.58),
    "bonk.mp3":                    ("kb100", "7718", 0.42),
    "metallic-bonk-and-rattle.mp3":("kb100", "7719", 1.96),
    "taco-bell-bong.mp3":          ("kb100", "7720", 1.38),
    "rubber-duck.mp3":             ("kb100", "7721", 1.21),
    "bamboo-hit.mp3":              ("kb100", "7722", 1.54),
    "boin4.mp3":                   ("kb100", "7723", 0.38),
    "windows-xp-shutdown.mp3":     ("kb100", "7724", 1.38),
    "windows-error.mp3":           ("kb100", "7725", 1.33),
    "tac.mp3":                     ("kb100", "7726", 1.33),
    "car-brake.mp3":               ("kb100", "7727", 4.42),
    "body-impact.mp3":             ("kb100", "7728", 1.04),
    "record-scratch.mp3":          ("kb100", "7729", 4.13),
    "hollywoodedge-slide-whistle-in-out-crt057601.mp3": ("kb100", "7732", 1.50),
    "duck-quack.mp3":              ("kb100", "7735", 0.83),
    "slip-2.mp3":                  ("kb101", "7834", 1.46),
    "sword-hit.mp3":               ("kb101", "7835", 0.46),
    "loading-lost-connection-green-screen-with-sound-effect-2_K8HORkT.mp3": ("kb101", "7836", 2.09),
    "splash.m4a":                  ("kb101", "7837", 1.84),
    "cartoon-throw.mp3":           ("kb101", "7845", 1.13),
    "gmod-fall-damage-1.mp3":      ("kb102", "7818", 0.88),
    "cartoon-boing-2.mp3":         ("kb105", "2340", 1.29),
    "slip.mp3":                    ("kb105", "2344", 0.71),
    "body-fall-sound-effect.mp3":  ("kb105", "2347", 1.71),
    "slide-whistle-fall-and-boomp.mp3": ("kb105", "2349", 2.34),
    "What the.mp3":                ("kb105", "2350", 2.50),
    "quick-car-crash.mp3":         ("kb105", "2352", 4.00),
    "(bursts into laughter) Pfft-hahaha!.mp3": ("kb105", "2353", 3.50),
    "fall-and-tumble.mp3":         ("kb105", "2354", 3.80),
    "395325__ihitokage__body-falling-on-the-ground-2_01.mp3": ("kb105", "2355", 1.71),
    "tree_fall_small.mp3":         ("kb106", "2150", 5.59),
    "house-collapse.mp3":          ("kb106", "2159", 6.01),
    "wobbly-junk-crash.mp3":       ("kb106", "2161", 4.30),
    "Wiii! Wheeee!.mp3":           ("kb106", "2162", 5.71),
    "ouch.mp3":                    ("kb106", "2163", 3.46),
    "Whoa, hold on!.mp3":          ("kb106", "2166", 3.96),
}

# Format: (clip_idx, impact_rel_sec, sfx_filename)
# Each SFX is chosen by visual context & semantic meaning, and its acoustic peak_offset_sec
# from sfx_full_catalog.json is aligned to (clip.start_sec + impact_rel_sec).
CONTEXT_SFX_PLANS = {
    "kb105": [
        # (Note: kb105 419..488s already has 18 user-placed SFX on A3/A4 which are preserved)
        (2,  3.67, "car-brake.mp3"),                  # itv.kb105.3-2 rally car skids off dirt road
        (4,  1.43, "tac.mp3"),                        # itv.kb105.5-2 2x4 wood block falls on foot
        (13, 4.80, "bamboo-hit.mp3"),                 # itv.kb105.15-2 axe chopping wood hits foot
        (25, 3.42, "metallic-bonk-and-rattle.mp3"),   # 04.mp4 basketball hoop falls onto girl's head
        (29, 3.23, "bonk.mp3"),                       # 08.mp4 guy swings golf club into his own face
        (32, 2.42, "body-fall-sound-effect.mp3"),     # 11.mp4 person trips on front walkway
        (38, 0.85, "Socket Fizzle - Electricity Short Circuit - Sound Effect 1 - YouTube.mp3"), # 18.mp4 welder spark burst
        (41, 3.02, "slip-2.mp3"),                     # 22.mp4 woman slips off bar chair
        (47, 2.25, "splash.m4a"),                     # 29.mp4 cyclist falls off narrow bridge into water
        (51, 1.77, "body-impact.mp3"),                # 33.mp4 gymnast flip slams onto mat
        (54, 0.90, "cartoon_bite_sound_effect.mp3"),  # 38.mp4 crab pinches bottle/hand
        (55, 0.60, "bonk.mp3"),                       # 39.mp4 guy hit in back of head at inflatable
        (62, 2.75, "body-impact.mp3"),                # 48.mp4 pull-up bar detaches, slams on floor
        (72, 2.70, "oof.mp3"),                        # 61.mp4 skateboarder lands on rail in groin
        (74, 1.83, "slide-whistle-fall-and-boomp.mp3"), # 63.mp4 person on ladder slips and falls down
    ],
    "kb106": [
        # (Note: kb106 92..98s and 438..476s already have 16 user-placed SFX on A3/A4 which are preserved)
        (3,  4.00, "body-impact.mp3"),                # itv.kb106.4-2 balance beam flip slam
        (10, 3.12, "slip-2.mp3"),                     # itv.kb106.10 slipping on icy driveway
        (20, 1.68, "metal-gear-solid.mp3"),           # 01 (2).mp4 jet/plane sudden pass overhead
        (26, 1.85, "fall-and-tumble.mp3"),            # 08 (2).mp4 two people carrying friend tumble onto patio
        (33, 2.48, "395325__ihitokage__body-falling-on-the-ground-2_01.mp3"), # 16 (2).mp4 snow slip flat on back
        (39, 1.50, "slip.mp3"),                       # 24 (2).mp4 scooter rider slips (AHAHAHA!!!!)
        (49, 3.55, "cartoon-boing-2.mp3"),            # 34 (2).mp4 gym trampoline bounce into pit
        (58, 1.30, "Whoa, hold on!.mp3"),             # 43 (2).mp4 high-speed vehicle on runway
        (61, 1.48, "hollywoodedge-slide-whistle-in-out-crt057601.mp3"), # 47 (2).mp4 playground spinner launch
        (64, 3.10, "slip-2.mp3"),                     # 51 (2).mp4 gym court slip & wipeout (HOHOHO)
        (68, 2.33, "splash.m4a"),                     # 55 (2).mp4 sliding off boat into water
        (73, 1.50, "windows-error.mp3"),              # 61 (2).mp4 guy confused on gym machine (FAILARMY)
    ],
    "kb107": [
        (0,  3.65, "house-collapse.mp3"),             # itv.kb107.1 house collapses onto excavator
        (15, 0.35, "gmod-fall-damage-1.mp3"),         # itv.kb107.16 indoor backflip lands on head/neck
        (27, 5.88, "wobbly-junk-crash.mp3"),          # 09 (2).mp4 pickup truck load/tailgate crash
        (30, 2.30, "body-impact.mp3"),                # 12 (2).mp4 living room jump crashes onto coffee table
        (38, 2.40, "fall-and-tumble.mp3"),            # 23 (2).mp4 dirt trail cyclist crashes over bars
        (43, 2.52, "splash.m4a"),                     # 29 (2).mp4 kayak/snow slide into water
        (47, 1.65, "slip-2.mp3"),                     # 35 (2).mp4 woman in red jacket slips on treadmill
        (51, 2.50, "oof.mp3"),                        # 39 (2).mp4 trampoline jump straddles pool wall in groin
        (54, 4.50, "Whoa, hold on!.mp3"),             # 42 (2).mp4 mountain biker on red rock cliff loses balance
        (62, 3.02, "body-fall-sound-effect.mp3"),     # 53 (2).mp4 girl at playground falls flat on ground
        (66, 4.33, "hollywoodedge-slide-whistle-in-out-crt057601.mp3"), # 58 (2).mp4 bicycle wheelie tips back
        (74, 3.60, "metallic-bonk-and-rattle.mp3"),   # 67 (2).mp4 weightlifter collapses backward under barbell
        (75, 1.50, "body-impact.mp3"),                # 68 (2).mp4 gym box jump with medicine ball slams down
        (77, 4.27, "splash.m4a"),                     # 03 (2).mp4 silent ending montage pool splash
        (80, 3.00, "bonk.mp3"),                       # 26 (2).mp4 silent ending montage impact
    ],
    "kb108": [
        (0,  0.65, "quick-car-crash.mp3"),            # itv.kb108.1 scooter crashes into parked car
        (6,  2.35, "body-fall-sound-effect.mp3"),     # itv.kb108.7 worker carrying drywall falls backward
        (13, 4.88, "What the.mp3"),                   # itv.kb108.14 workshop machine surprise
        (16, 1.50, "slip-2.mp3"),                     # itv.kb108.17 person in garage slips and falls
        (24, 5.65, "wobbly-junk-crash.mp3"),          # 05 (2).mp4 guy on gym weight bench tips over backward
        (31, 0.33, "duck-quack.mp3"),                 # 12 (2).mp4 dog & walker funny step
        (32, 3.42, "splash.m4a"),                     # 13 (2).mp4 wading in waterfall slips into water
        (37, 4.27, "hollywoodedge-slide-whistle-in-out-crt057601.mp3"), # 20 (2).mp4 sliding down blue ice glacier
        (43, 2.73, "splash.m4a"),                     # 30 (2).mp4 person on boat/water
        (49, 3.55, "oof.mp3"),                        # 39 (2).mp4 playground pods groin straddle & fall (ROFL)
        (60, 1.80, "splash.m4a"),                     # 52 (2).mp4 backyard pool belly-flop splash
        (62, 3.50, "bamboo-hit.mp3"),                 # 55 (2).mp4 horse & rider crash through jump fence bars
        (69, 4.15, "rubber-duck.mp3"),                # 63 (2).mp4 beach sandal/crab pinch
        (75, 4.27, "metal-gear-solid.mp3"),           # 16 (2).mp4 silent ending montage Ghostbusters car
        (78, 3.00, "bonk.mp3"),                       # 27 (2).mp4 silent ending montage hit
    ],
    "kb109": [
        (5,  2.65, "quick-car-crash.mp3"),            # itv.kb109.6 go-kart crashes into track barrier
        (8,  4.28, "car-brake.mp3"),                  # itv.kb109.8 black car on trailer/ramp shifts
        (12, 3.08, "house-collapse.mp3"),             # itv.kb109.12 old wooden structure demolition collapses
        (17, 8.05, "splash.m4a"),                     # itv.kb109.16 bamboo raft tips over into river
        (26, 3.88, "slip-2.mp3"),                     # 06 (2).mp4 delivery guy on Ring cam slips on steps
        (35, 1.52, "car-brake.mp3"),                  # 17 (2).mp4 yellow car spinning on highway
        (40, 5.50, "windows-error.mp3"),              # 22 (2).mp4 FedEx porch reaction
        (47, 2.15, "metallic-bonk-and-rattle.mp3"),   # 33 (2).mp4 parking lot van/truck bump
        (49, 2.60, "fall-and-tumble.mp3"),            # 35 (2).mp4 dirt bike in woods crashes onto trail
        (56, 5.35, "splash.m4a"),                     # 43 (2).mp4 stepping into lake/water
        (57, 2.20, "slide-whistle-fall-and-boomp.mp3"), # 44 (2).mp4 rope swing in forest drops into dirt
        (64, 1.56, "tac.mp3"),                        # 55 (2).mp4 pool table trick shot hit
        (76, 4.50, "slip.mp3"),                       # 24 (2).mp4 silent ending montage shop slip
        (80, 3.00, "body-impact.mp3"),                # 51 (2).mp4 silent ending montage impact
    ],
    "kb110": [
        (1,  4.17, "Large_truck_tire_bei_#2-1787641335082.mp3"), # itv.kb110.2 truck tire explodes & launches worker
        (3,  3.80, "slip-2.mp3"),                     # itv.kb110.4-2 person slips on icy driveway
        (4,  3.70, "slide-whistle-fall-and-boomp.mp3"), # itv.kb110.4 worker on ladder slides down wall
        (9,  2.35, "body-fall-sound-effect.mp3"),     # itv.kb110.9 firefighter knocked down by firehose
        (17, 1.68, "wobbly-junk-crash.mp3"),          # itv.kb110.17 woman leaning on stroller tips backward
        (23, 3.52, "oof.mp3"),                        # 03 (2).mp4 guy by lake hit/slipped in groin
        (29, 3.10, "metallic-bonk-and-rattle.mp3"),   # 10 (2).mp4 warehouse/workshop gate hit
        (39, 2.98, "body-impact.mp3"),                # 21 (2).mp4 indoor turf gym high jump slams onto back
        (45, 4.27, "tree_fall_small.mp3"),            # 29 (2).mp4 tree branch falls onto house porch
        (51, 3.70, "car-brake.mp3"),                  # 35 (2).mp4 snowy highway truck trailer spin
        (54, 3.80, "fall-and-tumble.mp3"),            # 40 (2).mp4 guy rolling inside black pipe tumbles out
        (64, 0.80, "quick-car-crash.mp3"),            # 52 (2).mp4 street car collision on dashcam/cam
        (68, 3.90, "395325__ihitokage__body-falling-on-the-ground-2_01.mp3"), # 56 (2).mp4 office chair tips backward
        (81, 1.20, "splash.m4a"),                     # 14 (2).mp4 silent ending montage dog by pool
    ],
}


# ==============================================================================
# 3. BGM TEMPLATES & SILENT-CLIP-ONLY BGM PLANS (Track A5)
# ==============================================================================
# Music templates across kb100, kb101, kb102:
BGM_TEMPLATES = {
    "brain_trust": ("kb100", "7741", 11.93), # [none] Brain Trust - Wayne Jones.mp3 (quirky/curious/DIY)
    "standoff":    ("kb100", "7742", 7.34),  # [none] Standoff - Density & Time.mp3 (tense/suspense)
    "chacha":      ("kb100", "7743", 20.35), # [none] ChaCha Fontanez.mp3 (playful dance/party/pets)
    "city_blocks": ("kb100", "7744", 28.32), # [none] City Blocks - TrackTribe.mp3 (smooth urban/street)
    "greaser":     ("kb100", "7745", 41.04), # [none] Greaser - TrackTribe.mp3 (energetic rockabilly montage)
    "kazoom":      ("kb101", "7852", 50.26), # [none] Kazoom - Quincas Moreira.mp3 (bouncy cartoon slapstick)
    "angel_lover": ("kb102", "7826", 50.47), # [none] Angel Lover - Retro - YouTube.mp3 (upbeat retro groove)
}

# Format: (start_clip_idx, end_clip_idx_inclusive, bgm_key)
# Placed ONLY on clips that have NO audible original sound (silent stream / no A1 clip)!
SILENT_BGM_PLANS = {
    "kb105": [
        (38, 38, "brain_trust"), # #38 (18.mp4, 208.04..213.25s, silent workshop clip)
        (66, 66, "chacha"),      # #66 (52.mp4, 346.39..351.60s, silent wedding couple dance)
        (80, 89, "greaser"),     # #80..#89 (419.04..488.78s, 10-clip silent ending montage)
    ],
    "kb106": [
        (31, 31, "city_blocks"), # #31 (14 (2).mp4, 170.75..176.55s, silent Cybertruck street clip)
        (49, 49, "kazoom"),      # #49 (34 (2).mp4, 269.35..274.06s, silent gym foam-pit jump)
        (54, 54, "brain_trust"), # #54 (39 (2).mp4, 297.25..303.05s, silent bear by fence)
        (56, 56, "brain_trust"), # #56 (41 (2).mp4, 308.77..314.56s, silent snowy steps)
        (70, 70, "chacha"),      # #70 (57 (2).mp4, 385.51..391.31s, silent macaw parrots playing)
        (72, 73, "kazoom"),      # #72..#73 (397.11..407.37s, silent toy excavator & gym machine)
        (80, 86, "angel_lover"), # #80..#86 (438.10..476.69s, 7-clip silent ending montage)
    ],
    "kb107": [
        (75, 75, "kazoom"),      # #75 (68 (2).mp4, 490.45..496.00s, silent gym box jump fail)
        (77, 84, "kazoom"),      # #77..#84 (503.34..555.60s, 8-clip silent ending montage)
    ],
    "kb108": [
        (24, 24, "kazoom"),      # #24 (05 (2).mp4, 164.62..172.80s, silent gym bench fail)
        (32, 32, "chacha"),      # #32 (13 (2).mp4, 215.38..219.93s, silent waterfall slip)
        (34, 34, "standoff"),    # #34 (15 (2).mp4, 226.44..232.94s, silent snowy windshield)
        (37, 37, "brain_trust"), # #37 (20 (2).mp4, 247.58..254.09s, silent blue ice glacier slide)
        (57, 57, "city_blocks"), # #57 (48 (2).mp4, 375.88..382.38s, silent ocean surfer)
        (65, 65, "brain_trust"), # #65 (59 (2).mp4, 423.42..429.93s, silent backyard clip)
        (68, 68, "standoff"),    # #68 (62 (2).mp4, 443.07..449.57s, silent rocky slope)
        (72, 72, "chacha"),      # #72 (66 (2).mp4, 466.76..473.26s, silent cat in sink)
        (75, 85, "greaser"),     # #75..#85 (484.57..548.55s, 11-clip silent ending montage)
    ],
    "kb109": [
        (58, 58, "standoff"),    # #58 (45 (2).mp4, 391.06..397.56s, silent street dashcam)
        (75, 85, "angel_lover"), # #75..#85 (507.59..576.03s, 11-clip silent ending montage)
    ],
    "kb110": [
        (3,  3,  "standoff"),    # #03 (itv.kb110.4-2, 16.98..26.98s, silent icy driveway slip)
        (22, 22, "chacha"),      # #22 (02 (2).mp4, 158.82..165.33s, silent cute puppy on couch)
        (53, 53, "brain_trust"), # #53 (37 (2).mp4, 348.39..354.90s, silent tabletop object)
        (74, 74, "brain_trust"), # #74 (63 (2).mp4, 471.55..477.10s, silent sweeping water)
        (80, 86, "kazoom"),      # #80..#86 (511.55..555.80s, 7-clip silent ending montage)
    ],
}


V8_GRAPHIC_TEMPLATES_100 = [
    "7645", "7647", "7655", "7642", "7649", "7652", "7659", "7640", "7650", "7644", "7656",
]

TRACK_FILTER_TEMPLATES_100 = {
    "Master": ["9428"],
    "A1": ["9300", "9301"],
    "A2": ["9345"],
    "A3": ["9395"],
    "A4": ["9399"],
    "A5": ["9413"],
}

ESP_AMBIENCE_PROPS = [
    ("ESP.VolumeSection.Gain.ComponentID", "4"),
    ("ESP.DuckingSection.2", "34"),
    ("ESP.VolumeSection.1", "1"),
    ("ESP.VolumeSection.2", "-20"),
    ("ESP.SoundEffectsSection.3", "1"),
    ("ESP.DuckingSection.6", "-24.9999961853"),
    ("ESP.DuckingSection.5", "200"),
    ("ESP.DuckingSection.1", "0"),
    ("ESP.DuckingSection.0", "1"),
    ("ESP.LoudnessSection.1", "1"),
    ("monitor.take.audio.linked", "true"),
    ("monitor.show.audio.waveform", "false"),
    ("ESP.Tag", "ambience"),
    ("ESP.PresetGuid", "b3526c89-21a6-48b6-bb5e-7f323a45a206"),
    ("ESP.ClipMixTypeID", "5"),
    ("MZ.EssentialSound.AdjustmentModeWorkflowType", "1"),
    ("ESP.AdjustmentsModeID", "ambience"),
]

MIXER_UI_PROPS = [
    ("audio.mixer.selected.effectparammenu0", "0"),
    ("audio.mixer.selected.effectparammenu1", "0"),
    ("audio.mixer.selected.effectparammenu2", "0"),
    ("audio.mixer.selected.effectparammenu3", "0"),
    ("audio.mixer.selected.effectparammenu4", "0"),
    ("audio.mixer.selected.menu.hilite.state", "1"),
    ("audio.mixer.selected.sendmenu", "4294967295"),
    ("audio.mixer.selected.effectmenu", "0"),
]

EXTRA_BLUR_CLIPS = {
    "kb105": {"single_bc": [35, 73, 74], "single_tl": [59, 80]},
    "kb106": {"single_bc": [39, 41, 44, 47, 57, 60, 69, 71, 80], "single_tl": [47, 54]},
    "kb107": {"single_bc": [32, 37, 39, 47, 58, 63, 79], "single_tl": [61]},
    "kb108": {"single_bc": [12, 25, 29, 70, 85], "single_tl": [36]},
    "kb109": {"single_bc": [25, 76, 79], "single_tl": [76, 79]},
    "kb110": {"single_bc": [38, 39, 40, 61, 69, 84], "single_tl": [26, 36, 58]},
}


def clone_sfx_into_project(sfx_name, dst_root, next_oid_fn):
    """
    Clone an AudioClipTrackItem for sfx_name into dst_root, either from PLACED_SFX_TEMPLATES
    or by pairing kb100's A3 TrackItem shell ('7718') with kb104's MasterClip & AudioMediaSource.
    """
    if sfx_name in PLACED_SFX_TEMPLATES:
        src_kb, ti_id, _ = PLACED_SFX_TEMPLATES[sfx_name]
        _, s_id, s_uid = SRC_PROJECTS[src_kb]
        new_ti_id, _, _ = clone_subgraph_into("id", ti_id, s_id, s_uid, dst_root, next_oid_fn)
        return new_ti_id

    if sfx_name not in KB104_SFX_MASTERCLIPS:
        raise KeyError(f"SFX {sfx_name} not found in PLACED_SFX_TEMPLATES or kb104 MasterClips")

    mc_uid_104, ams_id_104 = KB104_SFX_MASTERCLIPS[sfx_name]
    # Clone MasterClip subgraph from kb104
    new_mc_uid, id_map_104, _ = clone_subgraph_into("uid", mc_uid_104, id104, uid104, dst_root, next_oid_fn)
    new_ams_id = id_map_104[ams_id_104]

    # Clone '7718' (bonk.mp3) AudioClipTrackItem shell from kb100, stopping at its old MasterClip and old AudioMediaSource
    sc_100 = id100[id100["7718"].find(".//SubClip").attrib["ObjectRef"]]
    old_mc_uid = sc_100.find("MasterClip").attrib["ObjectURef"]
    ac_100 = id100[sc_100.find("Clip").attrib["ObjectRef"]]
    old_ams_id = ac_100.find(".//Source").attrib["ObjectRef"]

    new_ti_id, id_map_shell, _ = clone_subgraph_into(
        "id", "7718", id100, uid100, dst_root, next_oid_fn,
        stop_ids={old_ams_id}, stop_uids={old_mc_uid}
    )
    # Wire cloned SubClip and AudioClip to new_mc_uid and new_ams_id
    by_id_tmp = {e.attrib["ObjectID"]: e for e in dst_root if "ObjectID" in e.attrib}
    new_sc_el = by_id_tmp[id_map_shell[sc_100.attrib["ObjectID"]]]
    new_sc_el.find("MasterClip").attrib["ObjectURef"] = new_mc_uid
    new_sc_el.find("Name").text = sfx_name

    new_ac_el = by_id_tmp[id_map_shell[ac_100.attrib["ObjectID"]]]
    new_ac_el.find(".//Source").attrib["ObjectRef"] = new_ams_id
    for sec_ref in new_ac_el.findall("./SecondaryContents/SecondaryContentItem"):
        sec_el = by_id_tmp[sec_ref.attrib["ObjectRef"]]
        sec_el.find("Content").attrib["ObjectRef"] = new_ams_id

    return new_ti_id


def process_project(kb):
    prproj_path = rf"E:\ITV\Project\{kb}\{kb}.prproj"
    root, by_id, by_uid = load_xml(prproj_path)

    max_oid = max(int(k) for k in by_id.keys())
    def next_oid():
        nonlocal max_oid
        max_oid += 1
        return max_oid

    def refresh_maps():
        by_id.clear()
        by_uid.clear()
        for el in root:
            if "ObjectID" in el.attrib:
                by_id[el.attrib["ObjectID"]] = el
            if "ObjectUID" in el.attrib:
                by_uid[el.attrib["ObjectUID"]] = el

    vtg = next(root.iter("VideoTrackGroup"))
    atg = next(root.iter("AudioTrackGroup"))

    # 1. Ensure 8 Video Tracks (V1..V8)
    v_tracks_cont = vtg.find("./TrackGroup/Tracks")
    existing_v_tracks = v_tracks_cont.findall("Track")
    if kb in ("kb107", "kb108", "kb109", "kb110"):
        v1_el = by_uid[existing_v_tracks[0].attrib["ObjectURef"]]
        v3_el = by_uid[existing_v_tracks[2].attrib["ObjectURef"]]
        v1_ti = v1_el.find("./ClipTrack/ClipItems/TrackItems")
        v3_ci = v3_el.find("./ClipTrack/ClipItems")
        if v1_ti is not None and v3_ci is not None:
            v1_el.find("./ClipTrack/ClipItems").remove(v1_ti)
            v3_ci.insert(0, v1_ti)

    tmpl_vtg105 = next(root105_tmpl.iter("VideoTrackGroup"))
    tmpl_v_tracks = tmpl_vtg105.findall("./TrackGroup/Tracks/Track")
    while len(v_tracks_cont.findall("Track")) < 8:
        new_idx = len(v_tracks_cont.findall("Track"))
        src_tr_uid = tmpl_v_tracks[new_idx].attrib["ObjectURef"]
        src_tr_el = copy.deepcopy(uid105_tmpl[src_tr_uid])
        ci = src_tr_el.find("./ClipTrack/ClipItems")
        ti_old = ci.find("TrackItems")
        if ti_old is not None:
            ci.remove(ti_old)
        new_uid = str(uuid.uuid4())
        src_tr_el.attrib["ObjectUID"] = new_uid
        src_tr_el.find("./ClipTrack/Track/ID").text = str(new_idx + 1)
        src_tr_el.find("./ClipTrack/Track/Index").text = str(new_idx)
        ci.find("Index").text = str(new_idx)
        root.append(src_tr_el)
        by_uid[new_uid] = src_tr_el
        tr_ref = ET.SubElement(v_tracks_cont, "Track")
        tr_ref.attrib["Index"] = str(new_idx)
        tr_ref.attrib["ObjectURef"] = new_uid
    vtg.find("./TrackGroup/NextTrackID").text = "10"

    # 2. Ensure 5 Audio Tracks (A1..A5)
    a_tracks_cont = atg.find("./TrackGroup/Tracks")
    master_tr_el = by_id[atg.find("MasterTrack").attrib["ObjectRef"]]
    inlet_el = by_id[master_tr_el.find("Inlet").attrib["ObjectRef"]]
    inlet_sources = inlet_el.find("Sources")

    tmpl_atg100 = next(root100.iter("AudioTrackGroup"))
    tmpl_a5_uid = tmpl_atg100.findall("./TrackGroup/Tracks/Track")[4].attrib["ObjectURef"]
    if len(a_tracks_cont.findall("Track")) < 5:
        a5_ti_refs = {
            c.attrib["ObjectRef"]
            for c in uid100[tmpl_a5_uid].findall(".//TrackItems/TrackItem")
        }
        new_a5_uid, _, _ = clone_subgraph_into(
            "uid", tmpl_a5_uid, id100, uid100, root, next_oid, stop_ids=a5_ti_refs
        )
        refresh_maps()
        a5_el = by_uid[new_a5_uid]
        ci = a5_el.find("./ClipTrack/ClipItems")
        ti_old = ci.find("TrackItems")
        if ti_old is not None:
            ci.remove(ti_old)
        a5_el.find("./ClipTrack/Track/ID").text = "5"
        a5_el.find("./ClipTrack/Track/Index").text = "4"
        ci.find("Index").text = "4"
        tr_ref = ET.SubElement(a_tracks_cont, "Track")
        tr_ref.attrib["Index"] = "4"
        tr_ref.attrib["ObjectURef"] = new_a5_uid
        src_ref = ET.SubElement(inlet_sources, "Source")
        src_ref.attrib["Index"] = "4"
        src_ref.attrib["ObjectURef"] = new_a5_uid
        atg.find("./TrackGroup/NextTrackID").text = "7"

    refresh_maps()

    def get_track_items_container(tg_el, idx):
        t_uid = tg_el.findall("./TrackGroup/Tracks/Track")[idx].attrib["ObjectURef"]
        t_el = by_uid[t_uid]
        ci = t_el.find("./ClipTrack/ClipItems")
        ti_cont = ci.find("TrackItems")
        if ti_cont is None:
            ti_cont = ET.Element("TrackItems", {"Version": "1"})
            ci.insert(0, ti_cont)
        return ti_cont

    def append_ti_to_track(ti_cont, ti_oid):
        idx = len(ti_cont.findall("TrackItem"))
        el = ET.SubElement(ti_cont, "TrackItem")
        el.attrib["Index"] = str(idx)
        el.attrib["ObjectRef"] = str(ti_oid)

    def reindex_track_items(ti_cont):
        items = []
        for c in ti_cont.findall("TrackItem"):
            oid = c.attrib["ObjectRef"]
            ti_el = by_id[oid]
            st = int(ti_el.findtext(".//Start") or 0)
            items.append((st, oid))
        items.sort(key=lambda x: x[0])
        ti_cont.clear()
        ti_cont.attrib["Version"] = "1"
        for i, (_, oid) in enumerate(items):
            el = ET.SubElement(ti_cont, "TrackItem")
            el.attrib["Index"] = str(i)
            el.attrib["ObjectRef"] = str(oid)

    # Inspect V3 primary clips
    v3_cont = get_track_items_container(vtg, 2)
    v3_ti_refs = [c.attrib["ObjectRef"] for c in v3_cont.findall("TrackItem")]
    v3_clips = []
    for idx, oid in enumerate(v3_ti_refs):
        ti_el = by_id[oid]
        st = int(ti_el.findtext(".//Start") or 0)
        en = int(ti_el.findtext(".//End") or 0)
        sc = by_id[ti_el.find(".//SubClip").attrib["ObjectRef"]]
        vc = by_id[sc.find(".//Clip").attrib["ObjectRef"]]
        name = sc.findtext("Name") or ""
        v3_clips.append({
            "index": idx,
            "ti_id": oid,
            "ti_el": ti_el,
            "sc_el": sc,
            "vc_el": vc,
            "name": name,
            "start_ticks": st,
            "end_ticks": en,
            "start_sec": st / TICKS_PER_SEC,
            "end_sec": en / TICKS_PER_SEC,
        })
    total_ticks = v3_clips[-1]["end_ticks"]

    # 3. Populate Track V1 (500% Scale + Gaussian Blur Amount=3 background duplicate of V3)
    v1_cont = get_track_items_container(vtg, 0)
    v1_cont.clear()
    v1_cont.attrib["Version"] = "1"
    v1_chain_tmpl_id = id100["7437"].find(".//Components").attrib["ObjectRef"]
    for cinfo in v3_clips:
        new_chain_id, _, _ = clone_subgraph_into(
            "id", v1_chain_tmpl_id, id100, uid100, root, next_oid
        )
        vc_orig = cinfo["vc_el"]
        sc_orig = cinfo["sc_el"]
        ti_orig = cinfo["ti_el"]

        new_vc = copy.deepcopy(vc_orig)
        new_vc_id = str(next_oid())
        new_vc.attrib["ObjectID"] = new_vc_id
        cid_el = new_vc.find(".//ClipID")
        if cid_el is not None:
            cid_el.text = str(uuid.uuid4())
        root.append(new_vc)

        new_sc = copy.deepcopy(sc_orig)
        new_sc_id = str(next_oid())
        new_sc.attrib["ObjectID"] = new_sc_id
        new_sc.find("Clip").attrib["ObjectRef"] = new_vc_id
        root.append(new_sc)

        new_ti = copy.deepcopy(ti_orig)
        new_ti_id = str(next_oid())
        new_ti.attrib["ObjectID"] = new_ti_id
        new_ti.find(".//Components").attrib["ObjectRef"] = new_chain_id
        new_ti.find(".//SubClip").attrib["ObjectRef"] = new_sc_id
        links_el = new_ti.find(".//Links")
        if links_el is not None:
            links_el.clear()
            links_el.attrib["Version"] = "1"
        root.append(new_ti)
        append_ti_to_track(v1_cont, new_ti_id)

    refresh_maps()
    for c in v1_cont.findall("TrackItem"):
        strip_lumetri_from_ti(by_id[c.attrib["ObjectRef"]], by_id)

    # 4. Populate Track V2 (Brand Frame PNG)
    v2_cont = get_track_items_container(vtg, 1)
    v2_cont.clear()
    v2_cont.attrib["Version"] = "1"
    new_v2_ti_id, _, _ = clone_subgraph_into("id", "7566", id100, uid100, root, next_oid)
    refresh_maps()
    strip_lumetri_from_ti(by_id[new_v2_ti_id], by_id)
    set_trackitem_timing(by_id[new_v2_ti_id], by_id, 0, total_ticks, preserve_inpoint=True)
    append_ti_to_track(v2_cont, new_v2_ti_id)

    # 5. Populate Track V6 (Only-Logo.png) and Track V7 (wtm.png)
    v6_cont = get_track_items_container(vtg, 5)
    v6_cont.clear()
    v6_cont.attrib["Version"] = "1"
    new_v6_ti_id, _, _ = clone_subgraph_into("id", "7626", id100, uid100, root, next_oid)
    refresh_maps()
    set_trackitem_timing(by_id[new_v6_ti_id], by_id, 0, total_ticks, preserve_inpoint=True)
    append_ti_to_track(v6_cont, new_v6_ti_id)

    v7_cont = get_track_items_container(vtg, 6)
    v7_cont.clear()
    v7_cont.attrib["Version"] = "1"
    new_v7_ti_id, _, _ = clone_subgraph_into("id", "7629", id100, uid100, root, next_oid)
    refresh_maps()
    set_trackitem_timing(by_id[new_v7_ti_id], by_id, 0, total_ticks, preserve_inpoint=True)
    append_ti_to_track(v7_cont, new_v7_ti_id)

    # 6. Apply Logo & Watermark Shielding on Track V3
    blur_added_count = 0
    extra_cfg = EXTRA_BLUR_CLIPS.get(kb, {})
    for cinfo in v3_clips:
        idx = cinfo["index"]
        name = cinfo["name"]
        ti_el = cinfo["ti_el"]
        chain_el = by_id[ti_el.find(".//Components").attrib["ObjectRef"]]
        cc_inner = chain_el.find("ComponentChain")
        comps_el = cc_inner.find("Components")
        has_blur = (
            comps_el is not None
            and any(
                by_id[c.attrib["ObjectRef"]].findtext("MatchName") == "AE.Impact_Blur_FX"
                for c in comps_el.findall("Component")
                if c.attrib["ObjectRef"] in by_id
            )
        )
        if has_blur:
            continue

        tmpl_choice = None
        if name.startswith("itv."):
            if kb in ("kb105", "kb106", "kb108", "kb109"):
                tmpl_choice = ("105", "2425")
            elif kb == "kb107":
                tmpl_choice = ("100", "8264")
            elif kb == "kb110":
                tmpl_choice = ("105", "2425") if idx <= 2 else ("100", "8264")
        elif idx in extra_cfg.get("single_bc", []) and idx in extra_cfg.get("single_tl", []):
            tmpl_choice = ("105", "2425")
        elif idx in extra_cfg.get("single_bc", []):
            tmpl_choice = ("105", "2493")
        elif idx in extra_cfg.get("single_tl", []):
            tmpl_choice = ("100", "8550")

        if tmpl_choice is not None:
            if comps_el is None:
                comps_el = ET.SubElement(cc_inner, "Components", {"Version": "1"})
            src_tag, comp_oid = tmpl_choice
            if src_tag == "105":
                new_comp_id, _, _ = clone_subgraph_into("id", comp_oid, id105_tmpl, uid105_tmpl, root, next_oid)
            else:
                new_comp_id, _, _ = clone_subgraph_into("id", comp_oid, id100, uid100, root, next_oid)
            c_idx = len(comps_el.findall("Component"))
            c_sub = ET.SubElement(comps_el, "Component")
            c_sub.attrib["Index"] = str(c_idx)
            c_sub.attrib["ObjectRef"] = new_comp_id
            blur_added_count += 1

    refresh_maps()

    # 7. Populate Track V4 (Vision-Tracked & Semantically Matched Emoji Impact Shields)
    v4_cont = get_track_items_container(vtg, 3)
    if kb == "kb105":
        # Keep the 4 user-placed emojis in 0..160s, drop the stray 17.mp4 clip on V4
        kept_v4 = []
        for c in v4_cont.findall("TrackItem"):
            oid = c.attrib["ObjectRef"]
            sc = by_id[by_id[oid].find(".//SubClip").attrib["ObjectRef"]]
            if (sc.findtext("Name") or "").endswith(".gif"):
                kept_v4.append(oid)
        v4_cont.clear()
        v4_cont.attrib["Version"] = "1"
        for oid in kept_v4:
            append_ti_to_track(v4_cont, oid)
    else:
        v4_cont.clear()
        v4_cont.attrib["Version"] = "1"

    emoji_plans = VISION_EMOJI_PLANS.get(kb, [])
    emoji_clip_set = {p[0] for p in emoji_plans}
    for clip_idx, rel_st_sec, dur_sec, em_type, scale_pct, pts in emoji_plans:
        if clip_idx >= len(v3_clips):
            continue
        cinfo = v3_clips[clip_idx]
        em_start = cinfo["start_ticks"] + int(round(rel_st_sec * TICKS_PER_SEC))
        em_dur = int(round(dur_sec * TICKS_PER_SEC))
        em_end = min(cinfo["end_ticks"], em_start + em_dur)
        actual_dur = max(1, em_end - em_start)

        src_kb, tmpl_em_id = EMOJI_TEMPLATES[em_type]
        _, s_id, s_uid = SRC_PROJECTS[src_kb]
        new_em_ti_id, _, _ = clone_subgraph_into("id", tmpl_em_id, s_id, s_uid, root, next_oid)
        refresh_maps()
        # Set InPoint = 0 so keyframe ticks [0 .. actual_dur] align with timeline playback!
        set_trackitem_timing(by_id[new_em_ti_id], by_id, em_start, em_end, preserve_inpoint=False, explicit_in_ticks=0)
        set_emoji_motion_keyframes(by_id[new_em_ti_id], by_id, actual_dur, scale_pct, pts)
        append_ti_to_track(v4_cont, new_em_ti_id)
    reindex_track_items(v4_cont)

    # 8. Populate Track V8 (Safety Context Essential Graphics Text)
    v8_cont = get_track_items_container(vtg, 7)
    existing_v8_end = 0
    for c in v8_cont.findall("TrackItem"):
        oid = c.attrib["ObjectRef"]
        en = int(by_id[oid].findtext(".//End") or 0)
        if en > existing_v8_end:
            existing_v8_end = en

    v8_added = 0
    for cinfo in v3_clips:
        if cinfo["start_ticks"] < existing_v8_end + int(2.0 * TICKS_PER_SEC):
            continue
        if cinfo["index"] % 4 == 1 or cinfo["index"] in emoji_clip_set:
            tmpl_g_id = V8_GRAPHIC_TEMPLATES_100[(cinfo["index"] + v8_added) % len(V8_GRAPHIC_TEMPLATES_100)]
            new_g_ti_id, _, _ = clone_subgraph_into("id", tmpl_g_id, id100, uid100, root, next_oid)
            refresh_maps()
            set_trackitem_timing(by_id[new_g_ti_id], by_id, cinfo["start_ticks"], cinfo["end_ticks"], preserve_inpoint=True)
            append_ti_to_track(v8_cont, new_g_ti_id)
            existing_v8_end = cinfo["end_ticks"]
            v8_added += 1
    reindex_track_items(v8_cont)

    # 9. Populate Track A3 (Context-Matched & Peak-Aligned SFX from 401-file SFX Vault)
    a2_cont = get_track_items_container(atg, 1)
    a2_intervals = []
    for c in a2_cont.findall("TrackItem"):
        ti_el = by_id[c.attrib["ObjectRef"]]
        a2_intervals.append((int(ti_el.findtext(".//Start") or 0), int(ti_el.findtext(".//End") or 0)))

    a3_cont = get_track_items_container(atg, 2)
    existing_a3_intervals = []
    for c in a3_cont.findall("TrackItem"):
        ti_el = by_id[c.attrib["ObjectRef"]]
        existing_a3_intervals.append((int(ti_el.findtext(".//Start") or 0), int(ti_el.findtext(".//End") or 0)))

    def overlaps_any(st, en, intervals):
        for a, b in intervals:
            if st < b and en > a:
                return True
        return False

    sfx_plans = CONTEXT_SFX_PLANS.get(kb, [])
    for clip_idx, impact_rel_sec, sfx_name in sfx_plans:
        if clip_idx >= len(v3_clips):
            continue
        cinfo = v3_clips[clip_idx]
        cat_info = SFX_CATALOG_DATA.get(sfx_name, {"dur_sec": 1.5, "peak_offset_sec": 0.25})
        full_dur_sec = cat_info["dur_sec"]
        peak_off_sec = cat_info["peak_offset_sec"]

        # Cap overly long environmental/crash SFX to a tight 2.5s..3.5s window around its acoustic peak
        play_dur_sec = min(full_dur_sec, 3.2)
        if full_dur_sec > 3.2 and peak_off_sec > 1.2:
            in_offset_sec = max(0.0, min(full_dur_sec - play_dur_sec, peak_off_sec - 0.8))
            eff_peak_sec = peak_off_sec - in_offset_sec
        else:
            in_offset_sec = 0.0
            eff_peak_sec = min(play_dur_sec * 0.5, peak_off_sec)

        impact_seq_ticks = cinfo["start_ticks"] + int(round(impact_rel_sec * TICKS_PER_SEC))
        sfx_start = max(0, impact_seq_ticks - int(round(eff_peak_sec * TICKS_PER_SEC)))
        sfx_end = min(total_ticks, sfx_start + int(round(play_dur_sec * TICKS_PER_SEC)))
        if sfx_end <= sfx_start:
            continue
        if overlaps_any(sfx_start, sfx_end, a2_intervals) or overlaps_any(sfx_start, sfx_end, existing_a3_intervals):
            continue

        new_sfx_ti_id = clone_sfx_into_project(sfx_name, root, next_oid)
        refresh_maps()
        in_ticks = int(round(in_offset_sec * TICKS_PER_SEC))
        set_trackitem_timing(by_id[new_sfx_ti_id], by_id, sfx_start, sfx_end, preserve_inpoint=False, explicit_in_ticks=in_ticks)
        append_ti_to_track(a3_cont, new_sfx_ti_id)
        existing_a3_intervals.append((sfx_start, sfx_end))
    reindex_track_items(a3_cont)

    # 10. Populate Track A5 (BGM ONLY on Clips Without Original Sound) & Clean Silent A1 Clips
    a5_cont = get_track_items_container(atg, 4)
    a5_cont.clear()
    a5_cont.attrib["Version"] = "1"

    bgm_plans = SILENT_BGM_PLANS.get(kb, [])
    bgm_intervals = []
    bgm_added = 0
    for st_idx, en_idx, bgm_key in bgm_plans:
        if st_idx >= len(v3_clips):
            continue
        en_idx = min(len(v3_clips) - 1, en_idx)
        st_ticks = v3_clips[st_idx]["start_ticks"]
        en_ticks = v3_clips[en_idx]["end_ticks"]
        if en_ticks <= st_ticks:
            continue

        src_kb, bgm_tmpl_id, bgm_max_dur = BGM_TEMPLATES[bgm_key]
        _, s_id, s_uid = SRC_PROJECTS[src_kb]
        # If the silent montage interval is longer than bgm_max_dur, cap or tile cleanly;
        # note Kazoom (50.3s), Angel Lover (50.5s), Greaser (41.0s) have full 120s+ source media!
        new_bgm_ti_id, _, _ = clone_subgraph_into("id", bgm_tmpl_id, s_id, s_uid, root, next_oid)
        refresh_maps()
        set_trackitem_timing(by_id[new_bgm_ti_id], by_id, st_ticks, en_ticks, preserve_inpoint=True)
        append_ti_to_track(a5_cont, new_bgm_ti_id)
        bgm_intervals.append((st_ticks, en_ticks))
        bgm_added += 1
    reindex_track_items(a5_cont)

    # Remove dead-silent A1 clips that fall inside the silent BGM intervals (just like kb100..kb105)
    a1_cont = get_track_items_container(atg, 0)
    kb_aud_info = {x["index"]: x for x in AUDIO_ANALYSIS.get(kb, [])}
    kept_a1 = []
    removed_silent_a1 = 0
    for c in a1_cont.findall("TrackItem"):
        oid = c.attrib["ObjectRef"]
        ti_el = by_id[oid]
        st = int(ti_el.findtext(".//Start") or 0)
        en = int(ti_el.findtext(".//End") or 0)
        mid = (st + en) // 2
        # Check if this A1 clip is inside a BGM interval AND has dead-silent audio (rms <= -45 or peak <= -25)
        in_bgm = any(b_st <= mid <= b_en for b_st, b_en in bgm_intervals)
        if in_bgm:
            # Find matching v3 clip index
            v3_match = [vc_i["index"] for vc_i in v3_clips if vc_i["start_ticks"] <= mid <= vc_i["end_ticks"]]
            is_dead_silent = True
            if v3_match and v3_match[0] in kb_aud_info:
                ai = kb_aud_info[v3_match[0]]
                if ai["rms_db"] > -44.0 and ai["peak_db"] > -24.0:
                    is_dead_silent = False
            if is_dead_silent:
                removed_silent_a1 += 1
                continue
        kept_a1.append(oid)
    a1_cont.clear()
    a1_cont.attrib["Version"] = "1"
    for i, oid in enumerate(kept_a1):
        el = ET.SubElement(a1_cont, "TrackItem")
        el.attrib["Index"] = str(i)
        el.attrib["ObjectRef"] = str(oid)

    # 11. Apply Audio Track Mixer (Master, A1..A5) & Essential Sound (A1 Ambience + Loudness + Auto-Ducking)
    target_audio_tracks = [("Master", master_tr_el)]
    for tr_ref in atg.findall("./TrackGroup/Tracks/Track"):
        t_idx = int(tr_ref.attrib["Index"])
        t_uid = tr_ref.attrib["ObjectURef"]
        tname = f"A{t_idx + 1}"
        if tname in TRACK_FILTER_TEMPLATES_100 and t_uid in by_uid:
            target_audio_tracks.append((tname, by_uid[t_uid]))

    for tname, tr_el in target_audio_tracks:
        props_el = tr_el.find("./Track/Node/Properties")
        if props_el is None:
            props_el = tr_el.find("./ClipTrack/Track/Node/Properties")
        if props_el is not None:
            existing_tags = {c.tag for c in props_el}
            for k, v in MIXER_UI_PROPS:
                if k not in existing_tags:
                    sub = ET.SubElement(props_el, k)
                    sub.text = v

        chain_ref = tr_el.find(".//Components").attrib["ObjectRef"]
        chain_el = by_id[chain_ref]
        comps_container = chain_el.find("./ComponentChain/Components")
        fader_meter_refs = [
            c.attrib["ObjectRef"]
            for c in comps_container.findall("Component")
            if by_id[c.attrib["ObjectRef"]].tag in ("AudioFader", "AudioMeter")
        ]
        new_filter_refs = []
        for tmpl_f_oid in TRACK_FILTER_TEMPLATES_100[tname]:
            nf_id, _, _ = clone_subgraph_into("id", tmpl_f_oid, id100, uid100, root, next_oid)
            new_filter_refs.append(nf_id)

        all_refs = new_filter_refs + fader_meter_refs
        comps_container.clear()
        comps_container.attrib["Version"] = "1"
        for i_c, ref_id in enumerate(all_refs):
            c_el = ET.SubElement(comps_container, "Component")
            c_el.attrib["Index"] = str(i_c)
            c_el.attrib["ObjectRef"] = ref_id

    refresh_maps()

    a1_esp_count = 0
    for c in a1_cont.findall("TrackItem"):
        acti = by_id[c.attrib["ObjectRef"]]
        ti = acti.find("./ClipTrackItem/TrackItem")
        if ti is None:
            continue
        node = ti.find("Node")
        if node is None:
            node = ET.Element("Node", {"Version": "1"})
            props = ET.SubElement(node, "Properties", {"Version": "1"})
            ti.insert(0, node)
        else:
            props = node.find("Properties")
            if props is None:
                props = ET.Element("Properties", {"Version": "1"})
                node.insert(0, props)
        existing_tags = {ch.tag for ch in props}
        for k, v in ESP_AMBIENCE_PROPS:
            if k not in existing_tags:
                sub = ET.SubElement(props, k)
                sub.text = v
        a1_esp_count += 1

    # Canonicalize into exact Premiere Pro BFS discovery order and serialize
    canon_root, id_map = canonicalize_prproj(root, dict(GLOBAL_BH_POOL))
    gz_bytes = serialize_prproj_bytes(canon_root)
    with open(prproj_path, "wb") as f:
        f.write(gz_bytes)

    print(
        f"[{kb}] DONE: V1={len(v3_clips)} blur_bg | V2=1 frame | V3={len(v3_clips)} (+{blur_added_count} mask_blurs) | "
        f"V4={len(v4_cont.findall('TrackItem'))} tracked_emojis | V6=1 logo | V7=1 wtm | "
        f"V8={len(v8_cont.findall('TrackItem'))} graphics | A3={len(a3_cont.findall('TrackItem'))} sfx | "
        f"A5={bgm_added} silent_bgm (-{removed_silent_a1} silent_A1) | A1_ESP={a1_esp_count} | Objects={len(id_map)}"
    )


if __name__ == "__main__":
    for kb_name in ["kb105", "kb106", "kb107", "kb108", "kb109", "kb110"]:
        process_project(kb_name)

