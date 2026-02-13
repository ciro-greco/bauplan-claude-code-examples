---
name: self-healing-pipeline
description: "Diagnose a failed Bauplan pipeline run, pin the exact data and code state, collect evidence, apply a minimal fix, and rerun. Evidence first, changes second."
allowed-tools:
  - Bash(bauplan:*)
  - Bash(git)
  - Read
  - Write
  - Glob
  - Grep
  - WebFetch(domain:docs.bauplanlabs.com)
---

# Self-Healing Pipeline

Diagnose and fix failed Bauplan runs. Evidence first, changes second.

## Hard Rules

1. **NEVER touch `main`** — not in Bauplan, not in Git.
2. **NEVER change code without Git** — every edit lives on a debug branch with a commit.
3. **NEVER query a moving ref** — always target `branch@commit_hash` or a tag.
4. **NEVER rerun before inspecting** — understand the failure, then act.
5. **NEVER clean up debug branches** unless the user explicitly asks.

If any rule cannot be satisfied, **STOP** and report the blocker.

## Required Inputs

You need at least one of:

- Bauplan **job id** (preferred)
- Bauplan **branch name**
- **Time window** to locate failed jobs
- **Local path** to the project directory

If none are provided, infer from context (`bauplan info`, local Git state). If ambiguous, ask.

## Workflow

### Step 0 — Safety Check

**Bauplan:** Run `bauplan info`. If on `main`, create a debug branch first:
```bash
bauplan checkout --branch <username>.debug_<short_name>
```

**Git:** Verify `.git` exists and you are NOT on `main`. If Git is missing or broken, record the blocker and limit yourself to evidence collection only.

### Step 1 — Pin the Failing State

**Goal:** Get the exact Bauplan commit hash for the failed run.

- If you have a **job id**: fetch job metadata and logs, extract the ref/commit hash.
- If you have a **branch**: list recent commits, match to the failing job.
- Fall back to asking the user if neither approach yields a concrete hash.

End this step with either a **commit hash** or a clear statement that the data state cannot be pinned.

### Step 2 — Create Debug Branches

**Bauplan:** Branch from the pinned ref, not from `main`.
```
branch:  <username>.debug_<job_id_or_short_hash>
from_ref: <source_branch>@<commit_hash>
```

**Git:** Create `debug/bpln_<job_id_or_short_hash>`. If the working tree is dirty, commit a snapshot checkpoint first.

### Step 3 — Collect Evidence

Do this **before any fixes**.

| Evidence type | What to collect                                                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| **Code**      | Models (Python/SQL), expectations, decorators, `bauplan_project.yml`. Note whether code is pinned to a Git SHA or reflects current working state. |
| **Logs**      | Full error message, failing model/step, runtime context (Python version, deps, limits). Summarize from API responses only — no speculation.       |
| **Data**      | For each relevant table on the pinned ref: schema, row count, sample (10–20 rows), targeted anomaly query, basic stats (min/max/nulls).           |

Save to:
- `debug/code_snapshot/` — code files + pinning statement
- `debug/data_snapshot/<table>.md` — one file per table
- `debug/job/<job_id>.md` — job metadata, commit hash, branch names

### Step 4 — Classify the Failure

Based on evidence only, classify as one of:

- **Planning/compilation** — DAG or schema error before execution
- **Runtime** — crash, timeout, dependency issue during execution
- **Expectation** — data quality check failed
- **Logical correctness** — runs clean but produces wrong results

If you cannot reproduce the failure with a query on the pinned ref, the failure is not localized. Stop and report.

### Step 5 — Apply a Minimal Fix

Rules:
- One logical change per commit. No refactors.
- Prefer: schema corrections → input tightening → expectation fixes.
- Commit message must include the Bauplan job id.

Record in `debug/fix_log.md`: file changed, diff summary, reasoning.

Never amend or squash during debugging.

### Step 6 — Rerun

Rerun on the Bauplan debug branch from Step 2.

Preferred: `rerun(job_id, ref=<debug_branch>)`
Fallback: dry run first, then full run with `--strict`.

If Git SHA is unknown, label the rerun as **best-effort**.

After a green run, re-execute the queries that previously showed the failure. Record before vs. after evidence.

## Output Checklist

At the end you must have produced:

- [ ] `debug/job/<job_id>.md` — job metadata, pinned commit hash, Git SHA (or "unknown")
- [ ] `debug/code_snapshot/` — code at time of failure + pinning statement
- [ ] `debug/data_snapshot/` — data evidence from the pinned ref
- [ ] `debug/fix_log.md` — minimal fix history
- [ ] Either a **successful rerun** on the debug branch, or a **single concrete blocker** stated plainly