# SalesMake daily content engine

Collects the day's posts from 11 outbound/GTM sources, writes SalesMake's own
take on each (attributed + linked, never a spin), tailors a variant per
connected account, and schedules them through RobinReach.

## Files
- `sources.py`          – feeds, relevance keywords, RobinReach profile IDs, per-platform voice
- `content_engine.py`   – fetch → filter → rework → tailor → queue (and auto-post if enabled)
- `post_queue.py`       – manual approve-then-publish (human-in-the-loop path)
- `robinreach_client.py`– RobinReach REST client (unattended path)
- `daily.yml`           – GitHub Actions cron (drop in .github/workflows/)
- `requirements.txt`

## One-time setup
1. `pip install -r requirements.txt`
2. `export ANTHROPIC_API_KEY=...`
3. `python content_engine.py --check-feeds`  → confirm/fix any feed URLs
4. Get RobinReach API creds (dashboard → API; Bloom plan has access):
   - `export ROBINREACH_API_KEY=...`
   - `python robinreach_client.py --list-brands`    → copy your brand_id
   - `export ROBINREACH_BRAND_ID=...`
   - `python robinreach_client.py --list-profiles`  → confirm the 6 profile IDs
     match those in sources.py (update if the REST API uses different IDs)
5. `python robinreach_client.py --self-test`  → creates ONE draft (nothing goes
   live). Open it in RobinReach: if each platform shows its own text, per-account
   personalization works over the API. If not, keep the review path (below).

## Cadence
2-3 posts/day across 6 platforms. Surplus items go to `queue/_backlog.json` and
top up lean days, so the feed's uneven publishing rhythm doesn't create gaps or
floods. Change `MAX_ITEMS_PER_RUN`, `SCHEDULE_SLOTS`, or `POSTING_DAYS` in
content_engine.py to adjust.

## Daily use
- **Review-first (default, recommended to start):** cron runs the engine, drafts
  land in `queue/YYYY-MM-DD.md`. You skim, then `python post_queue.py queue/<date>.json`.
- **Fully unattended:** set `REVIEW_MODE = False` in content_engine.py. The cron
  then collects, drafts, and schedules to RobinReach for the next day at 11:00 UTC.

## Guardrails baked in
- Posts 2-3/day at 11:00, 13:00, 14:30 UTC (Tue-Fri, your configured preferred times/days); skips thin/promotional/off-topic items.
- Always attributes the source and links it; never reproduces >10 words.
- Unverifiable stats are attributed ("Per <source>…"), never stated as fact.
- Imageless posts are skipped (IG/Pinterest reject them) unless SALESMAKE_DEFAULT_IMAGE is set.
- Twitter gets the bare domain (that profile rejects URLs).
