# Session → Purchase Conversion (git-for-data)

Computes the **session→purchase conversion rate per customer value segment**
(high / medium / low) from this week's shopping activity, for the Q4 re-engagement
campaign.

## What's here

| File | Purpose |
|---|---|
| `ingest_sessions_week.py` | WAP ingestion: loads the S3 sessions export onto an isolated Bauplan branch |
| `models.py` | Pipeline DAG: `session_flags` → `segment_conversion` (joins `bauplan.ecommerce_users`) |
| `expectations.py` | 6 data-quality checks on `segment_conversion` (run as part of `bauplan run`) |
| `dashboard.py` | Streamlit dashboard (bar chart + headline KPIs) reading off the branch |
| `.bauplan-branch` | The data branch this PR publishes (read by CI) |
| `ci/summarize.py` | Emits the Markdown data summary posted to the PR |

## The two "merges"

Merging this PR does **two** things, gated by one human approval:

1. **Code merge** — the pipeline code lands on git `main` (the normal PR merge).
2. **Data merge** — `.github/workflows/bauplan-publish.yml` runs `bauplan branch merge`
   to publish the tables (`ecommerce_sessions_week`, `segment_conversion`) from the data
   branch onto Bauplan `main`.

On every push, `.github/workflows/bauplan-ci.yml` re-runs the pipeline + quality gates on
the data branch and posts the current numbers + `branch diff main` as a PR comment. A
failing quality gate turns the check red.

## One-time repo setup (required for the automation)

- **Secret:** add `BAUPLAN_API_KEY` in *Settings → Secrets and variables → Actions*.
  ```bash
  gh secret set BAUPLAN_API_KEY   # paste the key when prompted; never commit it
  ```
- **Branch protection:** protect `main` and require at least 1 approving review, so
  nothing publishes to Bauplan `main` unreviewed. Recommended required check:
  *Bauplan PR checks / validate-and-summarize*.

## Reproduce locally

```bash
python conversion-pipeline/ingest_sessions_week.py          # -> prints BRANCH_NAME=...
# put that branch in conversion-pipeline/.bauplan-branch, then:
cd conversion-pipeline && bauplan checkout <branch> && bauplan run --strict on
BAUPLAN_REF=<branch> streamlit run dashboard.py --server.port 8899
```
