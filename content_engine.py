#!/usr/bin/env python3
"""
SalesMake daily content engine
==============================

Pipeline, once per day:

  1. FETCH   – pull the last 24h of items from every source in sources.py
  2. FILTER  – keep only items relevant to SalesMake's niche, rank by fit
  3. REWORK  – turn each kept item into ORIGINAL SalesMake commentary:
               a genuine take, never a spin of the original. Always
               attributes the source by name and links to it.
  4. TAILOR  – generate a per-platform variant for each connected account
  5. QUEUE   – write everything to a dated review queue (JSON + Markdown)

Posting is deliberately a SEPARATE, approve-then-publish step (post_queue.py)
so nothing goes live unread. Flip REVIEW_MODE = False only once you trust it.

Deploy: drop this folder on anything that can run a daily cron —
GitHub Actions, a cloud function, a small VPS. Set ANTHROPIC_API_KEY.

    export ANTHROPIC_API_KEY=sk-ant-...
    python content_engine.py                 # normal daily run
    python content_engine.py --check-feeds   # validate feed URLs (run once)
    python content_engine.py --dry-run        # fetch+filter only, no API calls
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser

from sources import (
    SOURCES,
    RELEVANCE_KEYWORDS,
    ROBIN_REACH_PROFILES,
    PLATFORM_STYLE,
)

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
REVIEW_MODE = True                      # True = queue for review, never auto-post
LOOKBACK_HOURS = 26                     # 26 not 24 to absorb cron drift
MAX_ITEMS_PER_RUN = 3                   # posts per day (2-3 target)
MIN_ITEMS_PER_RUN = 2                   # if the feed is thin, top up from BACKLOG
# Posting timezone. SCHEDULE_SLOTS below are LOCAL wall-clock times in this zone
# and are converted to UTC at schedule time, so they track DST automatically.
# "CET" = Central European Time (CET in winter / CEST in summer). Change to your
# IANA zone if you relocate, e.g. "Europe/Madrid" or "America/New_York".
POSTING_TZ = "CET"
LOCAL_TZ = ZoneInfo(POSTING_TZ)
# Preferred posting times, LOCAL to POSTING_TZ (11am, 3pm, 9pm).
SCHEDULE_SLOTS = ["11:00", "15:00", "21:00"]
# Your configured preferred days. Set to None to post every day.
POSTING_DAYS = {"tuesday", "wednesday", "thursday", "friday"}
BACKLOG_FILE = Path("queue/_backlog.json")   # surplus drafts carry to lean days
MIN_RELEVANCE_SCORE = 2                 # keyword hits required to keep an item
WEBSITE = "https://salesmake.agency/"
CONTACT_URL = "https://salesmake.agency/contact"   # every CTA points here
BARE_DOMAIN = "salesmake.agency"                  # X profile rejects URLs — bare domain only
# Fallback image so Instagram/Pinterest posts validate (they reject imageless
# posts). Point this at a hosted SalesMake brand image, or leave blank to have
# imageless posts skipped instead of failing.
DEFAULT_MEDIA_URL = os.environ.get("SALESMAKE_DEFAULT_IMAGE", "")
MODEL = "claude-sonnet-4-6"             # rework model
OUT_DIR = Path("queue")
FEED_SUFFIX_PROBES = ["", "/feed", "/rss", "/rss.xml", "/feed/", "/atom.xml"]


# ----------------------------------------------------------------------------
# 1. FETCH
# ----------------------------------------------------------------------------
def parse_entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return dt.datetime(*t[:6], tzinfo=dt.timezone.utc)
    return None


def fetch_recent(source, cutoff):
    """Return list of recent entries for one source."""
    parsed = feedparser.parse(source["feed"])
    if parsed.bozo and not parsed.entries:
        return {"source": source, "error": str(parsed.bozo_exception), "items": []}

    items = []
    for e in parsed.entries:
        ts = parse_entry_time(e)
        if ts is None or ts >= cutoff:          # keep undated entries; feeds vary
            summary = re.sub(r"<[^>]+>", " ", e.get("summary", "")).strip()
            items.append({
                "title": e.get("title", "").strip(),
                "url": e.get("link", "").strip(),
                "published": ts.isoformat() if ts else None,
                "summary": summary[:1500],
            })
    return {"source": source, "error": None, "items": items}


# ----------------------------------------------------------------------------
# 2. FILTER / RANK
# ----------------------------------------------------------------------------
def relevance_score(item, weight):
    text = (item["title"] + " " + item["summary"]).lower()
    hits = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)
    return round(hits * weight, 2)


def collect_and_rank(cutoff):
    ranked = []
    for src in SOURCES:
        res = fetch_recent(src, cutoff)
        if res["error"]:
            print(f"  ! {src['name']}: {res['error']}", file=sys.stderr)
            continue
        for it in res["items"]:
            score = relevance_score(it, src["weight"])
            if score >= MIN_RELEVANCE_SCORE:
                it.update(source=src["name"], category=src["category"], score=score)
                ranked.append(it)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:MAX_ITEMS_PER_RUN]


# ----------------------------------------------------------------------------
# 3 + 4. REWORK into original commentary + per-platform variants
# ----------------------------------------------------------------------------
REWORK_SYSTEM = f"""You write B2B social content for SalesMake, an outbound/GTM \
consultancy (website {WEBSITE}). You are given ONE industry article. Your job is \
NOT to rewrite or spin it. Your job is to write SalesMake's own short take on the \
idea it raises — the kind of thing a sharp practitioner posts after reading \
something worth reacting to.

Hard rules:
- Lead with SalesMake's own point of view or a practical angle the original didn't spell out.
- ALWAYS name the source publication and include its link. This is curation with credit, not repackaging.
- NEVER reproduce more than a single short phrase (<10 words) from the original. No paragraph mirroring.
- If the article's core claim is a specific statistic you cannot verify, attribute it explicitly to the source ("Per <source>...") rather than stating it as fact.
- No hype, no "game-changer" language. Match the plain, relevance-over-volume voice of the brand.
- If the article is thin, promotional, or off-topic for an outbound audience, respond with exactly: SKIP

CALL TO ACTION — every variant ends with one, and it is always the same offer:
an open, low-pressure invitation to get in touch about cold outreach / outbound
sales help, pointing to {CONTACT_URL}.
- VARY THE WORDING every time. Never reuse a phrasing across posts. Rotate the
  framing: "if you need help with...", "if you're working on...", "happy to
  help if...", "feel free to reach out about...".
- Keep it inviting, not assertive. It is an open door, NOT a pitch, a claim of
  expertise, or a promise of results. Do not write "we fix X", "we audit X",
  "we build X" — write invitations to contact.
- One sentence. It sits after the source link, separated by a blank line.
- Twitter: no URLs allowed on this profile — use the BARE domain "{BARE_DOMAIN}"
  with NO path (a "/contact" path reads as a URL and fails validation). Keep the
  CTA to a short fragment.
- Instagram: captions can't hyperlink — say "link in bio" alongside the domain.
- Pinterest: {CONTACT_URL} goes in the "link" field; mention contact in the description.

Return STRICT JSON only, no markdown fences, shaped as:
{{
  "usable": true,
  "angle": "one sentence describing SalesMake's take",
  "variants": {{
    "linkedin":  {{"content": "..."}},
    "twitter":   {{"content": "..."}},
    "bluesky":   {{"content": "...", "website_url": "{CONTACT_URL}", "website_title": "SalesMake"}},
    "instagram": {{"content": "..."}},
    "pinterest": {{"content": "...", "title": "...", "link": "{CONTACT_URL}"}}
  }}
}}
(LinkedIn and Facebook share the LinkedIn body, so no separate facebook field.)
If you would SKIP, return {{"usable": false}} only."""


def build_user_prompt(item):
    style_block = "\n".join(f"- {p}: {s}" for p, s in PLATFORM_STYLE.items() if p != "facebook")
    return f"""ARTICLE
Source: {item['source']}
Title: {item['title']}
Link: {item['url']}
Summary: {item['summary']}

Per-platform voice:
{style_block}

Every variant must credit "{item['source']}" and link {item['url']} where the
platform allows links (Twitter forbids URLs — use "{BARE_DOMAIN}" and name the
source instead). Close every variant with a soft, varied contact CTA to {CONTACT_URL}."""


def rework(item, client):
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=REWORK_SYSTEM,
        messages=[{"role": "user", "content": build_user_prompt(item)}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    if raw == "SKIP":
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  ! could not parse model output for: {item['title']}", file=sys.stderr)
        return None
    if not data.get("usable"):
        return None
    data["_source_item"] = item
    return data


# ----------------------------------------------------------------------------
# 5. QUEUE
# ----------------------------------------------------------------------------
def write_queue(drafts, run_date):
    OUT_DIR.mkdir(exist_ok=True)
    stem = OUT_DIR / run_date.strftime("%Y-%m-%d")

    with open(f"{stem}.json", "w") as f:
        json.dump({"date": run_date.isoformat(), "drafts": drafts,
                   "profiles": ROBIN_REACH_PROFILES}, f, indent=2)

    # Human-readable review file
    lines = [f"# SalesMake content queue — {run_date:%A %d %b %Y}",
             f"\n{len(drafts)} item(s) for review. Approve in post_queue.py, "
             "then it schedules through Robin Reach.\n"]
    for i, d in enumerate(drafts, 1):
        src = d["_source_item"]
        lines += [f"\n## {i}. {src['title']}",
                  f"**Source:** {src['source']} — {src['url']}  (fit score {src['score']})",
                  f"**Angle:** {d.get('angle','')}\n"]
        for plat, v in d["variants"].items():
            lines += [f"**{plat.capitalize()}**", "```", v.get("content", ""), "```"]
    with open(f"{stem}.md", "w") as f:
        f.write("\n".join(lines))
    return f"{stem}.md", f"{stem}.json"


# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------
def check_feeds():
    print("Checking feeds (needs open-web access — run in your environment):\n")
    for src in SOURCES:
        base = src["feed"].rsplit("/feed", 1)[0].rsplit("/rss", 1)[0]
        ok = None
        for suf in FEED_SUFFIX_PROBES:
            url = src["feed"] if suf == "" else base + suf
            p = feedparser.parse(url)
            if p.entries:
                ok = url
                break
            time.sleep(0.3)
        status = f"OK  -> {ok}" if ok else "NO FEED FOUND — set manually"
        print(f"  {src['name']:<28} {status}")


# ----------------------------------------------------------------------------
# Backlog — evens out lean days
# ----------------------------------------------------------------------------
def load_backlog():
    if BACKLOG_FILE.exists():
        try:
            return json.load(open(BACKLOG_FILE))
        except json.JSONDecodeError:
            return []
    return []


def save_backlog(items):
    BACKLOG_FILE.parent.mkdir(exist_ok=True)
    json.dump(items[-30:], open(BACKLOG_FILE, "w"), indent=2)   # keep last 30


def local_slot_to_utc(base_date, hhmm):
    """Interpret 'HH:MM' as a LOCAL time in POSTING_TZ on base_date; return a UTC datetime.
    Uses base_date so the correct CET/CEST offset is applied for that date (DST-aware)."""
    h, m = (int(x) for x in hhmm.split(":"))
    local = dt.datetime.combine(base_date, dt.time(h, m), tzinfo=LOCAL_TZ)
    return local.astimezone(dt.timezone.utc)


def slot_times(base_date, n):
    """Return n UTC datetimes for the local posting slots on base_date."""
    return [local_slot_to_utc(base_date, hhmm) for hhmm in SCHEDULE_SLOTS[:n]]


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-feeds", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="fetch+filter only")
    args = ap.parse_args()

    if args.check_feeds:
        check_feeds()
        return

    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=LOOKBACK_HOURS)
    print(f"[{now:%Y-%m-%d %H:%M}] collecting items since {cutoff:%Y-%m-%d %H:%M} UTC")

    items = collect_and_rank(cutoff)
    print(f"  {len(items)} relevant item(s) after filtering")
    if not items:
        print("  nothing on-topic today — no queue written.")
        return

    if args.dry_run:
        for it in items:
            print(f"    [{it['score']}] {it['source']}: {it['title']}")
        return

    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    drafts = []
    for it in items:
        print(f"  reworking: {it['title'][:60]}...")
        d = rework(it, client)
        if d:
            drafts.append(d)
        else:
            print("    -> skipped (thin/off-topic or unparseable)")

    # Even out feed volume: surplus goes to the backlog, lean days draw from it.
    backlog = load_backlog()
    if len(drafts) > MAX_ITEMS_PER_RUN:
        backlog.extend(drafts[MAX_ITEMS_PER_RUN:])
        drafts = drafts[:MAX_ITEMS_PER_RUN]
    while len(drafts) < MIN_ITEMS_PER_RUN and backlog:
        drafts.append(backlog.pop(0))
        print("  topped up from backlog (thin feed day)")
    save_backlog(backlog)

    if not drafts:
        print("  every item skipped on quality — nothing queued.")
        return

    md, js = write_queue(drafts, now)
    mode = "REVIEW QUEUE (nothing posted)" if REVIEW_MODE else "AUTO-POST ENABLED"
    print(f"\n  {len(drafts)} draft(s) written [{mode}]\n    {md}\n    {js}")

    if REVIEW_MODE:
        print("  Next: review the .md, then run  python post_queue.py " + os.path.basename(js))
        return

    # Unattended path: schedule each draft for the next posting day at the local slots via REST.
    import robinreach_client as rr
    target = (now + dt.timedelta(days=1)).date()
    if POSTING_DAYS:                       # roll forward to the next preferred day
        while target.strftime("%A").lower() not in POSTING_DAYS:
            target += dt.timedelta(days=1)
    media = [DEFAULT_MEDIA_URL] if DEFAULT_MEDIA_URL else []
    posted = 0
    for d, when in zip(drafts, slot_times(target, len(drafts))):
        res = rr.schedule_draft(d, when, media_urls=media, status="scheduled")
        if res:
            posted += 1
            print(f"    {when:%H:%M} — {d['_source_item']['title'][:50]}")
    print(f"\n  {posted}/{len(drafts)} scheduled on RobinReach for {target} "
          f"at {', '.join(SCHEDULE_SLOTS[:len(drafts)])} {POSTING_TZ}")


if __name__ == "__main__":
    main()
