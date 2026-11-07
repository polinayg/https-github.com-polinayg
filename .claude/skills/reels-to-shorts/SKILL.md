---
name: reels-to-shorts
description: Repost the user's existing Instagram Reels to YouTube Shorts with a YouTube-optimized title, SEO description, hashtags and tags. Use when the user asks to repost, cross-post, repurpose or move reels/Instagram videos to YouTube Shorts, or to write Shorts titles/descriptions for their reels.
---

# Reels → YouTube Shorts

Pipeline: **fetch reels → check Shorts eligibility → write optimized metadata → user approves → upload → log**.

All scripts live in `scripts/` next to this file. Work in a folder named `reels_work/`
in the project root (it is gitignored) unless the user names another folder.

## 0. One-time setup (check first, only walk the user through what's missing)

```bash
pip install -r .claude/skills/reels-to-shorts/scripts/requirements.txt
```

Credentials (never commit them, never ask the user to paste secrets into chat if a safer route exists):

| What | Where it goes | How to get it |
|---|---|---|
| Instagram token | env `IG_ACCESS_TOKEN` | See `references/setup.md` → Instagram |
| YouTube OAuth client | `reels_work/client_secret.json` | See `references/setup.md` → YouTube |

Instagram is optional: if the user has no API token, they can drop their reel `.mp4` files
(plus an optional `.txt` with the same name holding the original caption) into
`reels_work/videos/` and you skip step 1.

## 1. Fetch reels

```bash
python .claude/skills/reels-to-shorts/scripts/fetch_reels.py --out reels_work --limit 10
# or, for local files:
python .claude/skills/reels-to-shorts/scripts/fetch_reels.py --out reels_work --local reels_work/videos
```

Writes `reels_work/manifest.json` – one entry per reel with `id`, `video_path`, `caption`,
`permalink`, `timestamp`, and `like_count`/`comments_count` when available. Reels already
in `reels_work/posted.json` are skipped automatically.

If the user named specific reels (a link, a date, a topic), filter the manifest down to those.

## 2. Check Shorts eligibility

```bash
python .claude/skills/reels-to-shorts/scripts/check_video.py reels_work/manifest.json
```

Adds a `check` block to each entry. YouTube treats an upload as a Short when it is
**≤ 3 minutes** and **vertical or square**. Report any that fail; don't upload them unless
the user insists (they'd post as regular videos).

## 3. Write optimized metadata (this is your job, not a script's)

For each eligible reel, read the original caption (and look at a few frames if the caption
is thin: `ffmpeg -ss 1 -i VIDEO -frames:v 1 frame.jpg`, then view the image). Then write
`reels_work/metadata/<id>.json` following **`references/seo-guide.md`** exactly. Shape:

```json
{
  "title": "How I Plan a Month of Content in 1 Hour #Shorts",
  "description": "…",
  "tags": ["content planning", "social media tips", "…"],
  "category_id": "22",
  "made_for_kids": false
}
```

Hard limits (the uploader validates these too): title ≤ 100 chars, description ≤ 5000
chars, no `<` or `>` anywhere, tags total ≤ 500 chars.

## 4. Get approval before anything goes live

Show the user a compact table: reel (date/permalink) → proposed title, first 2 lines of the
description, hashtags. Ask:
- approve / edit any of them,
- privacy: `public`, `unlisted`, `private`, or schedule (`--publish-at` ISO time, uploads as private and goes public then),
- how many per day (YouTube API quota allows ~6 uploads/day on a default project).

Uploading is public-facing and hard to undo — never skip this step, even if the user said
"just do it" earlier for a different batch.

## 5. Upload

```bash
python .claude/skills/reels-to-shorts/scripts/upload_short.py \
  --video reels_work/videos/<id>.mp4 \
  --meta reels_work/metadata/<id>.json \
  --source-id <id> --privacy public \
  --secrets reels_work/client_secret.json --log reels_work/posted.json
```

Add `--dry-run` to validate metadata without uploading. First real run opens a Google
sign-in link; the token is cached in `reels_work/youtube_token.json`.

Upload one at a time; stop on the first error and report it. Common errors:
- `quotaExceeded` → daily quota used up; resume tomorrow (posted.json prevents duplicates).
- Video forced to private / "locked" → the Google Cloud project hasn't passed YouTube's API
  audit; see `references/setup.md` → "Unverified projects".
- `invalidTitle` / `invalidDescription` → fix the metadata file and retry.

## 6. Report

Finish with a list of the new Shorts URLs (`https://youtube.com/shorts/<videoId>`), their
privacy/schedule, and anything skipped and why.
