import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── CONFIG ──
START_ID   = 3100        # First ID to ever check (change to your preferred start)
SCAN_AHEAD = 2200          # How many IDs ahead of last known to check each run
MAX_WORKERS = 10         # Parallel checks (speed)
STATE_FILE  = "state.json"
M3U_FILE    = "playlist.m3u"

CDN_BASE = "https://cdn.desitales2.com/{folder}/{id}/{id}.mp4"

def get_url(vid_id):
    if vid_id < 2000:
        folder = 1000
    elif vid_id < 3000:
        folder = 2000
    else:
        folder = 3000
    return CDN_BASE.format(folder=folder, id=vid_id)

# ── LOAD STATE ──
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"highest_id": START_ID - 1, "found_ids": []}

# ── SAVE STATE ──
def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ── CHECK ONE VIDEO ──
def check_video(vid_id):
    url = get_url(vid_id)
    try:
        r = requests.head(url, timeout=8, allow_redirects=True)
        if r.status_code == 200:
            print(f"  [FOUND] {vid_id}")
            return vid_id
        else:
            print(f"  [MISS]  {vid_id} → {r.status_code}")
            return None
    except Exception as e:
        print(f"  [ERR]   {vid_id} → {e}")
        return None

# ── WRITE M3U ──
def write_m3u(found_ids):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "#EXTM3U",
        f"# DesiTales AutoFeed — Updated: {now}",
        f"# Total videos: {len(found_ids)}",
        ""
    ]
    for vid_id in sorted(found_ids, reverse=True):  # newest first
        url = get_url(vid_id)
        lines.append(f"#EXTINF:-1,Video {vid_id}")
        lines.append(url)
        lines.append("")

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ playlist.m3u updated — {len(found_ids)} videos")

# ── MAIN ──
def main():
    print("🔄 DesiTales AutoFeed Updater")
    print(f"   {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")

    state = load_state()
    highest = state["highest_id"]
    found_ids = set(state["found_ids"])

    scan_start = highest + 1
    scan_end   = highest + SCAN_AHEAD

    print(f"📡 Scanning IDs {scan_start} → {scan_end}...")

    new_found = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(check_video, range(scan_start, scan_end + 1)))

    for vid_id in results:
        if vid_id is not None:
            found_ids.add(vid_id)
            new_found.append(vid_id)

    if new_found:
        new_highest = max(new_found)
        # If we found some, keep scanning a bit further to not miss any
        extra_start = scan_end + 1
        extra_end   = new_highest + SCAN_AHEAD
        if extra_end > scan_end:
            print(f"\n📡 Found new videos, extending scan to {extra_end}...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                extra = list(ex.map(check_video, range(extra_start, extra_end + 1)))
            for vid_id in extra:
                if vid_id is not None:
                    found_ids.add(vid_id)
                    new_found.append(vid_id)

        state["highest_id"] = max(found_ids)
        print(f"\n🆕 {len(new_found)} new videos found!")
    else:
        print(f"\n⏸ No new videos found this run.")

    state["found_ids"] = sorted(found_ids)
    save_state(state)
    write_m3u(found_ids)

if __name__ == "__main__":
    main()
