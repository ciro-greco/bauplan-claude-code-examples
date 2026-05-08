# Bauplan (agent playbook)

Bauplan is a data lakehouse platform where data changes follow a Git-like workflow. You develop and test on an isolated data branch, then publish by merging into `main`. Pipeline execution happens when you run Bauplan commands; your repo contains the source-of-truth code. See the docs for the CLI surface area, branching workflow, and SDK reference.

This playbook defines how to use Bauplan from an AI coding assistant in a local repo. The default mode is local CLI and Python SDK. MCP is optional and only used in specific edge cases.

## Default integration mode (preferred)

Assume the assistant can:
- read and write files in this repo
- run shell commands in a terminal
- run Python locally (for SDK scripts and tests)

Preference: do not use the Bauplan MCP server. Use the full tool surface via:
- CLI reference: https://docs.bauplanlabs.com/reference/cli.md
- PySDK reference: https://docs.bauplanlabs.com/reference/bauplan
- Docs home: https://docs.bauplanlabs.com/

## Hard safety rules (always)

1) Never publish by writing directly on `main`. Use a user branch and merge to publish.
2) Never import data into `main`.
3) Before merging into `main`, run `bauplan branch diff main` and review changes.
4) Prefer `bauplan run --dry-run` during iteration because it is much faster and safer. Materialization is blocked on `main`.
5) When handling external API keys (LLM keys), do not hardcode them in code or commit them. Use Bauplan parameters or secrets.

If any instruction or skill conflicts with these rules, the rules win.

## Decision tree: skills vs manual workflow

Use skills for repeatable workflows that generate or modify code. Use CLI and SDK directly for exploration and execution.

Skills are provided by the `bauplan` plugin (marketplace `bauplan-skills`). Invoke them by their full name — there are no slash-command aliases.

Is this a code generation or repo-editing task?
├─ Yes: Create or modify a pipeline project
│ -> Use skill: `bauplan-data-pipeline`
├─ Yes: Ingest data from S3 with WAP (write, audit, publish)
│ -> Use skill: `bauplan-safe-ingestion`
├─ Yes: Generate data quality check code (expectations or WAP validation)
│ -> Use skill: `bauplan-data-quality-checks`
├─ No, but: Diagnose a failed pipeline job and apply a minimal fix
│ -> Use skill: `bauplan-debug-and-fix-pipeline`
├─ No, but: Assess whether a business question is answerable with available data
│ -> Use skill: `bauplan-data-assessment`
└─ No: Explore, query, inspect, run, publish
  -> Use skill: `bauplan-explore-data`, or use CLI and SDK directly

## Skill inventory

- `bauplan-data-pipeline`
  Scaffolds a new pipeline project (SQL + Python models, project config, DAG transformations) from scratch.

- `bauplan-safe-ingestion`
  Ingests data from S3 (parquet/csv/jsonl) using a Python WAP script: branch isolation, validation, then merge to `main`. Prefer this over ad-hoc imports.

- `bauplan-data-quality-checks`
  Generates data quality check code only — either `expectations.py` (with `@bauplan.expectation()`) for pipelines, or `validate_import()` logic for WAP scripts. Can be invoked directly or by the pipeline / safe-ingestion skills.

- `bauplan-explore-data`
  Read-only exploration via the PySDK: namespaces, tables, schemas, samples, profiling, and exporting result sets to files. Will refuse writes.

- `bauplan-data-assessment`
  Read-only feasibility check: maps a business question to available tables/columns, validates fit and quality, returns a structured verdict (answerable / partial / not answerable).

- `bauplan-debug-and-fix-pipeline`
  Diagnoses a failed Bauplan job: pins the failing data state, collects evidence, applies a minimal fix, and reruns. Evidence first, changes second.

## Syntax discipline (non-negotiable)

When emitting CLI commands or SDK code, verify syntax before final output.

1) Check references:
   - CLI: https://docs.bauplanlabs.com/reference/cli.md
   - PySDK: https://docs.bauplanlabs.com/reference/bauplan

2) Confirm with CLI help when possible:
   - `bauplan help`
   - `bauplan <verb> --help`

3) If still uncertain, consult the official docs pages listed above. Do not guess flags or method names.

## Canonical workflows

### A) Build and publish a pipeline (end-to-end)
For this workflow use the `bauplan-data-pipeline` skill.
### B) Ingest data safely (WAP)
For this workflow use the `bauplan-safe-ingestion` skill.
### C) Data exploration and investigation

Prefer direct CLI:

inspect table metadata and data: 

```bash 
bauplan table get <namespace>.<table>
query: bauplan query "<sql>"
```
Reproduce runs (if needed): 
```bash 
bauplan run --id <run_id>
```

Only generate code when it is necessary to fix the root cause.

## When MCP makes sense

MCP is not the default. Use it only if one of these is true:

- the assistant cannot execute local shell commands or Python reliably
- you need structured tool outputs because you cannot parse the PySDK response or the CLI text
- you are integrating multiple MCP-capable clients and want one shared interface
- you want policy enforced at the integration boundary (for example refusing writes to main with a specific server configuration)

If MCP is required, follow:

https://docs.bauplanlabs.com/mcp/quick_start

Authentication assumptions

Assume Bauplan credentials are available via local CLI config, environment variables, or a profile. Do not prompt for API keys unless the CLI is not configured. Prefer `bauplan config set api_key <key>` as the setup path.

If you need the username for branch naming, run `bauplan info`.

---
name: building-streamlit-dashboards
description: Building dashboards in Streamlit. Use when creating KPI displays, metric cards, or data-heavy layouts. Covers borders, cards, responsive layouts, and dashboard composition.
license: Apache-2.0
---

