# 🎬 DesiTales AutoFeed

Auto-updating M3U playlist that checks for new videos every 30 minutes.

## Your Playlist URL

Once set up, your live playlist URL is:

```
https://raw.githubusercontent.com/YOUR_USERNAME/desitales-feed/main/playlist.m3u
```

Replace `YOUR_USERNAME` with your GitHub username.

## Add to VLC (Android)

1. Open VLC → tap **+** → **Stream**
2. Paste your playlist URL above
3. Done — VLC always loads the latest version!

## How it works

- GitHub Actions runs `update_feed.py` every 30 minutes (free)
- Script checks for new video IDs on the CDN
- Updates `playlist.m3u` and `state.json` automatically
- Commits changes back to this repo

## Manual trigger

Go to **Actions tab** → **DesiTales AutoFeed Updater** → **Run workflow**
