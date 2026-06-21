#!/bin/zsh
# Launchd entrypoint for the JMTY weekly workflow.
# It sets a predictable PATH, creates log directories, and delegates the real
# workflow to scripts/jmty_weekly_launchd.py.
set -eu

REPO_ROOT="/Users/deguchishouma/Desktop/jmty-workspace"
cd "$REPO_ROOT"

export PATH="/Users/deguchishouma/.nvm/versions/node/v22.17.1/bin:/opt/homebrew/bin:/usr/local/bin:/Users/deguchishouma/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1
export JMTY_GWS_KEYRING_BACKEND="${JMTY_GWS_KEYRING_BACKEND:-keyring}"
export JMTY_GWS_BIN="${JMTY_GWS_BIN:-/Users/deguchishouma/.nvm/versions/node/v22.17.1/bin/gws}"

mkdir -p "$REPO_ROOT/outputs/launchd"

exec /usr/bin/env python3 "$REPO_ROOT/scripts/jmty_weekly_launchd.py"
