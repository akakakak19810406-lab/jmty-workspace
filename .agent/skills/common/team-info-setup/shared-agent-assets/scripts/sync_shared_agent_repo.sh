#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${TEAM_INFO_ROOT:-$(cd "$script_dir/../../../../.." && pwd)}"
repo_parent="$(cd "$repo_root/.." && pwd)"

resolve_shared_repo_path() {
  if [ -n "${1:-}" ]; then
    printf '%s\n' "$1"
    return
  fi

  if [ -n "${TEAM_INFO_SHARED_AGENT_ASSETS_ROOT:-}" ]; then
    printf '%s\n' "$TEAM_INFO_SHARED_AGENT_ASSETS_ROOT"
    return
  fi

  for candidate in \
    "$repo_parent/shared-agent-assets" \
    "$repo_parent/shared-rules-repo"
  do
    if [ -d "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
}

shared_repo_path="$(resolve_shared_repo_path "${1:-}")"

if [ -z "$shared_repo_path" ]; then
  echo "⚠ shared agent repo path is not configured"
  exit 0
fi

if [ ! -d "$shared_repo_path/.git" ]; then
  echo "⚠ shared agent repo not found"
  exit 0
fi

if ! git -C "$shared_repo_path" rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "⚠ shared agent repo has no commits yet"
  exit 0
fi

if ! git -C "$shared_repo_path" diff --quiet || ! git -C "$shared_repo_path" diff --cached --quiet; then
  echo "⚠ shared agent repo has local changes"
  exit 0
fi

if ! git -C "$shared_repo_path" fetch --quiet >/dev/null 2>&1; then
  echo "⚠ shared agent repo fetch failed"
  exit 0
fi

local_head="$(git -C "$shared_repo_path" rev-parse HEAD)"
upstream_head="$(git -C "$shared_repo_path" rev-parse @{u} 2>/dev/null || true)"

if [ -z "$upstream_head" ]; then
  echo "⚠ shared agent repo upstream is not configured"
  exit 0
fi

if [ "$local_head" = "$upstream_head" ]; then
  echo "✓ shared agent assets are up to date"
  exit 0
fi

if git -C "$shared_repo_path" pull --ff-only --quiet >/dev/null 2>&1; then
  echo "✓ shared agent assets updated"
  exit 0
fi

echo "⚠ shared agent repo pull failed"
exit 0
