---
name: self-healing-pipeline
description: "Diagnose a failed Bauplan pipeline run, pin the exact data and code state, collect evidence, apply a minimal fix, and rerun. Then harden the pipeline with data quality expectations to prevent recurrence. Evidence first, changes second."
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

Diagnose and fix failed Bauplan runs, then prevent recurrence with data quality expectations. Evidence first, changes second.

## Hard Rules

1. **NEVER touch `main`** — not in Bauplan, not in Git.
2. **NEVER change code without Git** — every edit lives on a Git debug branch with a commit. The Git branch is created in Step 5 when fixes begin, not during investigation.
3. **NEVER query a moving ref** — always target `branch@commit_hash` or a tag.
4. **NEVER rerun before inspecting** — understand the failure, then act.
5. **NEVER clean up debug branches** unless the user explicitly asks.
6. **NEVER guess CLI flags.** Before running any `bauplan` CLI command, verify the exact flag names against the CLI reference doc in the project. If unsure about a flag, check first.
7. **NEVER create files outside `debug/` and the pipeline project directory.** No top-level documentation, no READMEs, no schema guides. Your outputs are: the `debug/` report files, and edits to existing pipeline code (models, expectations, project config). Nothing else.
8. **NEVER write Python scripts for diagnosis.** Steps 0–4 (evidence collection, classification, root cause analysis) use `bauplan` CLI commands exclusively. The only Python you write is pipeline code: model fixes in `models.py` and expectations in `expectations.py`.
9. **NEVER branch from the current checkout or a previous debug session.** The debug branch must be created from the failing job's own ref (`job_branch@job_commit` from Step 1). If you branch from anywhere else, you will investigate the wrong data and reach wrong conclusions.

Common CLI flag mistakes to avoid:
- ❌ `--format json` → ✅ `--output json` (or `-o json`)
- ❌ `--branch` on read commands → ✅ `--ref` (use `--branch` only for write operations like `create`, `delete`)
- ❌ `--id` on `job get` → ✅ positional argument: `bauplan job get <JOB_ID>`

If any rule cannot be satisfied, **STOP** and report the blocker.

## Required Inputs

You need at least one of:

- Bauplan **job id** (preferred)
- Bauplan **branch name**
- **Time window** to locate failed jobs
- **Local path** to the project directory

If none are provided, infer from context (`bauplan info`, local Git state). If ambiguous, ask.

## Workflow

### Step 0 — Setup

**Bauplan:** Run `bauplan info` to confirm connectivity and get your username (needed for branch naming in Step 2). Do not create any branches yet — Steps 1–4 are read-only and do not require a branch.

**Git:** Check whether `.git` exists. Note the result — you will need it in Step 5 when code changes begin. Do not create any Git branches yet.

**Create output directories:**
```bash
mkdir -p debug/{job,data_snapshot}
```

### Step 1 — Pin the Failing State

**Goal:** Extract three things from the failing job: the **branch** it ran on, the **commit hash** representing the data state, and the **raw error message**. Use CLI commands only — do not write scripts.

- If you have a **job id**:
  ```bash
  bauplan job get <job_id>
  bauplan job logs <job_id>
  ```
  From the output, extract:
  1. The **branch** the job ran against (e.g., `ciro.debug_2d87c900`)
  2. The **commit hash** on that branch at the time of the run
  3. The **error message** (copy verbatim — you will analyze it in Step 3)

- If `job get` does not show the commit hash directly, find it by listing commits on the job's branch:
  ```bash
  bauplan commit --ref <job_branch> --limit 10
  ```
  Match by timestamp against the job's created/finished time → extract `commit_hash`.

- If you need to find the job first:
  ```bash
  bauplan job ls --status fail --limit 10
  ```
  Identify the matching job, then `bauplan job get <job_id>`.

- Fall back to asking the user if neither approach yields a concrete hash.

End this step with three values:
- `job_branch`: the branch the failing job ran on
- `job_commit`: the commit hash on that branch (or a clear statement that the data state cannot be pinned)
- `raw_error`: the verbatim error message from the logs

**⏸ WRITE REPORT NOW:** Before proceeding, write `debug/job/<job_id>.md` using the Job Report template. The user needs something to read while you continue working. Do not defer this.

### Step 2 — Create Bauplan Debug Branch

**CRITICAL:** The debug branch must be created from the **failing job's own ref** — the `job_branch@job_commit` you extracted in Step 1. Do NOT branch from whatever happens to be checked out, from a previous debug session, or from `main`. The point of branching from the failing ref is to see the exact data state the job saw when it failed. If you branch from anywhere else, you will investigate the wrong data and reach wrong conclusions.

```bash
bauplan branch create <username>.debug_<job_id_short> --from-ref <job_branch>@<job_commit>
bauplan checkout <username>.debug_<job_id_short>
```

If `job_commit` could not be pinned in Step 1, branch from `job_branch` (without a hash). Note in the job report that the data ref is approximate.

### Step 3 — Collect Evidence

Do this **before any fixes**.

#### How to collect evidence

**Use the `bauplan` CLI for all data queries.** Do not write Python scripts to explore data or collect evidence. Every piece of information you need — schemas, row counts, samples, stats — is available through `bauplan table get` and `bauplan query`. Run these commands directly in the terminal.

#### Code assumption

**Assume the code in the current repository is what ran at the time of failure.** Do not copy pipeline files into the debug directory. It is the user's responsibility to ensure they are on the correct Git commit before invoking this skill. If the user is unsure, they should check out the appropriate commit first.

Read the pipeline code in place (`models.py`, `.sql` files, `expectations.py`, `bauplan_project.yml`) to understand the DAG structure, model inputs/outputs, and declared expectations. Reference it in your reports by file path, not by copying it.

#### 3A — Identify the failing model

Using the raw error from Step 1 and the pipeline code, identify:
- Which **model** failed (function name or SQL filename)
- Which **file** it lives in
- What the error message means in the context of that model's logic

Do not re-run `bauplan job get` or `bauplan job logs` — you already have the error from Step 1.

#### 3B — Scope tables to inspect

From the failing model, inspect exactly three layers:

1. **Inputs** — every table the failing model reads from (its `bauplan.Model(...)` references)
2. **Output** — the table the failing model produces (its function name or SQL filename)
3. **One level downstream** — any model that reads from the failing model's output

If the DAG is unclear from code:
```bash
bauplan table ls --ref <pinned_ref>
```
Then match against model definitions.

Do not inspect tables outside these three layers unless evidence points there.

#### 3C — Collect data evidence

**Query guardrails:** All sample queries must use `LIMIT 20`. All profiling queries (counts, stats) must use `LIMIT 1`. Never run unbounded queries.

For each table from 3B, run against the pinned ref:

```bash
# Schema
bauplan table get <ns>.<table> --ref <pinned_ref>

# Row count
bauplan query --ref <pinned_ref> "SELECT COUNT(*) as n FROM <ns>.<table>"

# Sample (20 rows)
bauplan query --ref <pinned_ref> --max-rows 20 "SELECT * FROM <ns>.<table> LIMIT 20"

# Basic stats per column
bauplan query --ref <pinned_ref> "SELECT MIN(<col>), MAX(<col>), COUNT(*) - COUNT(<col>) as nulls FROM <ns>.<table>"
```

Save data evidence to `debug/data_snapshot/<table>.md` — one file per table.

**⏸ WRITE REPORTS NOW:** Write each `debug/data_snapshot/<table>.md` file immediately after collecting evidence for that table, using the Data Report template. Do not wait until all tables are inspected. Write each one as you go so the user can review them in real time.

### Step 4 — Classify and Localize the Failure

This step is pure analysis — read the reports from Steps 1 and 3, do not run new queries.

Based on the raw error (Step 1), the pipeline code (Step 3A), and the data reports (Step 3C), determine:

**Classification** — one of:
- **Planning/compilation** — DAG or schema error before execution
- **Runtime** — crash, timeout, dependency issue during execution
- **Expectation** — data quality check failed
- **Logical correctness** — runs clean but produces wrong results

**Localization** — the model that errors is not necessarily the model with the bug. Review the data reports for the failing model's **input tables**. 
If an input has anomalies (unexpected nulls, wrong types, schema drift), the root cause is likely upstream of the failing model. Identify which model produced the bad input — that is the model to fix.

**Escape clause:** If evidence points to a model outside the three-layer scope from Step 3B, return to Step 3B to widen the scope, collect evidence for the additional tables, then resume here.

If you cannot localize the failure to a specific model using the collected evidence, stop and report.

### Step 5 — Apply a Minimal Fix

#### Git setup (first time only)

Code changes require version control. Before editing any files:

- **Git available and not on `main`:** Create a debug branch:
  ```bash
  git checkout -b debug/bpln_<job_id_short>
  ```
  If the working tree is dirty, commit a snapshot checkpoint first so the pre-fix state is preserved.

- **Git available but on `main`:** Create the debug branch from `main`, which moves you off it:
  ```bash
  git checkout -b debug/bpln_<job_id_short>
  ```

- **No Git repo:** Note code provenance as "unversioned" in the summary report. Fixes will go through `code_run` instead of local commits.

#### Fix priority

Prefer fixes closest to the data contract boundary, because contract-level issues propagate furthest and are cheapest to verify:

1. **Schema corrections** — wrong column types, missing columns, mismatched output declarations
2. **Input tightening** — add or fix `filter` / `columns` in `bauplan.Model()` to reject bad data earlier
3. **Expectation fixes** — adjust or add data quality checks that should have caught the issue
4. **Transform logic** — change the model's computation only if the above three don't resolve it

Rules:
- One logical change per commit. No refactors.
- Commit message must include the Bauplan job id.

Never amend or squash during debugging.

### Step 6 — Rerun

#### Determinism check

Before rerunning, assess what you can actually prove:

| Condition                      | Status |
|--------------------------------|--------|
| Data ref pinned to commit hash | ✅ or ❌ |
| Git SHA pinned for code        | ✅ or ❌ |

- **Both pinned** → rerun is **deterministic**. A green result proves the fix works against the exact failing state.
- **One or both unpinned** → rerun is **best-effort**. A green result is encouraging but not conclusive. State this explicitly.

#### Execute

```bash
# Preferred: strict mode, from the debug branch
bauplan run --project-dir <dir> --ref <debug_branch> --strict on

# Fallback: dry run first, then full run
bauplan run --project-dir <dir> --ref <debug_branch> --dry-run --strict on
bauplan run --project-dir <dir> --ref <debug_branch> --strict on
```

After a green run, re-execute the queries from Step 3 that previously showed the failure. Record before vs. after evidence.

### Step 7 — Prevent Recurrence with Data Quality Expectations

A fix without prevention is half the job. After the rerun is green, add expectations that would have caught this failure **before it reached the pipeline**.

#### 7A — Determine what to guard

Look at the root cause from Step 4:

| Root cause                                 | What to guard                                     | Where to place the expectation                                            |
|--------------------------------------------|---------------------------------------------------|---------------------------------------------------------------------------|
| Schema drift (type change, missing column) | Column types and presence on the **source table** | `expectations.py`, targeting the first model that reads the drifted table |
| Bad values (nulls, out-of-range, invalid)  | Value constraints on the **source table**         | `expectations.py`, targeting the model that reads the table               |
| Logic error in a transform                 | Output invariants on the **producing model**      | `expectations.py`, targeting the model's output table                     |

#### 7B — Write expectations

Create or update `expectations.py` in the pipeline project directory.

**Use built-in expectations when they fit.** These are available from `bauplan.standard_expectations`:

| Function                                                | Use when                                                    |
|---------------------------------------------------------|-------------------------------------------------------------|
| `expect_column_no_nulls(data, col)`                     | A column must never be null                                 |
| `expect_column_all_unique(data, col)`                   | A column must have no duplicates (IDs, keys)                |
| `expect_column_accepted_values(data, col, values)`      | A column must only contain known values (enums, categories) |
| `expect_column_mean_greater_than(data, col, threshold)` | Numeric column's average must exceed a floor                |
| `expect_column_mean_smaller_than(data, col, threshold)` | Numeric column's average must stay below a ceiling          |

**Write a custom expectation when no built-in fits.** Common cases that require custom expectations:

- Column type validation (no built-in exists for this)
- Cross-column consistency checks
- Row count thresholds
- Schema completeness (expected columns are present)

Custom expectation template:
```python
import bauplan

@bauplan.expectation()
@bauplan.python('3.11')
def test_custom_check(data=bauplan.Model('<table_name>')):
    """<Description of what this guards against>."""
    # your validation logic here — must return True or raise
    assert <condition>, '<failure message>'
    return True
```

#### 7C — Common pattern: type guard expectation

Schema drift (a column changing type after a bad import) has no built-in expectation. Write a custom one:

```python
import bauplan

@bauplan.expectation()
@bauplan.python('3.11')
def test_column_types(data=bauplan.Model('<source_table>')):
    """
    Guards against schema drift by verifying critical columns
    have the expected Arrow types. Catches type changes from
    upstream imports before they break downstream models.
    """
    expected_types = {
        '<column_name>': pa.float64(),   # adapt to your schema
        '<other_column>': pa.int64(),
    }
    schema = data.schema
    for col_name, expected_type in expected_types.items():
        actual_field = schema.field(col_name)
        assert actual_field.type == expected_type, (
            f"Column '{col_name}' has type {actual_field.type}, expected {expected_type}. "
            f"This likely means an upstream import introduced a schema change."
        )
    return True
```

#### 7D — Validate the expectations

1. Run the pipeline with expectations on the debug branch:
   ```bash
   bauplan run --project-dir <dir> --ref <debug_branch> --strict on
   ```
2. Verify expectations pass on the fixed state.
3. Confirm expectations **would have failed** on the broken state by reasoning about the evidence from Step 3 (e.g., "the type was string, our expectation asserts float64 → it would have caught it").
4. Commit the expectations file. Message: `"Add data quality guard for <root_cause> (job <job_id>)"`.

**⏸ WRITE REPORT NOW:** Write `debug/summary.md` using the Summary template. This is the final deliverable — the single document that explains what happened, what changed, and what prevents recurrence.

## Report Templates

Three report files, written at specific points in the workflow (marked with ⏸ above). Use these templates exactly.

### Report 1: Job Report → `debug/job/<job_id>.md`

Write this after Step 1 (pinning the failing state). This is a factual record of what the job reported — no analysis. Contents:

```markdown
# Job Report: <job_id>

## Metadata
- **Job ID**: <job_id>
- **Status**: Failed
- **Kind**: <kind from job get>
- **User**: <user>
- **Created**: <timestamp>
- **Finished**: <timestamp>
- **Job Branch** (branch the job ran on): <job_branch>
- **Job Commit** (data state at time of failure): <job_commit or "not pinned — approximate">
- **Debug Branch** (Bauplan, created from job ref): <username.debug_xxx>

## Error
<Full error message from job logs, verbatim. Do not interpret — just paste.>
```

### Report 2: Data Report → `debug/data_snapshot/<table>.md` (one per table)

Write these during Step 3. One file per table from the three-layer scope. Contents:

```markdown
# Data Evidence: <namespace>.<table>

## Role in Failure
<One of: "input to failing model", "output of failing model", "one level downstream">

## Schema
<Paste output of bauplan table get>

## Row Count
<number>

## Sample (20 rows)
<Paste query output>

## Anomalies
<Specific findings tied to the failure. If none, say "No anomalies detected.">
```

### Report 3: Summary → `debug/summary.md`

Write this last, after the fix is applied and the rerun completes. This is the single document someone reads to understand what happened and what changed. Contents:

```markdown
# Self-Healing Summary

## Job
<job_id> — failed on <job_branch> at <timestamp>
Pinned ref: <job_branch>@<job_commit>
Bauplan debug branch: <debug_branch> (created from pinned ref)
Git debug branch: <git_branch or "unversioned">

## Failing Model
- **Model**: <name>
- **File**: <path>
- **Classification**: <planning/compilation, runtime, expectation, or logical correctness>

## What broke
<One sentence: what the error was>

## Why it broke
<One sentence: the root cause, based on evidence from data snapshots>

## What was fixed
<List each commit with one-line description>

## Determinism
<"Deterministic" or "Best-effort" — cite which conditions were met>

## Prevention
<Which expectations were added and what they guard against>

## Rerun result
<"Green" or "Failed — <reason>">
```

Do not produce any other files. The fix itself lives in Git commits to pipeline code (models, expectations). The reports live in `debug/`. That is the complete output.