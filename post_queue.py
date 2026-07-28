#!/usr/bin/env python3
"""
Approve-then-publish handoff
============================

Reads a queue file written by content_engine.py, lets you approve items,
and turns each approved draft into the exact payload Robin Reach's create_post
expects — the same shape used to schedule the cold-outreach post.

Two ways to actually publish, depending on how you deploy:

  A) VIA THIS ASSISTANT (simplest, human-in-loop):
     Run `python post_queue.py queue/2026-07-28.json --print`, paste the
     approved payload(s) into a Claude chat with the Robin Reach connector,
     and say "schedule these." Zero extra infrastructure.

  B) VIA ROBIN REACH'S OWN API (fully unattended):
     If your Robin Reach plan exposes a REST API + key, fill in
     ROBINREACH_API_URL / key below and use --publish. Confirm the endpoint
     shape with Robin Reach first — this is a template, not a guaranteed route.

Usage:
    python post_queue.py queue/2026-07-28.json              # interactive approve
    python post_queue.py queue/2026-07-28.json --print      # print payloads only
    python post_queue.py queue/2026-07-28.json --publish    # requires API creds
"""

import argparse
import datetime as dt
import json
import os
import sys

from sources import ROBIN_REACH_PROFILES
from content_engine import (
    SCHEDULE_SLOTS, POSTING_DAYS, DEFAULT_MEDIA_URL, POSTING_TZ, local_slot_to_utc,
)

# Fill these only for path (B). Verify the real shape with Robin Reach docs.
ROBINREACH_API_URL = os.environ.get("ROBINREACH_API_URL", "")
ROBINREACH_API_KEY = os.environ.get("ROBINREACH_API_KEY", "")

# When to schedule approved posts. Default: 11:00 local (POSTING_TZ) tomorrow, as UTC.
def default_publish_time():
    tomorrow = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)
    return local_slot_to_utc(tomorrow, "11:00")


def build_payload(draft, publish_time):
    """Map a queued draft onto a Robin Reach create_post payload."""
    v = draft["variants"]
    li = v.get("linkedin", {}).get("content", "")   # LinkedIn body doubles as main
    return {
        "content": li,                              # main = LinkedIn + Facebook
        "platform_options": {
            "twitter":   v.get("twitter", {}),
            "bluesky":   v.get("bluesky", {}),
            "instagram": v.get("instagram", {}),
            "pinterest": v.get("pinterest", {}),
        },
        "social_profile_ids": list(ROBIN_REACH_PROFILES.values()),
        "post_status": "scheduled",
        "publish_time": publish_time.strftime("%Y-%m-%dT%H:%M:%S"),
        # NOTE: attach media_urls before posting — Instagram & Pinterest
        # require an image or the Robin Reach validator rejects the post.
        "media_urls": [],
    }


def approve_interactive(drafts):
    approved = []
    for i, d in enumerate(drafts, 1):
        src = d["_source_item"]
        print(f"\n[{i}/{len(drafts)}] {src['title']}")
        print(f"    source: {src['source']}  ({src['url']})")
        print(f"    angle : {d.get('angle','')}")
        print(f"    LI    : {d['variants'].get('linkedin',{}).get('content','')[:200]}...")
        ans = input("    approve? [y/N/q] ").strip().lower()
        if ans == "q":
            break
        if ans == "y":
            approved.append(d)
    return approved


def publish_via_api(payload):
    import urllib.request
    if not (ROBINREACH_API_URL and ROBINREACH_API_KEY):
        sys.exit("Set ROBINREACH_API_URL and ROBINREACH_API_KEY to use --publish.")
    req = urllib.request.Request(
        ROBINREACH_API_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {ROBINREACH_API_KEY}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queue_file")
    ap.add_argument("--print", dest="print_only", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--publish-all", action="store_true",
                    help="CI mode: schedule every draft in the queue. Only run this "
                         "behind a human approval gate (see .github/workflows/publish.yml).")
    args = ap.parse_args()

    data = json.load(open(args.queue_file))
    drafts = data["drafts"]
    publish_time = default_publish_time()

    if args.publish_all:
        # Human approval already happened at the GitHub environment gate.
        import robinreach_client as rr
        target = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)
        if POSTING_DAYS:
            while target.strftime("%A").lower() not in POSTING_DAYS:
                target += dt.timedelta(days=1)
        media = [DEFAULT_MEDIA_URL] if DEFAULT_MEDIA_URL else []
        n = 0
        for d, hhmm in zip(drafts, SCHEDULE_SLOTS):
            when = local_slot_to_utc(target, hhmm)   # local slot -> UTC (DST-aware)
            if rr.schedule_draft(d, when, media_urls=media, status="scheduled"):
                n += 1
                print(f"  {hhmm} {POSTING_TZ} — {d['_source_item']['title'][:55]}")
        print(f"\n{n}/{len(drafts)} scheduled for {target}")
        return

    approved = drafts if args.print_only else approve_interactive(drafts)
    if not approved:
        print("nothing approved.")
        return

    payloads = [build_payload(d, publish_time) for d in approved]

    if args.publish:
        for p in payloads:
            if not p["media_urls"]:
                print("  ! skipping a post with no media (IG/Pinterest need an image)")
                continue
            print(publish_via_api(p))
    else:
        print("\n=== Robin Reach payload(s) — attach media_urls, then schedule ===\n")
        print(json.dumps(payloads, indent=2))
        print(f"\n{len(payloads)} payload(s) ready. Add an image URL to each "
              "media_urls before scheduling (IG + Pinterest require it).")


if __name__ == "__main__":
    main()
