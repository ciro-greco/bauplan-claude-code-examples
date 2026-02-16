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
2. **NEVER change code without Git** — every edit lives on a debug branch with a commit.
3. **NEVER query a moving ref** — always target `branch@commit_hash` or a tag.
4. **NEVER rerun before inspecting** — understand the failure, then act.
5. **NEVER clean up debug branches** unless the user explicitly asks.
6. **NEVER guess CLI flags.** Before running any `bauplan` CLI command, verify the exact flag names against the CLI reference doc in the project. If unsure about a flag, check first.
7. **NEVER create files outside `debug/` and the pipeline project directory.** No top-level documentation, no READMEs, no schema guides. Your outputs are: the `debug/` report files, and edits to existing pipeline code (models, expectations, project config). Nothing else.
8. **NEVER write Python scripts for diagnosis.** Steps 0–4 (evidence collection, classification, root cause analysis) use `bauplan` CLI commands exclusively. The only Python you write is pipeline code: model fixes in `models.py` and expectations in `expectations.py`.

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

### Step 0 — Safety Check and Directory Setup

**Bauplan:** Run `bauplan info`. If on `main`, create a debug branch first:
```bash
bauplan checkout --branch <username>.debug_<short_name>
```

**Git:** Verify `.git` exists and you are NOT on `main`. If no local Git repo is available, skip Git branching, note code provenance as "unversioned", and proceed with evidence collection. Fixes will go through `code_run` instead of local commits.

**Create output directories:**
```bash
mkdir -p debug/{job,data_snapshot}
```

### Step 1 — Pin the Failing State

**Goal:** Get the exact Bauplan commit hash for the failed run. Use CLI commands only — do not write scripts.

- If you have a **job id**:
  ```bash
  bauplan job get <job_id>
  bauplan job logs <job_id>
  ```
  Extract the `ref` (branch + commit hash) and the full error from the output.

- If you need to find the job:
  ```bash
  bauplan job ls --status fail --limit 10
  ```
  Identify the matching job, then `bauplan job get <job_id>`.

- Map job to commit:
  ```bash
  bauplan commit --ref <branch> --limit 10
  ```
  Match by timestamp or job properties → extract `commit_hash`.

- Fall back to asking the user if neither approach yields a concrete hash.

End this step with either a **commit hash** or a clear statement that the data state cannot be pinned.

### Step 2 — Create Debug Branches

**Bauplan:** Branch from the pinned ref, not from `main`.
```bash
bauplan branch create <username>.debug_<job_id_or_short_hash> --from-ref <source_branch>@<commit_hash>
bauplan checkout <username>.debug_<job_id_or_short_hash>
```

**Git** (if available): Create `debug/bpln_<job_id_or_short_hash>`. If the working tree is dirty, commit a snapshot checkpoint first.

**Git unavailable:** Note in `debug/job/<job_id>.md` that code provenance is unversioned.

### Step 3 — Collect Evidence

Do this **before any fixes**.

#### How to collect evidence

**Use the `bauplan` CLI for all information gathering.** Do not write Python scripts to explore data or collect evidence. Every piece of information you need — job metadata, logs, schemas, row counts, samples, stats — is available through `bauplan job get`, `bauplan job logs`, `bauplan table get`, and `bauplan query`. Run these commands directly in the terminal.

#### Code assumption

**Assume the code in the current repository is what ran at the time of failure.** Do not copy pipeline files into the debug directory. It is the user's responsibility to ensure they are on the correct Git commit before invoking this skill. If the user is unsure, they should check out the appropriate commit first.

Read the pipeline code in place (`models.py`, `.sql` files, `expectations.py`, `bauplan_project.yml`) to understand the DAG structure, model inputs/outputs, and declared expectations. Reference it in your reports by file path, not by copying it.

#### 3A — Identify which tables to inspect

Start from the **failing model** identified in the job logs. Then inspect exactly three layers:

1. **Inputs** — every table the failing model reads from (its `bauplan.Model(...)` references)
2. **Output** — the table the failing model produces (its function name or SQL filename)
3. **One level downstream** — any model that reads from the failing model's output

If the DAG is unclear from code:
```bash
bauplan table ls --ref <pinned_ref>
```
Then match against model definitions.

Do not inspect tables outside these three layers unless evidence points there.

#### 3B — Collect by category

**Query guardrails:** All sample queries must use `LIMIT 20`. All profiling queries (counts, stats) must use `LIMIT 1`. Never run unbounded queries.

| Evidence type | What to collect | How |
|---------------|----------------|-----|
| **Logs** | Full error message, failing model/step, runtime context (Python version, deps, limits). Summarize from logs only — no speculation. | `bauplan job get <job_id>` and `bauplan job logs <job_id>` |
| **Data** | For each table from 3A: schema, row count, sample (20 rows), targeted anomaly query, basic stats (min/max/nulls). | See queries below |

**Data evidence queries** (run against the pinned ref for each table identified in 3A):

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

### Step 4 — Classify and Localize the Failure

Continue using CLI commands only. Do not write Python scripts for diagnosis.

#### 4A — Classify

Based on evidence only, classify as one of:

- **Planning/compilation** — DAG or schema error before execution
- **Runtime** — crash, timeout, dependency issue during execution
- **Expectation** — data quality check failed
- **Logical correctness** — runs clean but produces wrong results

#### 4B — Trace the DAG before blaming the failing model

The model that errors is not necessarily the model with the bug. Before fixing the failing model's code, check its inputs:

1. Run the sample and stats queries from Step 3 on each **input table**.
2. If an input table has anomalies (unexpected nulls, wrong row count, schema drift), the root cause is likely **upstream**. Shift your investigation to that model.
3. Repeat upward until you find a model whose inputs are clean but whose output is broken. That is the model to fix.

If you cannot reproduce the failure with a query on the pinned ref, the failure is not localized. Stop and report.

### Step 5 — Apply a Minimal Fix

**Fix priority** — prefer fixes closest to the data contract boundary, because contract-level issues propagate furthest and are cheapest to verify:

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

| Condition | Status |
|-----------|--------|
| Data ref pinned to commit hash | ✅ or ❌ |
| Git SHA pinned for code | ✅ or ❌ |

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

| Root cause | What to guard | Where to place the expectation |
|------------|---------------|-------------------------------|
| Schema drift (type change, missing column) | Column types and presence on the **source table** | `expectations.py`, targeting the first model that reads the drifted table |
| Bad values (nulls, out-of-range, invalid) | Value constraints on the **source table** | `expectations.py`, targeting the model that reads the table |
| Logic error in a transform | Output invariants on the **producing model** | `expectations.py`, targeting the model's output table |

#### 7B — Write expectations

Create or update `expectations.py` in the pipeline project directory.

**Use built-in expectations when they fit.** These are available from `bauplan.standard_expectations`:

| Function | Use when |
|----------|----------|
| `expect_column_no_nulls(data, col)` | A column must never be null |
| `expect_column_all_unique(data, col)` | A column must have no duplicates (IDs, keys) |
| `expect_column_accepted_values(data, col, values)` | A column must only contain known values (enums, categories) |
| `expect_column_mean_greater_than(data, col, threshold)` | Numeric column's average must exceed a floor |
| `expect_column_mean_smaller_than(data, col, threshold)` | Numeric column's average must stay below a ceiling |

**Write a custom expectation when no built-in fits.** Common cases that require custom expectations:

- Column type validation (no built-in exists for this)
- Cross-column consistency checks
- Row count thresholds
- Schema completeness (expected columns are present)

Custom expectation template:
```python
import bauplan
import pyarrow as pa

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
import pyarrow as pa

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

## Required Reports (in this order)

After completing the workflow, produce exactly three report files in the `debug/` directory, in this order. Do not produce other files.

### Report 1: Job Report → `debug/job/<job_id>.md`

Write this after Step 1 (pinning the failing state). Contents:

```markdown
# Job Report: <job_id>

## Metadata
- **Job ID**: <job_id>
- **Status**: Failed
- **Kind**: <kind from job get>
- **User**: <user>
- **Created**: <timestamp>
- **Finished**: <timestamp>
- **Bauplan Branch**: <branch>
- **Pinned Data Ref**: <commit_hash or "not pinned">

## Error Summary
<Full error message from job logs, verbatim>

## Failing Model
- **Model name**: <name>
- **File**: <path to file>
- **Line**: <if available>

## Failure Classification
<One of: planning/compilation, runtime, expectation, logical correctness>

## Root Cause
<One-paragraph explanation based on evidence only. No speculation.>
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

Write this last, after the fix is applied and the rerun completes. 
This is the single document someone reads to understand what happened and what changed. 
Contents:

```markdown
# Self-Healing Summary

## Job
<job_id> — failed on <branch> at <timestamp>

## What broke
<One sentence: what the error was>

## Why it broke
<One sentence: the root cause>

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