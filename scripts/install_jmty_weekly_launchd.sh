#!/bin/zsh
# Installs the JMTY weekly LaunchAgent for the current macOS user.
# It copies the repository plist into ~/Library/LaunchAgents and registers it
# with launchctl for Sunday 23:55 local-time execution.
set -eu

LABEL="com.deguchishouma.jmty.weekly"
REPO_ROOT="/Users/deguchishouma/Desktop/jmty-workspace"
PLIST_SRC="$REPO_ROOT/launchd/${LABEL}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -f "$PLIST_SRC" ]]; then
  echo "plist not found: $PLIST_SRC" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$REPO_ROOT/outputs/launchd"

cp "$PLIST_SRC" "$PLIST_DST"
chmod 644 "$PLIST_DST"

launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST_DST"
launchctl enable "$DOMAIN/$LABEL"

echo "installed: $PLIST_DST"
launchctl print "$DOMAIN/$LABEL"
