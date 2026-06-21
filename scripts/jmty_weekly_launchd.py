#!/usr/bin/env python3
# Runs the JMTY weekly bulk workflow from launchd without starting the GUI server.
# It reuses the GUI worker functions, checks Google Workspace auth before syncing,
# and posts failure/auth-recovery notices to the JMTY Discord webhook.
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import jmty_gui


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "outputs/jmty-weekly/current"
DEFAULT_TEMPLATES_DIR = ROOT / "inputs/jmty_image_prompt_templates"
DEFAULT_LOG_DIR = ROOT / "outputs/launchd"
DEFAULT_LOCK_FILE = DEFAULT_LOG_DIR / "jmty-weekly.lock"
DISCORD_ENV = "JMTY_DISCORD_JMTY_WEBHOOK_URL"
LEGACY_DISCORD_ENV = "TEAM_INFO_DISCORD_JMTY_WEBHOOK_URL"
DISCORD_CONFIG = ROOT / "config/discord-jmty-webhook.json"
TERMINAL_STATUSES = {"done", "failed", "cancelled"}
DISCORD_CONTENT_LIMIT = 1900


class LaunchdWeeklyError(RuntimeError):
    pass


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def redact_secrets(text: str) -> str:
    return re.sub(
        r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
        "https://discord.com/api/webhooks/REDACTED",
        str(text or ""),
    )


def clip(text: str, limit: int = DISCORD_CONTENT_LIMIT) -> str:
    text = redact_secrets(text)
    if len(text) <= limit:
        return text
    return text[: limit - 4].rstrip() + " ..."


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def load_webhook_url() -> tuple[str | None, str | None]:
    value = os.environ.get(DISCORD_ENV)
    if value and value.strip():
        return value.strip(), "env"

    legacy = os.environ.get(LEGACY_DISCORD_ENV)
    if legacy and legacy.strip():
        os.environ[DISCORD_ENV] = legacy.strip()
        return legacy.strip(), "legacy-env"

    loaded = load_json(DISCORD_CONFIG, {})
    if isinstance(loaded, dict):
        url = str(loaded.get(DISCORD_ENV) or loaded.get("url") or "").strip()
        if url:
            os.environ[DISCORD_ENV] = url
            return url, "config-json"
    return None, None


def send_discord(content: str, *, disabled: bool = False) -> bool:
    if disabled:
        return False
    webhook_url, source = load_webhook_url()
    if not webhook_url:
        print("[discord] JMTY webhook is not configured; skipped notification", file=sys.stderr)
        return False
    payload = json.dumps(
        {"content": clip(content), "username": "JMTY週次自動化"},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "jmty-weekly-launchd/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status not in {200, 204}:
                print(f"[discord] failed: status={response.status}", file=sys.stderr)
                return False
    except urllib.error.URLError as exc:
        print(f"[discord] failed: {exc}", file=sys.stderr)
        return False
    print(f"[discord] sent via {source}", file=sys.stderr)
    return True


@contextmanager
def single_run_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LaunchdWeeklyError(f"別のJMTY週次自動化が実行中です: {path}") from exc
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()} {now_text()}\n".encode("utf-8"))
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def parse_display_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def persisted_running_jobs(max_age_hours: int) -> list[dict[str, Any]]:
    payload = load_json(jmty_gui.JOBS_STATE_PATH, {})
    jobs = payload.get("jobs") if isinstance(payload, dict) else []
    if not isinstance(jobs, list):
        return []
    now = datetime.now()
    recent: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict) or job.get("status") != "running":
            continue
        started = parse_display_time(str(job.get("started_at") or ""))
        if started is None:
            recent.append(job)
            continue
        if started.tzinfo is not None:
            age_seconds = (datetime.now(started.tzinfo) - started).total_seconds()
        else:
            age_seconds = (now - started).total_seconds()
        if age_seconds < max_age_hours * 3600:
            recent.append(job)
    return recent


def job_snapshot(job_id: str) -> dict[str, Any]:
    with jmty_gui.jobs_lock:
        job = jmty_gui.jobs.get(job_id)
        return jmty_gui.job_to_dict(job) if job else {}


def wait_for_job(job_id: str, *, poll_seconds: float) -> dict[str, Any]:
    last_line = ""
    while True:
        snapshot = job_snapshot(job_id)
        if not snapshot:
            raise LaunchdWeeklyError(f"実行ログが見つかりません: {job_id}")
        line = (
            f"[{now_text()}] {snapshot.get('command')} "
            f"{snapshot.get('status')} {snapshot.get('progress')}% "
            f"{snapshot.get('phase') or ''}"
        )
        if line != last_line:
            print(line, flush=True)
            last_line = line
        if snapshot.get("status") in TERMINAL_STATUSES:
            return snapshot
        time.sleep(max(1.0, poll_seconds))


def job_tail(snapshot: dict[str, Any]) -> str:
    stdout = str(snapshot.get("stdout") or "").strip()
    stderr = str(snapshot.get("stderr") or "").strip()
    parts = []
    if stdout:
        parts.append("stdout:\n" + stdout[-1800:])
    if stderr:
        parts.append("stderr:\n" + stderr[-1800:])
    return redact_secrets("\n\n".join(parts).strip())


def ensure_paths(output_root: Path, templates_dir: Path) -> None:
    if not jmty_gui.WEEKLY_SCRIPT.exists():
        raise LaunchdWeeklyError(f"週次処理スクリプトが見つかりません: {jmty_gui.WEEKLY_SCRIPT}")
    if not templates_dir.exists():
        raise LaunchdWeeklyError(f"画像プロンプトテンプレートフォルダが見つかりません: {templates_dir}")
    output_root.mkdir(parents=True, exist_ok=True)
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)


def direct_gws_auth_status(timeout_seconds: int) -> dict[str, Any]:
    executable = jmty_gui.resolve_gws_executable()
    result = subprocess.run(
        [executable, "auth", "status"],
        cwd=ROOT,
        env=jmty_gui.gws_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=max(5, timeout_seconds),
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        return {
            "available": True,
            "state": "auth_status_failed",
            "label": "gws認証確認失敗",
            "ok": False,
            "detail": detail[-1200:],
            "checked_at": jmty_gui.display_time(),
        }
    status = jmty_gui.parse_gws_json(result.stdout)
    if not isinstance(status, dict):
        return {
            "available": True,
            "state": "auth_status_invalid",
            "label": "gws認証結果不正",
            "ok": False,
            "detail": "gws auth status のJSONを読めませんでした",
            "checked_at": jmty_gui.display_time(),
        }
    return {
        **jmty_gui.summarize_gws_auth_status(status),
        "available": True,
        "checked_at": jmty_gui.display_time(),
        "keyring_backend": status.get("keyring_backend", ""),
        "user": status.get("user", ""),
    }


def ensure_gws_auth(args: argparse.Namespace) -> dict[str, Any]:
    auth = jmty_gui.gws_auth_status(force=True)
    if not auth.get("ok") and auth.get("state") == "timeout":
        try:
            auth = direct_gws_auth_status(args.auth_status_timeout_seconds)
            if auth.get("ok"):
                jmty_gui.clear_gws_auth_cache()
        except Exception as exc:
            auth = {
                **auth,
                "detail": f"{auth.get('detail') or ''} / direct auth status failed: {exc}",
            }
    if auth.get("ok"):
        print(f"[gws] ok: {auth.get('label')}", flush=True)
        return auth

    detail = auth.get("label") or auth.get("detail") or "未認証"
    message = "\n".join(
        [
            "【JMTY週次自動化: GWS認証エラー】",
            f"- 時刻: {now_text()}",
            f"- 状態: {detail}",
            f"- リポジトリ: `{ROOT}`",
        ]
    )
    send_discord(message, disabled=args.no_discord)

    if args.skip_auth_login:
        raise LaunchdWeeklyError(f"GWS認証が必要です: {detail}")

    print("[gws] auth is not ready; starting gws auth login", flush=True)
    login_job = jmty_gui.start_gws_auth_login()
    deadline = time.monotonic() + max(10, args.auth_retry_wait_seconds)
    notified_url = ""
    final_snapshot: dict[str, Any] = {}

    while time.monotonic() < deadline:
        snapshot = job_snapshot(login_job.id)
        final_snapshot = snapshot
        auth_url = str(snapshot.get("auth_url") or "").strip()
        if auth_url and auth_url != notified_url:
            notified_url = auth_url
            send_discord(
                "\n".join(
                    [
                        "【JMTY週次自動化: GWS再認証が必要】",
                        f"- 時刻: {now_text()}",
                        "- Google認証URLが発行されました。開いてログインしてください。",
                        f"- 認証URL: {auth_url}",
                        "- 認証後、次回のlaunchd実行または手動の途中再実行で復旧できます。",
                    ]
                ),
                disabled=args.no_discord,
            )
        if snapshot.get("status") in TERMINAL_STATUSES:
            break
        time.sleep(2)

    auth = jmty_gui.gws_auth_status(force=True)
    if auth.get("ok"):
        print(f"[gws] recovered: {auth.get('label')}", flush=True)
        return auth

    if final_snapshot.get("status") == "running":
        try:
            jmty_gui.request_job_cancel({"job_id": login_job.id})
        except Exception as exc:
            print(f"[gws] could not cancel auth login job: {exc}", file=sys.stderr)

    raise LaunchdWeeklyError(
        "GWS認証を自動復旧できませんでした。"
        "OAuthログインはGoogle画面での操作が必要です。"
        f" 状態: {auth.get('label') or auth.get('detail') or detail}"
    )


def run_preflight(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).expanduser().resolve()
    templates_dir = Path(args.templates_dir).expanduser().resolve()
    ensure_paths(output_root, templates_dir)
    if not args.no_discord:
        webhook_url, source = load_webhook_url()
        if webhook_url:
            print(f"[discord] configured via {source}", flush=True)
        else:
            print("[discord] not configured", flush=True)
    if args.preflight_only:
        if args.skip_auth_login:
            auth = jmty_gui.gws_auth_status(force=True)
            if not auth.get("ok") and auth.get("state") == "timeout":
                try:
                    auth = direct_gws_auth_status(args.auth_status_timeout_seconds)
                except Exception as exc:
                    auth = {**auth, "detail": f"{auth.get('detail') or ''} / direct auth status failed: {exc}"}
            if not auth.get("ok"):
                print(f"[gws] not ok: {auth.get('label') or auth.get('detail')}", flush=True)
                return 2
        else:
            ensure_gws_auth(args)
        print("[preflight] ok", flush=True)
    return 0


def run_weekly(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).expanduser().resolve()
    templates_dir = Path(args.templates_dir).expanduser().resolve()
    lock_file = Path(args.lock_file).expanduser().resolve()

    with single_run_lock(lock_file):
        recent_running = persisted_running_jobs(args.running_job_stale_hours)
        if recent_running:
            labels = [
                f"{job.get('id') or ''} / {job.get('command') or ''} / {job.get('started_at') or ''}"
                for job in recent_running[:5]
            ]
            raise LaunchdWeeklyError("実行中のGUI/週次ジョブがあるため開始しません: " + " / ".join(labels))

        jmty_gui.load_persisted_jobs()
        ensure_paths(output_root, templates_dir)
        ensure_gws_auth(args)
        if args.preflight_only:
            print("[preflight] ok", flush=True)
            return 0

        print(f"[weekly] starting {'resume' if args.resume else 'full'} run", flush=True)
        job = jmty_gui.start_weekly_bulk_job(output_root, templates_dir, resume=args.resume)
        snapshot = wait_for_job(job.id, poll_seconds=args.poll_seconds)
        status = str(snapshot.get("status") or "")
        if status == "done":
            if args.notify_success:
                send_discord(
                    "\n".join(
                        [
                            "【JMTY週次自動化: 完了】",
                            f"- 時刻: {now_text()}",
                            f"- ジョブ: `{snapshot.get('id')}`",
                            f"- 状態: {snapshot.get('phase') or '完了'}",
                        ]
                    ),
                    disabled=args.no_discord,
                )
            return 0

        raise LaunchdWeeklyError(
            "\n".join(
                [
                    f"週次一括実行が失敗しました: {snapshot.get('phase') or status}",
                    f"ジョブ: {snapshot.get('id')}",
                    job_tail(snapshot),
                ]
            ).strip()
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the JMTY weekly bulk workflow for launchd")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--templates-dir", default=str(DEFAULT_TEMPLATES_DIR))
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    parser.add_argument("--resume", action="store_true", help="途中再実行モードで開始する")
    parser.add_argument("--preflight-only", action="store_true", help="パス、Webhook、GWS認証だけ確認して終了する")
    parser.add_argument("--skip-auth-login", action="store_true", help="認証NG時にgws auth loginを開始しない")
    parser.add_argument("--auth-status-timeout-seconds", type=int, default=30)
    parser.add_argument("--auth-retry-wait-seconds", type=int, default=120)
    parser.add_argument("--running-job-stale-hours", type=int, default=20)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--notify-success", action="store_true")
    parser.add_argument("--no-discord", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    print("[jmty-weekly-launchd] 週次自動化は一時的に無効化されています。中止要求に基づき終了します。", file=sys.stderr)
    return 0
    args = parse_args(argv)
    try:
        if args.preflight_only:
            return run_preflight(args)
        return run_weekly(args)
    except Exception as exc:
        message = "\n".join(
            [
                "【JMTY週次自動化: 失敗】",
                f"- 時刻: {now_text()}",
                f"- エラー: {redact_secrets(str(exc))}",
                f"- リポジトリ: `{ROOT}`",
                f"- ログ: `{DEFAULT_LOG_DIR}`",
            ]
        )
        send_discord(message, disabled=getattr(args, "no_discord", False))
        print(redact_secrets(str(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
