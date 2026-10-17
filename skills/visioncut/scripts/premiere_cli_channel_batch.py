"""High-speed channel-aware Premiere-CLI batch executor for VisionCut.

Executes Crop (unblur pillarbox/letterbox), Scale (fit-to-frame + edge-logo push),
and Track V2 feathered Gaussian Blur + Crop logo shields in < 15 seconds via
direct HTTP requests to the premiere-cli bridge daemon (127.0.0.1:47823/command).
"""

import argparse
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BRIDGE_URL = "http://127.0.0.1:47823/command"
PROFILES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources",
    "channel_profiles.json",
)


def call_cli_bridge(command: str, args: dict) -> dict:
  body = json.dumps({"command": command, "args": args}).encode("utf-8")
  req = urllib.request.Request(
      BRIDGE_URL,
      data=body,
      headers={"Content-Type": "application/json"},
      method="POST",
  )
  with urllib.request.urlopen(req, timeout=30) as resp:
    return json.loads(resp.read().decode("utf-8"))


def apply_batch_plan(sequence_name: str, plan_path: str) -> dict:
  with open(plan_path, "r", encoding="utf-8") as f:
    plan = json.load(f)

  scaled = 0
  cropped = 0
  shielded = 0

  for item in plan.get("v1_clips", []):
    ci = item["clipIndex"]
    if "scale" in item and item["scale"] is not None:
      res = call_cli_bridge(
          "set-clip-scale",
          {
              "sequenceName": sequence_name,
              "trackType": "video",
              "trackIndex": 0,
              "clipIndex": ci,
              "scale": float(item["scale"]),
          },
      )
      if res.get("ok"):
        scaled += 1

    crop = item.get("crop")
    if crop:
      call_cli_bridge(
          "apply-effect",
          {
              "sequenceName": sequence_name,
              "trackType": "video",
              "trackIndex": 0,
              "clipIndex": ci,
              "effectName": "Crop",
          },
      )
      for prop, key in [
          ("Left", "left"),
          ("Top", "top"),
          ("Right", "right"),
          ("Bottom", "bottom"),
      ]:
        val = float(crop.get(key, 0.0))
        if val > 0:
          call_cli_bridge(
              "set-effect-property",
              {
                  "sequenceName": sequence_name,
                  "trackType": "video",
                  "trackIndex": 0,
                  "clipIndex": ci,
                  "componentName": "Crop",
                  "propertyName": prop,
                  "value": val,
                  "valueType": "number",
              },
          )
      cropped += 1

  for sh in plan.get("v2_shields", []):
    v1_ci = sh["v1ClipIndex"]
    info = call_cli_bridge(
        "get-full-clip-info",
        {
            "sequenceName": sequence_name,
            "trackType": "video",
            "trackIndex": 0,
            "clipIndex": v1_ci,
        },
    )["result"]
    nid = info["projectItem"]["nodeId"]
    call_cli_bridge(
        "set-item-in-out",
        {
            "nodeId": nid,
            "inSeconds": info["inPointSeconds"],
            "outSeconds": info["outPointSeconds"],
        },
    )
    add_res = call_cli_bridge(
        "add-to-timeline",
        {
            "sequenceName": sequence_name,
            "nodeId": nid,
            "trackType": "video",
            "trackIndex": 1,
            "startSeconds": info["startSeconds"],
            "mode": "overwrite",
        },
    )["result"]
    v2_idx = add_res["trackClipCountAfter"] - 1
    if "scale" in sh and sh["scale"] is not None:
      call_cli_bridge(
          "set-clip-scale",
          {
              "sequenceName": sequence_name,
              "trackType": "video",
              "trackIndex": 1,
              "clipIndex": v2_idx,
              "scale": float(sh["scale"]),
          },
      )
    call_cli_bridge(
        "apply-effect",
        {
            "sequenceName": sequence_name,
            "trackType": "video",
            "trackIndex": 1,
            "clipIndex": v2_idx,
            "effectName": "Gaussian Blur",
        },
    )
    call_cli_bridge(
        "apply-effect",
        {
            "sequenceName": sequence_name,
            "trackType": "video",
            "trackIndex": 1,
            "clipIndex": v2_idx,
            "effectName": "Crop",
        },
    )
    for prop, val in [
        ("Left", sh.get("left", 0)),
        ("Top", sh.get("top", 0)),
        ("Right", sh.get("right", 0)),
        ("Bottom", sh.get("bottom", 0)),
        ("Edge Feather", sh.get("feather", 15)),
    ]:
      call_cli_bridge(
          "set-effect-property",
          {
              "sequenceName": sequence_name,
              "trackType": "video",
              "trackIndex": 1,
              "clipIndex": v2_idx,
              "componentName": "Crop",
              "propertyName": prop,
              "value": float(val),
              "valueType": "number",
          },
      )
    shielded += 1

  call_cli_bridge("save-project", {})
  return {
      "sequenceName": sequence_name,
      "scaled": scaled,
      "cropped": cropped,
      "shielded": shielded,
  }


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--sequence-name", required=True)
  parser.add_argument("--plan", required=True)
  args = parser.parse_args()
  result = apply_batch_plan(args.sequence_name, args.plan)
  print(json.dumps(result, ensure_ascii=False))
