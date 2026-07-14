---
name: bauplan-pipeline-pr
description: Open a git-for-data review PR for a freshly-built Bauplan pipeline, so a human reviews and merges instead of the agent publishing directly — and merging the PR publishes the data to `main`. Use after a pipeline has been built on an isolated Bauplan branch (e.g. by the marketing-agent flow) and you want to hand it to a data engineer for review. Bundles the `open_pipeline_pr.sh` helper and documents the two GitHub Actions workflows that make the gate work.
license: Apache-2.0
---

# Bauplan pipeline PR (the git-for-data gate)

Turns "a pipeline was built on an isolated Bauplan branch" into "there is a GitHub PR a
data engineer can review, and merging it publishes the data to production `main`." The
agent never publishes directly — a human approves by merging.

## The gate has three moving parts

1. **`open_pipeline_pr.sh`** (bundled in this folder) — the reference implementation that
   opens the PR. Deterministic git/GitHub plumbing so the agent never hand-rolls git.
2. **`.github/workflows/bauplan-ci.yml`** (lives in `.github/` — GitHub requires it there) —
   on the PR, re-runs the pipeline + quality gates and posts the review summary comment.
   Delegates the *content* of that summary to the **`bauplan-pr-summary`** skill.
3. **`.github/workflows/bauplan-publish.yml`** (also in `.github/`) — on **merge to `main`**,
   runs `bauplan branch merge` to publish the branch's tables to Bauplan `main`.

The two workflow files can't live in a skill folder (GitHub only runs workflows under
`.github/workflows/`), so this skill *documents and owns* them but references them by path.

## The flow

```
built pipeline on branch ──▶ open_pipeline_pr.sh ──▶ PR opened (never merged by the agent)
                                                        │
                          bauplan-ci.yml re-runs + posts summary (via bauplan-pr-summary)
                                                        │
                             human reviews + Merges ──▶ bauplan-publish.yml → bauplan branch merge → main
```

## The manifest — how the workflows know what to publish

`open_pipeline_pr.sh` writes a repo-root manifest `.bauplan/pr.env` into the PR. Both
workflows read it (skip cleanly if absent):

```
BAUPLAN_BRANCH=<the isolated data branch to publish>
PROJECT_DIR=<the pipeline project dir, e.g. conversion-pipeline>
RESULT_TABLE=<fully-qualified result table, e.g. bauplan.segment_conversion>
DASHBOARD_URL=<optional preview link>
```

Keep the manifest the single source of truth: never hardcode a branch or table name in the
workflows.

## Using the helper

```
.claude/skills/bauplan-pipeline-pr/open_pipeline_pr.sh <project_dir> <bauplan_branch> [result_table] [dashboard_url]
```

It: branches off `origin/main` in an **isolated git worktree** (never touches the working
tree), copies the built project in, writes the manifest, commits, pushes, builds the PR
body via the `bauplan-pr-summary` reference script, `gh pr create`s, prints `PR_URL=<url>`
on the last line, and cleans up the worktree. It **does not merge** — that is the reviewer's
action, and merging is what publishes.

## Requirements (one-time, per repo)

- The two workflows must be on `main` (so every PR inherits them and publish-on-merge fires).
- A `BAUPLAN_API_KEY` GitHub Actions **secret** (never commit it) — the headless runner uses
  it to run the pipeline and merge. Optionally protect `main` to require review before merge.

## Hard rules

- The helper **never merges** and never writes to Bauplan `main` — publishing happens only
  when a human merges the PR, via `bauplan-publish.yml`.
- Only the *generator* lives on `main` (this skill, `bauplan-pr-summary`, the workflows, the
  command). The pipeline project + `.bauplan/pr.env` are generated per request and arrive as
  the PR's diff.

## Reference implementation & keeping in sync

The maintained helper lives **next to this file**, at `open_pipeline_pr.sh` in this folder.
This skill is the source of truth: any change to the helper's behavior (new manifest key,
new step, new caller) MUST be reflected here in the same change. They live in the same folder
for exactly this reason. The only external caller is the `/marketing-agent` command, which
invokes the helper by its path above.
