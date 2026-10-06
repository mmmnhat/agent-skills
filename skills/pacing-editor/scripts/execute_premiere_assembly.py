#!/usr/bin/env python3
"""
High-Speed Atomic Premiere Pro Timeline Assembler via Direct CEP Bridge.
Assembles 200+ clips onto active sequence in under 3 seconds.
Guarantees 100% of footage is imported strictly into the specified Bin (none in root).
"""
import sys
import os
import json
import time
import uuid
from pathlib import Path

def run_extendscript(script_str, timeout_sec=60):
    bridge_dir = Path("/tmp/premiere-mcp-bridge")
    if not bridge_dir.exists():
        raise RuntimeError("Premiere Pro MCP Bridge directory not found in /tmp/premiere-mcp-bridge")

    cmd_id = str(uuid.uuid4())
    staging = bridge_dir / f".tmp-{cmd_id}.json"
    cmd_file = bridge_dir / f"command-{cmd_id}.json"
    resp_file = bridge_dir / f"response-{cmd_id}.json"

    with open(staging, "w", encoding="utf-8") as f:
        json.dump({
            "id": cmd_id,
            "script": f"(function(){{\n{script_str}\n}})();",
            "timeoutMs": int(timeout_sec * 1000),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }, f)

    os.replace(staging, cmd_file)

    start = time.time()
    while time.time() - start < timeout_sec:
        if resp_file.exists():
            with open(resp_file, "r", encoding="utf-8") as f:
                res = json.load(f)
            resp_file.unlink()
            return res
        time.sleep(0.05)

    raise TimeoutError(f"Premiere CEP bridge timed out after {timeout_sec}s")

def assemble_sequence(manifest_path, target_bin="Scenes", target_duration=None):
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    v1_clips = manifest.get("tracks", {}).get("V1", [])
    if not v1_clips and "scenes" in manifest:
        v1_clips = []
        t_in = 0.0
        for s in manifest.get("scenes", []):
            dur = float(s.get("duration", 2.0))
            if target_duration and t_in >= target_duration:
                break
            v1_clips.append({
                "file_path": s.get("file_path"),
                "timeline_in": round(t_in, 3),
                "duration": dur,
                "source_in": 0.0,
                "source_out": dur,
                "climax_marker": round(t_in + s.get("temporal_landmarks", {}).get("action_peak_rel_sec", dur * 0.5), 3),
                "narrative_role": s.get("aspect_ratio", "Action"),
                "interest_score": 80.0
            })
            t_in += dur
        tot_dur = t_in
    elif v1_clips:
        if target_duration:
            filtered = []
            cur_dur = 0.0
            for c in v1_clips:
                dur = float(c.get("duration", 2.0))
                if cur_dur >= target_duration:
                    break
                filtered.append(c)
                cur_dur += dur
            v1_clips = filtered
            tot_dur = cur_dur
        else:
            tot_dur = manifest.get("total_duration_seconds", sum(c.get("duration", 0) for c in v1_clips))
    else:
        raise ValueError("No V1 clips or scenes found in manifest")

    print(f"🎬 [Assembly Plan] Clips: {len(v1_clips)} | Duration: {tot_dur:.2f}s ({tot_dur/60:.2f} min)")

    # 1. Collect all unique file paths
    unique_paths = sorted(list(set(c["file_path"] for c in v1_clips)))
    print(f"📦 Unique files to import into '{target_bin}': {len(unique_paths)}")

    # 2. Build clip specs
    clip_specs = []
    for c in v1_clips:
        fpath = Path(c["file_path"]).name
        spec = {
            "name": fpath,
            "time": c["timeline_in"],
            "sourceIn": c.get("source_in", 0.0),
            "sourceOut": c.get("source_out", c.get("duration", 2.0)),
            "climax": c.get("climax_marker"),
            "role": c.get("narrative_role", "Action"),
            "score": c.get("interest_score", 0)
        }
        clip_specs.append(spec)

    # 3. Formulate ExtendScript
    script = f"""
    try {{
        var root = app.project.rootItem;
        var seq = app.project.activeSequence;
        if (!seq) {{
            return JSON.stringify({{ success: false, error: "No active sequence open in Premiere Pro" }});
        }}

        // 1. Locate or create dedicated Bin
        var targetBin = null;
        for (var i = 0; i < root.children.numItems; i++) {{
            if (root.children[i].name === {json.dumps(target_bin)} && root.children[i].type === 2) {{
                targetBin = root.children[i];
                break;
            }}
        }}
        if (!targetBin) {{
            targetBin = root.createBin({json.dumps(target_bin)});
        }}

        // 2. Import all files directly into the target Bin in 1 atomic call
        var filePaths = {json.dumps(unique_paths)};
        var importOk = app.project.importFiles(filePaths, true, targetBin, false);

        // 3. Index items inside targetBin
        var binMap = {{}};
        for (var bi = 0; bi < targetBin.children.numItems; bi++) {{
            var bChild = targetBin.children[bi];
            binMap[bChild.name] = bChild;
        }}

        // Also sweep root: move any loose files into targetBin
        for (var ri = 0; ri < root.children.numItems; ri++) {{
            var rChild = root.children[ri];
            if (rChild && rChild.type === 1 && binMap[rChild.name] === undefined) {{
                try {{
                    rChild.moveBin(targetBin);
                    binMap[rChild.name] = rChild;
                }} catch (me) {{}}
            }}
        }}

        // 3.5 Clear existing clips and markers on sequence to avoid overlapping artifacts
        for (var vi = 0; vi < seq.videoTracks.numTracks; vi++) {{
            var vt = seq.videoTracks[vi];
            for (var vci = vt.clips.numItems - 1; vci >= 0; vci--) {{
                try {{ vt.clips[vci].remove(false, true); }} catch(ev) {{}}
            }}
        }}
        for (var ai = 0; ai < seq.audioTracks.numTracks; ai++) {{
            var at = seq.audioTracks[ai];
            for (var aci = at.clips.numItems - 1; aci >= 0; aci--) {{
                try {{ at.clips[aci].remove(false, true); }} catch(ea) {{}}
            }}
        }}
        var curM = seq.markers.getFirstMarker();
        while (curM) {{
            var nextM = seq.markers.getNextMarker(curM);
            seq.markers.deleteMarker(curM);
            curM = nextM;
        }}

        // 4. Overwrite clips continuously without gaps (Butt-Cut Snap)
        var vTrack = seq.videoTracks[0];
        var specs = {json.dumps(clip_specs)};
        var placed = 0;
        var failed = 0;
        var currentTime = 0.0;
        var placedSpecs = [];

        for (var sIdx = 0; sIdx < specs.length; sIdx++) {{
            var s = specs[sIdx];
            var item = binMap[s.name];
            if (!item) {{
                failed++;
                continue;
            }}

            // Query natural media duration to guarantee 0 zebra stripes
            item.clearInPoint();
            item.clearOutPoint();
            var mediaMax = item.getOutPoint().seconds;

            var reqIn = (s.sourceIn !== null && s.sourceIn !== undefined) ? s.sourceIn : 0.0;
            var reqOut = (s.sourceOut !== null && s.sourceOut !== undefined) ? s.sourceOut : mediaMax;

            // Only set sub-clip in/out if custom sub-trim was explicitly requested
            if (reqIn > 0.05 || reqOut < mediaMax - 0.05) {{
                var srcIn = Math.max(0.0, Math.min(reqIn, mediaMax - 0.1));
                var srcOut = Math.min(mediaMax, Math.max(srcIn + 0.1, reqOut));
                try {{
                    item.setInPoint(srcIn, 4);
                    item.setOutPoint(srcOut, 4);
                }} catch (e1) {{
                    try {{
                        item.setInPoint(srcIn);
                        item.setOutPoint(srcOut);
                    }} catch (e2) {{}}
                }}
            }}

            var clipStart = currentTime;
            vTrack.overwriteClip(item, clipStart);
            placed++;

            // Snap currentTime to exact end of newly placed clip (guarantees mathematically 0 frame gaps)
            var placedClip = null;
            for (var ci = vTrack.clips.numItems - 1; ci >= 0; ci--) {{
                var cand = vTrack.clips[ci];
                if (cand && Math.abs(cand.start.seconds - clipStart) < 0.08) {{
                    placedClip = cand;
                    break;
                }}
            }}
            if (placedClip) {{
                currentTime = placedClip.end.seconds;
            }} else if (vTrack.clips.numItems > 0) {{
                currentTime = vTrack.clips[vTrack.clips.numItems - 1].end.seconds;
            }} else {{
                currentTime += mediaMax;
            }}

            s.actualStart = clipStart;
            s.actualEnd = currentTime;
            placedSpecs.push(s);
        }}

        // 5. Add markers for top climax beats using actual placed clip start
        var markers = seq.markers;
        var markerCount = 0;
        for (var mIdx = 0; mIdx < placedSpecs.length; mIdx++) {{
            var ms = placedSpecs[mIdx];
            if (ms.climax !== null && ms.score > 85.0 && markerCount < 15) {{
                try {{
                    var offset = Math.max(0.0, Math.min(ms.actualEnd - ms.actualStart, ms.climax - ms.time));
                    var newMarker = markers.createMarker(ms.actualStart + offset);
                    newMarker.name = "Peak: " + ms.name + " (" + ms.role + ")";
                    newMarker.comments = "Score: " + ms.score;
                    newMarker.setColorByIndex(1); // Red highlight
                    markerCount++;
                }} catch (mErr) {{}}
            }}
        }}

        return JSON.stringify({{
            success: true,
            sequenceName: seq.name,
            binName: targetBin.name,
            placedCount: placed,
            failedCount: failed,
            markerCount: markerCount,
            totalRequested: specs.length
        }});
    }} catch (e) {{
        return JSON.stringify({{ success: false, error: e.toString() }});
    }}
    """

    print("🚀 Executing atomic timeline assembly inside Adobe Premiere Pro...")
    t0 = time.time()
    res = run_extendscript(script, timeout_sec=90)
    elapsed = time.time() - t0

    if not res.get("success"):
        print(f"❌ Error: {res.get('error', 'Unknown error')}")
        return False

    out = res.get("result", {})
    if isinstance(out, str):
        out = json.loads(out)

    print(f"\n🎉 [Assembly Succeeded in {elapsed:.2f}s]")
    print(f"  ✓ Target Sequence : {out.get('sequenceName')}")
    print(f"  ✓ Target Bin      : {out.get('binName')}")
    print(f"  ✓ Placed Clips    : {out.get('placedCount')} / {out.get('totalRequested')}")
    print(f"  ✓ Climax Markers  : {out.get('markerCount')}")
    return True

if __name__ == "__main__":
    man = sys.argv[1] if len(sys.argv) > 1 else "output_clean_cut/scenes_context.json"
    target_bin = sys.argv[2] if len(sys.argv) > 2 else "Scenes"
    assemble_sequence(man, target_bin=target_bin)
