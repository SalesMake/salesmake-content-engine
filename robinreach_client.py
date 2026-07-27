#!/usr/bin/env python3
"""
RobinReach REST API client
==========================

Turns approved drafts into live scheduled posts via RobinReach's REST API,
so the whole pipeline can run unattended on a cron.

Field shapes below are taken from RobinReach's own open-source n8n node
(github.com/RobinReach/RobinReach-N8N) plus the documented curl example.
Two official sources disagree on a couple of field names (the marketing
curl says `media_urls`; the n8n node maps media to `attachments`; the curl
implies `post_status` while the node uses `status`). I can't hit the live
API from where this was built, so the client sends the most-documented name
and you confirm with ONE safe call:

    export ROBINREACH_API_KEY=...          # from RobinReach dashboard
    python robinreach_client.py --list-brands           # get your brand_id
    export ROBINREACH_BRAND_ID=...
    python robinreach_client.py --list-profiles         # confirm profile IDs
    python robinreach_client.py --self-test             # posts ONE draft (not live)

--self-test creates a DRAFT in RobinReach (status=draft, nothing publishes).
Open it in the dashboard: if each platform shows its own tailored text, the
API honors per-platform overrides and you're done. If they all show the same
body, per-platform text isn't supported over REST — see the note --self-test
prints. Either way nothing went public.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

from sources import ROBIN_REACH_PROFILES

BASE = "https://robinreach.com/api/v1"

# If the live API rejects a field name, flip these to the alternates noted above.
MEDIA_FIELD = "media_urls"      # alt: "attachments"
STATUS_FIELD = "status"         # alt: "post_status"


def _creds():
    key = os.environ.get("ROBINREACH_API_KEY")
    brand = os.environ.get("ROBINREACH_BRAND_ID")
    if not key:
        sys.exit("Set ROBINREACH_API_KEY (RobinReach dashboard → API).")
    return key, brand


def _request(method, path, body=None, params=None):
    key, brand = _creds()
    params = params or {}
    params["api_key"] = key                     # documented auth: query param
    if brand and "brand_id" not in params:
        params["brand_id"] = brand
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",   # node also sends Bearer; harmless
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"HTTP {e.code} from {path}: {detail}\n"
                 f"(401=bad key, 403=plan/permissions, 400=bad field names — "
                 f"try flipping MEDIA_FIELD/STATUS_FIELD at top of this file.)")


# ----------------------------------------------------------------------------
# Payload construction (shared by scheduling and self-test)
# ----------------------------------------------------------------------------
def build_body(draft, when, status, media_urls):
    v = draft["variants"]
    main = v.get("linkedin", {}).get("content", "")   # main = LinkedIn + Facebook

    body = {
        "content": main,
        "social_profile_ids": list(ROBIN_REACH_PROFILES.values()),
        STATUS_FIELD: status,
        "title": v.get("pinterest", {}).get("title", ""),
        MEDIA_FIELD: media_urls,

        # (1) Full per-platform CONTENT overrides — same shape the chat
        #     connector honored. Sent in case REST supports it.
        "platform_options": {
            "twitter":   v.get("twitter", {}),
            "bluesky":   v.get("bluesky", {}),
            "instagram": v.get("instagram", {}),
            "pinterest": v.get("pinterest", {}),
        },

        # (2) Documented platform_attributes the n8n node supports —
        #     graceful-degradation layer the REST API definitely reads.
        "platform_attributes": {
            "instagram": {"post_type": "post"},
            "facebook":  {"post_type": "post"},
        },
    }
    if status == "scheduled":
        body["publish_time"] = when.strftime("%Y-%m-%dT%H:%M:%SZ")
        body["timezone"] = "UTC"
    return {k: val for k, val in body.items() if val not in ("", None)}


# ----------------------------------------------------------------------------
# Public operations
# ----------------------------------------------------------------------------
def list_brands():
    print(json.dumps(_request("GET", "/brands"), indent=2))


def list_profiles():
    print(json.dumps(_request("GET", "/social_profiles"), indent=2))


def schedule_draft(draft, when, media_urls, status="scheduled"):
    if status == "scheduled" and not media_urls:
        # Instagram + Pinterest reject imageless posts — skip rather than fail.
        print(f"  ! no media — skipping (IG/Pinterest need an image): "
              f"{draft['_source_item']['title'][:50]}", file=sys.stderr)
        return None
    body = build_body(draft, when, status, media_urls)
    return _request("POST", "/posts", body=body)


def self_test():
    """Create ONE draft (nothing publishes) to verify field names + per-platform text."""
    demo = {
        "angle": "self-test",
        "variants": {
            "linkedin":  {"content": "[self-test] shared/LinkedIn body — RobinReach API check."},
            "twitter":   {"content": "[self-test] Twitter-specific body. salesmake.agency"},
            "bluesky":   {"content": "[self-test] Bluesky-specific body.", "website_url": "https://salesmake.agency/", "website_title": "SalesMake"},
            "instagram": {"content": "[self-test] Instagram-specific body. #test"},
            "pinterest": {"content": "[self-test] Pinterest-specific body.", "title": "Self Test", "link": "https://salesmake.agency/"},
        },
        "_source_item": {"title": "self-test draft"},
    }
    res = schedule_draft(demo, dt.datetime.now(dt.timezone.utc), media_urls=[], status="draft")
    print(json.dumps(res, indent=2))
    print("\n>>> Open this draft in RobinReach. If each platform shows its OWN body,\n"
          "    per-platform personalization works over the API — leave everything as is.\n"
          "    If every platform shows the LinkedIn body, REST ignores platform_options:\n"
          "    keep REVIEW_MODE=True and publish through a daily chat with the connector\n"
          "    (which does honor per-platform text). Nothing was published either way.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-brands", action="store_true")
    ap.add_argument("--list-profiles", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--dry", metavar="QUEUE_JSON", help="print bodies for a queue file, no HTTP")
    args = ap.parse_args()

    if args.list_brands:
        list_brands()
    elif args.list_profiles:
        list_profiles()
    elif args.self_test:
        self_test()
    elif args.dry:
        data = json.load(open(args.dry))
        when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
        for d in data["drafts"]:
            print(json.dumps(build_body(d, when, "scheduled", ["https://EXAMPLE/image.jpg"]), indent=2))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
