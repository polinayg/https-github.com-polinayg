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

# Instagram-login tokens use graph.instagram.com. Unified-login (system user) and
# Facebook-login tokens use graph.facebook.com with the Instagram account's id.
IG_API = "https://graph.instagram.com"
FB_API = "https://graph.facebook.com"
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


def api_get(base: str, path: str, token: str, **params) -> dict:
    q = urllib.parse.urlencode({**params, "access_token": token})
    return get_json(f"{base}/{path}?{q}")


def resolve_account(token: str, ig_user_id: str | None):
    """Return (api_base, account_id) that the token can read media from."""
    if ig_user_id:
        return FB_API, ig_user_id
    errors = []
    # 1. Instagram-login token.
    try:
        api_get(IG_API, "me", token, fields="id")
        return IG_API, "me"
    except urllib.error.HTTPError as e:
        errors.append(f"graph.instagram.com/me: {e.code}")
    # 2. Unified-login system user token: accounts assigned in the business portfolio.
    try:
        accts = api_get(FB_API, "me/assigned_instagram_accounts", token,
                        fields="id,username").get("data", [])
        if accts:
            print(f"using Instagram account @{accts[0].get('username', accts[0]['id'])}",
                  file=sys.stderr)
            return FB_API, accts[0]["id"]
        errors.append("assigned_instagram_accounts: none assigned")
    except urllib.error.HTTPError as e:
        errors.append(f"assigned_instagram_accounts: {e.code}")
    # 3. Facebook-login user token: Instagram account linked to a Page.
    try:
        for page in api_get(FB_API, "me/accounts", token,
                            fields="instagram_business_account").get("data", []):
            if iba := page.get("instagram_business_account"):
                return FB_API, iba["id"]
        errors.append("me/accounts: no Page with a linked Instagram account")
    except urllib.error.HTTPError as e:
        errors.append(f"me/accounts: {e.code}")
    sys.exit("Couldn't find an Instagram account for this token ("
             + "; ".join(errors) + "). Pass --ig-user-id, or see references/setup.md.")


def fetch_instagram(token: str, limit: int, skip: set, ig_user_id: str | None = None):
    base, acct = resolve_account(token, ig_user_id)
    url = f"{base}/{acct}/media?" + urllib.parse.urlencode(
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
    ap.add_argument("--ig-user-id", default=os.environ.get("IG_USER_ID"),
                    help="Instagram account id (only needed if auto-detect fails)")
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
        for m in fetch_instagram(token, a.limit, skip, a.ig_user_id):
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
