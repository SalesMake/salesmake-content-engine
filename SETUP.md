# Setup + how approval works

## A. One-time GitHub setup (~10 minutes)

1. **Create a private repo** — e.g. `salesmake-content-engine`.
2. **Push these files.** From the unzipped folder:
   ```bash
   git init && git add . && git commit -m "content engine"
   git remote add origin git@github.com:<you>/salesmake-content-engine.git
   git push -u origin main
   ```
3. **Move the workflows into place:**
   ```bash
   mkdir -p .github/workflows
   mv workflows/collect.yml workflows/publish.yml .github/workflows/
   git add -A && git commit -m "workflows" && git push
   ```
4. **Add secrets** — repo → Settings → Secrets and variables → Actions → New secret:
   | Secret | Where to get it |
   |---|---|
   | `ANTHROPIC_API_KEY` | console.anthropic.com |
   | `ROBINREACH_API_KEY` | RobinReach dashboard → API |
   | `ROBINREACH_BRAND_ID` | `python robinreach_client.py --list-brands` |
   | `SALESMAKE_DEFAULT_IMAGE` | (optional) URL of a hosted brand image |

5. **Create the approval gate** — repo → Settings → Environments → New environment
   → name it exactly **`social-publishing`** → tick **Required reviewers** → add
   yourself → Save.

   This is the whole approval mechanism. Without it the publish job runs
   unattended; with it, the job *pauses and waits for you*.

## B. How you approve posts, day to day

Every weekday at 06:00 UTC the collect job runs on its own: it reads the feeds,
drafts 2–3 posts, and commits them to `queue/`. Then it hands off to the publish
job — which **stops and waits**.

You get a GitHub notification (email + mobile app) saying a deployment needs
review. To approve:

1. Open the run — Actions tab, or straight from the email.
2. Read the drafts. Either:
   - the job log lists the headlines, or
   - open `queue/<date>.md` in the repo for the full text of all six platform
     variants.
3. Click **Review deployments → social-publishing → Approve and deploy.**
   (Or **Reject** — nothing posts, the queue file just sits there.)

On approval the posts schedule to RobinReach for the next posting day at
11:00, 13:00 and 14:30 UTC.

### Approving only *some* of the batch
The gate is all-or-nothing per run. To drop one item: edit
`queue/<date>.json`, delete that draft object from the `drafts` array, commit,
then approve. The job reads the file at approval time, so your edit takes effect.

### If you'd rather approve from your laptop instead of GitHub
Skip the environment gate and run it locally:
```bash
git pull
python post_queue.py queue/<date>.json     # interactive y/N per post
```

## C. Before the first automated run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...  ROBINREACH_API_KEY=...
python content_engine.py --check-feeds          # confirm/fix feed URLs
python robinreach_client.py --list-brands       # get brand id
export ROBINREACH_BRAND_ID=...
python robinreach_client.py --list-profiles     # confirm the 6 profile IDs
python robinreach_client.py --self-test         # creates ONE draft, publishes nothing
```

The self-test answers the one open question: whether the REST API keeps
per-platform copy. Open the draft in RobinReach — six different bodies means
yes. If they're identical, keep approving through this chat instead, since the
chat connector definitely preserves all six.

## D. Turning the gate off later
Once you trust the output, delete the required reviewer from the
`social-publishing` environment. Everything then runs end to end with no
human step. `REVIEW_MODE` in `content_engine.py` stays `True` — the gate is
what controls publishing, and it keeps the drafts committed either way.
