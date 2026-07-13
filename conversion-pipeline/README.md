# Session → Purchase Conversion (git-for-data)

Computes the **session→purchase conversion rate per customer value segment**
(high / medium / low) from this week's shopping activity, for the Q4 re-engagement
campaign.

| File | Purpose |
|---|---|
| `ingest_sessions_week.py` | WAP ingestion: loads the S3 sessions export onto an isolated Bauplan branch |
| `models.py` | Pipeline DAG: `session_flags` → `segment_conversion` (joins `bauplan.ecommerce_users`) |
| `expectations.py` | 6 data-quality checks on `segment_conversion` (run as part of `bauplan run`) |
| `dashboard.py` | Streamlit dashboard (bar chart + headline KPIs) reading off the branch |

## How this gets published

This project is opened as a **GitHub PR** automatically by `/marketing-agent`
(via `scripts/open_pipeline_pr.sh`). The PR carries a manifest at the repo root,
`.bauplan/pr.env`, naming the Bauplan data branch to publish. Then:

- `.github/workflows/bauplan-ci.yml` re-runs the pipeline + quality gates on that branch
  and posts the numbers + `branch diff main` as a PR comment (red check if quality fails).
- Merging the PR triggers `.github/workflows/bauplan-publish.yml`, which runs
  `bauplan branch merge` to publish the tables (`ecommerce_sessions_week`,
  `segment_conversion`) onto Bauplan `main`.

So a data engineer just **reviews and merges the PR** — no hand-building required.
Requires a `BAUPLAN_API_KEY` Actions secret (already configured).

## Reproduce locally

```bash
python conversion-pipeline/ingest_sessions_week.py     # prints BRANCH_NAME=...
cd conversion-pipeline && bauplan checkout <branch> && bauplan run --strict on
BAUPLAN_REF=<branch> streamlit run dashboard.py --server.port 8899
```
