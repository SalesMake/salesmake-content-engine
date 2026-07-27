"""
Source feeds for the SalesMake daily content engine.

Each source: the public RSS/Atom feed + a category tag used for relevance
weighting. Substack publications all expose /feed. Most blogs expose
/feed, /rss, or /rss.xml — the engine auto-probes those suffixes if the
listed URL 404s, so you rarely have to hunt one down by hand.

VERIFY THE FEED URLS ONCE when you first deploy: run `python content_engine.py --check-feeds`.
This sandbox can't reach the open web, so the URLs below are the standard
patterns for each platform, not live-tested. The --check-feeds pass will
tell you which resolve and which need a manual URL.
"""

SOURCES = [
    # --- GTM strategy & GTM engineering (highest relevance to enrichment work) ---
    {"name": "The GTM Engineer (Clay)",   "feed": "https://thegtme.com/feed",                        "category": "gtm_engineering", "weight": 1.4},
    {"name": "Claymation",                "feed": "https://www.claymation.io/feed",                   "category": "gtm_engineering", "weight": 1.3},
    {"name": "Clay Blog",                 "feed": "https://www.clay.com/blog/rss.xml",                "category": "gtm_engineering", "weight": 1.2},
    {"name": "Growth Unhinged",           "feed": "https://www.growthunhinged.com/feed",              "category": "gtm_strategy",    "weight": 1.3},
    {"name": "GTM Strategist (Maja Voje)","feed": "https://gtmstrategist.substack.com/feed",          "category": "gtm_strategy",    "weight": 1.2},

    # --- Cold email outreach ---
    {"name": "Lemlist Blog",              "feed": "https://www.lemlist.com/blog/rss.xml",             "category": "cold_email",      "weight": 1.1},
    {"name": "Hunter.io Blog",            "feed": "https://hunter.io/blog/feed/",                     "category": "cold_email",      "weight": 1.0},
    {"name": "Instantly Blog",            "feed": "https://instantly.ai/blog/feed",                   "category": "cold_email",      "weight": 1.0},
    {"name": "Belkins Blog",              "feed": "https://belkins.io/blog/rss",                      "category": "cold_email",      "weight": 1.0},

    # --- LinkedIn outreach & social selling ---
    {"name": "Expandi Blog",              "feed": "https://expandi.io/blog/feed/",                    "category": "linkedin",        "weight": 1.1},
    {"name": "Taplio Blog",               "feed": "https://taplio.com/blog/rss.xml",                  "category": "linkedin",        "weight": 0.9},
]

# Terms that mark an item as on-topic for SalesMake. Used to score & filter
# so you don't republish, say, a Clay post about their office move.
RELEVANCE_KEYWORDS = [
    "cold email", "outbound", "deliverability", "reply rate", "sequence",
    "linkedin", "social selling", "prospect", "icp", "gtm", "go-to-market",
    "clay", "enrichment", "signal", "intent", "sdr", "pipeline", "revops",
    "personalization", "outreach", "lead", "waterfall", "automation",
]

# Robin Reach connected profiles (from your account). Used by the posting
# handoff so approved drafts map straight onto create_post.
ROBIN_REACH_PROFILES = {
    "linkedin":  1550,
    "facebook":  1601,
    "twitter":   1540,
    "bluesky":   1604,
    "instagram": 1605,
    "pinterest": 1606,
}

# Per-platform voice guidance — mirrors Robin Reach's own validator hints so
# the drafts pass validation on the first try.
PLATFORM_STYLE = {
    "linkedin":  "Professional, value-driven. Hook + insight + a question to the reader. 1-3 short paragraphs. Sparse hashtags. This is the flagship channel — give it the fullest take.",
    "facebook":  "Friendly, story-driven, slightly longer is fine. 1-2 hashtags. (Shares the LinkedIn body — no separate override needed.)",
    "twitter":   "Punchy, <=280 chars, hook in line one, 1-2 hashtags max, no fluff. NO URLs in the body (this profile rejects links) — use the bare domain salesmake.agency instead.",
    "bluesky":   "Concise, <=300 chars, plain-spoken, light on hashtags. A link card is attached separately.",
    "instagram": "Visual-first caption, hook in line 1, arrow or emoji bullets, 3-10 niche hashtags at the end. Caption can't hyperlink — point to 'link in bio'.",
    "pinterest": "Keyword-rich description, action verb up front, plus a short title. Destination URL set on the pin.",
}
