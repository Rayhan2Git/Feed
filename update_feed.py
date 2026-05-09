import requests
import json
import os
import re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── CONFIG ──
START_ID    = 1000
SCAN_AHEAD  = 60
MAX_WORKERS = 10

STATE_FILE  = "state.json"
M3U_FILE    = "playlist.m3u"

# ── CLOUDFLARE WORKER ──
WORKER_BASE = "https://feedscroll.rayhandox.workers.dev/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Android 13; Mobile) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://www.desitales2.com/"
}


# ─────────────────────────────
# URL HELPERS
# ─────────────────────────────

def get_folder(vid_id):
    if vid_id < 2000:
        return 1000
    elif vid_id < 3000:
        return 2000
    return 3000


def get_original_cdn_url(vid_id):
    folder = get_folder(vid_id)

    return (
        f"https://cdn.desitales2.com/"
        f"{folder}/{vid_id}/{vid_id}.mp4"
    )


def proxify(url):
    encoded = quote(url, safe="")

    return (
        f"{WORKER_BASE}"
        f"?url={encoded}"
    )


def get_cdn_url(vid_id):
    original = get_original_cdn_url(vid_id)
    return proxify(original)


def get_thumb_url(vid_id):
    folder = get_folder(vid_id)

    return (
        "https://www.desitales2.com/"
        f"videos/contents/videos_screenshots/"
        f"{folder}/{vid_id}/320x180/1.jpg"
    )


# ─────────────────────────────
# STATE
# ─────────────────────────────

def load_state():

    if os.path.exists(STATE_FILE):

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    return {
        "highest_id": START_ID - 1,
        "videos": {}
    }


def save_state(state):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False
        )


# ─────────────────────────────
# VIDEO CHECKS
# ─────────────────────────────

def check_cdn(vid_id):

    try:

        original_url = get_original_cdn_url(vid_id)

        r = requests.head(
            original_url,
            timeout=8,
            headers=HEADERS,
            allow_redirects=True
        )

        return r.status_code == 200

    except Exception as e:

        print(f"  [ERROR] {vid_id}: {e}")

        return False


def check_video(vid_id):

    exists = check_cdn(vid_id)

    if exists:

        print(f"  [FOUND] {vid_id}")

        return vid_id

    else:

        print(f"  [MISS]  {vid_id}")

        return None


# ─────────────────────────────
# TITLE FETCHING
# ─────────────────────────────

def fetch_titles_from_listing(offset=0):

    url = (
        "https://www.desitales2.com/"
        f"videos/latest-updates/?from={offset}"
    )

    titles = {}

    try:

        r = requests.get(
            url,
            timeout=10,
            headers=HEADERS
        )

        if r.status_code != 200:
            return titles

        html = r.text

        pattern = (
            r'data-fav-video-id="(\d+)"'
            r'[^>]*?>.*?alt="([^"]+)"'
        )

        matches = re.findall(
            pattern,
            html,
            re.DOTALL
        )

        for vid_id, title in matches:

            titles[int(vid_id)] = title.strip()

    except Exception as e:

        print(
            f"  [WARN] Listing fetch failed: {e}"
        )

    return titles


def fetch_title_embed(vid_id):

    try:

        r = requests.get(
            f"https://www.desitales2.com/videos/embed/{vid_id}",
            timeout=8,
            headers=HEADERS
        )

        if r.status_code == 200:

            m = re.search(
                r'video_title[\'"\s:]+[\'"]([^\'"]+)[\'"]',
                r.text
            )

            if m:
                return m.group(1).strip()

            m2 = re.search(
                r'<title>([^<]+)</title>',
                r.text
            )

            if m2:
                return m2.group(1).strip()

    except Exception:
        pass

    return f"Video {vid_id}"


# ─────────────────────────────
# PLAYLIST GENERATION
# ─────────────────────────────

def write_m3u(videos_dict):

    now = datetime.utcnow().strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    lines = [
        "#EXTM3U",
        f"# DesiTales AutoFeed — Updated: {now}",
        f"# Total: {len(videos_dict)} videos",
        ""
    ]

    for vid_id in sorted(
        videos_dict.keys(),
        reverse=True
    ):

        info = videos_dict[vid_id]

        title = info.get(
            "title",
            f"Video {vid_id}"
        )

        thumb = info.get(
            "thumb",
            get_thumb_url(vid_id)
        )

        url = get_cdn_url(vid_id)

        lines.append(
            f'#EXTINF:-1 '
            f'tvg-id="{vid_id}" '
            f'tvg-logo="{thumb}" '
            f'group-title="DesiTales",'
            f'{title}'
        )

        lines.append(url)

        lines.append("")

    with open(
        M3U_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write("\n".join(lines))

    print(
        f"\n✅ playlist.m3u — "
        f"{len(videos_dict)} videos"
    )


# ─────────────────────────────
# MAIN
# ─────────────────────────────

def main():

    print(
        "🔄 DesiTales AutoFeed "
        "(Cloudflare Edition)"
    )

    print(
        f"   {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    state = load_state()

    highest = state.get(
        "highest_id",
        START_ID - 1
    )

    videos = {
        int(k): v
        for k, v in state.get(
            "videos",
            {}
        ).items()
    }

    scan_start = highest + 1
    scan_end   = highest + SCAN_AHEAD

    print(
        f"📡 Scanning IDs "
        f"{scan_start} → {scan_end}..."
    )

    new_found = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as ex:

        for vid_id in ex.map(
            check_video,
            range(scan_start, scan_end + 1)
        ):

            if vid_id:
                new_found.append(vid_id)

    # Extend scan if new videos found
    if new_found:

        extra_end = (
            max(new_found) + SCAN_AHEAD
        )

        if extra_end > scan_end:

            print(
                f"\n📡 Extending to {extra_end}..."
            )

            with ThreadPoolExecutor(
                max_workers=MAX_WORKERS
            ) as ex:

                for vid_id in ex.map(
                    check_video,
                    range(
                        scan_end + 1,
                        extra_end + 1
                    )
                ):

                    if vid_id:
                        new_found.append(vid_id)

    # Get titles
    if new_found:

        print(
            f"\n🏷️  Getting titles for "
            f"{len(new_found)} new videos..."
        )

        listing_titles = {}

        for offset in [0, 30, 60, 90]:

            listing_titles.update(
                fetch_titles_from_listing(offset)
            )

        for vid_id in new_found:

            title = (
                listing_titles.get(vid_id)
                or fetch_title_embed(vid_id)
            )

            thumb = get_thumb_url(vid_id)

            videos[vid_id] = {
                "title": title,
                "thumb": thumb
            }

            print(
                f"  ✓ {vid_id} → "
                f"{title[:55]}"
            )

        state["highest_id"] = max(
            videos.keys()
        )

        print(
            f"\n🆕 {len(new_found)} "
            f"new videos added!"
        )

    else:

        print(
            f"\n⏸  No new videos this run."
        )

    # Fix missing titles
    missing = [

        k for k, v in videos.items()

        if v.get(
            "title",
            ""
        ).startswith("Video ")
    ]

    if missing:

        print(
            f"\n🔁 Fixing "
            f"{len(missing)} missing titles..."
        )

        listing_titles = {}

        for offset in range(0, 300, 30):

            listing_titles.update(
                fetch_titles_from_listing(offset)
            )

            if not any(
                k in missing
                for k in listing_titles
            ):
                break

        for vid_id in missing:

            if vid_id in listing_titles:

                videos[vid_id]["title"] = (
                    listing_titles[vid_id]
                )

                print(
                    f"  ✓ Fixed {vid_id} → "
                    f"{listing_titles[vid_id][:50]}"
                )

    # Save state
    state["videos"] = {
        str(k): v
        for k, v in videos.items()
    }

    save_state(state)

    # Generate playlist
    write_m3u(videos)


if __name__ == "__main__":
    main()
