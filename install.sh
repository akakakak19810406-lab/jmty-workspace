#!/usr/bin/env bash
# JMTY workspace の初回セットアップ入口です。
# Python がない端末でも Python 3 を用意し、
# その後 scripts/setup_jmty.py にセットアップ本体を渡します。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
  printf '[jmty-setup] %s\n' "$*"
}

die() {
  printf '[jmty-setup] ERROR: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

sudo_cmd() {
  if [ "${EUID:-$(id -u)}" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

python_ok() {
  "$1" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

find_python() {
  for candidate in python3 python; do
    if have "$candidate" && python_ok "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

load_brew_path() {
  if have brew; then
    return 0
  fi
  for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
    if [ -x "$brew_bin" ]; then
      eval "$("$brew_bin" shellenv)"
      return 0
    fi
  done
  return 1
}

install_homebrew_macos() {
  if load_brew_path; then
    return 0
  fi
  log "Homebrew が見つからないためインストールします。途中で macOS のパスワード入力が必要になる場合があります。"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  load_brew_path || die "Homebrew のインストール後に brew が見つかりませんでした。"
}

install_python_macos() {
  install_homebrew_macos
  log "Python 3 を Homebrew でインストールします。"
  brew install python
}

install_python_linux() {
  log "Python 3 を Linux の package manager でインストールします。"
  if have apt-get; then
    sudo_cmd apt-get update
    sudo_cmd apt-get install -y python3 python3-venv python3-pip curl git
  elif have dnf; then
    sudo_cmd dnf install -y python3 python3-pip curl git
  elif have yum; then
    sudo_cmd yum install -y python3 python3-pip curl git
  elif have pacman; then
    sudo_cmd pacman -Sy --noconfirm python python-pip curl git
  elif have apk; then
    sudo_cmd apk add python3 py3-pip curl git
  else
    die "対応している package manager が見つかりません。Python 3.10 以上を手動で入れてから再実行してください。"
  fi
}

PYTHON_BIN="$(find_python || true)"

if [ -z "$PYTHON_BIN" ]; then
  case "$(uname -s)" in
    Darwin) install_python_macos ;;
    Linux) install_python_linux ;;
    *) die "この install.sh は macOS / Linux 用です。Python 3.10 以上を入れて scripts/setup_jmty.py を実行してください。" ;;
  esac
  PYTHON_BIN="$(find_python || true)"
fi

[ -n "$PYTHON_BIN" ] || die "Python 3.10 以上が見つかりませんでした。"

log "Python: $("$PYTHON_BIN" --version 2>&1)"

# --- AI エージェント環境セットアップ（prompt-optimizer）---
SKILL_DIR="$HOME/.claude/skills/prompt-optimizer/scripts"
if [ -f "$SKILL_DIR/setup-eval.sh" ]; then
  log "AI エージェント環境をセットアップします"
  (cd "$ROOT_DIR" && bash "$SKILL_DIR/setup-eval.sh")
  (cd "$ROOT_DIR" && bash "$SKILL_DIR/select-vault.sh")
fi

exec "$PYTHON_BIN" "$ROOT_DIR/scripts/setup_jmty.py" "$@"
