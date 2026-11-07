#!/usr/bin/env python3
"""Collect reels into a manifest, from the Instagram API or a local folder.

Instagram:  IG_ACCESS_TOKEN=... fetch_reels.py --out reels_work --limit 10
Local:      fetch_reels.py --out reels_work --local path/to/mp4s
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://graph.instagram.com/v21.0"
FIELDS = ("id,caption,media_type,media_product_type,media_url,permalink,"
          "timestamp,like_count,comments_count")
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}


def load_posted(out: Path) -> set:
    log = out / "posted.json"
    if not log.exists():
        return set()
    return {e["source_id"] for e in json.loads(log.read_text())}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def fetch_instagram(token: str, limit: int, skip: set):
    url = f"{API}/me/media?" + urllib.parse.urlencode(
        {"fields": FIELDS, "limit": 50, "access_token": token})
    found = []
    while url and len(found) < limit:
        try:
            page = get_json(url)
        except urllib.error.HTTPError as e:
            sys.exit(f"Instagram API error {e.code}: {e.read().decode()[:500]}")
        for m in page.get("data", []):
            is_reel = m.get("media_product_type") == "REELS" or m.get("media_type") == "VIDEO"
            if is_reel and m["id"] not in skip and m.get("media_url"):
                found.append(m)
                if len(found) >= limit:
                    break
        url = page.get("paging", {}).get("next")
    return found


def download(url: str, dest: Path):
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reels_work")
    ap.add_argument("--limit", type=int, default=10, help="max reels to fetch")
    ap.add_argument("--local", help="folder of video files instead of the Instagram API")
    a = ap.parse_args()

    out = Path(a.out)
    videos = out / "videos"
    videos.mkdir(parents=True, exist_ok=True)
    (out / "metadata").mkdir(exist_ok=True)
    skip = load_posted(out)
    manifest = []

    if a.local:
        for p in sorted(Path(a.local).iterdir()):
            if p.suffix.lower() not in VIDEO_EXTS or p.stem in skip:
                continue
            cap = p.with_suffix(".txt")
            manifest.append({
                "id": p.stem,
                "video_path": str(p),
                "caption": cap.read_text().strip() if cap.exists() else "",
                "permalink": None,
                "timestamp": None,
            })
            if len(manifest) >= a.limit:
                break
    else:
        token = os.environ.get("IG_ACCESS_TOKEN")
        if not token:
            sys.exit("IG_ACCESS_TOKEN is not set. See references/setup.md, or use --local.")
        for m in fetch_instagram(token, a.limit, skip):
            dest = videos / f"{m['id']}.mp4"
            if not dest.exists():
                print(f"downloading {m['id']} …", file=sys.stderr)
                download(m["media_url"], dest)
            manifest.append({
                "id": m["id"],
                "video_path": str(dest),
                "caption": m.get("caption", ""),
                "permalink": m.get("permalink"),
                "timestamp": m.get("timestamp"),
                "like_count": m.get("like_count"),
                "comments_count": m.get("comments_count"),
            })

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"{len(manifest)} reel(s) → {out / 'manifest.json'} "
          f"({len(skip)} already posted were skipped)")


if __name__ == "__main__":
    main()
