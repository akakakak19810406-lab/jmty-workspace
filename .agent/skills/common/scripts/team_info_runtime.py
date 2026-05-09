#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from runtime_common import (
    build_python_runtime_image,
    clear_discord_git_webhook_url,
    clear_shared_discord_git_webhook_url,
    clear_worked_before,
    clear_owner_machine,
    configure_repo_git_hooks,
    detect_shared_root,
    ensure_remotion_venv,
    format_bytes_for_humans,
    get_discord_git_webhook_url,
    get_git_lfs_free_plan_status,
    get_python_runtime_image,
    get_python_runtime_mode,
    get_shared_discord_git_webhook_path,
    get_worked_before_path,
    has_worked_before,
    get_local_state_path,
    get_machine_fingerprint,
    get_repo_root,
    get_voicevox_base_url,
    is_owner_machine,
    is_voicevox_available,
    is_voicevox_container_running,
    mark_worked_before,
    pull_voicevox_engine_image,
    resolve_input_path,
    run_remotion_python,
    save_discord_git_webhook_url,
    save_shared_discord_git_webhook_url,
    save_owner_machine,
    save_repo_root,
    start_voicevox_engine_container,
    stop_voicevox_engine_container,
)


DISCORD_CONTENT_LIMIT = 2000
DISCORD_WEBHOOK_HOSTS = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
)
SIMPLIFY_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("プルリクエスト", "見てもらうページ"),
    ("pull request", "見てもらうページ"),
    ("Pull Request", "見てもらうページ"),
    ("リファクタリングしました", "書き方を整理しました"),
    ("リファクタリングした", "書き方を整理した"),
    ("リファクタリング", "書き方を整理した"),
    ("最適化しました", "むだを減らしました"),
    ("最適化した", "むだを減らした"),
    ("最適化", "むだを減らした"),
    ("改善しました", "もっとよくしました"),
    ("改善した", "もっとよくした"),
    ("改善", "もっとよくした"),
    ("追加しました", "足しました"),
    ("追加した", "足した"),
    ("追加", "足した"),
    ("修正しました", "直しました"),
    ("修正した", "直した"),
    ("修正", "直した"),
    ("更新しました", "新しくしました"),
    ("更新した", "新しくした"),
    ("更新", "新しくした"),
    ("作成しました", "作りました"),
    ("作成した", "作った"),
    ("作成", "作った"),
    ("対応しました", "できるようにしました"),
    ("対応した", "できるようにした"),
    ("対応", "できるようにした"),
)


def _copy_to_shared(source: Path, shared_root: Path, subpath: str | None) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"Source was not found: {source}")

    destination = shared_root / subpath if subpath else shared_root / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)

    return destination


def _format_shell_export(repo_root: Path, shell_name: str) -> str:
    repo_root_str = str(repo_root)
    if shell_name == "powershell":
        return f'$env:TEAM_INFO_ROOT = "{repo_root_str}"'
    if shell_name == "cmd":
        return f"set TEAM_INFO_ROOT={repo_root_str}"
    return f'export TEAM_INFO_ROOT="{repo_root_str}"'


def _print_git_lfs_free_plan_status(*, remote_name: str, remote_url: str | None, pre_push_lines: list[str] | None) -> int:
    try:
        status = get_git_lfs_free_plan_status(
            remote_name=remote_name,
            remote_url=remote_url,
            pre_push_lines=pre_push_lines,
        )
    except RuntimeError as exc:
        print(f"Git LFS 無料枠チェックに失敗しました: {exc}", file=sys.stderr)
        return 1

    target_remote = status.remote_url or status.remote_name
    print("Git LFS 無料枠チェック", file=sys.stderr)
    print(f"- リモート: {target_remote}", file=sys.stderr)
    print(
        f"- 無料枠: {format_bytes_for_humans(status.free_storage_bytes)}"
        f" / 予約分: {format_bytes_for_humans(status.reserved_bytes)}"
        f" / 利用可能: {format_bytes_for_humans(status.available_bytes)}",
        file=sys.stderr,
    )
    print(
        f"- 現在の推定総量: {format_bytes_for_humans(status.current_bytes)}"
        f" ({status.current_object_count} 個)",
        file=sys.stderr,
    )
    print(
        f"- 今回の push で増える見込み: {format_bytes_for_humans(status.incoming_bytes)}"
        f" ({status.incoming_object_count} 個)",
        file=sys.stderr,
    )
    print(
        f"- push 後の推定総量: {format_bytes_for_humans(status.projected_bytes)}"
        f" ({status.projected_object_count} 個)",
        file=sys.stderr,
    )

    if not status.has_lfs_content:
        print("- LFS ポインタは見つかりませんでした。", file=sys.stderr)
        return 0

    if status.warning:
        print(f"警告: {status.warning}", file=sys.stderr)

    if status.within_budget:
        print("結果: push 可能です。", file=sys.stderr)
        return 0

    print("結果: push を拒否しました。", file=sys.stderr)
    if status.rejection_reason:
        print(f"理由: {status.rejection_reason}", file=sys.stderr)
    print("対策:", file=sys.stderr)
    print("- LFS に入れる大きいファイルを減らす。", file=sys.stderr)
    print("- 既存の LFS 履歴を整理して容量を下げる。", file=sys.stderr)
    print("- 同じ GitHub アカウントで他の LFS を使うなら、予約分を設定する。", file=sys.stderr)
    print("- 有料枠を使わない方針なら、LFS 以外の置き場へ逃がす。", file=sys.stderr)
    return 1


def _mask_secret_url(url: str) -> str:
    if len(url) <= 24:
        return "***"
    return f"{url[:24]}...{url[-8:]}"


def _is_discord_webhook_url(url: str) -> bool:
    normalized = url.strip()
    return any(normalized.startswith(prefix) for prefix in DISCORD_WEBHOOK_HOSTS)


def _run_git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError("git command was not found.") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return completed.stdout.strip()


def _simplify_text(text: str) -> str:
    simplified = re.sub(r"\s+", " ", text.strip())
    if not simplified:
        return ""

    for source, target in SIMPLIFY_REPLACEMENTS:
        simplified = simplified.replace(source, target)

    simplified = simplified.rstrip("。.")
    if simplified:
        simplified += "。"
    return simplified


def _github_repo_url(remote_url: str | None) -> str | None:
    if not remote_url:
        return None

    normalized = remote_url.strip()
    repo_path: str | None = None

    if normalized.startswith("git@github.com:"):
        repo_path = normalized.split(":", 1)[1]
    elif normalized.startswith("ssh://git@github.com/"):
        repo_path = normalized.split("github.com/", 1)[1]
    elif normalized.startswith("https://github.com/"):
        repo_path = normalized.split("github.com/", 1)[1]
    elif normalized.startswith("http://github.com/"):
        repo_path = normalized.split("github.com/", 1)[1]

    if repo_path is None:
        return None

    cleaned = repo_path.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if "/" not in cleaned:
        return None
    return f"https://github.com/{cleaned}"


def _resolve_sha(repo_root: Path, ref: str) -> str:
    return _run_git(repo_root, "rev-parse", ref).strip()


def _short_sha(repo_root: Path, ref: str) -> str:
    return _run_git(repo_root, "rev-parse", "--short", ref).strip()


def _commit_shas(repo_root: Path, *, base_sha: str | None, head_sha: str) -> list[str]:
    resolved_head = _resolve_sha(repo_root, head_sha)

    if base_sha:
        resolved_base = _resolve_sha(repo_root, base_sha)
        output = _run_git(repo_root, "log", "--reverse", "--format=%H", f"{resolved_base}..{resolved_head}")
        commits = [line.strip() for line in output.splitlines() if line.strip()]
        if commits:
            return commits

    return [resolved_head]


def _commit_subject(repo_root: Path, sha: str) -> str:
    return _run_git(repo_root, "show", "-s", "--format=%s", sha).strip()


def _commit_author(repo_root: Path, sha: str) -> str:
    return _run_git(repo_root, "show", "-s", "--format=%an", sha).strip()


def _commit_body_lines(repo_root: Path, sha: str) -> list[str]:
    body = _run_git(repo_root, "show", "-s", "--format=%b", sha)
    lines: list[str] = []
    for raw_line in body.splitlines():
        stripped = raw_line.strip().lstrip("-").strip()
        if stripped:
            lines.append(stripped)
    return lines


def _changed_files(repo_root: Path, *, base_sha: str | None, head_sha: str) -> list[str]:
    if base_sha:
        resolved_base = _resolve_sha(repo_root, base_sha)
        resolved_head = _resolve_sha(repo_root, head_sha)
        output = _run_git(
            repo_root,
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            resolved_base,
            resolved_head,
        )
    else:
        output = _run_git(
            repo_root,
            "show",
            "--pretty=",
            "--name-only",
            "--diff-filter=ACMR",
            head_sha,
        )
    return [line.strip() for line in output.splitlines() if line.strip()]


def _current_branch(repo_root: Path) -> str:
    branch = _run_git(repo_root, "branch", "--show-current").strip()
    return branch or "detached-head"


def _detail_lines(repo_root: Path, commits: list[str]) -> list[str]:
    details: list[str] = []
    seen: set[str] = set()

    for sha in commits:
        for raw_line in _commit_body_lines(repo_root, sha):
            simplified = _simplify_text(raw_line)
            if not simplified or simplified in seen:
                continue
            seen.add(simplified)
            details.append(simplified)
            if len(details) >= 3:
                return details

    if details:
        return details

    for sha in commits:
        simplified = _simplify_text(_commit_subject(repo_root, sha))
        if not simplified or simplified in seen:
            continue
        seen.add(simplified)
        details.append(simplified)
        if len(details) >= 3:
            break
    return details


def _file_summary(files: list[str]) -> str | None:
    if not files:
        return None
    shown = ", ".join(f"`{path}`" for path in files[:4])
    if len(files) > 4:
        shown = f"{shown} ほか {len(files) - 4}こ"
    return f"いじったファイル: {shown}"


def _impact_lines(files: list[str], details: list[str]) -> list[str]:
    impacts: list[str] = []

    if details:
        summary = details[0].rstrip("。.")
        impacts.append(f"{summary}。これで、次から同じ流れをたどりやすくなったよ。")

    has_remotion_src = any(path.startswith("Remotion/my-video/src/") for path in files)
    has_text_layout = any(
        (
            "textLayout.ts" in path
            or "/Subtitle" in path
            or "/Hook" in path
            or "SleepTravelLong" in path
            or "CanvaSlideshow" in path
        )
        for path in files
    )
    has_docs = any(
        path.startswith(".agent/skills/") or path.startswith("setup/") or path.endswith("CLAUDE.md")
        for path in files
    )
    has_package = any(
        path.endswith("package.json") or path.endswith("package-lock.json")
        for path in files
    )

    if has_remotion_src and has_text_layout:
        impacts.append("字幕や見出しの見え方がそろって、今後の画面づくりでも同じルールを使いやすくなったよ。")
    elif has_remotion_src:
        impacts.append("画面の作り方がまとまって、あとから同じ場所を直しやすくなったよ。")

    if has_docs:
        impacts.append("案内の紙もそろったので、次から迷いにくくなったよ。")

    if has_package:
        impacts.append("必要な道具が入ったので、同じ動きを再現しやすくなったよ。")

    if not impacts:
        impacts.append("同じ場所を次からなおしやすくなったよ。")

    # 3行前後に収める
    deduped: list[str] = []
    seen: set[str] = set()
    for line in impacts:
        if line in seen:
            continue
        seen.add(line)
        deduped.append(line)
        if len(deduped) >= 3:
            break
    return deduped


def _clip_discord_content(text: str) -> str:
    if len(text) <= DISCORD_CONTENT_LIMIT:
        return text
    clipped = text[: DISCORD_CONTENT_LIMIT - 4].rstrip()
    return f"{clipped}..."


def _build_discord_git_report(
    *,
    repo_root: Path,
    event: str,
    base_sha: str | None,
    head_sha: str,
    branch: str | None,
    base_branch: str,
    pr_title: str | None,
    pr_url: str | None,
) -> str:
    commits = _commit_shas(repo_root, base_sha=base_sha, head_sha=head_sha)
    subjects = [_commit_subject(repo_root, sha) for sha in commits]
    latest_subject = pr_title.strip() if pr_title else subjects[-1]
    latest_subject = _simplify_text(latest_subject).rstrip("。")
    commit_count = len(commits)
    files = _changed_files(repo_root, base_sha=base_sha, head_sha=head_sha)
    details = _detail_lines(repo_root, commits)
    branch_name = branch or _current_branch(repo_root)
    author_name = _commit_author(repo_root, commits[-1])

    SHO_MENTION = "<@910139480546091039>"

    if event == "pr":
        event_icon = "🔀"
        event_label = f"**プルリクエスト** {SHO_MENTION}"
        title_line = f"「{latest_subject}」のプルリクエストを出したよ。"
    else:
        event_icon = "📤"
        event_label = "**プッシュ**"
        if commit_count == 1:
            title_line = f"「{latest_subject}」をプッシュしたよ。"
        else:
            title_line = f"「{latest_subject}」など {commit_count}こ をプッシュしたよ。"

    lines = [
        f"👤 **作業した人:** {author_name}",
        f"{event_icon} {event_label}",
        title_line,
        "",
        "📝 **何をしたか:**",
    ]

    if commit_count > 1:
        lines.append(f"・まとめて {commit_count}こ のコミットをプッシュしたよ。")

    for detail in details[:3]:
        lines.append(f"・{detail}")

    file_summary = _file_summary(files)
    if file_summary:
        lines.append(f"・{file_summary}")

    if event == "pr":
        lines.append(
            f"・`{branch_name}` から `{base_branch}` へプルリクエストを出したよ。"
        )
    else:
        lines.append(f"・プッシュしたブランチは `{branch_name}` です。")

    lines.extend(["", "✨ **何が変わったの？:**"])
    lines.extend(f"・{impact}" for impact in _impact_lines(files, details))

    repo_url = _github_repo_url(_run_git(repo_root, "remote", "get-url", "origin"))
    resolved_head = _resolve_sha(repo_root, head_sha)
    commit_url = f"{repo_url}/commit/{resolved_head}" if repo_url else None

    link_lines: list[str] = []
    if pr_url:
        link_lines.append(pr_url.strip())
    elif commit_url:
        link_lines.append(commit_url)

    if link_lines:
        lines.extend(["", "🔗 **見る場所:**"])
        lines.extend(link_lines)

    return _clip_discord_content("\n".join(lines))


def _post_discord_message(webhook_url: str, content: str) -> None:
    payload = json.dumps({"content": content, "username": "Git更新通知"}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "team-info-bot/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status not in {200, 204}:
                raise RuntimeError(
                    f"Discord webhook returned unexpected status: {response.status}"
                )
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Discord webhook call failed: {exc}") from exc


def main() -> int:
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Resolve cross-platform paths used by team-info skills."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("repo-root")
    repo_path_parser = subparsers.add_parser("repo-path")
    repo_path_parser.add_argument("relative_path")
    subparsers.add_parser("remotion-python")
    subparsers.add_parser("python-runtime-mode")
    subparsers.add_parser("build-remotion-python")
    subparsers.add_parser("pull-voicevox-engine")
    subparsers.add_parser("start-voicevox-engine")
    subparsers.add_parser("stop-voicevox-engine")
    subparsers.add_parser("voicevox-engine-status")
    subparsers.add_parser("shared-root")
    subparsers.add_parser("shared-jmty-root")
    subparsers.add_parser("local-state-path")
    subparsers.add_parser("worked-before-path")
    subparsers.add_parser("machine-id")
    subparsers.add_parser("owner-status")
    subparsers.add_parser("worked-before-status")
    subparsers.add_parser("mark-worked-before")
    subparsers.add_parser("clear-worked-before")
    subparsers.add_parser("mark-owner-machine")
    subparsers.add_parser("clear-owner-machine")
    subparsers.add_parser("discord-git-webhook-shared-path")
    subparsers.add_parser("discord-git-webhook-status")
    discord_webhook_set_parser = subparsers.add_parser("discord-git-webhook-set")
    discord_webhook_set_parser.add_argument("--url", required=True)
    discord_webhook_shared_set_parser = subparsers.add_parser("discord-git-webhook-shared-set")
    discord_webhook_shared_set_parser.add_argument("--url", required=True)
    subparsers.add_parser("discord-git-webhook-clear")
    subparsers.add_parser("discord-git-webhook-shared-clear")
    subparsers.add_parser("install-git-hooks")

    git_lfs_status_parser = subparsers.add_parser("git-lfs-free-plan-status")
    git_lfs_status_parser.add_argument("--remote-name", default="origin")
    git_lfs_status_parser.add_argument("--remote-url")

    git_lfs_guard_parser = subparsers.add_parser("git-lfs-pre-push-guard")
    git_lfs_guard_parser.add_argument("--remote-name", default="origin")
    git_lfs_guard_parser.add_argument("--remote-url")

    setup_parser = subparsers.add_parser("setup-local-machine")
    setup_parser.add_argument(
        "--repo-root",
        default=".",
        help="Path to the local team-info checkout. Default: current directory.",
    )
    setup_parser.add_argument(
        "--owner",
        action="store_true",
        help="Mark the current machine as the owner machine.",
    )
    setup_parser.add_argument(
        "--shell",
        choices=("sh", "powershell", "cmd"),
        default="sh",
        help="Shell format used when printing TEAM_INFO_ROOT export guidance.",
    )

    shell_export_parser = subparsers.add_parser("shell-export")
    shell_export_parser.add_argument(
        "--shell",
        choices=("sh", "powershell", "cmd"),
        default="sh",
        help="Shell format used when printing TEAM_INFO_ROOT export guidance.",
    )

    copy_parser = subparsers.add_parser("copy-to-shared")
    copy_parser.add_argument("source")
    copy_parser.add_argument("--subpath")
    copy_parser.add_argument("--shared-root")

    run_parser = subparsers.add_parser("run-remotion-python")
    run_parser.add_argument("run_args", nargs=argparse.REMAINDER)

    discord_report_parser = subparsers.add_parser("discord-git-report")
    discord_report_parser.add_argument("--event", choices=("push", "pr"), required=True)
    discord_report_parser.add_argument("--base-sha")
    discord_report_parser.add_argument("--head-sha", default="HEAD")
    discord_report_parser.add_argument("--branch")
    discord_report_parser.add_argument("--base-branch", default="main")
    discord_report_parser.add_argument("--pr-title")
    discord_report_parser.add_argument("--pr-url")
    discord_report_parser.add_argument("--webhook-url")
    discord_report_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "repo-root":
        print(get_repo_root())
        return 0

    if args.command == "repo-path":
        print(get_repo_root() / args.relative_path)
        return 0

    if args.command == "remotion-python":
        if get_python_runtime_mode() == "docker":
            print(f"docker://{get_python_runtime_image()}")
        else:
            print(ensure_remotion_venv())
        return 0

    if args.command == "python-runtime-mode":
        print(get_python_runtime_mode())
        return 0

    if args.command == "build-remotion-python":
        print(build_python_runtime_image())
        return 0

    if args.command == "pull-voicevox-engine":
        print(pull_voicevox_engine_image())
        return 0

    if args.command == "start-voicevox-engine":
        print(start_voicevox_engine_container())
        return 0

    if args.command == "stop-voicevox-engine":
        print(stop_voicevox_engine_container())
        return 0

    if args.command == "voicevox-engine-status":
        if is_voicevox_container_running() and is_voicevox_available():
            print(f"running {get_voicevox_base_url()}")
        elif is_voicevox_container_running():
            print("starting")
        else:
            print("stopped")
        return 0

    if args.command == "shared-root":
        shared_root = detect_shared_root()
        if shared_root is None:
            print(
                "Shared root could not be detected. "
                "Set TEAM_INFO_SHARED_ROOT to the synced team-info directory.",
                file=sys.stderr,
            )
            return 1
        print(shared_root)
        return 0

    if args.command == "shared-jmty-root":
        shared_root = detect_shared_root()
        if shared_root is None:
            print(
                "Shared root could not be detected. "
                "Set TEAM_INFO_SHARED_ROOT to the synced team-info directory.",
                file=sys.stderr,
            )
            return 1
        print(shared_root / "outputs" / "jmty")
        return 0

    if args.command == "local-state-path":
        print(get_local_state_path())
        return 0

    if args.command == "worked-before-path":
        print(get_worked_before_path())
        return 0

    if args.command == "machine-id":
        print(get_machine_fingerprint())
        return 0

    if args.command == "owner-status":
        print("owner" if is_owner_machine() else "other")
        return 0

    if args.command == "worked-before-status":
        print("known" if has_worked_before() else "new")
        return 0

    if args.command == "mark-worked-before":
        print(mark_worked_before())
        return 0

    if args.command == "clear-worked-before":
        removed = clear_worked_before()
        print("cleared" if removed else "not-found")
        return 0

    if args.command == "mark-owner-machine":
        print(save_owner_machine())
        return 0

    if args.command == "clear-owner-machine":
        clear_owner_machine()
        print("cleared")
        return 0

    if args.command == "discord-git-webhook-shared-path":
        print(get_shared_discord_git_webhook_path())
        return 0

    if args.command == "discord-git-webhook-status":
        webhook_url, source = get_discord_git_webhook_url()
        if webhook_url is None or source is None:
            print("not-configured")
            return 0
        print(f"configured:{source}:{_mask_secret_url(webhook_url)}")
        return 0

    if args.command == "discord-git-webhook-set":
        if not _is_discord_webhook_url(args.url):
            print("Discord webhook URL の形ではありません。", file=sys.stderr)
            return 1
        saved_path = save_discord_git_webhook_url(args.url)
        print(saved_path)
        return 0

    if args.command == "discord-git-webhook-shared-set":
        if not _is_discord_webhook_url(args.url):
            print("Discord webhook URL の形ではありません。", file=sys.stderr)
            return 1
        saved_path = save_shared_discord_git_webhook_url(args.url)
        print(saved_path)
        return 0

    if args.command == "discord-git-webhook-clear":
        cleared = clear_discord_git_webhook_url()
        print("cleared" if cleared else "not-found")
        return 0

    if args.command == "discord-git-webhook-shared-clear":
        cleared = clear_shared_discord_git_webhook_url()
        print("cleared" if cleared else "not-found")
        return 0

    if args.command == "install-git-hooks":
        try:
            print(configure_repo_git_hooks())
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.command == "git-lfs-free-plan-status":
        return _print_git_lfs_free_plan_status(
            remote_name=args.remote_name,
            remote_url=args.remote_url,
            pre_push_lines=None,
        )

    if args.command == "git-lfs-pre-push-guard":
        pre_push_lines = [line.rstrip("\n") for line in sys.stdin]
        return _print_git_lfs_free_plan_status(
            remote_name=args.remote_name,
            remote_url=args.remote_url,
            pre_push_lines=pre_push_lines,
        )

    if args.command == "setup-local-machine":
        repo_root = save_repo_root(args.repo_root)
        print(f"Saved repo root: {repo_root}")
        print(f"Local state: {get_local_state_path()}")
        print(f"Worked before file: {mark_worked_before()}")
        print(f"Git hooks: {configure_repo_git_hooks(repo_root)}")

        if args.owner:
            save_owner_machine()
            print("Owner machine: current machine was marked as owner")
        else:
            print("Owner machine: unchanged")

        print("Shell export:")
        print(_format_shell_export(repo_root, args.shell))
        return 0

    if args.command == "shell-export":
        print(_format_shell_export(get_repo_root(), args.shell))
        return 0

    if args.command == "copy-to-shared":
        shared_root: Path | None = (
            resolve_input_path(args.shared_root)
            if args.shared_root
            else detect_shared_root()
        )
        if shared_root is None:
            print(
                "Shared root could not be detected. "
                "Set TEAM_INFO_SHARED_ROOT or pass --shared-root.",
                file=sys.stderr,
            )
            return 1

        assert shared_root is not None  # 型チェッカー向けナローイング
        source = resolve_input_path(args.source)
        destination = _copy_to_shared(source, shared_root, args.subpath)
        print(destination)
        return 0

    if args.command == "run-remotion-python":
        run_args: list[str] = list(args.run_args)
        if run_args and run_args[0] == "--":
            run_args.pop(0)
        if not run_args:
            print("No command was provided to run-remotion-python.", file=sys.stderr)
            return 1

        try:
            completed = run_remotion_python(run_args)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return completed.returncode

    if args.command == "discord-git-report":
        repo_root = get_repo_root()
        branch = args.branch or _current_branch(repo_root)

        try:
            content = _build_discord_git_report(
                repo_root=repo_root,
                event=args.event,
                base_sha=args.base_sha,
                head_sha=args.head_sha,
                branch=branch,
                base_branch=args.base_branch,
                pr_title=args.pr_title,
                pr_url=args.pr_url,
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(content)

        if args.dry_run:
            return 0

        webhook_url = args.webhook_url
        if webhook_url is None:
            webhook_url, _ = get_discord_git_webhook_url()

        if not webhook_url:
            print("Discord webhook URL がまだ設定されていないため、送信はスキップしました。", file=sys.stderr)
            return 0

        if not _is_discord_webhook_url(webhook_url):
            print("Discord webhook URL の形ではありません。", file=sys.stderr)
            return 1

        try:
            _post_discord_message(webhook_url, content)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print("discord:sent", file=sys.stderr)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
