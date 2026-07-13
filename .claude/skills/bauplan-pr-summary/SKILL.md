---
name: bauplan-pr-summary
description: Generate a review summary for a Bauplan pipeline Pull Request, derived from Bauplan's introspection APIs (commits, jobs, table metadata) rather than hand-assembled. Use when opening or updating a PR that publishes Bauplan tables to `main` — so the reviewing data engineer sees EVERYTHING the merge writes to production, plus the DAG, lineage, run status, data-quality result, and provenance. Produces/maintains a `pr_summary.py`.
license: Apache-2.0
---

# Bauplan PR summary

A pipeline PR is a request to publish data to production `main`. The reviewer (a data
engineer) must be able to see **everything the merge will do**, not just the headline
result. This skill builds a `pr_summary.py` that **derives** the summary from Bauplan's
own introspection APIs — the ground truth of what happened and what merging applies.

## Core principle

> Derive the PR summary from the run's **job context + commits + table metadata**.
> Never hand-wave what merging publishes, and never reproduce the pipeline code — the
> code is already in the PR diff.

If a table gets written to `main`, it MUST appear in the summary with its row count. The
most common failure is showing only the final result table while a large raw/imported
table silently rides along — that is exactly what this skill prevents.

## The API → section mapping

Build each section from the API that is its source of truth:

| Section | Source of truth | APIs |
|---|---|---|
| **⚠️ Publish impact** — every table the merge adds/modifies/drops on `main`, with rows·cols·size·role | the branch-vs-main diff, enriched with table metadata | `bauplan branch diff main <branch>` (authoritative) → per table `client.get_table(fqn, ref)` for `.records`, `.fields`, `.size` |
| **🧬 Pipeline** — DAG (as a **Mermaid diagram**), lineage, status, timing (NO code) | the run job's context | `client.get_job_context(run_job_id, include_snapshot=True)` → `dag_nodes` / `dag_edges`; `client.get_job(run_job_id)` → status + created/started/finished |
| **✅ Data quality** — expectations + verdict | the run job (strict) + its snapshot | job `human_readable_status == "Completed"` (strict ⇒ all passed); expectation names via regex over `snapshot_dict["expectations.py"]` |
| **🧭 Provenance** — how the branch was built | commits unique to the branch | `client.get_commits(ref=branch)` minus `client.get_commits(ref="main")` |
| **📊 Result preview** — the business answer | the result table | `client.query("SELECT * FROM <result_table>", ref=branch)` |

## Getting the run job id (the key link)

Do **not** scan `get_jobs()` to find the run — it returns oldest-first and drops recent
jobs. Instead, read it from provenance: the branch's materialize commit has the subject
`Run job_id=<id>`. Extract it:

```python
for c in branch_provenance:            # commits unique to the branch
    if c.subject.startswith("Run"):
        run_job_id = re.search(r"job_id=(\S+)", c.subject).group(1)
```

Pass it explicitly if the caller already captured it from `bauplan run` output; otherwise
derive it this way.

## DAG + lineage without code

- `dag_nodes` = the models (`.id`, `.name`). `dag_edges` = dependencies. Keep only edges
  where **both** `source_model` and `destination_model` are node ids — the ones with
  `source_model = None` are "reads a source table" roots, not model→model edges.
- Classify each published table by **role** using the DAG: an added table whose name
  matches a `dag_node` name is a **pipeline output**; an added table that is *not* a model
  is an **imported source**. This gives table-level lineage (sources → outputs) with no
  code parsing.

## Render the DAG as a Mermaid diagram

GitHub renders ```` ```mermaid ```` fenced blocks in PR bodies and comments, so emit the
DAG as a picture, not just text. Build it from the same `dag_nodes` / `dag_edges` — still
no code parsing:

- `flowchart LR`; one node per model — sanitize the name to a Mermaid id (`re.sub(r"\W","_",name)`),
  keep the real name as the label.
- One `A --> B` per **real** model→model edge (the filtered ones; skip `source_model = None` roots).
- Highlight **materialized-output** models (those whose name matches a published output
  table) with a `classDef` so the reviewer sees at a glance where data lands. Example:

  ````
  ```mermaid
  flowchart LR
      session_flags["session_flags"]
      segment_conversion["segment_conversion"]:::output
      session_flags --> segment_conversion
      classDef output fill:#dcfce7,stroke:#16a34a,color:#14532d;
  ```
  ````

Keep node ids sanitized (model names are usually identifier-safe, but never assume).

## Table metadata is free

`client.get_table(fqn, ref)` already returns `.records` (row count), `.fields` (schema),
and `.size` (bytes) — never run `COUNT(*)` for this.

## Inputs / outputs

`pr_summary.py <branch> [result_table] [dashboard_url]` (also honors env `BAUPLAN_BRANCH`,
`RESULT_TABLE`, `DASHBOARD_URL`, `RUN_JOB_ID`). It prints Markdown to stdout — used both
for the PR **body** (by `scripts/open_pipeline_pr.sh`) and the CI **comment** (by
`.github/workflows/bauplan-ci.yml`). It must degrade gracefully: if the run job can't be
found, still print publish impact + provenance + result, and note the code is in the diff.

## Reference implementation

A working, maintained implementation lives **next to this file**, at
`pr_summary.py` in this skill folder (`.claude/skills/bauplan-pr-summary/pr_summary.py`) —
the skill is a self-contained package, so the instructions and the reference
implementation travel together. Its callers invoke it by that path: the CI workflow
(`.github/workflows/bauplan-ci.yml`) and the PR helper (`scripts/open_pipeline_pr.sh`).

When adapting it, keep the section order (publish impact FIRST) and the principle above.
Validate against a real branch: build a pipeline on a branch, run it, then
`python .claude/skills/bauplan-pr-summary/pr_summary.py <branch> <result_table>` and
confirm every published table appears with a row count.

## Keep the skill and the script in sync

This skill is the source of truth, not the script. **Any improvement to `pr_summary.py`
(a new section, a new rendering like the Mermaid DAG, a new API used) MUST be reflected
here** — update the API→section table and the relevant section — otherwise the next run
regenerates the old version and the improvement is lost. Treat "edit the script" and
"edit this skill" as one change, never two. They live in the same folder for exactly this
reason.