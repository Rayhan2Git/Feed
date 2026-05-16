#!/usr/bin/env python3
"""
DesiNetwork Multi-Site AutoFeed v2.0
====================================
Fixed version with correct thumbnail paths and proxy support.
- DesiTales: Works as-is
- DesiKahani: Fixed thumbnail path
- Xahani: Added proxy support (403 fix)
- IndianBF: Fixed thumbnail path (/videos_sources/screenshots/)
"""

import requests
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ══════════════════════════════════════════════════════
# SITE CONFIGURATIONS — Fixed v2.0
# ══════════════════════════════════════════════════════

SITES = {
    "desitales": {
        "name": "DesiTales",
        "cdn_base": "https://cdn.desitales2.com",
        "thumb_base": "https://www.desitales2.com/videos/contents/videos_screenshots",
        "listing_url": "https://www.desitales2.com/videos/latest-updates/",
        "embed_url": "https://www.desitales2.com/videos/embed/",
        "referer": "https://www.desitales2.com/",
        "start_id": 1000,
        "needs_proxy": False,
        # Thumbnail: /videos/contents/videos_screenshots/{folder}/{id}/320x180/1.jpg ✅ WORKS
    },
    "desikahani": {
        "name": "DesiKahani",
        "cdn_base": "https://cdn.desikahani2.net",
        "thumb_base": "https://www.desikahani2.net/videos/contents/videos_screenshots",
        "listing_url": "https://www.desikahani2.net/videos/latest-updates/",
        "embed_url": "https://www.desikahani2.net/videos/embed/",
        "referer": "https://www.desikahani2.net/",
        "start_id": 100,
        "needs_proxy": False,
        # FIXED: Uses 390x218 dimensions (not 320x180!)
        # Pattern: /videos/contents/videos_screenshots/{folder}/{id}/390x218/1.jpg
    },
    "xahani": {
        "name": "Xahani",
        "cdn_base": "https://cdn.xahani.com",
        "thumb_base": "https://www.xahani.com/videos/contents/videos_screenshots",
        "listing_url": "https://www.xahani.com/videos/latest-updates/",
        "embed_url": "https://www.xahani.com/videos/embed/",
        "referer": "https://www.xahani.com/",
        "start_id": 1,
        "needs_proxy": True,  # FIXED: CDN returns 403, needs Cloudflare Worker proxy
        # Video: Use proxy: https://feedscroll.rayhandox.workers.dev?url={cdn_url}
        # Thumbnail: /videos/contents/videos_screenshots/{folder}/{id}/320x180/1.jpg ✅ WORKS
    },
    "indianbf": {
        "name": "IndianBF",
        "cdn_base": "https://cdn.indianbfvideos.com",
        "thumb_base": "https://www.indianbfvideos.com/contents/videos_sources",  # FIXED: different path
        "listing_url": "https://www.indianbfvideos.com/latest-updates/",
        "embed_url": "https://www.indianbfvideos.com/embed/",
        "referer": "https://www.indianbfvideos.com/",
        "start_id": 39000,
        "needs_proxy": False,
        # Thumbnail: /contents/videos_sources/{folder}/{id}/screenshots/1.jpg ✅ WORKS
    },
}

# Cloudflare Worker Proxy URL for Xahani
PROXY_URL = "https://feedscroll.rayhandox.workers.dev"

# Scan settings
SCAN_AHEAD = 500  # Change to 2200 for first full scan
MAX_WORKERS = 10
STATE_FILE = "state.json"
M3U_FILE = "playlist.m3u"

# ══════════════════════════════════════════════════════
# FOLDER LOGIC — handles all CDN patterns
# ══════════════════════════════════════════════════════

def get_folder(site_key, vid_id):
    """Calculate folder path based on video ID ranges."""
    if site_key == "indianbf":
        # IndianBF: ID 41844 → folder 41000, ID 40220 → folder 40000
        return (vid_id // 1000) * 1000
    else:
        # All others: 0-999→0, 1000-1999→1000, 2000-2999→2000, 3000+→3000
        if vid_id < 1000:
            return 0
        if vid_id < 2000:
            return 1000
        if vid_id < 3000:
            return 2000
        return 3000

def get_cdn_url(site_key, vid_id):
    """Get direct CDN URL for video file."""
    folder = get_folder(site_key, vid_id)
    base = SITES[site_key]["cdn_base"]
    return f"{base}/{folder}/{vid_id}/{vid_id}.mp4"

def get_proxied_url(site_key, vid_id):
    """Get proxied URL for sites that need CORS proxy (Xahani)."""
    direct_url = get_cdn_url(site_key, vid_id)
    return f"{PROXY_URL}?url={requests.utils.quote(direct_url)}"

def get_thumb_url(site_key, vid_id):
    """Get thumbnail URL with source-specific path adjustments."""
    folder = get_folder(site_key, vid_id)
    site = SITES[site_key]

    if site_key == "indianbf":
        # IndianBF uses different path: /contents/videos_sources/{folder}/{id}/screenshots/1.jpg
        return f"{site['thumb_base']}/{folder}/{vid_id}/screenshots/1.jpg"
    elif site_key == "desikahani":
        # FIXED: DesiKahani uses 390x218 dimensions (not 320x180!)
        return f"{site['thumb_base']}/{folder}/{vid_id}/390x218/1.jpg"
    else:
        # Standard path for DesiTales and Xahani: 320x180
        return f"{site['thumb_base']}/{folder}/{vid_id}/320x180/1.jpg"

def get_headers(site_key):
    """Get HTTP headers for requests to specific site."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": SITES[site_key]["referer"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

# ══════════════════════════════════════════════════════
# CDN CHECK FUNCTIONS
# ══════════════════════════════════════════════════════

def check_video_exists(url, headers=None, use_proxy=False):
    """Check if video file exists on CDN."""
    try:
        if use_proxy:
            # Use Cloudflare Worker proxy for Xahani
            check_url = f"{PROXY_URL}?url={requests.utils.quote(url)}"
            r = requests.head(check_url, timeout=15, allow_redirects=True)
        else:
            r = requests.head(url, timeout=10, headers=headers, allow_redirects=True)
        return r.status_code == 200
    except Exception as e:
        print(f"      [ERR] Check failed: {e}")
        return False

def check_thumb_exists(url):
    """Check if thumbnail image exists."""
    try:
        r = requests.head(url, timeout=8, allow_redirects=True)
        return r.status_code == 200
    except:
        return False

# ══════════════════════════════════════════════════════
# STATE MANAGEMENT
# ══════════════════════════════════════════════════════

def load_state():
    """Load existing state from JSON file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    """Save state to JSON file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ══════════════════════════════════════════════════════
# TITLE SCRAPING
# ══════════════════════════════════════════════════════

def fetch_titles_from_listing(listing_url, headers, offset=0):
    """Fetch video titles from listing pages using multiple regex patterns."""
    titles = {}
    try:
        url = f"{listing_url}?from={offset}" if "?" not in listing_url else f"{listing_url}&from={offset}"
        r = requests.get(url, timeout=12, headers=headers)
        if r.status_code != 200:
            return titles
        html = r.text

        # Pattern 1: fav-video-id + alt text (common CMS pattern)
        for vid_id, title in re.findall(
            r'data-fav-video-id="(\d+)"[^>]*?>.*?alt="([^"]+)"',
            html, re.DOTALL
        ):
            titles[int(vid_id)] = title.strip()

        # Pattern 2: data-rt id attribute with anchor title
        for title, vid_id in re.findall(
            r'<a[^>]+title="([^"]+)"[^>]*data-rt="[^"]*:(\d+):\d+:">',
            html
        ):
            if int(vid_id) not in titles:
                titles[int(vid_id)] = title.strip()

        # Pattern 3: IndianBF specific pattern (data-id attribute)
        for vid_id, title in re.findall(
            r'data-id="(\d+)"[^>]*?>.*?<(?:h2|h3|div class="title")[^>]*>([^<]+)<',
            html, re.DOTALL
        ):
            if int(vid_id) not in titles:
                titles[int(vid_id)] = title.strip()

        # Pattern 4: Simple anchor with href containing video ID
        for vid_id, title in re.findall(
            r'/videos/\d+-.*?/"[^>]*>\s*([^<]+)\s*</a>|/videos/(\d+)/"[^>]*>\s*([^<]+)\s*</a>',
            html
        ):
            if title and vid_id:
                titles[int(vid_id)] = title.strip()

    except Exception as e:
        print(f"      [WARN] Listing scrape failed: {e}")
    return titles

def fetch_title_embed(embed_url, vid_id, headers):
    """Fallback: Get title from embed page."""
    try:
        r = requests.get(f"{embed_url}{vid_id}", timeout=8, headers=headers)
        if r.status_code == 200:
            # Try video_title pattern
            m = re.search(r'video_title["\'\s:,]+["\']([^"\']+)["\']', r.text)
            if m:
                return m.group(1).strip()
            # Try <title> tag
            m2 = re.search(r'<title>([^<|]+)', r.text)
            if m2:
                return m2.group(1).strip()
    except:
        pass
    return None

# ══════════════════════════════════════════════════════
# THUMBNAIL FALLBACK LOGIC
# ══════════════════════════════════════════════════════

def get_thumb_url_with_fallback(site_key, vid_id):
    """Get thumbnail URL with fallback patterns if primary fails."""
    folder = get_folder(site_key, vid_id)
    site = SITES[site_key]

    # Generate potential URL patterns
    patterns = []

    if site_key == "indianbf":
        # IndianBF primary and fallback patterns
        patterns.append(f"https://www.indianbfvideos.com/contents/videos_sources/{folder}/{vid_id}/screenshots/1.jpg")
        patterns.append(f"https://www.indianbfvideos.com/contents/videos_sources/{folder}/{vid_id}/screenshots/0.jpg")
        patterns.append(f"https://www.indianbfvideos.com/contents/videos_sources/{folder}/{vid_id}/thumbs/0.jpg")
        patterns.append(f"https://indianbfvideos.com/contents/videos_sources/{folder}/{vid_id}/screenshots/1.jpg")
    elif site_key == "desikahani":
        # FIXED: DesiKahani uses 390x218 dimensions (not 320x180!)
        patterns.append(f"https://www.desikahani2.net/videos/contents/videos_screenshots/{folder}/{vid_id}/390x218/1.jpg")
        patterns.append(f"https://www.desikahani2.net/videos/contents/videos_screenshots/{folder}/{vid_id}/390x218/0.jpg")
        patterns.append(f"https://www.desikahani2.net/videos/contents/videos_screenshots/{folder}/{vid_id}/320x180/1.jpg")
        patterns.append(f"https://desikahani2.net/videos/contents/videos_screenshots/{folder}/{vid_id}/390x218/1.jpg")
    elif site_key == "xahani":
        # Xahani uses 320x180 but video needs proxy
        patterns.append(f"https://www.xahani.com/videos/contents/videos_screenshots/{folder}/{vid_id}/320x180/1.jpg")
        patterns.append(f"https://www.xahani.com/videos/contents/videos_screenshots/{folder}/{vid_id}/390x218/1.jpg")
    else:
        # DesiTales - standard pattern
        patterns.append(f"https://www.desitales2.com/videos/contents/videos_screenshots/{folder}/{vid_id}/320x180/1.jpg")
        patterns.append(f"https://www.desitales2.com/videos/contents/videos_screenshots/{folder}/{vid_id}/390x218/1.jpg")

    # Return primary URL (will be checked at runtime for fallback)
    return patterns[0]

# ══════════════════════════════════════════════════════
# SCAN ONE SITE
# ══════════════════════════════════════════════════════

def scan_site(site_key, site_state):
    """Scan a single site for new videos."""
    site = SITES[site_key]
    headers = get_headers(site_key)
    needs_proxy = site.get("needs_proxy", False)

    # Get or initialize state
    highest = site_state.get("highest_id", site["start_id"] - 1)
    videos = {int(k): v for k, v in site_state.get("videos", {}).items()}

    scan_start = highest + 1
    scan_end = highest + SCAN_AHEAD

    print(f"\n{'='*60}")
    print(f" 📡 [{site['name']}] Scanning IDs {scan_start} → {scan_end}")
    print(f"    Proxy: {'YES (Xahani)' if needs_proxy else 'NO'}")
    print(f"{'='*60}")

    def check_video(vid_id):
        """Check if a single video ID exists."""
        url = get_cdn_url(site_key, vid_id)
        exists = check_video_exists(url, headers, use_proxy=needs_proxy)
        status = "✅ FOUND" if exists else "❌ MISS"
        print(f"      [ID {vid_id}] {status}")
        return vid_id if exists else None

    # Parallel scan for videos
    new_found = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_video, vid): vid for vid in range(scan_start, scan_end + 1)}
        for future in as_completed(futures):
            result = future.result()
            if result:
                new_found.append(result)

    # Extend scan if videos found near edge
    if new_found:
        extra_end = max(new_found) + SCAN_AHEAD
        if extra_end > scan_end:
            print(f"    📡 Extending scan to {extra_end}...")
            new_found += [r for r in ThreadPoolExecutor(MAX_WORKERS).map(
                check_video, range(scan_end + 1, extra_end + 1)
            ) if r]

    # Fetch titles for new videos
    if new_found:
        print(f"\n    🏷️ Fetching titles for {len(new_found)} videos...")

        # Get titles from listing pages
        listing_titles = {}
        for offset in [0, 30, 60, 90, 120]:
            listing_titles.update(fetch_titles_from_listing(
                site["listing_url"], headers, offset
            ))
            time.sleep(0.2)  # Rate limiting

        # Process each found video
        for vid_id in new_found:
            # Get title from listings or embed fallback
            title = (
                listing_titles.get(vid_id) or
                fetch_title_embed(site["embed_url"], vid_id, headers) or
                f"Video {vid_id}"
            )

            # Get thumbnail URL with fallback logic
            thumb = get_thumb_url_with_fallback(site_key, vid_id)

            videos[vid_id] = {
                "title": title,
                "thumb": thumb,
                "cdn_url": get_cdn_url(site_key, vid_id),
                "needs_proxy": needs_proxy
            }
            print(f"    ✅ {vid_id} → {title[:50]}")

        site_state["highest_id"] = max(videos.keys())
        print(f"\n    🆕 {len(new_found)} new videos from {site['name']}!")
    else:
        print(f"    ⏸️ No new videos found.")

    # Fix missing titles for existing videos
    missing = [k for k, v in videos.items() if v.get("title", "").startswith("Video ")]
    if missing:
        print(f"    🔁 Fixing {len(missing)} missing titles...")
        listing_titles = {}
        for offset in range(0, 300, 30):
            listing_titles.update(fetch_titles_from_listing(
                site["listing_url"], headers, offset
            ))
            time.sleep(0.2)
        for vid_id in missing:
            if vid_id in listing_titles:
                videos[vid_id]["title"] = listing_titles[vid_id]
                print(f"    🔧 Fixed title for {vid_id}")

    site_state["videos"] = {str(k): v for k, v in videos.items()}
    return site_state, videos

# ══════════════════════════════════════════════════════
# GENERATE M3U PLAYLIST
# ══════════════════════════════════════════════════════

def write_m3u(all_videos_by_site):
    """Generate M3U playlist file with all videos."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = sum(len(v) for v in all_videos_by_site.values())

    lines = [
        "#EXTM3U",
        f"# DesiNetwork AutoFeed v2.0 — Updated: {now}",
        f"# Total: {total} videos | {len(all_videos_by_site)} sites",
        f"# Proxy: https://feedscroll.rayhandox.workers.dev (for Xahani)",
        ""
    ]

    for site_key, videos in all_videos_by_site.items():
        site_name = SITES[site_key]["name"]
        site = SITES[site_key]

        for vid_id in sorted(videos.keys(), reverse=True):
            info = videos[vid_id]
            title = info.get("title", f"Video {vid_id}")
            thumb = info.get("thumb", get_thumb_url(site_key, vid_id))

            # For Xahani, we'll note it needs proxy but include direct URL
            # The app should handle proxying
            needs_proxy = info.get("needs_proxy", site.get("needs_proxy", False))

            lines.append(
                f'#EXTINF:-1 tvg-id="{site_key}_{vid_id}" '
                f'tvg-logo="{thumb}" '
                f'group-title="{site_name}",{title}'
            )

            # Include video URL (app should proxy if needed)
            url = info.get("cdn_url", get_cdn_url(site_key, vid_id))
            lines.append(url)
            lines.append("")

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n{'='*60}")
    print(f" ✅ playlist.m3u generated successfully!")
    print(f"    Total videos: {total}")
    print(f"{'='*60}")
    for site_key, videos in all_videos_by_site.items():
        name = SITES[site_key]["name"]
        count = len(videos)
        proxy = " [PROXY]" if SITES[site_key].get("needs_proxy") else ""
        print(f"    {name:15} {count:5} videos{proxy}")

# ══════════════════════════════════════════════════════
# VALIDATION & REPORTING
# ══════════════════════════════════════════════════════

def validate_sample_videos(all_videos_by_site, sample_count=3):
    """Validate a sample of videos from each site."""
    print(f"\n{'='*60}")
    print(f" 🔍 Validating sample videos...")
    print(f"{'='*60}")

    for site_key, videos in all_videos_by_site.items():
        if not videos:
            continue

        site = SITES[site_key]
        needs_proxy = site.get("needs_proxy", False)
        sample_ids = list(videos.keys())[:sample_count]

        print(f"\n [{site['name']}] Testing {len(sample_ids)} samples:")

        for vid_id in sample_ids:
            info = videos[vid_id]
            title = info.get("title", f"Video {vid_id}")[:40]

            # Check video
            video_url = info.get("cdn_url", get_cdn_url(site_key, vid_id))
            video_ok = check_video_exists(video_url, get_headers(site_key), needs_proxy)

            # Check thumbnail
            thumb_url = info.get("thumb", "")
            thumb_ok = check_thumb_exists(thumb_url) if thumb_url else False

            status = "✅" if video_ok else "❌"
            thumb_status = "✅" if thumb_ok else "❌"

            print(f"    ID {vid_id}: Video {status}, Thumb {thumb_status} - {title}")

# ══════════════════════════════════════════════════════
# MAIN EXECUTION
# ══════════════════════════════════════════════════════

def main():
    """Main entry point."""
    print("\n" + "="*60)
    print(" 🔄 DesiNetwork Multi-Site AutoFeed v2.0")
    print("    Fixed: IndianBF thumbnails, Xahani proxy support")
    print("="*60)
    print(f"    Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"    Sites: {' + '.join(s['name'] for s in SITES.values())}")
    print(f"    Proxy: {PROXY_URL}")
    print("="*60)

    # Load existing state
    state = load_state()
    all_videos = {}

    # Scan each site
    for site_key in SITES:
        print(f"\n\nProcessing: {site_key.upper()}")
        site_state = state.get(site_key, {})
        updated, videos = scan_site(site_key, site_state)
        state[site_key] = updated
        all_videos[site_key] = videos
        time.sleep(1)  # Pause between sites

    # Save state
    save_state(state)

    # Generate M3U playlist
    write_m3u(all_videos)

    # Validate sample videos
    validate_sample_videos(all_videos)

    print(f"\n{'='*60}")
    print(" 🎉 AutoFeed completed successfully!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()