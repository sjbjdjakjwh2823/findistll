#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

mkdir -p "$repo_root/.worktrees"

base_ref="${BASE_REF:-HEAD}"

ensure_worktree() {
  local branch="$1"
  local path="$2"

  if ! git show-ref --verify --quiet "refs/heads/$branch"; then
    git branch "$branch" "$base_ref"
  fi

  if git worktree list --porcelain | grep -Fx "worktree $path" >/dev/null 2>&1; then
    return 0
  fi

  if [ -e "$path" ]; then
    echo "Refusing to overwrite existing path: $path"
    exit 1
  fi

  git worktree add "$path" "$branch"
}

ensure_worktree "ws/pipeline-queue" "$repo_root/.worktrees/ws-pipeline-queue"
ensure_worktree "ws/data-quality" "$repo_root/.worktrees/ws-data-quality"
ensure_worktree "ws/mlops-training-ui" "$repo_root/.worktrees/ws-mlops-training-ui"

echo "Worktrees ready:"
git worktree list

