#!/usr/bin/env bash
#
# Open a GitHub PR for a freshly-built Bauplan pipeline so a data engineer can review it.
#
# Deterministic git/GitHub work, invoked by /marketing-agent after it builds the pipeline:
#   - branches off origin/main in an isolated worktree (never disturbs the working tree)
#   - copies the built project + writes the manifest the CI/publish workflows read
#   - commits, pushes, and opens a PR whose body has the data summary + dashboard link
#   - prints "PR_URL=<url>" on the last line so the caller can grab it
#
# It does NOT merge. Merging the PR is what publishes the data (via bauplan-publish.yml).
#
# Usage:
#   .claude/skills/bauplan-pipeline-pr/open_pipeline_pr.sh <project_dir> <bauplan_branch> [result_table] [dashboard_url]
set -euo pipefail

PROJECT_DIR="${1:?project dir required (e.g. conversion-pipeline)}"
BAUPLAN_BRANCH="${2:?bauplan data branch required}"
RESULT_TABLE="${3:-bauplan.segment_conversion}"
DASHBOARD_URL="${4:-http://localhost:8899}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

[ -d "$PROJECT_DIR" ] || { echo "ERROR: project dir '$PROJECT_DIR' not found" >&2; exit 1; }

PY="$REPO_ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

STAMP="$(date +%Y%m%d-%H%M%S)"
GIT_BRANCH="pipeline/${PROJECT_DIR//\//-}-${STAMP}"
WT="$(mktemp -d)/pr-tree"

echo "Fetching origin/main..."
git fetch --quiet origin main

echo "Creating isolated worktree off origin/main..."
git worktree add --quiet -b "$GIT_BRANCH" "$WT" origin/main
cleanup() { git worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Mirror the built project into the worktree (drop caches).
mkdir -p "$WT/$PROJECT_DIR"
rsync -a --delete --exclude '__pycache__' "$REPO_ROOT/$PROJECT_DIR/" "$WT/$PROJECT_DIR/"

# Write the manifest the workflows read.
mkdir -p "$WT/.bauplan"
cat > "$WT/.bauplan/pr.env" <<EOF
BAUPLAN_BRANCH=$BAUPLAN_BRANCH
PROJECT_DIR=$PROJECT_DIR
RESULT_TABLE=$RESULT_TABLE
DASHBOARD_URL=$DASHBOARD_URL
EOF

git -C "$WT" add "$PROJECT_DIR" .bauplan/pr.env
git -C "$WT" commit --quiet -m "Pipeline: ${PROJECT_DIR} on ${BAUPLAN_BRANCH}

Auto-opened by /marketing-agent. Merging this PR publishes the resulting tables to Bauplan main.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"

git -C "$WT" push --quiet -u origin "$GIT_BRANCH"

# Build the PR body from the principled summary (CI re-posts a fresh copy as a comment).
BODY_FILE="$(mktemp)"
{
  echo "## Auto-generated pipeline for review"
  echo
  echo "Built by \`/marketing-agent\` on Bauplan branch \`$BAUPLAN_BRANCH\` — **nothing is on Bauplan \`main\` yet.**"
  echo
  if ! "$PY" "$REPO_ROOT/.claude/skills/bauplan-pr-summary/pr_summary.py" "$BAUPLAN_BRANCH" "$RESULT_TABLE" "$DASHBOARD_URL" 2>/dev/null; then
    echo "_(full summary will be posted by CI once checks run)_"
  fi
  echo
  echo "### How to publish"
  echo "Review the publish impact + the green check, then **Approve & Merge**. Merging runs \`bauplan branch merge\` to publish the tables above to \`main\`."
  echo
  echo "🤖 Auto-opened by /marketing-agent"
} > "$BODY_FILE"

PR_URL="$(gh pr create --base main --head "$GIT_BRANCH" \
  --title "Pipeline: ${PROJECT_DIR} on ${BAUPLAN_BRANCH}" \
  --body-file "$BODY_FILE")"

echo "PR_URL=$PR_URL"
