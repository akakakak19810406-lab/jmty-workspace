#!/usr/bin/env python3
"""Manage team-info's per-machine Obsidian + agent bridge.

This script installs Claudian into an Obsidian vault and can also create the
personal claude-obsidian vault used by Codex, Claude Code, and similar agents.
Runtime knowledge lives under personal/<account>/ and stays out of shared git.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


CLAUDE_OBSIDIAN_REPO = "https://github.com/AgriciDaniel/claude-obsidian.git"
CLAUDIAN_RELEASE_API = "https://api.github.com/repos/YishenTu/claudian/releases/latest"
CLAUDIAN_ASSETS = ("main.js", "manifest.json", "styles.css")
DEFAULT_AGENT_TEMPLATES = {
    "note-summarizer.md": """---
name: NoteSummarizer
description: Read attached notes and summarize them in Japanese with short, structured output.
model: sonnet
tools: [Read, Grep, Glob, LS]
---
You are a note summarizer for an Obsidian vault.

When invoked:
1. Read the attached note or the note explicitly mentioned by the user.
2. Summarize in Japanese.
3. Keep the response concise and structured.

Default response format:
- 3-line summary
- Key points
- Open questions or next actions

Do not edit files unless the user explicitly asks you to do so.
If the note context is missing, say what you need.
""",
    "file-organizer.md": """---
name: FileOrganizer
description: Inspect notes or folders, propose a clean organization plan in Japanese, and execute only after explicit approval.
model: sonnet
tools: [Read, Grep, Glob, LS, Bash, Write, Edit, MultiEdit]
---
You organize notes and folders in an Obsidian vault.

When invoked:
1. Inspect the specified folder, tags, or notes.
2. Explain the current issues in Japanese.
3. Propose a reorganization plan before making changes.
4. Wait for explicit user approval before editing, renaming, or moving files.

When preparing the plan, include:
- Current structure problems
- Proposed folders or naming rules
- Exact edits, renames, or moves you want to perform

After approval, execute carefully and report the changes you made.
""",
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_command(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def repo_root_from_args(raw_repo_root: str | None) -> Path:
    if raw_repo_root:
        return Path(raw_repo_root).expanduser().resolve()
    env_root = os.environ.get("TEAM_INFO_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path.cwd().resolve()


def git_user_name(repo_root: Path) -> str:
    try:
        result = run_command(["git", "-C", str(repo_root), "config", "user.name"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.environ.get("USER", "local")
    return result.stdout.strip() or os.environ.get("USER", "local")


def account_slug_from_name(raw_name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u3040-\u30ff\u3400-\u9fff]+", "", raw_name.lower())
    return slug or "local"


def resolve_personal_account(repo_root: Path, account: str | None = None) -> str:
    if account:
        return account

    derived = account_slug_from_name(git_user_name(repo_root))
    personal_root = repo_root / "personal"
    derived_path = personal_root / derived
    if derived_path.exists():
        return derived

    if personal_root.exists():
        candidates = [path.name for path in personal_root.iterdir() if path.is_dir()]
        if len(candidates) == 1:
            return candidates[0]

    return derived


def default_personal_vault_path(repo_root: Path, account: str | None = None) -> Path:
    account_name = resolve_personal_account(repo_root, account)
    return repo_root / "personal" / account_name / "obsidian" / "claude-obsidian"


def write_team_info_bridge_note(vault_path: Path, repo_root: Path) -> Path:
    bridge_path = vault_path / "TEAM_INFO_BRIDGE.md"
    content = f"""# team-info AI bridge

This vault is the local personal knowledge base for team-info agents.

- team-info root: `{repo_root}`
- vault root: `{vault_path}`
- source inbox: `.raw/`
- generated wiki: `wiki/`
- recent context: `wiki/hot.md`

## Agent usage

For Claude Code, open this vault folder and use `/wiki`, `ingest [file]`,
`/save`, `lint the wiki`, and `/autoresearch [topic]`. Claude Code can use
this folder directly because it contains the claude-obsidian plugin metadata.

For Codex, open this vault folder and read `AGENTS.md` first. The same skills
live in `skills/`. If they are not auto-discovered, run this from team-info:

```bash
python "$TEAM_INFO_ROOT/.agent/skills/common/team-info-setup/obsidian-claudian/scripts/team_info_obsidian_claudian.py" bootstrap --setup-multi-agent
```

Keep runtime knowledge in this vault. Do not move machine-specific notes into
shared team-info folders unless the user explicitly asks to share them.
"""
    if bridge_path.exists() and bridge_path.read_text(encoding="utf-8") == content:
        return bridge_path
    bridge_path.write_text(content, encoding="utf-8")
    return bridge_path


def ensure_claude_obsidian_vault(
    repo_root: Path,
    vault_path: Path,
    run_setup: bool,
    update_existing: bool,
    setup_multi_agent: bool,
) -> dict:
    created = False
    updated = False
    if not vault_path.exists():
        vault_path.parent.mkdir(parents=True, exist_ok=True)
        run_command(["git", "clone", CLAUDE_OBSIDIAN_REPO, str(vault_path)], cwd=repo_root)
        created = True
    elif update_existing and (vault_path / ".git").exists():
        run_command(["git", "fetch", "origin"], cwd=vault_path)
        run_command(["git", "pull", "--ff-only"], cwd=vault_path)
        updated = True

    if run_setup:
        setup_script = vault_path / "bin" / "setup-vault.sh"
        if not setup_script.exists():
            raise RuntimeError(f"setup-vault.sh was not found: {setup_script}")
        run_command(["bash", str(setup_script), str(vault_path)], cwd=repo_root)

    multi_agent_output = ""
    if setup_multi_agent:
        multi_agent_script = vault_path / "bin" / "setup-multi-agent.sh"
        if not multi_agent_script.exists():
            raise RuntimeError(f"setup-multi-agent.sh was not found: {multi_agent_script}")
        result = run_command(["bash", str(multi_agent_script)], cwd=vault_path)
        multi_agent_output = result.stdout

    bridge_path = write_team_info_bridge_note(vault_path, repo_root)
    return {
        "repo_root": str(repo_root),
        "vault": str(vault_path),
        "created": created,
        "updated": updated,
        "setup_vault_ran": run_setup,
        "setup_multi_agent_ran": setup_multi_agent,
        "bridge_note": str(bridge_path),
        "multi_agent_output": multi_agent_output,
    }


def obsidian_json_path() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "obsidian" / "obsidian.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"
    xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg_config) / "obsidian" / "obsidian.json"


def obsidian_app_exists() -> bool:
    if shutil.which("obsidian"):
        return True

    if sys.platform == "darwin":
        return Path("/Applications/Obsidian.app").exists()

    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Programs" / "Obsidian" / "Obsidian.exe",
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Obsidian" / "Obsidian.exe",
        ]
        return any(candidate.exists() for candidate in candidates)

    return False


def find_active_vault() -> Path:
    config_path = obsidian_json_path()
    data = load_json(config_path, {})
    vaults = data.get("vaults", {})
    if not isinstance(vaults, dict):
        raise RuntimeError(f"Invalid Obsidian vault metadata: {config_path}")

    fallback = None
    for value in vaults.values():
        if not isinstance(value, dict):
            continue
        path = value.get("path")
        if isinstance(path, str) and path:
            candidate = Path(path).expanduser()
            if fallback is None:
                fallback = candidate
            if value.get("open"):
                return candidate

    if fallback is not None:
        return fallback
    raise RuntimeError(f"No Obsidian vault was found in {config_path}")


def obsidian_cli_enabled() -> bool:
    data = load_json(obsidian_json_path(), {})
    return isinstance(data, dict) and bool(data.get("cli"))


def enable_obsidian_cli() -> None:
    config_path = obsidian_json_path()
    data = load_json(config_path, {})
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid Obsidian config: {config_path}")
    if data.get("cli") is True:
        return
    data["cli"] = True
    save_json(config_path, data)


def normalize_media_folder(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    value = raw_value.strip()
    if value in {"", ".", "./", "/"}:
        return ""
    if value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def read_attachment_folder(vault_path: Path) -> str:
    app_json = vault_path / ".obsidian" / "app.json"
    data = load_json(app_json, {})
    attachment_folder = ""
    if isinstance(data, dict):
        attachment_folder = data.get("attachmentFolderPath", "")
    return normalize_media_folder(attachment_folder)


def fetch_latest_claudian_release() -> dict:
    request = urllib.request.Request(
        CLAUDIAN_RELEASE_API,
        headers={"User-Agent": "team-info-obsidian-claudian"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "team-info-obsidian-claudian"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def install_claudian_plugin(vault_path: Path) -> dict:
    release = fetch_latest_claudian_release()
    assets = {
        asset.get("name"): asset.get("browser_download_url")
        for asset in release.get("assets", [])
        if isinstance(asset, dict)
    }

    missing_assets = [name for name in CLAUDIAN_ASSETS if not assets.get(name)]
    if missing_assets:
        joined = ", ".join(missing_assets)
        raise RuntimeError(f"Claudian release assets are incomplete: {joined}")

    plugin_dir = vault_path / ".obsidian" / "plugins" / "claudian"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    for asset_name in CLAUDIAN_ASSETS:
        download_file(assets[asset_name], plugin_dir / asset_name)

    return {
        "plugin_dir": str(plugin_dir),
        "version": release.get("tag_name", ""),
    }


def enable_claudian_plugin(vault_path: Path) -> None:
    plugins_path = vault_path / ".obsidian" / "community-plugins.json"
    plugins = load_json(plugins_path, [])
    if not isinstance(plugins, list):
        plugins = []

    normalized = [item for item in plugins if isinstance(item, str)]
    if "claudian" not in normalized:
        normalized.append("claudian")
    save_json(plugins_path, normalized)


def update_claudian_settings(
    vault_path: Path,
    user_name: str | None,
    locale: str,
    permission_mode: str,
) -> Path:
    settings_path = vault_path / ".claude" / "claudian-settings.json"
    settings = load_json(settings_path, {})
    if not isinstance(settings, dict):
        settings = {}

    claude_cli_path = shutil.which("claude") or ""
    hostname = platform.node() or os.uname().nodename or "local"
    cli_paths = settings.get("claudeCliPathsByHost", {})
    if not isinstance(cli_paths, dict):
        cli_paths = {}
    if claude_cli_path:
        cli_paths[hostname] = claude_cli_path

    settings["locale"] = locale
    settings["permissionMode"] = permission_mode
    settings["loadUserClaudeSettings"] = True
    settings["mediaFolder"] = read_attachment_folder(vault_path)
    settings["claudeCliPathsByHost"] = cli_paths

    if user_name is not None:
        settings["userName"] = user_name

    save_json(settings_path, settings)
    return settings_path


def seed_default_agents(vault_path: Path) -> list[str]:
    agents_dir = vault_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    for file_name, content in DEFAULT_AGENT_TEMPLATES.items():
        destination = agents_dir / file_name
        if destination.exists():
            continue
        destination.write_text(content, encoding="utf-8")
        created.append(file_name)
    return created


def existing_default_agents(vault_path: Path) -> list[str]:
    agents_dir = vault_path / ".claude" / "agents"
    found: list[str] = []
    for file_name in DEFAULT_AGENT_TEMPLATES:
        if (agents_dir / file_name).exists():
            found.append(file_name)
    return found


def read_plugin_manifest(vault_path: Path) -> dict | None:
    manifest_path = vault_path / ".obsidian" / "plugins" / "claudian" / "manifest.json"
    if not manifest_path.exists():
        return None
    data = load_json(manifest_path, {})
    if isinstance(data, dict):
        return data
    return None


def build_doctor_status(vault_path: Path | None) -> dict:
    status = {
        "obsidian_app_exists": obsidian_app_exists(),
        "obsidian_cli_path": shutil.which("obsidian") or "",
        "obsidian_cli_enabled": obsidian_cli_enabled(),
        "claude_cli_path": shutil.which("claude") or "",
        "active_vault": str(vault_path) if vault_path else "",
    }

    if vault_path is None:
        return status

    settings_path = vault_path / ".claude" / "claudian-settings.json"
    manifest = read_plugin_manifest(vault_path)
    status.update(
        {
            "vault_attachment_folder": read_attachment_folder(vault_path),
            "claudian_plugin_installed": manifest is not None,
            "claudian_plugin_version": manifest.get("version", "") if manifest else "",
            "claudian_settings_exists": settings_path.exists(),
            "default_agents": existing_default_agents(vault_path),
        }
    )
    return status


def command_doctor(args: argparse.Namespace) -> int:
    vault_path = Path(args.vault).expanduser() if args.vault else None
    if vault_path is None:
        try:
            vault_path = find_active_vault()
        except RuntimeError:
            vault_path = None

    status = build_doctor_status(vault_path)
    json.dump(status, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def command_install(args: argparse.Namespace) -> int:
    enable_obsidian_cli()
    if args.vault:
        vault_path = Path(args.vault).expanduser()
    else:
        try:
            vault_path = find_active_vault()
        except RuntimeError:
            if args.skip_if_no_vault:
                summary = {
                    "skipped": "no_active_vault",
                    "obsidian_cli_path": shutil.which("obsidian") or "",
                    "obsidian_cli_enabled": obsidian_cli_enabled(),
                    "claude_cli_path": shutil.which("claude") or "",
                }
                json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
                return 0
            raise

    if not vault_path.exists():
        if args.skip_if_no_vault:
            summary = {
                "skipped": f"vault_not_found:{vault_path}",
                "obsidian_cli_path": shutil.which("obsidian") or "",
                "obsidian_cli_enabled": obsidian_cli_enabled(),
                "claude_cli_path": shutil.which("claude") or "",
            }
            json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0
        raise RuntimeError(f"Vault does not exist: {vault_path}")

    install_result = install_claudian_plugin(vault_path)
    enable_claudian_plugin(vault_path)
    settings_path = update_claudian_settings(
        vault_path=vault_path,
        user_name=args.user_name,
        locale=args.locale,
        permission_mode=args.permission_mode,
    )
    created_agents = seed_default_agents(vault_path)

    summary = {
        "vault": str(vault_path),
        "plugin_dir": install_result["plugin_dir"],
        "claudian_version": install_result["version"],
        "settings_path": str(settings_path),
        "created_default_agents": created_agents,
        "obsidian_cli_path": shutil.which("obsidian") or "",
        "obsidian_cli_enabled": obsidian_cli_enabled(),
        "claude_cli_path": shutil.which("claude") or "",
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def command_vault_path(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_args(args.repo_root)
    vault_path = Path(args.vault).expanduser().resolve() if args.vault else default_personal_vault_path(repo_root, args.account)
    summary = {
        "repo_root": str(repo_root),
        "account": resolve_personal_account(repo_root, args.account),
        "vault": str(vault_path),
        "exists": vault_path.exists(),
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def command_ensure_vault(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_args(args.repo_root)
    vault_path = Path(args.vault).expanduser().resolve() if args.vault else default_personal_vault_path(repo_root, args.account)
    summary = ensure_claude_obsidian_vault(
        repo_root=repo_root,
        vault_path=vault_path,
        run_setup=not args.no_setup,
        update_existing=args.update,
        setup_multi_agent=args.setup_multi_agent,
    )
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def codex_skill_link_status(vault_path: Path) -> dict:
    target = vault_path / "skills"
    destination = Path.home() / ".codex" / "skills" / "claude-obsidian"
    status = {
        "destination": str(destination),
        "target": str(target),
        "exists": destination.exists() or destination.is_symlink(),
        "is_symlink": destination.is_symlink(),
        "points_to_target": False,
    }
    if destination.is_symlink():
        try:
            status["points_to_target"] = destination.resolve() == target.resolve()
        except FileNotFoundError:
            status["points_to_target"] = False
    return status


def claude_code_vault_status(vault_path: Path) -> dict:
    return {
        "vault": str(vault_path),
        "agent_instructions": str(vault_path / "AGENTS.md"),
        "claude_instructions": str(vault_path / "CLAUDE.md"),
        "plugin_manifest": str(vault_path / ".claude-plugin" / "plugin.json"),
        "skills_dir": str(vault_path / "skills"),
        "agent_instructions_exists": (vault_path / "AGENTS.md").exists(),
        "claude_instructions_exists": (vault_path / "CLAUDE.md").exists(),
        "plugin_manifest_exists": (vault_path / ".claude-plugin" / "plugin.json").exists(),
        "skills_dir_exists": (vault_path / "skills").is_dir(),
    }


def command_bootstrap(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_args(args.repo_root)
    account = resolve_personal_account(repo_root, args.account)
    vault_path = Path(args.vault).expanduser().resolve() if args.vault else default_personal_vault_path(repo_root, account)

    if not obsidian_app_exists():
        summary = {
            "skipped": "obsidian_not_installed",
            "repo_root": str(repo_root),
            "account": account,
            "vault": str(vault_path),
            "message": "Obsidian is not installed on this machine, so no personal knowledge vault was created.",
        }
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    summary = {
        "repo_root": str(repo_root),
        "account": account,
        "vault": str(vault_path),
        "obsidian_app_exists": True,
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        summary.update(
            {
                "would_create_or_update_vault": True,
                "would_run_setup_vault": not args.no_setup,
                "would_setup_multi_agent": args.setup_multi_agent,
                "codex_skill_link": codex_skill_link_status(vault_path),
                "claude_code": claude_code_vault_status(vault_path),
            }
        )
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    vault_summary = ensure_claude_obsidian_vault(
        repo_root=repo_root,
        vault_path=vault_path,
        run_setup=not args.no_setup,
        update_existing=args.update,
        setup_multi_agent=args.setup_multi_agent,
    )
    summary.update(vault_summary)
    summary["codex_skill_link"] = codex_skill_link_status(vault_path)
    summary["claude_code"] = claude_code_vault_status(vault_path)

    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="team-info helper for Obsidian CLI + Claudian")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="inspect Obsidian / Claudian status")
    doctor_parser.add_argument("--vault", help="override vault path")
    doctor_parser.set_defaults(func=command_doctor)

    vault_path_parser = subparsers.add_parser("vault-path", help="print the default personal claude-obsidian vault path")
    vault_path_parser.add_argument("--repo-root", help="override TEAM_INFO_ROOT")
    vault_path_parser.add_argument("--account", help="override personal account slug")
    vault_path_parser.add_argument("--vault", help="override vault path")
    vault_path_parser.set_defaults(func=command_vault_path)

    ensure_parser = subparsers.add_parser("ensure-vault", help="create or refresh the default personal claude-obsidian vault")
    ensure_parser.add_argument("--repo-root", help="override TEAM_INFO_ROOT")
    ensure_parser.add_argument("--account", help="override personal account slug")
    ensure_parser.add_argument("--vault", help="override vault path")
    ensure_parser.add_argument("--no-setup", action="store_true", help="skip bin/setup-vault.sh")
    ensure_parser.add_argument("--update", action="store_true", help="git fetch + pull --ff-only when the vault already exists")
    ensure_parser.add_argument(
        "--setup-multi-agent",
        action="store_true",
        help="run bin/setup-multi-agent.sh to link skills into Codex/Gemini/OpenCode config folders",
    )
    ensure_parser.set_defaults(func=command_ensure_vault)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="set up the personal claude-obsidian vault only when Obsidian is installed",
    )
    bootstrap_parser.add_argument("--repo-root", help="override TEAM_INFO_ROOT")
    bootstrap_parser.add_argument("--account", help="override personal account slug")
    bootstrap_parser.add_argument("--vault", help="override vault path")
    bootstrap_parser.add_argument("--no-setup", action="store_true", help="skip bin/setup-vault.sh")
    bootstrap_parser.add_argument("--update", action="store_true", help="git fetch + pull --ff-only when the vault already exists")
    bootstrap_parser.add_argument(
        "--setup-multi-agent",
        action="store_true",
        help="run bin/setup-multi-agent.sh to link skills into Codex/Gemini/OpenCode config folders",
    )
    bootstrap_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be configured without cloning, writing, or linking",
    )
    bootstrap_parser.set_defaults(func=command_bootstrap)

    install_parser = subparsers.add_parser("install", help="install Claudian into the active vault")
    install_parser.add_argument("--vault", help="override vault path")
    install_parser.add_argument("--user-name", default=os.environ.get("USER", ""), help="Claudian userName")
    install_parser.add_argument("--locale", default="ja", help="Claudian locale")
    install_parser.add_argument(
        "--permission-mode",
        choices=("normal", "plan", "yolo"),
        default="normal",
        help="initial Claudian permission mode",
    )
    install_parser.add_argument(
        "--skip-if-no-vault",
        action="store_true",
        help="exit successfully when no active vault exists yet",
    )
    install_parser.set_defaults(func=command_install)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except urllib.error.URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
