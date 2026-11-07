#!/usr/bin/env python3
"""Check each video in a manifest is Shorts-eligible (<= 3 min, vertical or square).

Usage: check_video.py reels_work/manifest.json
"""
import json
import subprocess
import sys
from pathlib import Path

MAX_SECONDS = 180


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:stream_side_data=rotation:format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    w, h = s["width"], s["height"]
    rot = next((abs(int(x.get("rotation", 0))) for x in s.get("side_data_list", [])), 0)
    if rot in (90, 270):
        w, h = h, w
    return {"width": w, "height": h, "duration": round(float(d["format"]["duration"]), 1)}


def main():
    mpath = Path(sys.argv[1] if len(sys.argv) > 1 else "reels_work/manifest.json")
    manifest = json.loads(mpath.read_text())
    for e in manifest:
        try:
            info = probe(e["video_path"])
        except Exception as ex:  # missing file, bad codec, etc.
            e["check"] = {"ok": False, "problems": [f"could not read video: {ex}"]}
            continue
        problems = []
        if info["duration"] > MAX_SECONDS:
            problems.append(f"too long ({info['duration']}s > {MAX_SECONDS}s)")
        if info["width"] > info["height"]:
            problems.append(f"horizontal ({info['width']}x{info['height']})")
        e["check"] = {**info, "ok": not problems, "problems": problems}
        status = "OK " if not problems else "BAD"
        print(f"{status} {e['id']}  {info['width']}x{info['height']}  {info['duration']}s  "
              + "; ".join(problems))
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
