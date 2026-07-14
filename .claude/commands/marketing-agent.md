---
description: Handle the latest #marketing-agent Slack request as a full Bauplan end-to-end cycle (3 skills)
---

You are wired to the Slack channel **#marketing-agent** (id `C0BGPUME2LV`, workspace `bauplanlabs.slack.com`). Read the most recent message(s).

If there is no data request yet, just confirm you're wired and wait.

If it **is** a data request, run a **FULL end-to-end cycle on one isolated branch** (never `main`), using the three Bauplan skills **in this order** — do not hand-roll these steps with raw CLI:

1. Post a one-line "on it" back to the channel.
2. **Ingest** → use the **`bauplan-safe-ingestion`** skill to load the S3 data referenced in the request into an isolated branch. Do **not** let it merge to `main` — keep the branch open for review. All later steps reuse this same branch.
   **Persist the import as code — never run it ephemerally.** Always write the WAP import script to `conversion-pipeline/ingestion.py` (create the folder if it doesn't exist yet) so the ingestion is reproducible and ships in the review PR next to the pipeline. Make it a standalone, re-runnable script guarded by `if __name__ == "__main__":` — it is not a Bauplan model, so `bauplan run` won't pick it up.
3. **Pipeline** → use the **`bauplan-data-pipeline`** skill to build the requested transformation on that branch (e.g. session→purchase conversion per customer segment, joining `bauplan.ecommerce_users`).
4. **Quality** → use the **`bauplan-data-quality-checks`** skill to generate and run expectations on the result (e.g. `customer_segment` must be high/medium/low with no nulls).
5. If the request asks for a dashboard, use the **`building-streamlit-dashboards`** skill, then **launch it locally** with Streamlit headless in the background (e.g. `.venv/bin/streamlit run <app>.py --server.headless true --server.port 8899`) so it's reachable at `http://localhost:8899`. Point its data source at the open branch for the pre-publish preview.
6. **Open a PR automatically for the data engineer to review.** Build the pipeline into the `conversion-pipeline/` project directory (fixed convention the workflows expect), then run:
   ```
   .claude/skills/bauplan-pipeline-pr/open_pipeline_pr.sh conversion-pipeline <data-branch> bauplan.<result_table> http://localhost:8899
   ```
   Capture the printed `PR_URL`. This opens a GitHub PR containing the generated pipeline; its CI re-runs the pipeline + quality checks and posts the numbers + diff as a comment. Do **NOT** merge it yourself — the engineer reviews and merges, and merging auto-publishes the tables to `main` (via `.github/workflows/bauplan-publish.yml`).
7. Post a short status back to the **#marketing-agent** channel: branch name, key numbers, quality result, the **dashboard link** `http://localhost:8899`, and the **PR link** (`PR_URL`) — both as markdown links — noting the engineer can review & merge the PR to publish.

Hard rules (from `.claude/CLAUDE.md`): never write/import to `main`; verify the active branch before any run; **never merge to `main` yourself** — publishing happens only when a human merges the PR. Reuse ONE branch across all steps and build the pipeline into `conversion-pipeline/`. Be concise — do the work, don't explain the demo.