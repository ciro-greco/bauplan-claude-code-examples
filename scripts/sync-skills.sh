#!/usr/bin/env bash
# Fetches the latest Bauplan skills from the upstream GitHub repo.
# Source: https://github.com/BauplanLabs/bauplan-mcp-server/tree/main/skills
#
# Uses gh CLI (authenticated) to avoid GitHub API rate limits.
# Requires: gh (GitHub CLI), jq.

set -euo pipefail

REPO="BauplanLabs/bauplan-mcp-server"
BRANCH="main"
SRC_PATH="skills"
DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/.claude/skills"

echo "[sync-skills] Fetching latest skills from $REPO/$SRC_PATH ..."

# Use gh CLI for authenticated API access
TREE_JSON=$(gh api "repos/${REPO}/git/trees/${BRANCH}?recursive=1" 2>/dev/null) || {
  echo "[sync-skills] WARNING: Could not reach GitHub API. Skipping skill sync." >&2
  exit 0
}

# Filter to only files under skills/
FILES=$(echo "$TREE_JSON" | jq -r \
  --arg prefix "$SRC_PATH/" \
  '.tree[] | select(.type == "blob" and (.path | startswith($prefix))) | .path')

if [ -z "$FILES" ]; then
  echo "[sync-skills] No skill files found. Skipping." >&2
  exit 0
fi

# Clean existing skills (except hidden files like .DS_Store)
find "$DEST_DIR" -mindepth 1 -not -name '.*' -delete 2>/dev/null || true
mkdir -p "$DEST_DIR"

COUNT=0
for FILE_PATH in $FILES; do
  REL_PATH="${FILE_PATH#${SRC_PATH}/}"
  TARGET="$DEST_DIR/$REL_PATH"

  mkdir -p "$(dirname "$TARGET")"

  # Download raw file content via gh api
  gh api "repos/${REPO}/contents/${FILE_PATH}?ref=${BRANCH}" \
    --jq '.content' 2>/dev/null \
    | base64 -d > "$TARGET" || {
    echo "[sync-skills] WARNING: Failed to download $FILE_PATH" >&2
    continue
  }
  COUNT=$((COUNT + 1))
done

echo "[sync-skills] Synced $COUNT files into $DEST_DIR"
