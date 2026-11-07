#!/usr/bin/env python3
"""Upload one video to YouTube as a Short using a metadata JSON file.

upload_short.py --video V.mp4 --meta M.json --source-id ID --privacy public \
    --secrets reels_work/client_secret.json --log reels_work/posted.json [--dry-run]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def validate(meta: dict) -> list:
    errs = []
    title = meta.get("title", "")
    desc = meta.get("description", "")
    tags = meta.get("tags", [])
    if not title.strip():
        errs.append("title is empty")
    if len(title) > 100:
        errs.append(f"title is {len(title)} chars (max 100)")
    if len(desc.encode()) > 5000:
        errs.append(f"description is {len(desc.encode())} bytes (max 5000)")
    for name, val in (("title", title), ("description", desc)):
        if "<" in val or ">" in val:
            errs.append(f"{name} contains < or >")
    # YouTube counts quoted tags with spaces as +2 chars, plus a comma between tags.
    tag_len = sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)
    if tag_len > 500:
        errs.append(f"tags total {tag_len} chars (max 500)")
    if "#shorts" not in (title + " " + desc).lower():
        errs.append("add #Shorts to the title or description")
    return errs


def youtube_client(secrets: Path, token: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secrets.exists():
                sys.exit(f"{secrets} not found. See references/setup.md → YouTube.")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)
        token.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--source-id", required=True, help="reel id, for the duplicate log")
    ap.add_argument("--privacy", default="private", choices=["public", "unlisted", "private"])
    ap.add_argument("--publish-at", help="ISO 8601 time to go public (uploads as private)")
    ap.add_argument("--secrets", default="reels_work/client_secret.json")
    ap.add_argument("--token", default=None, help="defaults to youtube_token.json beside --secrets")
    ap.add_argument("--log", default="reels_work/posted.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    meta = json.loads(Path(a.meta).read_text())
    if errs := validate(meta):
        sys.exit("Metadata problems:\n  - " + "\n  - ".join(errs))

    log_path = Path(a.log)
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    if any(e["source_id"] == a.source_id for e in log):
        sys.exit(f"{a.source_id} is already in {log_path}; not uploading twice.")
    if not Path(a.video).exists():
        sys.exit(f"video not found: {a.video}")

    status = {
        "privacyStatus": "private" if a.publish_at else a.privacy,
        "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", False)),
    }
    if a.publish_at:
        status["publishAt"] = a.publish_at
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "categoryId": str(meta.get("category_id", "22")),
        },
        "status": status,
    }

    if a.dry_run:
        print("DRY RUN – metadata valid. Would upload:")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    secrets = Path(a.secrets)
    token = Path(a.token) if a.token else secrets.parent / "youtube_token.json"
    yt = youtube_client(secrets, token)
    media = MediaFileUpload(a.video, mimetype="video/*", chunksize=8 << 20, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    resp = None
    try:
        while resp is None:
            prog, resp = req.next_chunk(num_retries=5)
            if prog:
                print(f"  {int(prog.progress() * 100)}%", file=sys.stderr)
    except HttpError as e:
        sys.exit(f"YouTube API error {e.resp.status}: {e.content.decode()[:800]}")

    vid = resp["id"]
    entry = {
        "source_id": a.source_id,
        "youtube_id": vid,
        "url": f"https://youtube.com/shorts/{vid}",
        "title": meta["title"],
        "privacy": status["privacyStatus"],
        "publish_at": a.publish_at,
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    log.append(entry)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()
