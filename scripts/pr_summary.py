"""
Build a principled Markdown review summary for a Bauplan pipeline PR.

The summary is DERIVED from Bauplan's own introspection APIs — not hand-assembled — so it
faithfully reflects what happened and, crucially, everything merging will write to `main`:

  Section            Source of truth
  -----------------  ----------------------------------------------------------------
  Publish impact     `bauplan branch diff main <branch>` + `get_table` (rows/cols/size)
  Pipeline           `get_job_context` (DAG + lineage) + `get_job` (status/timing)
  Data quality       run job (strict COMPLETE) + expectation names from the run snapshot
  Provenance         `get_commits(branch)` (ops since the branch forked from main)
  Result preview     query the result table

We deliberately DO NOT reproduce the pipeline code — it is already in the PR diff.

Usage (args or env vars):
    python scripts/pr_summary.py <branch> [result_table] [dashboard_url]
    env: BAUPLAN_BRANCH, RESULT_TABLE, DASHBOARD_URL, RUN_JOB_ID (optional; else discovered)
"""

import os
import re
import subprocess
import sys
from decimal import Decimal

import bauplan

BASE = "main"
_SYM = {"+": "➕ new", "-": "➖ dropped", "~": "✏️ modified"}
_KIND = {"+": "added", "-": "dropped", "~": "modified"}


# --------------------------------------------------------------------------- helpers
def _fmt(v):
    if isinstance(v, Decimal):
        v = int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _human_size(n):
    if not isinstance(n, (int, float)):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _duration(job):
    start = getattr(job, "started_at", None) or getattr(job, "created_at", None)
    end = getattr(job, "finished_at", None)
    if start and end:
        secs = (end - start).total_seconds()
        return f"{secs:.1f}s"
    return "?"


# --------------------------------------------------------------------------- data pulls
def diff_changes(branch):
    """Authoritative (kind, symbol, fqn) list of what merging `branch` applies to `main`."""
    proc = subprocess.run(
        ["bauplan", "branch", "diff", BASE, branch], capture_output=True, text=True
    )
    out = []
    for line in f"{proc.stdout}\n{proc.stderr}".splitlines():
        m = re.match(r"^\s*([+\-~])\s*TABLE\s+(\S+)", line)
        if m:
            out.append((_KIND.get(m.group(1), "changed"), _SYM.get(m.group(1), m.group(1)), m.group(2)))
    return out


def table_meta(client, fqn, ref):
    """(records, num_cols, size_bytes) for a table on a ref, or (None, None, None)."""
    try:
        t = client.get_table(table=fqn, ref=ref)
        return getattr(t, "records", None), len(getattr(t, "fields", []) or []), getattr(t, "size", None)
    except Exception:
        return None, None, None


def find_run_job(client, branch, explicit_id=None):
    """Return (job, context) for the run that produced this branch, or (None, None)."""
    if explicit_id:
        try:
            return client.get_job(explicit_id), client.get_job_context(explicit_id, include_snapshot=True)
        except Exception:
            return None, None
    try:
        runs = [j for j in client.get_jobs(limit=100) if getattr(j.kind, "name", "") == "RUN"]
    except Exception:
        return None, None
    runs.sort(key=lambda j: getattr(j, "created_at", None) or 0, reverse=True)
    for j in runs[:30]:
        try:
            ctx = client.get_job_context(j.id, include_snapshot=True)
        except Exception:
            continue
        if getattr(ctx, "ref", None) == branch:
            return j, ctx
    return None, None


def branch_provenance(client, branch, base=BASE):
    """Commits unique to `branch` (its ops since it forked from `base`), newest first."""
    try:
        base_hashes = {c.ref.hash for c in client.get_commits(ref=base, limit=200)}
    except Exception:
        base_hashes = set()
    prov = []
    try:
        for c in client.get_commits(ref=branch, limit=50):
            if getattr(c.ref, "hash", None) in base_hashes:
                break
            prov.append(c)
    except Exception:
        pass
    return prov


def run_job_id_from_provenance(prov):
    """The run job id is embedded in the branch's 'Run job_id=...' commit — the reliable link."""
    for c in prov:
        subj = getattr(c, "subject", "") or ""
        if subj.startswith("Run"):
            m = re.search(r"job_id=(\S+)", subj)
            if m:
                return m.group(1)
    return None


def expectation_names(ctx):
    """Names of @bauplan.expectation functions from the run snapshot (metadata, not code)."""
    snap = getattr(ctx, "snapshot_dict", None) or {}
    src = snap.get("expectations.py", "")
    names = re.findall(r"@bauplan\.expectation\([^)]*\)\s*(?:@[^\n]*\n\s*)*def\s+(\w+)", src)
    return names


def md_rows(rows):
    if not rows:
        return "_(no rows)_"
    cols = list(rows[0].keys())
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(_fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- render
def main():
    branch = os.environ.get("BAUPLAN_BRANCH") or (sys.argv[1] if len(sys.argv) > 1 else None)
    result_table = os.environ.get("RESULT_TABLE") or (sys.argv[2] if len(sys.argv) > 2 else None)
    dashboard = os.environ.get("DASHBOARD_URL") or (sys.argv[3] if len(sys.argv) > 3 else None)
    run_job_id = os.environ.get("RUN_JOB_ID")
    if not branch:
        sys.exit("usage: pr_summary.py <branch> [result_table] [dashboard_url]")

    client = bauplan.Client()
    changes = diff_changes(branch)
    prov = branch_provenance(client, branch)
    run_id = run_job_id or run_job_id_from_provenance(prov)
    job, ctx = find_run_job(client, branch, run_id)
    node_names = {n.name for n in getattr(ctx, "dag_nodes", [])} if ctx else set()

    def role(kind, fqn):
        name = fqn.split(".")[-1]
        if kind == "added" and (name in node_names or fqn == result_table):
            return "pipeline output"
        if kind == "added":
            return "imported source"
        return kind

    # 1) Publish impact ----------------------------------------------------------------
    print(f"## ⚠️ Merging publishes {len(changes)} change(s) to Bauplan `{BASE}`")
    print()
    if not changes:
        print("_No table changes vs `main`._")
    else:
        print("| Table | Change | Rows | Cols | Size | Role |")
        print("|---|---|--:|--:|--:|---|")
        for kind, sym, fqn in changes:
            ref = BASE if kind == "dropped" else branch
            recs, cols, size = table_meta(client, fqn, ref)
            print(f"| `{fqn}` | {sym} | {_fmt(recs) if recs is not None else '?'} | "
                  f"{cols if cols is not None else '?'} | {_human_size(size)} | {role(kind, fqn)} |")

    # 2) Pipeline (DAG + lineage + status + timing; NO code) ----------------------------
    print()
    print("### 🧬 Pipeline")
    if job and ctx:
        status = getattr(job, "human_readable_status", None) or getattr(job, "status", "?")
        print(f"- **Run** `{job.id}` — {status} in {_duration(job)} on `{branch}`")
        edges = getattr(ctx, "dag_edges", []) or []
        names = {n.id: n.name for n in getattr(ctx, "dag_nodes", [])}
        # keep only real model->model edges (root edges have source_model=None)
        model_edges = [(e.source_model, e.destination_model) for e in edges
                       if e.source_model in names and e.destination_model in names]
        if model_edges:
            chain = "  \n".join(f"  `{names[s]}` → `{names[d]}`" for s, d in model_edges)
            print(f"- **DAG** ({len(names)} models):  \n{chain}")
        elif names:
            print(f"- **Models:** {', '.join(f'`{n}`' for n in names.values())}")
        outs = [f"`{fqn}`" for k, _, fqn in changes if role(k, fqn) == "pipeline output"]
        srcs = [f"`{fqn}`" for k, _, fqn in changes if role(k, fqn) == "imported source"]
        if srcs:
            print(f"- **Lineage — imported sources:** {', '.join(srcs)}")
        if outs:
            print(f"- **Lineage — materialized outputs:** {', '.join(outs)}")
    else:
        print("_Run job not found via introspection; see the pipeline code in this PR's diff._")

    # 3) Data quality ------------------------------------------------------------------
    print()
    print("### ✅ Data quality")
    names = expectation_names(ctx) if ctx else []
    if names:
        hrs = (getattr(job, "human_readable_status", "") or "") if job else ""
        verdict = "**all passed** ✅" if hrs.lower().startswith("complet") else f"run status: {hrs or '?'}"
        print(f"{len(names)} expectation(s), {verdict} (strict run — a failure would have blocked the run):")
        print(", ".join(f"`{n}`" for n in names))
    else:
        print("_No expectations found in the run snapshot._")

    # 4) Provenance --------------------------------------------------------------------
    if prov:
        print()
        print("### 🧭 Provenance (how this branch was built)")
        for c in reversed(prov):  # oldest first
            when = c.authored_date.strftime("%Y-%m-%d %H:%M") if getattr(c, "authored_date", None) else ""
            who = getattr(getattr(c, "author", None), "name", "")
            subj = re.sub(r"\s*job_id=\S+", "", getattr(c, "subject", "") or "")
            print(f"- {when} — {subj} _({who})_")

    # 5) Result preview ----------------------------------------------------------------
    if result_table:
        print()
        print(f"### 📊 Result — `{result_table}`")
        try:
            rows = client.query(f"SELECT * FROM {result_table}", ref=branch).to_pylist()
            print(f"Data branch `{branch}` · {len(rows)} rows")
            print()
            print(md_rows(rows))
        except Exception as exc:
            print(f"_(could not read {result_table}: {exc})_")

    if dashboard:
        print()
        print(f"📊 Dashboard preview: [{dashboard}]({dashboard})")


if __name__ == "__main__":
    main()
