# SCRAPING.md — Data acquisition reference

Locked 2026-04-26. Phase 1 deliverable. Smoke-tested against r/antiwork.

## Primary source — Arctic Shift HTTP API

**Base URL:** `https://arctic-shift.photon-reddit.com`

**Posts search endpoint:** `GET /api/posts/search`

### Verified working call (smoke test, 2026-04-26)

```
GET https://arctic-shift.photon-reddit.com/api/posts/search
    ?subreddit=antiwork
    &after=2021-03-01
    &before=2021-03-08
    &limit=100
    &sort=asc
```

Returned: 100-post array (the maximum per call) for the first week of March 2021. Each post is a complete Reddit submission object including `title`, `selftext` (body), `id`, `created_utc`, `author`, `score`, `num_comments`, plus deletion markers (`removed_by_category`, `edited`).

### Parameter reference

| Parameter | Type | Notes |
|---|---|---|
| `subreddit` | string | Use bare name: `antiwork` (no `r/` prefix) |
| `after` | date | ISO 8601 partial (`2021-03-01`), epoch seconds, or relative like `1year` |
| `before` | date | Same format options |
| `limit` | int 1–100 \| "auto" | Hard cap is 100 per call. Use 100 for bulk pulls. |
| `sort` | `asc` \| `desc` | **Use `asc` for paginated bulk pulls** so cursor advances forward |
| `author` | string | Optional |
| `title` | string | Optional substring filter (case-insensitive) |
| `selftext` | string | Optional substring filter |

### Pagination strategy

Limit is capped at 100, so a 4-year r/antiwork pull needs cursor pagination:

```python
# Pseudocode for src/scrape.py
def fetch_window(after_iso, before_iso):
    cursor = after_iso
    while True:
        resp = requests.get(BASE + "/api/posts/search", params={
            "subreddit": "antiwork",
            "after": cursor,
            "before": before_iso,
            "limit": 100,
            "sort": "asc",
        }).json()
        posts = resp["data"]
        if not posts:
            break
        yield from posts
        # Advance cursor to the timestamp just past the last post
        last_ts = max(p["created_utc"] for p in posts)
        cursor = last_ts + 1   # epoch seconds; +1 avoids re-fetching the last post
```

**De-dup on `id`** after collection — boundary posts can occasionally appear in two windows due to integer-second resolution.

### Rate limiting

Arctic Shift is a single-maintainer hobby project. Be polite:

- Cap requests at ~1 per second (`time.sleep(1)` between calls)
- Cache raw JSON to `data/raw/` per call so partial pulls are resumable
- Volume estimate: r/antiwork at ~100+ posts/week (March 2021) → ~5,000–20,000 posts/month at peak (no filter applied yet) → roughly 200k–500k posts total for 4 years before the boss/manager/supervisor/team-lead filter

## Fields we care about (subset of the full response)

The API returns ~85 fields per post. Phase 2 keeps only:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Reddit base36 (e.g. `luuhm1`) — primary key |
| `created_utc` | int | Unix seconds, UTC |
| `subreddit` | string | Verify == `antiwork` |
| `title` | string | Used in primary analysis |
| `selftext` | string | Post body — used in modernized pipeline (was unused in original) |
| `author` | string | `[deleted]` if removed |
| `score` | int | Final score at archive time |
| `num_comments` | int | Final comment count at archive time |
| `removed_by_category` | string \| null | If non-null, post was removed (mod / spam / author) |
| `edited` | bool \| int | If int, the post was edited at that timestamp |

All other fields (flair metadata, awards, media URLs, etc.) are dropped.

## Backup source — Academic Torrents

If Arctic Shift goes offline mid-Phase, the deterministic offline fallback is:

**Torrent:** `Subreddit comments/submissions 2005-06 to 2025-12`
**Magnet/Hash:** `3e3f64dee22dc304cdd2546254ca1f8e8ae542b4`
**URL:** https://academictorrents.com/details/3e3f64dee22dc304cdd2546254ca1f8e8ae542b4

This is the per-subreddit-split version (40,000 subreddits in separate files), so we only need to download the r/antiwork file — likely <5 GB compressed instead of the full 3.4 TB dump. Format: zstandard-compressed NDJSON, one post per line, same Reddit submission schema as Arctic Shift.

**When to switch:** only if Arctic Shift becomes unavailable. The torrent is slower (BitTorrent peer pool, hours to days for first download) and harder to filter per-window than the API.

## Verification — PRAW

PRAW (Reddit's official API wrapper) is **not** used for bulk collection — Reddit's API can't return pre-2023 history reliably. PRAW is reserved for one job:

**Spot-check verification.** After Phase 2 builds the corpus, randomly sample 50–100 post IDs and call `reddit.submission(id=...)` via PRAW to confirm:

- Title matches Arctic Shift's archived `title`
- Body matches Arctic Shift's archived `selftext`
- Author matches (or is `[deleted]` in both)
- Post still exists (not removed since archive)

This catches one specific failure mode: Arctic Shift serving stale or pre-deletion content that no longer reflects what readers see today. Disagreements should be logged but don't necessarily invalidate the corpus — Reddit content changes after archiving is the norm, not the exception.

PRAW credentials needed: a Reddit account + a registered "script" application at https://www.reddit.com/prefs/apps. ~5-minute setup, free.
