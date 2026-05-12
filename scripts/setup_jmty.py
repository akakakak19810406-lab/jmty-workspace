#!/usr/bin/env python3
# JMTY workspace を新しい端末で使える状態にするセットアップ本体です。
# Homebrew / OS package manager で必要な CLI をそろえ、
# 最後に `jmty` コマンドでローカル GUI を起動できるように登録します。

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_BIN = Path.home() / ".local" / "bin"


class SetupError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[jmty-setup] {message}", flush=True)


def warn(message: str) -> None:
    print(f"[jmty-setup] WARN: {message}", flush=True)


def have(command: str) -> bool:
    return shutil.which(command) is not None


def command_path(command: str) -> str:
    return shutil.which(command) or ""


def run(
    args: list[str],
    *,
    check: bool = True,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(args)
    if dry_run:
        log(f"dry-run: {printable}")
        return subprocess.CompletedProcess(args, 0, "", "")
    log(printable)
    completed = subprocess.run(
        args,
        cwd=str(cwd or ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and completed.returncode != 0:
        raise SetupError(f"command failed ({completed.returncode}): {printable}")
    return completed


def capture(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def is_macos() -> bool:
    return platform.system() == "Darwin"


def is_linux() -> bool:
    return platform.system() == "Linux"


def with_local_bin(env: dict[str, str] | None = None) -> dict[str, str]:
    next_env = dict(env or os.environ)
    path = next_env.get("PATH", "")
    local_bin = str(LOCAL_BIN)
    if local_bin not in path.split(os.pathsep):
        next_env["PATH"] = f"{local_bin}{os.pathsep}{path}" if path else local_bin
    return next_env


def sudo_prefix() -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    if have("sudo"):
        return ["sudo"]
    return []


def brew_bin() -> str:
    found = shutil.which("brew")
    if found:
        return found
    for candidate in (
        "/opt/homebrew/bin/brew",
        "/usr/local/bin/brew",
        "/home/linuxbrew/.linuxbrew/bin/brew",
    ):
        if Path(candidate).exists():
            return candidate
    return ""


def ensure_homebrew(args: argparse.Namespace) -> str:
    found = brew_bin()
    if found:
        log(f"Homebrew: {found}")
        return found
    if not is_macos():
        raise SetupError("Homebrew が見つかりません。Linux では OS package manager と既存 brew のみ対応します。")
    if args.skip_brew:
        raise SetupError("Homebrew が見つかりません。--skip-brew が指定されています。")
    log("Homebrew をインストールします。macOS のパスワード入力が必要になる場合があります。")
    run(
        ["/bin/bash", "-c", "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"],
        dry_run=args.dry_run,
    )
    found = brew_bin()
    if not found and not args.dry_run:
        raise SetupError("Homebrew をインストールしましたが brew が見つかりません。新しいターミナルで再実行してください。")
    return found or "brew"


def brew_installed(brew: str, name: str, *, cask: bool = False) -> bool:
    subcommand = "--cask" if cask else "--formula"
    return capture([brew, "list", subcommand, name]).returncode == 0


def brew_install(args: argparse.Namespace, names: list[str], *, cask: bool = False) -> None:
    if not names:
        return
    brew = ensure_homebrew(args)
    missing = [name for name in names if not brew_installed(brew, name, cask=cask)]
    if not missing:
        log(("Homebrew cask" if cask else "Homebrew formula") + " はインストール済みです。")
        return
    command = [brew, "install"]
    if cask:
        command.append("--cask")
    command.extend(missing)
    run(command, dry_run=args.dry_run)


def linux_install_packages(args: argparse.Namespace, packages: list[str]) -> None:
    if not packages:
        return
    sudo = sudo_prefix()
    if have("apt-get"):
        run([*sudo, "apt-get", "update"], dry_run=args.dry_run)
        run([*sudo, "apt-get", "install", "-y", *packages], dry_run=args.dry_run)
    elif have("dnf"):
        run([*sudo, "dnf", "install", "-y", *packages], dry_run=args.dry_run)
    elif have("yum"):
        run([*sudo, "yum", "install", "-y", *packages], dry_run=args.dry_run)
    elif have("pacman"):
        run([*sudo, "pacman", "-Sy", "--noconfirm", *packages], dry_run=args.dry_run)
    elif have("apk"):
        run([*sudo, "apk", "add", *packages], dry_run=args.dry_run)
    else:
        warn("Linux package manager が見つからないため OS package の自動インストールをスキップします。")


def ensure_os_tools(args: argparse.Namespace) -> None:
    if is_macos():
        if not args.skip_brew:
            ensure_homebrew(args)
        brew_install(args, ["git", "python", "node", "googleworkspace-cli", "tesseract", "tesseract-lang"])
        return

    if is_linux():
        if have("apt-get"):
            packages = ["python3", "python3-pip", "git", "curl", "nodejs", "npm", "tesseract-ocr", "tesseract-ocr-jpn"]
        elif have("dnf") or have("yum"):
            packages = ["python3", "python3-pip", "git", "curl", "nodejs", "npm", "tesseract", "tesseract-langpack-jpn"]
        elif have("pacman"):
            packages = ["python", "python-pip", "git", "curl", "nodejs", "npm", "tesseract", "tesseract-data-jpn"]
        else:
            packages = ["python3", "python3-pip", "git", "curl", "nodejs", "npm", "tesseract-ocr"]
        linux_install_packages(args, packages)
        if not have("gws") and brew_bin():
            brew_install(args, ["googleworkspace-cli"])
        elif not have("gws"):
            warn("googleworkspace-cli(gws) は Linux package manager からは自動導入していません。Homebrew for Linux を入れて再実行してください。")
        return

    warn(f"{platform.system()} は自動インストール対象外です。既存コマンドの確認だけ行います。")


def ensure_npm_user_prefix(args: argparse.Namespace) -> None:
    if not have("npm"):
        warn("npm が見つからないため Codex CLI の npm インストールをスキップします。")
        return
    if args.dry_run:
        log(f"dry-run: npm config set prefix {Path.home() / '.local'}")
        return
    prefix = capture(["npm", "config", "get", "prefix"]).stdout.strip()
    if prefix and os.access(prefix, os.W_OK):
        return
    LOCAL_BIN.parent.mkdir(parents=True, exist_ok=True)
    run(["npm", "config", "set", "prefix", str(LOCAL_BIN.parent)], dry_run=args.dry_run)


def ensure_codex(args: argparse.Namespace) -> None:
    if args.skip_codex:
        return
    if have("codex"):
        log(f"Codex CLI: {command_path('codex')}")
        return

    if is_macos() and brew_bin():
        completed = run([brew_bin(), "install", "--cask", "codex"], check=False, dry_run=args.dry_run)
        if args.dry_run or completed.returncode == 0 or have("codex"):
            return
        warn("Homebrew cask で Codex CLI を入れられなかったため npm を試します。")

    ensure_npm_user_prefix(args)
    if have("npm") or args.dry_run:
        run(["npm", "install", "-g", "@openai/codex"], dry_run=args.dry_run, env=with_local_bin())


def gws_env() -> dict[str, str]:
    env = with_local_bin()
    env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", "keyring")
    env.setdefault("JMTY_GWS_KEYRING_BACKEND", "keyring")
    return env


def gws_status() -> dict[str, object]:
    if not have("gws"):
        return {}
    completed = capture(["gws", "auth", "status"], env=gws_env())
    if completed.returncode != 0:
        return {"error": completed.stderr.strip() or completed.stdout.strip()}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"raw": completed.stdout.strip()}


def ensure_gws_auth(args: argparse.Namespace) -> None:
    if args.skip_gws_auth:
        log("gws 認証は --skip-gws-auth によりスキップしました。")
        return
    if not have("gws"):
        warn("gws が見つからないため Google 認証を開始できません。")
        return

    status = gws_status()
    if status.get("auth_method") and status.get("auth_method") != "none":
        log("gws 認証は完了済みです。")
        return

    if not status.get("client_config_exists") and not (
        os.environ.get("GOOGLE_WORKSPACE_CLI_CLIENT_ID") and os.environ.get("GOOGLE_WORKSPACE_CLI_CLIENT_SECRET")
    ):
        warn("gws の OAuth client 設定がありません。`gws auth setup` を実行します。Google Cloud のログインが必要です。")
        run(["gws", "auth", "setup"], dry_run=args.dry_run, env=gws_env())

    log("gws auth login --full を開始します。ブラウザで Google ログインを完了してください。")
    run(["gws", "auth", "login", "--full"], dry_run=args.dry_run, env=gws_env())


def setup_workspace(args: argparse.Namespace) -> None:
    runtime = ROOT / ".agent" / "skills" / "common" / "scripts" / "jmty_runtime.py"
    sync_commands = ROOT / "scripts" / "sync_cross_cli_commands.py"
    register_aliases = ROOT / ".agent" / "skills" / "common" / "scripts" / "register_aliases.py"

    for directory in (
        ROOT / "outputs" / "jmty-gui",
        ROOT / "outputs" / "jmty-gui" / "generation_requests",
        ROOT / "outputs" / "jmty-weekly" / "current",
        ROOT / "inputs" / "jmty_image_prompt_templates" / "_previews",
    ):
        if args.dry_run:
            log(f"dry-run: mkdir -p {directory}")
        else:
            directory.mkdir(parents=True, exist_ok=True)

    run([sys.executable, str(runtime), "setup-local-machine", "--repo-root", str(ROOT)], dry_run=args.dry_run)
    run([sys.executable, str(sync_commands)], dry_run=args.dry_run)
    run([sys.executable, str(register_aliases), "--root", str(ROOT)], dry_run=args.dry_run)


def verify(args: argparse.Namespace) -> None:
    checks = [
        ("git", ["git", "--version"]),
        ("python", [sys.executable, "--version"]),
        ("node", ["node", "--version"]),
        ("npm", ["npm", "--version"]),
        ("gws", ["gws", "--help"]),
        ("tesseract", ["tesseract", "--version"]),
        ("codex", ["codex", "--version"]),
    ]
    failures: list[str] = []
    env = gws_env()
    for name, command in checks:
        if not have(command[0]) and command[0] != sys.executable:
            failures.append(name)
            warn(f"{name}: not found")
            continue
        completed = capture(command, env=env)
        if completed.returncode != 0:
            failures.append(name)
            warn(f"{name}: check failed")
        else:
            first_line = (completed.stdout or completed.stderr).splitlines()[0:1]
            log(f"{name}: {first_line[0] if first_line else 'ok'}")

    completed = capture([sys.executable, str(ROOT / "scripts" / "jmty_gui.py"), "--help"], env=with_local_bin())
    if completed.returncode != 0:
        failures.append("jmty_gui")
        warn("jmty_gui.py --help failed")
    else:
        log("jmty_gui.py: ok")

    if have("tesseract"):
        langs = capture(["tesseract", "--list-langs"])
        if langs.returncode == 0 and "jpn" not in langs.stdout.split():
            warn("tesseract の日本語データ jpn が見つかりません。画像OCR検証の精度が落ちます。")

    if failures:
        warn("未完了の項目: " + ", ".join(failures))


def print_next_steps(args: argparse.Namespace) -> None:
    log("セットアップ処理が完了しました。")
    print()
    print("次のどちらかで起動できます:")
    print("  jmty")
    print(f"  python3 \"{ROOT / 'scripts' / 'jmty_gui.py'}\" --open")
    print()
    print("`jmty` が今のターミナルで見つからない場合:")
    print("  新しいターミナルを開く")
    print("  または source ~/.config/jmty/env.sh")
    print()
    if not args.skip_gws_auth:
        print("Google Sheets / Drive を使うには、ブラウザで gws の Google ログインを完了しておいてください。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and configure JMTY local GUI dependencies.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without changing the machine.")
    parser.add_argument("--skip-brew", action="store_true", help="Do not install Homebrew automatically.")
    parser.add_argument("--skip-codex", action="store_true", help="Do not install Codex CLI.")
    parser.add_argument("--skip-gws-auth", action="store_true", help="Install gws but do not start Google login.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip final command checks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log(f"repo: {ROOT}")
    try:
        ensure_os_tools(args)
        ensure_codex(args)
        setup_workspace(args)
        ensure_gws_auth(args)
        if not args.skip_verify:
            verify(args)
        print_next_steps(args)
        return 0
    except SetupError as exc:
        print(f"[jmty-setup] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
