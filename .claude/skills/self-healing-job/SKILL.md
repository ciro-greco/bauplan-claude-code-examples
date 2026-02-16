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
mkdir -p debug/{job,code_snapshot,data_snapshot}
```

### Step 1 — Pin the Failing State

**Goal:** Get the exact Bauplan commit hash for the failed run.

- If you have a **job id**: `get_job(job_id)` → extract `ref` and `logs` from the response.
- If you need to find the job: `list_jobs(status="FAIL")` → identify the matching job → `get_job(job_id)`.
- Map job to commit: `get_commits(ref=<branch>, limit=10)` → match by timestamp or job properties → extract `commit_hash`.
- Fall back to asking the user if neither approach yields a concrete hash.

End this step with either a **commit hash** or a clear statement that the data state cannot be pinned.

### Step 2 — Create Debug Branches

**Bauplan:** Branch from the pinned ref, not from `main`.
```
create_branch(branch="<username>.debug_<job_id_or_short_hash>", from_ref="<source_branch>@<commit_hash>")
```

**Git** (if available): Create `debug/bpln_<job_id_or_short_hash>`. If the working tree is dirty, commit a snapshot checkpoint first.

**Git unavailable:** Record in `debug/job/<job_id>.md`:
```
git_base_sha: unversioned
code_provenance: working directory snapshot, not pinned to any commit
```

### Step 3 — Collect Evidence

Do this **before any fixes**.

#### 3A — Identify which tables to inspect

Start from the **failing model** identified in the job logs. Then inspect exactly three layers:

1. **Inputs** — every table the failing model reads from (its `bauplan.Model(...)` references)
2. **Output** — the table the failing model produces (its function name or SQL filename)
3. **One level downstream** — any model that reads from the failing model's output

To find these, read the pipeline code (`models.py`, `.sql` files, `bauplan_project.yml`). If the DAG is unclear, `run_query("SELECT * FROM information_schema.tables", ref=<pinned_ref>)` to list available tables, then match against model definitions.

Do not inspect tables outside these three layers unless evidence points there.

#### 3B — Collect by category

**Query guardrails:** All sample queries must use `LIMIT 20`. All profiling queries (counts, stats) must use `LIMIT 1`. Never run unbounded queries.

| Evidence type | What to collect                                                                                                                                   | How                              |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------|
| **Code**      | Models (Python/SQL), expectations, decorators, `bauplan_project.yml`. Note whether code is pinned to a Git SHA or reflects current working state. | Read local files or job snapshot |
| **Logs**      | Full error message, failing model/step, runtime context (Python version, deps, limits). Summarize from API responses only — no speculation.       | `get_job(job_id)` → extract logs |
| **Data**      | For each table from 3A: schema, row count, sample (20 rows), targeted anomaly query, basic stats (min/max/nulls).                                 | See queries below                |

**Data evidence queries** (run against the pinned ref for each table identified in 3A):
```
Schema:    get_table(table=<name>, ref=<pinned_ref>)
Row count: run_query("SELECT COUNT(*) as n FROM <ns>.<table>", ref=<pinned_ref>)
Sample:    run_query("SELECT * FROM <ns>.<table> LIMIT 20", ref=<pinned_ref>)
Stats:     run_query("SELECT MIN(<col>), MAX(<col>), COUNT(*) - COUNT(<col>) as nulls FROM <ns>.<table>", ref=<pinned_ref>)
```

Save to:
- `debug/code_snapshot/` — code files + pinning statement
- `debug/data_snapshot/<table>.md` — one file per table
- `debug/job/<job_id>.md` — job metadata, commit hash, branch names

### Step 4 — Classify and Localize the Failure

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

Record in `debug/fix_log.md`: file changed, diff summary, reasoning.

Never amend or squash during debugging.

### Step 6 — Rerun

#### Determinism check

Before rerunning, assess what you can actually prove:

| Condition                      | Status |
|--------------------------------|--------|
| Data ref pinned to commit hash | ✅ or ❌ |
| Git SHA pinned for code        | ✅ or ❌ |

- **Both pinned** → rerun is **deterministic**. A green result proves the fix works against the exact failing state.
- **One or both unpinned** → rerun is **best-effort**. A green result is encouraging but not conclusive. State this explicitly in `debug/fix_log.md`.

#### Execute

Preferred: `project_run(project_dir=<dir>, ref=<debug_branch>)` with `--strict` flag.
Fallback: dry run first (`dry_run=True`), then full run.

After a green run, re-execute the queries from Step 3 that previously showed the failure. Record before vs. after evidence in `debug/fix_log.md`.

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

Create or update `expectations.py` in the project directory.

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
   `project_run(project_dir=<dir>, ref=<debug_branch>)` with `--strict`.
2. Verify expectations pass on the fixed state.
3. Confirm expectations **would have failed** on the broken state by reasoning about the evidence from Step 3 (e.g., "the type was string, our expectation asserts float64 → it would have caught it").
4. Commit the expectations file. Message: `"Add data quality guard for <root_cause> (job <job_id>)"`.

Record in `debug/fix_log.md`: which expectations were added, what they guard, and confirmation they cover the original failure mode.

## Output Checklist

At the end you must have produced:

- [ ] `debug/job/<job_id>.md` — job metadata, pinned commit hash, Git SHA (or "unversioned")
- [ ] `debug/code_snapshot/` — code at time of failure + pinning statement
- [ ] `debug/data_snapshot/` — data evidence from the pinned ref (one file per table from the three-layer scope)
- [ ] `debug/fix_log.md` — minimal fix history with before/after evidence and determinism assessment
- [ ] `expectations.py` — data quality expectations that prevent the specific failure from recurring
- [ ] Either a **successful rerun** on the debug branch (with expectations passing), or a **single concrete blocker** stated plainly