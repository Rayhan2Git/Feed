import requests
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ══════════════════════════════════════════════════════
#  SITE CONFIGURATIONS — 4 confirmed working sites
# ══════════════════════════════════════════════════════
SITES = {
    "desitales": {
        "name":        "DesiTales",
        "cdn_base":    "https://cdn.desitales2.com",
        "thumb_base":  "https://www.desitales2.com/videos/contents/videos_screenshots",
        "listing_url": "https://www.desitales2.com/videos/latest-updates/",
        "embed_url":   "https://www.desitales2.com/videos/embed/",
        "referer":     "https://www.desitales2.com/",
        "start_id":    1000,
    },
    "desikahani": {
        "name":        "DesiKahani",
        "cdn_base":    "https://cdn.desikahani2.net",
        "thumb_base":  "https://www.desikahani2.net/videos/contents/videos_screenshots",
        "listing_url": "https://www.desikahani2.net/videos/latest-updates/",
        "embed_url":   "https://www.desikahani2.net/videos/embed/",
        "referer":     "https://www.desikahani2.net/",
        "start_id":    100,
    },
    "xahani": {
        "name":        "Xahani",
        "cdn_base":    "https://cdn.xahani.com",
        "thumb_base":  "https://www.xahani.com/videos/contents/videos_screenshots",
        "listing_url": "https://www.xahani.com/videos/latest-updates/",
        "embed_url":   "https://www.xahani.com/videos/embed/",
        "referer":     "https://www.xahani.com/",
        "start_id":    1,
    },
    "indianbf": {
        "name":        "IndianBF",
        "cdn_base":    "https://cdn.indianbfvideos.com",
        "thumb_base":  "https://www.indianbfvideos.com/contents/videos_screenshots",
        "listing_url": "https://www.indianbfvideos.com/latest-updates/",
        "embed_url":   "https://www.indianbfvideos.com/embed/",
        "referer":     "https://www.indianbfvideos.com/",
        "start_id":    39000,
    },
}

SCAN_AHEAD  = 500      # ← Change to 2200 for first full scan
MAX_WORKERS = 10
STATE_FILE  = "state.json"
M3U_FILE    = "playlist.m3u"

# ══════════════════════════════════════════════════════
#  FOLDER LOGIC — handles all CDN patterns
# ══════════════════════════════════════════════════════
def get_folder(site_key, vid_id):
    if site_key == "indianbf":
        # IndianBF: ID 41844 → folder 41000, ID 40220 → folder 40000
        return (vid_id // 1000) * 1000
    else:
        # All others: 0-999→0, 1000-1999→1000, 2000-2999→2000, 3000+→3000
        if vid_id < 1000: return 0
        if vid_id < 2000: return 1000
        if vid_id < 3000: return 2000
        return 3000

def get_cdn_url(site_key, vid_id):
    folder = get_folder(site_key, vid_id)
    base   = SITES[site_key]["cdn_base"]
    return f"{base}/{folder}/{vid_id}/{vid_id}.mp4"

def get_thumb_url(site_key, vid_id):
    folder = get_folder(site_key, vid_id)
    base   = SITES[site_key]["thumb_base"]
    return f"{base}/{folder}/{vid_id}/320x180/1.jpg"

def get_headers(site_key):
    return {
        "User-Agent": "Mozilla/5.0 (Android 13; Mobile) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer":    SITES[site_key]["referer"]
    }

# ══════════════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════════════
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ══════════════════════════════════════════════════════
#  CDN CHECK
# ══════════════════════════════════════════════════════
def check_cdn(url, headers):
    try:
        r = requests.head(url, timeout=8, headers=headers, allow_redirects=True)
        return r.status_code == 200
    except:
        return False

# ══════════════════════════════════════════════════════
#  TITLE SCRAPER
# ══════════════════════════════════════════════════════
def fetch_titles_from_listing(listing_url, headers, offset=0):
    titles = {}
    try:
        r = requests.get(f"{listing_url}?from={offset}", timeout=10, headers=headers)
        if r.status_code != 200:
            return titles
        html = r.text
        # Pattern 1: fav-video-id + alt text
        for vid_id, title in re.findall(
            r'data-fav-video-id="(\d+)"[^>]*?>.*?alt="([^"]+)"', html, re.DOTALL):
            titles[int(vid_id)] = title.strip()
        # Pattern 2: anchor title + data-rt id
        for title, vid_id in re.findall(
            r'<a[^>]+title="([^"]+)"[^>]*data-rt="[^"]*:(\d+):\d+:"', html):
            if int(vid_id) not in titles:
                titles[int(vid_id)] = title.strip()
        # Pattern 3: indianbfvideos uses different structure
        for vid_id, title in re.findall(
            r'data-id="(\d+)"[^>]*?>.*?<(?:h2|h3|div class="title")[^>]*>([^<]+)<', html, re.DOTALL):
            if int(vid_id) not in titles:
                titles[int(vid_id)] = title.strip()
    except Exception as e:
        print(f"    [WARN] Listing scrape: {e}")
    return titles

def fetch_title_embed(embed_url, vid_id, headers):
    try:
        r = requests.get(f"{embed_url}{vid_id}", timeout=8, headers=headers)
        if r.status_code == 200:
            m = re.search(r"video_title['\"\s:,]+['\"]([^'\"]+)['\"]", r.text)
            if m: return m.group(1).strip()
            m2 = re.search(r"<title>([^<|]+)", r.text)
            if m2: return m2.group(1).strip()
    except:
        pass
    return None

# ══════════════════════════════════════════════════════
#  SCAN ONE SITE
# ══════════════════════════════════════════════════════
def scan_site(site_key, site_state):
    site    = SITES[site_key]
    headers = get_headers(site_key)
    highest = site_state.get("highest_id", site["start_id"] - 1)
    videos  = {int(k): v for k, v in site_state.get("videos", {}).items()}

    scan_start = highest + 1
    scan_end   = highest + SCAN_AHEAD

    print(f"\n{'='*54}")
    print(f"  📡 [{site['name']}] Scanning {scan_start} → {scan_end}")
    print(f"{'='*54}")

    def check(vid_id):
        url = get_cdn_url(site_key, vid_id)
        if check_cdn(url, headers):
            print(f"    [FOUND] {vid_id}")
            return vid_id
        print(f"    [MISS]  {vid_id}")
        return None

    new_found = [r for r in ThreadPoolExecutor(MAX_WORKERS).map(
        check, range(scan_start, scan_end + 1)) if r]

    # Extend if new videos near edge
    if new_found:
        extra_end = max(new_found) + SCAN_AHEAD
        if extra_end > scan_end:
            print(f"    📡 Extending to {extra_end}...")
            new_found += [r for r in ThreadPoolExecutor(MAX_WORKERS).map(
                check, range(scan_end + 1, extra_end + 1)) if r]

    # Fetch titles
    if new_found:
        print(f"\n    🏷️  Getting titles for {len(new_found)} videos...")
        listing_titles = {}
        for offset in [0, 30, 60, 90]:
            listing_titles.update(fetch_titles_from_listing(
                site["listing_url"], headers, offset))

        for vid_id in new_found:
            title = (listing_titles.get(vid_id)
                     or fetch_title_embed(site["embed_url"], vid_id, headers)
                     or f"Video {vid_id}")
            thumb = get_thumb_url(site_key, vid_id)
            videos[vid_id] = {"title": title, "thumb": thumb}
            print(f"    ✓ {vid_id} → {title[:55]}")

        site_state["highest_id"] = max(videos.keys())
        print(f"\n    🆕 {len(new_found)} new videos from {site['name']}!")
    else:
        print(f"    ⏸  No new videos.")

    # Fix missing titles
    missing = [k for k, v in videos.items() if v.get("title", "").startswith("Video ")]
    if missing:
        print(f"    🔁 Fixing {len(missing)} missing titles...")
        listing_titles = {}
        for offset in range(0, 300, 30):
            listing_titles.update(fetch_titles_from_listing(
                site["listing_url"], headers, offset))
        for vid_id in missing:
            if vid_id in listing_titles:
                videos[vid_id]["title"] = listing_titles[vid_id]

    site_state["videos"] = {str(k): v for k, v in videos.items()}
    return site_state, videos

# ══════════════════════════════════════════════════════
#  WRITE COMBINED M3U
# ══════════════════════════════════════════════════════
def write_m3u(all_videos_by_site):
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = sum(len(v) for v in all_videos_by_site.values())

    lines = [
        "#EXTM3U",
        f"# DesiNetwork AutoFeed — Updated: {now}",
        f"# Total: {total} videos | {len(all_videos_by_site)} sites",
        ""
    ]

    for site_key, videos in all_videos_by_site.items():
        site_name = SITES[site_key]["name"]
        for vid_id in sorted(videos.keys(), reverse=True):
            info  = videos[vid_id]
            title = info.get("title", f"Video {vid_id}")
            thumb = info.get("thumb", get_thumb_url(site_key, vid_id))
            url   = get_cdn_url(site_key, vid_id)
            lines.append(
                f'#EXTINF:-1 tvg-id="{site_key}_{vid_id}" '
                f'tvg-logo="{thumb}" '
                f'group-title="{site_name}",{title}'
            )
            lines.append(url)
            lines.append("")

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ playlist.m3u — {total} total videos")
    for site_key, videos in all_videos_by_site.items():
        print(f"   {SITES[site_key]['name']:15} {len(videos):5} videos")

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    print("🔄 DesiNetwork Multi-Site AutoFeed")
    print(f"   {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Sites: {' + '.join(s['name'] for s in SITES.values())}\n")

    state      = load_state()
    all_videos = {}

    for site_key in SITES:
        site_state           = state.get(site_key, {})
        updated, videos      = scan_site(site_key, site_state)
        state[site_key]      = updated
        all_videos[site_key] = videos

    save_state(state)
    write_m3u(all_videos)

if __name__ == "__main__":
    main()
    
