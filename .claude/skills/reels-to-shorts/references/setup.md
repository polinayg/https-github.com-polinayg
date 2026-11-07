# One-time setup

## Instagram (optional — needed only to pull reels automatically)

The Instagram API works with **Business or Creator** accounts.

1. In the Instagram app: Settings → Account type → switch to Creator or Business (free).
2. Go to <https://developers.facebook.com/apps> → **Create app** → use case
   **"Manage messaging & content on Instagram"** → skip the business step → **Create app**.
3. Dashboard → **Use cases → Customize** → **API setup with Unified login**.
   (New apps no longer get "API setup with Instagram login".)
4. Connect a **business portfolio** when asked (free; create one with your name/brand).
5. Under **Configure your app** → **Create new configuration**, choose your Instagram account
   as the asset, and generate the **system-user access token**. It never expires.
6. Make it available to the scripts:
   ```bash
   export IG_ACCESS_TOKEN="…"
   ```
   `fetch_reels.py` finds the Instagram account automatically. If it can't, find the
   account's id in the business portfolio settings and also `export IG_USER_ID="…"`.

Older apps that still have **API setup with Instagram login** work too: generate the token
there instead (it lasts ~60 days; refresh with
`curl "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=$IG_ACCESS_TOKEN"`).

Files fetched this way are the original uploads without the Instagram watermark — YouTube
down-ranks watermarked reposts, so avoid screen-recorded or third-party-downloaded copies.

**No API?** Download your reels from Instagram (Settings → Your activity → Download your
information, or save each reel from the app), put the `.mp4` files in `reels_work/videos/`,
and optionally add `<same-name>.txt` with each original caption.

## YouTube (required)

1. Go to <https://console.cloud.google.com/>, create a project.
2. *APIs & Services → Library* → enable **YouTube Data API v3**.
3. *APIs & Services → OAuth consent screen* → External, fill the basics, add your Google
   account under **Test users**.
4. *APIs & Services → Credentials → Create credentials → OAuth client ID* → type
   **Desktop app**. Download the JSON and save it as `reels_work/client_secret.json`.
5. The first upload prints a sign-in link; open it, pick the channel, approve. The token is
   saved in `reels_work/youtube_token.json` for later runs.

### Quota

Default quota is 10,000 units/day; each upload costs ~1,600, so about **6 uploads per day**.
`posted.json` remembers what's done, so just rerun the next day. You can request more quota
in the Cloud Console.

### Unverified projects

YouTube locks videos uploaded through API projects that haven't passed its compliance audit
to **private**. If uploads end up private no matter what you choose, either:
- apply for the audit: <https://support.google.com/youtube/contact/yt_api_form>, or
- upload as private and switch each to public in YouTube Studio (one click per video).
