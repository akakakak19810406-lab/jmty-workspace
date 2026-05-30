#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import random
import shutil
import subprocess
import ssl
import sys
import tempfile
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import urllib.error
import urllib.request


SPREADSHEET_ID = "1GKBTHwBS6W0D30X_yK7vqsaDRWw3p1tXM7lnFhyb0Uw"
SHEET_NAME = "アカウント情報"
PARENT_FOLDER_ID = "16P5sOzyJHLemwURON6Wf1i7NjodK3WWF"
DEFAULT_OUTPUT_ROOT = Path("outputs/jmty-weekly/current")
DEFAULT_PROMPT_TEMPLATES_DIR = Path("inputs/jmty_image_prompt_templates")
FACTORY_CASES_PATH = Path(os.environ.get("JMTY_FACTORY_CASES_PATH", "inputs/jmty_factory_cases/2026-02_案件一覧.md"))
SHEET_CACHE_PATH = Path("outputs/jmty-gui/sheet_cache.json")
GUI_IMAGE_VALIDATION_PATH = Path("outputs/jmty-gui/image_validation.json")

FACTORY_REGION_INDEX = 7   # H
FACTORY_IMAGE_COL = "I"
FACTORY_POST_INDEX = 9     # J
REMOTE_REGION_INDEX = 16   # Q
REMOTE1_IMAGE_COL = "R"
REMOTE1_POST_INDEX = 18    # S
REMOTE2_IMAGE_COL = "T"
REMOTE2_POST_INDEX = 20    # U
ROTATION_REPORT_FILENAME = "rotation_report.md"
DRIVE_SYNC_MANIFEST_FILENAME = "drive_sync_manifest.json"
IMAGE_ONLY_DIRNAME = "_drive_images"
IMPROVEMENT_REPORT_DIRNAME = "_improvement_reports"
DISCORD_JMTY_WEBHOOK_URL_ENV = "JMTY_DISCORD_JMTY_WEBHOOK_URL"
LEGACY_DISCORD_JMTY_WEBHOOK_URL_ENV = "TEAM_INFO_DISCORD_JMTY_WEBHOOK_URL"
DISCORD_JMTY_WEBHOOK_PATH = Path("config") / "discord-jmty-webhook.json"
DISCORD_CONTENT_LIMIT = 1900
OCR_TIMEOUT_SECONDS = int(os.environ.get("JMTY_OCR_TIMEOUT_SECONDS", "45") or "45")

EXPECTED_IMAGE_FILENAMES = {
    "factory": "工場.jpg",
    "remote1": "在宅1.jpg",
    "remote2": "在宅2.jpg",
}


def public_task_label(task_kind: str) -> str:
    return "在宅" if str(task_kind) in {"remote1", "remote2", "remote"} else "工場"

FACTORY_KIND_OCR_HINTS = ("工場", "製造", "寮", "ライン", "組立", "検査", "部品", "軽作業", "倉庫")
REMOTE_KIND_OCR_HINTS = ("在宅", "リモート", "自宅", "PC", "文章", "ライター", "オンライン", "データ入力", "SNS", "通勤なし")
SHEET_POST_VALIDATION_MIN_LENGTH = 140


CTA_VARIANTS = [
    "公式LINEに登録後、ボタン押すだけ！",
    "LINE追加後、そのままボタンをタップ！",
    "LINE登録だけでOK！あとはボタンを押すだけ！",
    "まずはLINE追加！10秒で問い合わせ完了！",
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


class JmtyWeeklyAssetsError(RuntimeError):
    pass


@dataclass
class Task:
    account_no: str
    account_name: str
    row_idx: int
    kind: str
    label_ja: str
    image_col: str
    post_col: str
    region: str
    post_text: str
    salary_text: str
    folder_name: str
    image_filename: str
    post_filename: str
    prompt_filename: str
    prompt_text: str
    prompt_template_name: str = ""
    prompt_template: str = ""


def resolve_gws_executable() -> str:
    explicit = os.environ.get("JMTY_GWS_BIN") or os.environ.get("GWS_BIN")
    candidates = [explicit] if explicit else ["gws", "gws.cmd"]
    for candidate in candidates:
        if not candidate:
            continue
        expanded = str(Path(candidate).expanduser()) if "/" in candidate else candidate
        found = shutil.which(expanded)
        if found:
            return found
        if "/" in expanded and Path(expanded).exists():
            return expanded
    raise JmtyWeeklyAssetsError(
        "\n".join(
            [
                "Google Workspace CLI `gws` が見つかりません。",
                "このスクリプトの rotate-sheet / prepare / sync-drive / sync-sheet は、スプレッドシートやDriveを読むために `gws` が必要です。",
                "対応方法:",
                "- `gws` をPATHへ入れてから再実行する",
                "- 別名やフルパスで入っている場合は `JMTY_GWS_BIN=/path/to/gws` を指定する",
                "- ChromeだけでDriveを開く運用でも、prepare用のシート読取には `gws` か同等の入力が必要です",
            ]
        )
    )


def run_gws(args: list[str]) -> dict:
    gws_executable = resolve_gws_executable()
    verify_paths = ssl.get_default_verify_paths()
    keyring_backend = os.environ.get("JMTY_GWS_KEYRING_BACKEND", "keyring")
    shell_cmd = (
        f"export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND={_shell_quote(keyring_backend)}; "
        + (
            f"export SSL_CERT_FILE={_shell_quote(verify_paths.cafile)}; "
            if verify_paths.cafile
            else ""
        )
        + (
            f"export SSL_CERT_DIR={_shell_quote(verify_paths.capath)}; "
            if verify_paths.capath
            else ""
        )
        + " ".join(_shell_quote(part) for part in [gws_executable, *args])
    )
    result = subprocess.run(
        ["/bin/zsh", "-lc", shell_cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise JmtyWeeklyAssetsError(f"`gws` の実行に失敗しました:\n{detail}")
    stdout = result.stdout.strip()
    if stdout.startswith("Using keyring backend:"):
        stdout = stdout.split("\n", 1)[1].strip()
    return json.loads(stdout) if stdout else {}


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _clip_discord_content(text: str) -> str:
    if len(text) <= DISCORD_CONTENT_LIMIT:
        return text
    return text[: DISCORD_CONTENT_LIMIT - 4].rstrip() + " ..."


def get_discord_jmty_webhook_url(repo_root: Path | None = None) -> tuple[str | None, str | None]:
    env_value = os.environ.get(DISCORD_JMTY_WEBHOOK_URL_ENV)
    if env_value and env_value.strip():
        return env_value.strip(), "env"

    legacy_env_value = os.environ.get(LEGACY_DISCORD_JMTY_WEBHOOK_URL_ENV)
    if legacy_env_value and legacy_env_value.strip():
        os.environ[DISCORD_JMTY_WEBHOOK_URL_ENV] = legacy_env_value.strip()
        return legacy_env_value.strip(), "legacy-env"

    resolved_root = repo_root or Path.cwd()
    config_path = resolved_root / DISCORD_JMTY_WEBHOOK_PATH
    if not config_path.exists():
        return None, None
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    if not isinstance(loaded, dict):
        return None, None
    url = str(loaded.get(DISCORD_JMTY_WEBHOOK_URL_ENV) or loaded.get("url") or "").strip()
    if url:
        os.environ[DISCORD_JMTY_WEBHOOK_URL_ENV] = url
        return url, "config-json-env"
    return None, None


def post_discord_jmty_message(content: str, repo_root: Path | None = None) -> bool:
    webhook_url, source = get_discord_jmty_webhook_url(repo_root)
    if not webhook_url:
        print("Discord jmty webhook URL が未設定のため、通知はスキップしました。", file=sys.stderr)
        return False

    payload = json.dumps(
        {"content": _clip_discord_content(content), "username": "JMTY改善メモ"},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "jmty-weekly-assets/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status not in {200, 204}:
                print(f"Discord 通知に失敗しました: status={response.status}", file=sys.stderr)
                return False
    except urllib.error.URLError as exc:
        print(f"Discord 通知に失敗しました: {exc}", file=sys.stderr)
        return False

    print(f"discord:sent:{source}", file=sys.stderr)
    return True


def classify_failure(exc: BaseException) -> tuple[str, list[str], list[str]]:
    message = str(exc)
    lowered = message.lower()
    if "gws" in lowered and ("見つかりません" in message or "command not found" in lowered):
        return (
            "GWS CLI 未検出",
            [
                "`gws` の場所を `JMTY_GWS_BIN` / `GWS_BIN` で指定できるようにしておく",
                "将来の改善候補: シート内容をCSV/JSONで渡せるローカル入力モードを追加する",
            ],
            [
                "`gws` がPATHにないと週次処理を開始できないことを自動判定",
                "次に必要な設定をエラー本文と改善レポートに出力",
            ],
        )
    if "tasks.json" in message:
        return (
            "tasks.json 未生成",
            [
                "`prepare` が完了してから画像生成・検証へ進むガードを強化する",
                "将来の改善候補: 既存タスクがない場合に入力不足一覧を自動作成する",
            ],
            [
                "画像生成前の前提ファイル不足を自動判定",
                "再実行すべきコマンドを改善レポートに残す",
            ],
        )
    if "permission" in lowered or "operation not permitted" in lowered or "権限" in message:
        return (
            "権限エラー",
            [
                "書き込み先を workspace 配下または `/private/tmp` に寄せる",
                "キャッシュ生成が原因の場合は `PYTHONPYCACHEPREFIX=/private/tmp/jmty-pycache` を使う",
            ],
            [
                "権限系の失敗を自動判定",
                "安全な書き込み先の候補を改善レポートに残す",
            ],
        )
    if isinstance(exc, NameError) and "normalized_condition_text" in message:
        return (
            "validate-sheet-posts 修復処理の関数名エラー",
            [
                "`validate-sheet-posts --repair` の比較処理で定義済みの `normalize_condition_text` を使う",
                "修復処理でだけ通る分岐は `--repair` 付きで構文と名前解決を確認する",
            ],
            [
                "`normalized_condition_text` の未定義エラーを既知エラーとして分類",
                "再発時に修正対象の関数名と実行コマンドを改善レポートへ残す",
            ],
        )
    return (
        "未分類エラー",
        [
            "エラー本文と実行コマンドをもとに再発防止策を追加する",
            "同じ失敗が繰り返される場合は known error として分類ルールを増やす",
        ],
        [
            "未分類でも改善レポートとDiscord通知の対象にする",
            "次回以降の分類追加に使える情報を保存する",
        ],
    )


def write_improvement_report(command: str, output_root: Path, exc: BaseException) -> Path | None:
    category, proposals, automated = classify_failure(exc)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = output_root / IMPROVEMENT_REPORT_DIRNAME
    report_path = report_dir / f"{timestamp}_{command}.md"
    lines = [
        f"# JMTY週次処理 改善レポート {timestamp}",
        "",
        f"- コマンド: `{command}`",
        f"- 分類: {category}",
        f"- エラー種別: `{type(exc).__name__}`",
        "",
        "## エラー概要",
        "```text",
        str(exc).strip(),
        "```",
        "",
        "## 自動で行った改善プロセス",
        *[f"- {item}" for item in automated],
        "",
        "## 次の改善候補",
        *[f"- {item}" for item in proposals],
        "",
    ]
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path
    except OSError as write_exc:
        print(f"改善レポートを書き込めませんでした: {write_exc}", file=sys.stderr)
        return None


def notify_improvement(command: str, output_root: Path, exc: BaseException, report_path: Path | None) -> None:
    category, proposals, automated = classify_failure(exc)
    report_line = f"- レポート: `{report_path}`" if report_path else "- レポート: 作成失敗"
    content = "\n".join(
        [
            "【ジモティ週次処理 改善メモ】",
            f"- コマンド: `{command}`",
            f"- 分類: {category}",
            f"- 改善済み: {automated[0] if automated else '改善レポート化'}",
            f"- 次の改善案: {proposals[0] if proposals else '分類ルールを追加'}",
            report_line,
        ]
    )
    post_discord_jmty_message(content)


def record_and_notify_failure(command: str, output_root: Path, exc: BaseException) -> Path | None:
    report_path = write_improvement_report(command, output_root, exc)
    notify_improvement(command, output_root, exc, report_path)
    return report_path


def read_sheet_rows() -> list[list[str]]:
    res = run_gws(
        [
            "sheets",
            "spreadsheets",
            "values",
            "get",
            "--params",
            json.dumps(
                {
                    "spreadsheetId": SPREADSHEET_ID,
                    "range": f"{SHEET_NAME}!A7:U",
                    "valueRenderOption": "FORMULA",
                },
                ensure_ascii=False,
            ),
        ]
    )
    return res.get("values", [])


def current_sheet_account_rows(rows: list[list[str]]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    duplicates: set[str] = set()
    for row_idx, row in enumerate(rows, start=7):
        account_name = sanitize_name(str(row[1]).strip() if len(row) > 1 else "")
        if not account_name:
            continue
        if account_name in index:
            duplicates.add(account_name)
            continue
        index[account_name] = {"row_idx": row_idx, "row": row}
    if duplicates:
        raise RuntimeError(
            "スプレッドシート上でアカウント名が重複しているため反映先を確定できません: "
            + " / ".join(sorted(duplicates))
        )
    return index


def list_drive_child_folders(parent_id: str) -> list[dict]:
    res = run_gws(
        [
            "drive",
            "files",
            "list",
            "--params",
            json.dumps(
                {
                    "q": f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                    "fields": "files(id,name,mimeType)",
                    "pageSize": 1000,
                },
                ensure_ascii=False,
            ),
        ]
    )
    return res.get("files", [])


def delete_drive_file(file_id: str) -> None:
    run_gws(["drive", "files", "delete", "--params", json.dumps({"fileId": file_id}, ensure_ascii=False)])


def create_drive_folder(name: str, parent_id: str) -> str:
    res = run_gws(
        [
            "drive",
            "files",
            "create",
            "--json",
            json.dumps(
                {
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                ensure_ascii=False,
            ),
        ]
    )
    return res["id"]


def upload_drive_file(file_path: Path, parent_id: str) -> str:
    res = run_gws(
        [
            "drive",
            "files",
            "create",
            "--upload",
            str(file_path),
            "--json",
            json.dumps({"name": file_path.name, "parents": [parent_id]}, ensure_ascii=False),
        ]
    )
    return res["id"]


def update_drive_file(file_path: Path, file_id: str) -> str:
    res = run_gws(
        [
            "drive",
            "files",
            "update",
            "--params",
            json.dumps({"fileId": file_id}, ensure_ascii=False),
            "--upload",
            str(file_path),
            "--json",
            json.dumps({"name": file_path.name}, ensure_ascii=False),
        ]
    )
    return str(res.get("id") or file_id)


def compact_gws_error(exc: BaseException) -> str:
    text = str(exc).strip()
    if "The user does not have sufficient permissions for this file" in text:
        return "このファイルへの更新/削除権限がありません"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else str(exc)


def delete_drive_files_by_name(parent_id: str, name: str) -> None:
    res = run_gws(
        [
            "drive",
            "files",
            "list",
            "--params",
            json.dumps(
                {
                    "q": f"'{parent_id}' in parents and name = '{name}' and trashed = false",
                    "fields": "files(id,name,mimeType)",
                    "pageSize": 1000,
                },
                ensure_ascii=False,
            ),
        ]
    )
    for file in res.get("files", []):
        delete_drive_file(file["id"])


def find_drive_file_by_name(parent_id: str, name: str) -> dict | None:
    res = run_gws(
        [
            "drive",
            "files",
            "list",
            "--params",
            json.dumps(
                {
                    "q": f"'{parent_id}' in parents and name = '{name}' and trashed = false",
                    "fields": "files(id,name,mimeType,modifiedTime)",
                    "pageSize": 10,
                    "orderBy": "modifiedTime desc",
                },
                ensure_ascii=False,
            ),
        ]
    )
    files = res.get("files", [])
    return files[0] if files else None


def drive_file_available(file_id: str, expected_name: str = "") -> bool:
    try:
        res = run_gws(
            [
                "drive",
                "files",
                "get",
                "--params",
                json.dumps(
                    {
                        "fileId": file_id,
                        "fields": "id,name,mimeType,trashed",
                        "supportsAllDrives": True,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
    except JmtyWeeklyAssetsError:
        return False
    if res.get("trashed"):
        return False
    if expected_name and str(res.get("name") or "") != expected_name:
        return False
    return bool(res.get("id"))


def list_drive_child_files(parent_id: str) -> list[dict]:
    res = run_gws(
        [
            "drive",
            "files",
            "list",
            "--params",
            json.dumps(
                {
                    "q": f"'{parent_id}' in parents and trashed = false",
                    "fields": "files(id,name,mimeType,modifiedTime)",
                    "pageSize": 1000,
                    "orderBy": "modifiedTime desc",
                },
                ensure_ascii=False,
            ),
        ]
    )
    return [file for file in res.get("files", []) if isinstance(file, dict)]


def drive_files_by_name(files: list[dict]) -> dict[str, dict]:
    by_name: dict[str, dict] = {}
    for file in files:
        name = str(file.get("name") or "")
        if name and name not in by_name:
            by_name[name] = file
    return by_name


def drive_manifest_key(task: dict) -> str:
    return f"{task['account_name']}::{task['kind']}"


def emit_progress(percent: int, message: str) -> None:
    safe_percent = max(0, min(100, int(percent)))
    print(f"[progress] {safe_percent}% {message}", flush=True)


def image_validation_key(account_name: str, kind: str) -> str:
    return f"{account_name}::{kind}"


def load_gui_image_validations() -> dict[str, dict]:
    path = Path.cwd() / GUI_IMAGE_VALIDATION_PATH
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(key): value for key, value in loaded.items() if isinstance(value, dict)}


def post_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def image_mtime(path: Path) -> int:
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return 0


def image_ocr_prevalidated(
    task: dict,
    image_path: Path,
    post_text: str,
    image_validations: dict[str, dict],
) -> bool:
    item = image_validations.get(image_validation_key(str(task.get("account_name") or ""), str(task.get("kind") or "")))
    if not isinstance(item, dict):
        return False
    if item.get("source") == "post-validation":
        return False
    if str(item.get("status") or "") not in {"ok", "acknowledged"}:
        return False
    saved_image_mtime = int(item.get("image_mtime") or 0)
    saved_post_hash = str(item.get("post_hash") or "")
    return bool(
        saved_image_mtime
        and saved_post_hash
        and saved_image_mtime == image_mtime(image_path)
        and saved_post_hash == post_hash(post_text)
    )


def resolve_ocr_workers(requested_workers: int | None, target_count: int) -> int:
    if target_count <= 1:
        return 1
    if requested_workers and requested_workers > 0:
        return max(1, min(target_count, requested_workers))
    cpu_count = os.cpu_count() or 4
    return max(2, min(target_count, cpu_count, 6))


def load_drive_sync_manifest(output_root: Path) -> dict:
    path = output_root / DRIVE_SYNC_MANIFEST_FILENAME
    if not path.exists():
        return {"items": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": {}}
    return loaded if isinstance(loaded, dict) else {"items": {}}


def write_drive_sync_manifest(output_root: Path, manifest: dict) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
    manifest["parent_folder_id"] = PARENT_FOLDER_ID
    (output_root / DRIVE_SYNC_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_drive_image_files(parent_id: str) -> int:
    res = run_gws(
        [
            "drive",
            "files",
            "list",
            "--params",
            json.dumps(
                {
                    "q": f"'{parent_id}' in parents and trashed = false",
                    "fields": "files(id,name,mimeType)",
                    "pageSize": 1000,
                },
                ensure_ascii=False,
            ),
        ]
    )
    deleted = 0
    skipped: list[str] = []
    for file in res.get("files", []):
        name = str(file.get("name") or "")
        mime_type = str(file.get("mimeType") or "")
        if not (mime_type.startswith("image/") or Path(name).suffix.lower() in IMAGE_EXTENSIONS):
            continue
        try:
            delete_drive_file(file["id"])
            deleted += 1
        except JmtyWeeklyAssetsError as exc:
            skipped.append(f"{name} ({compact_gws_error(exc)})")
    if skipped:
        shown = " / ".join(skipped[:5])
        suffix = f" ほか{len(skipped) - 5}件" if len(skipped) > 5 else ""
        print(f"⚠️ Drive画像 {len(skipped)}件は削除権限がないためスキップします: {shown}{suffix}", flush=True)
    return deleted


def replace_drive_file(file_path: Path, parent_id: str, existing_files: dict[str, dict] | None = None) -> str:
    existing = existing_files.get(file_path.name) if existing_files is not None else find_drive_file_by_name(parent_id, file_path.name)
    if existing and existing.get("id"):
        try:
            file_id = update_drive_file(file_path, str(existing["id"]))
            if existing_files is not None:
                existing_files[file_path.name] = {"id": file_id, "name": file_path.name}
            return file_id
        except JmtyWeeklyAssetsError as exc:
            print(
                f"⚠️ Drive既存ファイルを更新できないため、新規アップロードに切り替えます: "
                f"{file_path.name} / {compact_gws_error(exc)}",
                flush=True,
            )
    file_id = upload_drive_file(file_path, parent_id)
    if existing_files is not None:
        existing_files[file_path.name] = {"id": file_id, "name": file_path.name}
    return file_id


def make_public(file_id: str) -> None:
    run_gws(
        [
            "drive",
            "permissions",
            "create",
            "--params",
            json.dumps({"fileId": file_id}, ensure_ascii=False),
            "--json",
            json.dumps({"role": "reader", "type": "anyone"}, ensure_ascii=False),
        ]
    )


def batch_update_sheet(data: list[dict]) -> None:
    payload = {"valueInputOption": "USER_ENTERED", "data": data}
    run_gws(
        [
            "sheets",
            "spreadsheets",
            "values",
            "batchUpdate",
            "--params",
            json.dumps({"spreadsheetId": SPREADSHEET_ID}, ensure_ascii=False),
            "--json",
            json.dumps(payload, ensure_ascii=False),
        ]
    )


def row_value(row: list[str], index: int) -> str:
    return str(row[index]).strip() if len(row) > index else ""


def cell_value(row: list[str], index: int) -> str:
    return str(row[index]) if len(row) > index else ""


def ensure_row_width(row: list[str], width: int) -> None:
    if len(row) < width:
        row.extend([""] * (width - len(row)))


def rotate_bundles(rows: list[list[str]], target_indexes: list[int], column_indexes: list[int]) -> dict[int, list[str]]:
    old_bundles = {
        row_idx: [cell_value(rows[row_idx], col_idx) for col_idx in column_indexes]
        for row_idx in target_indexes
    }
    if len(target_indexes) <= 1:
        return old_bundles

    shuffled_source_indexes = list(target_indexes)
    rng = random.SystemRandom()
    for _ in range(20):
        rng.shuffle(shuffled_source_indexes)
        if any(row_idx != source_idx for row_idx, source_idx in zip(target_indexes, shuffled_source_indexes)):
            break
    else:
        shuffled_source_indexes = target_indexes[-1:] + target_indexes[:-1]

    return {
        row_idx: old_bundles[source_idx]
        for row_idx, source_idx in zip(target_indexes, shuffled_source_indexes)
    }


def render_rotation_report(rows: list[list[str]], factory_rows: list[int], remote_rows: list[int]) -> str:
    lines = [
        "【地域ランダム割当確認】",
        "■ 工場（H列）",
        "| アカウント名 | 担当エリア（ランダム割当後） |",
        "|------------|---------------------------|",
    ]
    for row_idx in factory_rows:
        row = rows[row_idx]
        account_name = re.sub(r"\s+", " ", row_value(row, 1)) or "未設定"
        lines.append(f"| {account_name} | {normalize_prefecture(row_value(row, FACTORY_REGION_INDEX)) or '未設定'} |")

    lines.extend(
        [
            "",
            "■ 在宅1（Q列1行目）",
            "| アカウント名 | 担当エリア（ランダム割当後） |",
            "|------------|---------------------------|",
        ]
    )
    for row_idx in remote_rows:
        row = rows[row_idx]
        account_name = re.sub(r"\s+", " ", row_value(row, 1)) or "未設定"
        remote1_region, _ = split_remote_regions(row_value(row, REMOTE_REGION_INDEX))
        lines.append(f"| {account_name} | {remote1_region or '未設定'} |")

    lines.extend(
        [
            "",
            "■ 在宅2（Q列2行目）",
            "| アカウント名 | 担当エリア（ランダム割当後） |",
            "|------------|---------------------------|",
        ]
    )
    for row_idx in remote_rows:
        row = rows[row_idx]
        account_name = re.sub(r"\s+", " ", row_value(row, 1)) or "未設定"
        _, remote2_region = split_remote_regions(row_value(row, REMOTE_REGION_INDEX))
        lines.append(f"| {account_name} | {remote2_region or '未設定'} |")
    return "\n".join(lines)


def rotate_sheet(output_root: Path, dry_run: bool) -> None:
    rows = read_sheet_rows()
    for row in rows:
        ensure_row_width(row, REMOTE2_POST_INDEX + 1)

    factory_rows = [idx for idx, row in enumerate(rows) if row_value(row, FACTORY_POST_INDEX)]
    remote_rows = [
        idx
        for idx, row in enumerate(rows)
        if row_value(row, REMOTE1_POST_INDEX) and row_value(row, REMOTE2_POST_INDEX)
    ]

    factory_rotated = rotate_bundles(rows, factory_rows, [FACTORY_REGION_INDEX, FACTORY_POST_INDEX])
    remote_rotated = rotate_bundles(rows, remote_rows, [REMOTE_REGION_INDEX, REMOTE1_POST_INDEX, REMOTE2_POST_INDEX])

    for row_idx, values in factory_rotated.items():
        rows[row_idx][FACTORY_REGION_INDEX] = values[0]
        rows[row_idx][FACTORY_POST_INDEX] = values[1]
    for row_idx, values in remote_rotated.items():
        rows[row_idx][REMOTE_REGION_INDEX] = values[0]
        rows[row_idx][REMOTE1_POST_INDEX] = values[1]
        rows[row_idx][REMOTE2_POST_INDEX] = values[2]

    report = render_rotation_report(rows, factory_rows, remote_rows)
    print(report)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / ROTATION_REPORT_FILENAME).write_text(report + "\n", encoding="utf-8")

    if dry_run:
        print(json.dumps({"dry_run": True, "factory_rows": len(factory_rows), "remote_rows": len(remote_rows)}, ensure_ascii=False))
        return

    updates: list[dict] = []
    for row_idx, values in factory_rotated.items():
        sheet_row = row_idx + 7
        updates.extend(
            [
                {"range": f"{SHEET_NAME}!H{sheet_row}", "values": [[values[0]]]},
                {"range": f"{SHEET_NAME}!J{sheet_row}", "values": [[values[1]]]},
            ]
        )
    for row_idx, values in remote_rotated.items():
        sheet_row = row_idx + 7
        updates.extend(
            [
                {"range": f"{SHEET_NAME}!Q{sheet_row}", "values": [[values[0]]]},
                {"range": f"{SHEET_NAME}!S{sheet_row}", "values": [[values[1]]]},
                {"range": f"{SHEET_NAME}!U{sheet_row}", "values": [[values[2]]]},
            ]
        )

    if updates:
        batch_update_sheet(updates)
    print(
        json.dumps(
            {
                "dry_run": False,
                "factory_rows": len(factory_rows),
                "remote_rows": len(remote_rows),
                "updated_cells": len(updates),
            },
            ensure_ascii=False,
        )
    )


def normalize_prefecture(value: str) -> str:
    text = clean_display_text(value)
    if not text:
        return ""
    if text.endswith(("都", "道", "府", "県")):
        return text
    special_names = {
        "北海道": "北海道",
        "東京": "東京都",
        "大阪": "大阪府",
        "京都": "京都府",
    }
    if text in special_names:
        return special_names[text]
    return f"{text}県"


def split_remote_regions(value: str) -> tuple[str, str]:
    parts = [
        normalize_prefecture(part)
        for part in re.split(r"[\r\n]+", str(value or ""))
        if part.strip()
    ]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], parts[1]


def region_for_kind(kind: str, value: str) -> str:
    if kind == "remote1":
        return split_remote_regions(value)[0]
    if kind == "remote2":
        return split_remote_regions(value)[1]
    return normalize_prefecture(value)


def sheet_cache_value(values: dict, key: str) -> str:
    item = values.get(key, {}) if isinstance(values, dict) else {}
    return str(item.get("value") or "").strip() if isinstance(item, dict) else ""


def load_sheet_region_index() -> dict[tuple[str, str], str]:
    if not SHEET_CACHE_PATH.exists():
        return {}
    try:
        cache = json.loads(SHEET_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    accounts = cache.get("accounts", []) if isinstance(cache, dict) else []
    index: dict[tuple[str, str], str] = {}
    for account in accounts:
        if not isinstance(account, dict):
            continue
        account_name = sanitize_name(str(account.get("account_name") or ""))
        values = account.get("values") if isinstance(account.get("values"), dict) else {}
        remote1_region, remote2_region = split_remote_regions(sheet_cache_value(values, "remote_region"))
        if account_name:
            index[(account_name, "factory")] = sheet_cache_value(values, "factory_region")
            index[(account_name, "remote1")] = sheet_cache_value(values, "remote1_region") or remote1_region
            index[(account_name, "remote2")] = sheet_cache_value(values, "remote2_region") or remote2_region
    return index


def clean_display_text(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[0]


def load_factory_case_blocks() -> list[str]:
    if not FACTORY_CASES_PATH.exists():
        return []
    raw = FACTORY_CASES_PATH.read_text(encoding="utf-8")
    blocks = re.split(r"\n\n(?=[①②③④⑤⑥⑦⑧⑨⑩]【)", raw)
    return [block.strip() for block in blocks if block.strip() and "工場案件見本ルール" not in block]


def choose_factory_case(account_no: str, row_idx: int, fallback_text: str) -> str:
    cases = load_factory_case_blocks()
    if not cases:
        return fallback_text
    rng = random.Random(f"{account_no}:{row_idx}:factory")
    return cases[rng.randrange(len(cases))]


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "未設定アカウント"


def strip_markdown_markers(text: str) -> str:
    value = str(text or "")
    if not value:
        return ""
    cleaned_lines = []
    for line in value.splitlines():
        cleaned = re.sub(r"^\s{0,3}[#＃]{1,6}\s*", "", line.rstrip())
        cleaned = cleaned.replace("#", "").replace("＃", "")
        cleaned = cleaned.replace("*", "").replace("＊", "")
        cleaned_lines.append(cleaned.rstrip())
    return "\n".join(cleaned_lines).strip()


def fenced(text: str) -> str:
    return f"```text\n{text.rstrip()}\n```"


def load_prompt_templates(templates_dir: Path, task_type: str) -> list[tuple[str, str]]:
    if not templates_dir.exists():
        return []

    candidates = []
    aliases = {
        "factory": ("factory", "工場", "all", "common", "共通"),
        "remote1": ("remote", "remote1", "在宅", "在宅1", "all", "common", "共通"),
        "remote2": ("remote", "remote2", "在宅", "在宅2", "all", "common", "共通"),
    }.get(task_type, ("all", "common", "共通"))

    for path in sorted(templates_dir.glob("*.md")) + sorted(templates_dir.glob("*.txt")):
        stem = path.stem.lower()
        if any(alias.lower() in stem for alias in aliases):
            text = path.read_text(encoding="utf-8").strip()
            if "banana" in text.lower() or "gafoo source reference" in text.lower():
                continue
            if text:
                candidates.append((path.name, text))
    return candidates


def choose_prompt_template(templates_dir: Path, task_type: str, account_no: str, row_idx: int, label_ja: str) -> tuple[str, str]:
    templates = load_prompt_templates(templates_dir, task_type)
    if not templates:
        return "", ""
    return random.SystemRandom().choice(templates)


def clean_template_stem(template_name: str) -> str:
    clean_name = Path(str(template_name or "").strip()).name
    suffix = Path(clean_name).suffix.lower()
    if suffix in {".md", ".txt", *IMAGE_EXTENSIONS}:
        return clean_name[: -len(suffix)]
    return clean_name


def template_preview_path(templates_dir: Path, template_name: str) -> Path | None:
    clean_name = clean_template_stem(template_name)
    if not clean_name:
        return None
    preview_dir = templates_dir / "_previews"
    for ext in sorted(IMAGE_EXTENSIONS):
        candidate = preview_dir / f"{clean_name}{ext}"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def style_reference_block(templates_dir: Path, template_name: str) -> str:
    preview_path = template_preview_path(templates_dir, template_name)
    if not preview_path:
        return ""
    return "\n".join(
        [
            "選択された画風テンプレ見本画像:",
            f"- パス: {preview_path}",
            "- このアップロード済み/保存済み見本画像を、色・文字組み・密度・質感・雰囲気の画風ガイドとして確認して使う。",
            "- 見本画像は画風だけを参考にし、人物・小物・作業内容・画像内の職種表記は投稿文の職種に合わせる。",
            "- ロゴ、人物、ブランド記号、QRコード、既存テキストをそのままコピーしない。",
        ]
    )


def render_prompt_template(template_text: str, values: dict[str, str]) -> str:
    rendered = template_text
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


PREFECTURE_NAMES_FOR_IMAGE_REDACTION = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)


def detected_prefecture_names(text: str) -> list[str]:
    found: list[str] = []
    for prefecture in PREFECTURE_NAMES_FOR_IMAGE_REDACTION:
        if prefecture in str(text or "") and prefecture not in found:
            found.append(prefecture)
    return found


def remove_region_names_for_image_prompt(text: str, region: str = "") -> str:
    result = str(text or "")
    aliases = set(PREFECTURE_NAMES_FOR_IMAGE_REDACTION)
    cleaned_region = clean_display_text(region)
    if cleaned_region:
        aliases.add(cleaned_region)
        aliases.add(normalize_prefecture(cleaned_region))
    for alias in sorted(aliases, key=len, reverse=True):
        if alias:
            result = result.replace(alias, "完全在宅")
    result = re.sub(r"完全在宅(?:県|府|都|道)", "完全在宅", result)
    return result


def sanitize_image_template_prompt(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in str(text or "").splitlines():
        lowered = line.lower()
        if "banana" in lowered or "gafoo source reference" in lowered:
            continue
        line = re.sub(r"\bRegion\b\s*[:：]?\s*「?地名なし」?", "Location text: {{region}}", line, flags=re.IGNORECASE)
        line = re.sub(r"地域[:：]?\s*「?地名なし」?", "地域: {{region}}", line)
        line = line.replace("地名なし", "{{region}}")
        line = line.replace("地域なし", "{{region}}")
        line = line.replace("住所なし", "{{region}}")
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def build_banner_prompt(
    task_type: str,
    region: str,
    post_text: str,
    account_name: str,
    salary_text: str,
    role_phrase: str,
    prompt_template: str = "",
    prompt_template_name: str = "",
    prompt_templates_dir: Path = DEFAULT_PROMPT_TEMPLATES_DIR,
) -> str:
    post_text = strip_markdown_markers(post_text)
    region_text = normalize_prefecture(region) or clean_display_text(region)
    is_factory = task_type == "factory"
    prompt_post_text = post_text if is_factory else remove_region_names_for_image_prompt(post_text, region)
    if is_factory:
        location_note = f"工場案件の画像内テキストには、投稿文に掲載されている県名「{region_text or '投稿文の県名'}」を必ず入れる。地名がないことを示す文言は使わない。"
    else:
        location_note = "在宅案件の画像内テキストには、都道府県名・市区町村名・駅名などを入れない。地名がないことを示す文言も使わない。"
    template_values = {
        "account_name": account_name,
        "task_type": public_task_label(task_type),
        "region": region_text if is_factory else "完全在宅",
        "salary_text": salary_text,
        "role_phrase": role_phrase,
        "post_text": prompt_post_text.strip(),
        "region_note": location_note,
    }
    if prompt_template:
        rendered = render_prompt_template(sanitize_image_template_prompt(prompt_template), template_values)
        source = f"テンプレート: {prompt_template_name}\n\n" if prompt_template_name else ""
        style_reference = style_reference_block(prompt_templates_dir, prompt_template_name)
        post_heading = "投稿文:" if is_factory else "在宅条件として整えた投稿文:"
        parts = [source + rendered.strip()]
        if style_reference:
            parts.append(style_reference)
        parts.append(
            "\n".join(
                [
                    "職種に合わせる優先ルール:",
                    f"- 画像の作業シーン、人物、小物、短い職種コピーは投稿文の職種「{role_phrase}」に合わせる。",
                    "- 画風テンプレは色・文字組み・密度・質感・雰囲気だけを参考にする。",
                    "- テンプレ見本の元の職業や小物が投稿文と違う場合は、投稿文の職種を優先して置き換える。",
                ]
            )
        )
        parts.extend([location_note, f"{post_heading}\n{prompt_post_text.strip()}"])
        return "\n\n".join(part for part in parts if part.strip())

    common = [
        "あなたは求人広告バナーを作るデザイナーです。",
        "正方形1:1の求人広告バナーを作成してください。",
        "スマホで読んでも視認性が高い日本語タイポグラフィ。",
        "大きな見出し、訴求ポイント3つ前後、CTAを入れる。",
        "誇張しすぎず、求人広告として信頼感のあるデザイン。",
        "文字切れ、細かすぎる文字、英語だらけの装飾は避ける。",
    ]
    if task_type == "factory":
        specific = [
            "カテゴリ: 工場求人",
            location_note,
            f"勤務地表記: {region_text or '投稿文の県名'}",
            f"職種表記: {role_phrase}",
            f"給与表記: {salary_text}",
            "工場・製造の仕事だとひと目でわかるビジュアル。",
            "寮費無料、高収入、未経験歓迎など、本文から強みを拾って反映する。",
        ]
    else:
        specific = [
            "カテゴリ: 在宅求人",
            location_note,
            f"職種表記: {role_phrase}",
            f"給与表記: {salary_text}",
            "完全在宅、全国OK、出勤不要だとひと目でわかるビジュアル。",
            "ノートPC、在宅ワーク、チャット、オンライン業務の雰囲気を反映する。",
        ]
    body = "\n".join(common + specific)
    post_heading = "投稿文:" if is_factory else "在宅条件として整えた投稿文:"
    return f"{body}\n\nアカウント名: {account_name}\n\n{post_heading}\n{prompt_post_text.strip()}"


def extract_salary_text(source_text: str, task_kind: str) -> str:
    text = source_text or ""
    patterns = [
        r"(月収\s*[\d,]+(?:\.\d+)?(?:〜|-|～)[\d,]+(?:\.\d+)?万円)",
        r"(月収\s*[\d,]+(?:\.\d+)?万円(?:目安|前後|以上|可)?)",
        r"(月給\s*[\d,]+(?:\.\d+)?万円(?:前後|以上|可|目安)?)",
        r"(日給\s*[\d,]+(?:\.\d+)?円(?:〜|-|～)[\d,]+(?:\.\d+)?円?)",
        r"(時給\s*[\d,]+(?:,\d{3})*(?:\.\d+)?円(?:〜|-|～)[\d,]+(?:,\d{3})*(?:\.\d+)?円?)",
        r"(時給\s*[\d,]+(?:,\d{3})*(?:\.\d+)?円)",
        r"(年収\s*[\d,]+(?:\.\d+)?万円(?:前後|以上|可|目安)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"\s+", "", match.group(1))

    if task_kind == "factory":
        return "月収30万円前後"
    return "月収44万円前後"


def extract_role_phrase(source_text: str, task_kind: str) -> str:
    text = (source_text or "").strip()
    if task_kind == "factory":
        if "マシンオペ" in text:
            return "製造スタッフ（マシンオペレーター）"
        if "バッテリー" in text:
            return "バッテリー製造スタッフ"
        if "製造補助" in text:
            return "製造補助スタッフ"
        if "材料セット" in text or "ボタン操作" in text:
            return "マシンオペレーター"
        if "自動車" in text:
            return "自動車部品の製造"
        if "食品" in text:
            return "食品加工"
        if "半導体" in text:
            return "半導体関連製造"
        if "電子" in text:
            return "電子部品の製造"
        if "検査" in text:
            return "検査・品質チェック"
        if "組立" in text:
            return "組立・ライン作業"
        if "工場" in text or "製造" in text:
            return "製造スタッフ（マシンオペレーター）"
        return "製造・軽作業"

    remote_keywords = [
        ("ライター", "文章作成・リライト"),
        ("文章", "文章作成・リライト"),
        ("事務", "在宅事務・データ整理"),
        ("データ入力", "データ入力・入力補助"),
        ("SNS", "SNS運用サポート"),
        ("サポート", "オンラインサポート"),
        ("営業", "在宅営業サポート"),
        ("デザイン", "デザイン補助"),
        ("動画", "動画編集補助"),
        ("AI", "AI活用ライティング"),
        ("カスタマー", "在宅カスタマーサポート"),
    ]
    for keyword, phrase in remote_keywords:
        if keyword in text:
            return phrase
    return "在宅ワーク"


def sheet_column_index(column: str) -> int:
    result = 0
    for char in column.strip().upper():
        if not ("A" <= char <= "Z"):
            raise ValueError(f"不正な列文字です: {column}")
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


def normalize_condition_text(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def compact_condition_text(value: str) -> str:
    return re.sub(r"\s+", "", normalize_condition_text(value))


def extract_salary_mentions(text: str) -> list[str]:
    normalized = normalize_condition_text(text)
    patterns = [
        r"(月収\s*\d+(?:\.\d+)?\s*(?:〜|～|-|ー|－)\s*\d+(?:\.\d+)?\s*万円(?:目安|前後|以上|可)?)",
        r"(月収\s*\d+(?:\.\d+)?\s*万円(?:目安|前後|以上|可)?)",
        r"(月給\s*\d+(?:\.\d+)?\s*万円(?:目安|前後|以上|可)?)",
        r"(時給\s*\d+(?:,\d{3})*(?:\.\d+)?\s*円(?:\s*(?:〜|～|-|ー|－)\s*\d+(?:,\d{3})*(?:\.\d+)?\s*円?)?)",
        r"(年収\s*\d+(?:\.\d+)?\s*万円(?:目安|前後|以上|可)?)",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, normalized):
            value = re.sub(r"\s+", "", match.group(1))
            if value not in found:
                found.append(value)
    return found


def first_salary_mention(text: str) -> str:
    mentions = extract_salary_mentions(text)
    return mentions[0] if mentions else ""


def normalize_salary_for_compare(value: str) -> str:
    text = compact_condition_text(value)
    text = text.replace("〜", "～").replace("-", "～").replace("ー", "～").replace("－", "～")
    text = re.sub(r"(目安|前後|可|程度)", "", text)
    return text


def salary_matches(expected: str, actual: str) -> bool:
    expected_norm = normalize_salary_for_compare(expected)
    actual_norm = normalize_salary_for_compare(actual)
    if not expected_norm or not actual_norm:
        return True
    if expected_norm == actual_norm:
        return True
    expected_numbers = re.findall(r"\d+(?:\.\d+)?", expected_norm)
    actual_numbers = re.findall(r"\d+(?:\.\d+)?", actual_norm)
    expected_unit = re.sub(r"[\d.,～]+", "", expected_norm)
    actual_unit = re.sub(r"[\d.,～]+", "", actual_norm)
    return bool(expected_numbers) and expected_numbers == actual_numbers and expected_unit == actual_unit


def quoted_copy_values(line: str) -> list[str]:
    return [part.strip() for part in re.findall(r"「([^」]+)」", line) if part.strip()]


def looks_like_role(value: str) -> bool:
    text = compact_condition_text(value)
    if not text or len(text) > 40:
        return False
    if re.search(r"(月収|月給|時給|年収|万円|円|応募|未経験|歓迎|OK|かんたん|安定|給与|勤務地)", text):
        return False
    return True


def extract_role_candidates(text: str, task_kind: str) -> list[str]:
    normalized = normalize_condition_text(text)
    candidates: list[str] = []
    line_patterns = [
        r"職種(?:表記)?[:：]\s*([^\n\r]+)",
        r"仕事内容[:：]\s*([^\n\r]+)",
        r"今回の業務は、([^。\n\r]+?)を中心",
        r"([^。\n\r]{2,40}?)の募集で、",
        r"／([^｜|\n\r]{2,40})[｜|]",
    ]
    for pattern in line_patterns:
        for match in re.finditer(pattern, normalized):
            candidate = match.group(1).strip()
            if looks_like_role(candidate) and candidate not in candidates:
                candidates.append(candidate)

    for line in normalized.splitlines():
        if "Main copy" not in line:
            continue
        for candidate in quoted_copy_values(line):
            if looks_like_role(candidate) and candidate not in candidates:
                candidates.append(candidate)

    fallback = extract_role_phrase(normalized, task_kind)
    if fallback and looks_like_role(fallback) and fallback not in candidates:
        candidates.append(fallback)
    return candidates


def first_role_candidate(text: str, task_kind: str) -> str:
    candidates = extract_role_candidates(text, task_kind)
    return candidates[0] if candidates else ""


def normalize_role_for_compare(value: str) -> str:
    text = compact_condition_text(value)
    text = re.sub(r"[()（）【】「」『』/／・\-ー－|｜]", "", text)
    text = re.sub(r"(スタッフ|作業員|担当|業務|補助)$", "", text)
    return text


def role_matches(expected: str, actual: str, task_kind: str) -> bool:
    expected_norm = normalize_role_for_compare(expected)
    actual_norm = normalize_role_for_compare(actual)
    if not expected_norm or not actual_norm:
        return True
    if expected_norm == actual_norm or expected_norm in actual_norm or actual_norm in expected_norm:
        return True
    if task_kind == "factory":
        keywords = ("検査", "品質", "組立", "ライン", "マシン", "オペ", "自動車", "食品", "半導体", "電子", "製造")
    else:
        keywords = ("文章", "リライト", "ライター", "事務", "データ入力", "SNS", "サポート", "営業", "デザイン", "動画", "AI")
    expected_hits = {keyword for keyword in keywords if keyword in expected_norm}
    actual_hits = {keyword for keyword in keywords if keyword in actual_norm}
    return bool(expected_hits and actual_hits and expected_hits == actual_hits)


def logical_post_kind(task_kind: str) -> str:
    return "remote" if task_kind in {"remote1", "remote2"} else "factory"


def classify_condition_kind(text: str) -> str:
    normalized = compact_condition_text(text)
    if not normalized:
        return ""
    if re.search(r"(種別|カテゴリ)[:：]?工場", normalized) or "工場求人画像として作る" in normalized:
        return "factory"
    if re.search(r"(種別|カテゴリ)[:：]?在宅", normalized) or "在宅求人画像として作る" in normalized:
        return "remote"
    factory_score = 0
    remote_score = 0
    for keyword in ("工場", "製造", "寮", "ライン", "組立", "検査", "品質", "マシン", "部品"):
        if keyword in normalized:
            factory_score += 1
    for keyword in ("完全在宅", "在宅", "リモート", "自宅", "出勤不要", "PC", "オンライン", "チャット", "文章作成"):
        if keyword in normalized:
            remote_score += 1
    if "完全在宅" in normalized or "出勤不要" in normalized:
        remote_score += 2
    if factory_score > remote_score:
        return "factory"
    if remote_score > factory_score:
        return "remote"
    return ""


def extract_drive_file_id(value: str) -> str:
    text = str(value or "")
    patterns = [
        r"[?&]id=([A-Za-z0-9_-]+)",
        r"/d/([A-Za-z0-9_-]+)",
        r"uc\?id=([A-Za-z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def download_drive_image_for_ocr(file_id: str) -> Path | None:
    if not file_id:
        return None
    cache_dir = Path(tempfile.gettempdir()) / "jmty-sheet-post-validation"
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{file_id}.img"
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "jmty-weekly-assets/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read(20 * 1024 * 1024)
            content_type = response.headers.get("Content-Type", "")
        if "html" in content_type.lower() or data.lstrip().startswith(b"<"):
            return None
        destination.write_bytes(data)
        return destination
    except (OSError, urllib.error.URLError):
        return None


def read_prompt_metadata_text(output_root: Path, task: dict) -> str:
    parts: list[str] = []
    prompt_relpath = str(task.get("prompt_relpath") or "")
    if prompt_relpath:
        prompt_path = output_root / prompt_relpath
        if prompt_path.exists():
            parts.append(prompt_path.read_text(encoding="utf-8"))
    task_prompt = str(task.get("prompt_text") or "")
    if task_prompt:
        parts.append(task_prompt)
    return "\n\n".join(parts)


def extract_image_conditions(output_root: Path, task: dict, sheet_row: list[str], include_drive_ocr: bool = False) -> dict[str, str]:
    task_kind = str(task.get("kind") or "")
    sources: list[str] = []
    texts_by_source: list[tuple[str, str]] = []

    image_relpath = str(task.get("image_relpath") or "")
    if image_relpath:
        image_path = output_root / image_relpath
        if image_path.exists():
            text = ocr_text(image_path)
            if text:
                texts_by_source.append(("local_ocr", text))
                sources.append("local_ocr")

    image_index = sheet_column_index(str(task.get("image_col") or "A"))
    image_formula = cell_value(sheet_row, image_index)
    drive_file_id = extract_drive_file_id(image_formula)
    if include_drive_ocr:
        drive_image_path = download_drive_image_for_ocr(drive_file_id)
        if drive_image_path:
            text = ocr_text(drive_image_path)
            if text:
                texts_by_source.append(("drive_ocr", text))
                sources.append("drive_ocr")

    prompt_metadata = read_prompt_metadata_text(output_root, task)
    if prompt_metadata:
        texts_by_source.append(("prompt_metadata", prompt_metadata))
        sources.append("prompt_metadata")

    salary = ""
    role = ""
    kind = ""
    for _, text in texts_by_source:
        if not salary:
            salary = first_salary_mention(text)
        if not role:
            role = first_role_candidate(text, task_kind)
        if not kind:
            kind = classify_condition_kind(text)

    return {
        "salary": salary,
        "role": role,
        "kind": kind,
        "source": ",".join(dict.fromkeys(sources)),
        "drive_file_id": drive_file_id,
    }


def extract_post_conditions(post_text: str, task_kind: str) -> dict[str, str]:
    return {
        "salary": first_salary_mention(post_text),
        "role": first_role_candidate(post_text, task_kind),
        "kind": classify_condition_kind(post_text),
    }


def has_location_condition(post_text: str, task_kind: str, region: str) -> bool:
    text = compact_condition_text(post_text)
    if logical_post_kind(task_kind) == "remote":
        return "完全在宅" in text or "全国どこからでも" in text or "出勤不要" in text
    region_text = compact_condition_text(region)
    return bool(region_text and region_text in text) or "勤務地" in text


def remote_post_has_region_name(post_text: str, region: str = "") -> bool:
    text = str(post_text or "")
    if not text:
        return False
    region_text = clean_display_text(region)
    candidates = set(PREFECTURE_NAMES_FOR_IMAGE_REDACTION)
    if region_text:
        candidates.add(region_text)
        candidates.add(normalize_prefecture(region_text))
    return any(candidate and candidate in text for candidate in candidates)


def validate_sheet_post_quality(task: dict, sheet_post_text_value: str, post_conditions: dict[str, str], effective_task_kind: str = "") -> list[str]:
    issues: list[str] = []
    text = strip_markdown_markers(sheet_post_text_value)
    compact = compact_condition_text(text)
    task_kind = effective_task_kind or str(task.get("kind") or "")
    if len(compact) < SHEET_POST_VALIDATION_MIN_LENGTH:
        issues.append("投稿文が短すぎます")
    if re.search(r"(仮文|仮置き|TODO|TBD|テスト|ダミー|サンプル|Lorem)", text, flags=re.IGNORECASE):
        issues.append("仮文またはテスト文の可能性があります")
    if not post_conditions.get("role"):
        issues.append("職種が読み取れません")
    if not post_conditions.get("salary"):
        issues.append("給与が読み取れません")
    if not has_location_condition(text, task_kind, str(task.get("region") or "")):
        issues.append("勤務地または在宅条件が不足しています")
    if "応募" not in compact and "LINE" not in text.upper():
        issues.append("応募導線が不足しています")
    if "応募条件" not in text and "未経験" not in text and "経験" not in text:
        issues.append("応募条件が不足しています")
    post_kind = post_conditions.get("kind") or ""
    if task_kind == "factory" and post_kind == "remote":
        issues.append("工場投稿文に在宅系の文言が強く出ています")
    if task_kind in {"remote1", "remote2"} and post_kind == "factory":
        issues.append("在宅投稿文に工場系の文言が強く出ています")
    if task_kind in {"remote1", "remote2"} and "完全在宅" not in text:
        issues.append("在宅投稿文に完全在宅の表記がありません")
    if task_kind in {"remote1", "remote2"} and remote_post_has_region_name(text, str(task.get("region") or "")):
        issues.append("在宅投稿文に地名が含まれています")
    return issues


def repair_kind_for_image(task_kind: str, image_kind: str) -> str:
    if image_kind == "factory":
        return "factory"
    if image_kind == "remote":
        return task_kind if task_kind in {"remote1", "remote2"} else "remote1"
    return task_kind


def collect_sheet_post_validation(
    output_root: Path,
    rows: list[list[str]],
    tasks: list[dict],
    include_drive_ocr: bool = False,
) -> list[dict]:
    findings: list[dict] = []
    for task in tasks:
        validate_manifest_task(task)
        row_idx = int(task["row_idx"])
        sheet_row_index = row_idx - 7
        if sheet_row_index < 0 or sheet_row_index >= len(rows):
            findings.append(
                {
                    "account_name": task.get("account_name", ""),
                    "kind": task.get("kind", ""),
                    "label_ja": task.get("label_ja", ""),
                    "row_idx": row_idx,
                    "cell": f"{task.get('post_col', '?')}{row_idx}",
                    "issues": ["スプレッドシート行が取得できません"],
                    "image_conditions": {},
                    "post_conditions": {},
                    "current_post": "",
                }
            )
            continue

        row = rows[sheet_row_index]
        post_index = sheet_column_index(str(task.get("post_col") or "A"))
        current_post = cell_value(row, post_index)
        image_conditions = extract_image_conditions(output_root, task, row, include_drive_ocr=include_drive_ocr)
        post_conditions = extract_post_conditions(current_post, str(task.get("kind") or ""))

        issues: list[str] = []
        image_salary = image_conditions.get("salary", "")
        post_salary = post_conditions.get("salary", "")
        if image_salary and post_salary and not salary_matches(image_salary, post_salary):
            issues.append(f"画像の給与 `{image_salary}` と投稿文の給与 `{post_salary}` が違います")
        if image_salary and not post_salary:
            issues.append(f"画像の給与 `{image_salary}` が投稿文から読み取れません")

        image_role = image_conditions.get("role", "")
        post_role = post_conditions.get("role", "")
        if image_role and post_role and not role_matches(image_role, post_role, str(task.get("kind") or "")):
            issues.append(f"画像の職種 `{image_role}` と投稿文の職種 `{post_role}` が違います")
        if image_role and not post_role:
            issues.append(f"画像の職種 `{image_role}` が投稿文から読み取れません")

        image_kind = image_conditions.get("kind", "")
        post_kind = post_conditions.get("kind", "")
        if image_kind and post_kind and image_kind != post_kind:
            issues.append(f"画像種別 `{image_kind}` と投稿文種別 `{post_kind}` が違います")
        quality_kind = repair_kind_for_image(str(task.get("kind") or ""), image_kind) if image_kind else str(task.get("kind") or "")
        issues.extend(validate_sheet_post_quality(task, current_post, post_conditions, effective_task_kind=quality_kind))
        if issues:
            findings.append(
                {
                    "account_name": task.get("account_name", ""),
                    "kind": task.get("kind", ""),
                    "label_ja": task.get("label_ja", ""),
                    "row_idx": row_idx,
                    "cell": f"{task.get('post_col', '?')}{row_idx}",
                    "issues": list(dict.fromkeys(issues)),
                    "image_conditions": image_conditions,
                    "post_conditions": post_conditions,
                    "current_post": current_post,
                }
            )
    return findings


def validate_sheet_posts(output_root: Path, repair: bool, include_drive_ocr: bool = False) -> None:
    tasks = read_tasks(output_root)
    rows = read_sheet_rows()
    findings = collect_sheet_post_validation(output_root, rows, tasks, include_drive_ocr=include_drive_ocr)

    if repair:
        if findings:
            raise JmtyWeeklyAssetsError(
                "投稿文の自動修復は停止しました。Python固定テンプレートでは本文を作成せず、"
                "投稿文作成スキルまたはGUIのAI再作成で投稿文を作り直してください。"
            )
        recheck_rows = read_sheet_rows()
        recheck_findings = collect_sheet_post_validation(output_root, recheck_rows, tasks, include_drive_ocr=include_drive_ocr)
    else:
        recheck_findings = []

    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "dry_run": not repair,
                "checked": len(tasks),
                "issue_count": len(findings),
                "planned_or_updated_cells": [] if repair else [item["cell"] for item in findings],
                "updated_cells": 0,
                "remaining_issue_count": len(recheck_findings) if repair else None,
                "updates": [],
                "findings": [
                    {
                        "account_name": item["account_name"],
                        "label_ja": item["label_ja"],
                        "kind": item["kind"],
                        "cell": item["cell"],
                        "issues": item["issues"],
                        "image_conditions": item["image_conditions"],
                        "post_conditions": item["post_conditions"],
                    }
                    for item in findings
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def render_prompt_document(task: dict | Task, image_path: Path, post_text: str, prompt_text: str) -> str:
    account_name = task["account_name"] if isinstance(task, dict) else task.account_name
    row_idx = task["row_idx"] if isinstance(task, dict) else task.row_idx
    label_ja = task["label_ja"] if isinstance(task, dict) else task.label_ja
    kind = task["kind"] if isinstance(task, dict) else task.kind
    display_label = public_task_label(kind)
    region = task["region"] if isinstance(task, dict) else task.region
    image_path_display = str(image_path) if display_label == "工場" else "内部管理ファイル"
    return "\n".join(
        [
            f"# {display_label} 画像プロンプト",
            "",
            "## メタ情報",
            f"- アカウント名: {account_name}",
            f"- 行番号: {row_idx}",
            f"- 種別: {display_label}",
            f"- 投稿先地域: {region or '未設定'}",
            f"- 画像保存先: `{image_path_display}`",
            "",
            "## 投稿文章",
            fenced(post_text),
            "",
            "## 画像プロンプト",
            fenced(prompt_text),
            "",
        ]
    )


def sheet_post_text(task_kind: str, post_text: str) -> str:
    return strip_markdown_markers(post_text)


def prepare_existing_post_text(task_type: str, source_text: str, label: str) -> tuple[str, str]:
    post_text = strip_markdown_markers(source_text)
    if not post_text:
        raise JmtyWeeklyAssetsError(f"{label}の投稿文が空です。Pythonでは本文を作成しないため、AI作成済みの投稿文を入れてください。")
    return post_text, extract_salary_text(post_text, task_type)


def post_filename_for_label(label_ja: str) -> str:
    return f"{label_ja}の投稿文章.md"


def expected_image_filename(task_kind: str) -> str:
    try:
        return EXPECTED_IMAGE_FILENAMES[task_kind]
    except KeyError as exc:
        raise ValueError(f"未知のタスク種別です: {task_kind}") from exc


def ocr_text(file_path: Path) -> str:
    if shutil.which("tesseract") is None:
        return ""
    try:
        result = subprocess.run(
            ["tesseract", str(file_path), "stdout", "--psm", "6", "-l", "jpn+eng"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"⚠️ OCRがタイムアウトしたため種別検証をスキップします: {file_path}", file=sys.stderr, flush=True)
        return ""
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def validate_image_kind_text(text: str, task_kind: str, account_name: str, file_name: str) -> None:
    if not text:
        return

    normalized = re.sub(r"\s+", "", text)
    factory_hits = sum(1 for hint in FACTORY_KIND_OCR_HINTS if hint in normalized)
    remote_hits = sum(1 for hint in REMOTE_KIND_OCR_HINTS if hint in normalized)

    if task_kind == "factory":
        if "在宅" in normalized or "リモート" in normalized or remote_hits >= 2:
            raise RuntimeError(
                f"画像種別の不整合を検出しました: {account_name} / 工場 で `{file_name}` に在宅系の語が多く含まれます。"
            )
        if factory_hits == 0 and remote_hits >= 1:
            raise RuntimeError(
                f"画像種別の不整合を検出しました: {account_name} / 工場 で `{file_name}` の OCR に工場系語が見当たりません。"
            )
    elif task_kind in {"remote1", "remote2"}:
        if "工場" in normalized or "製造" in normalized or factory_hits >= 2:
            raise RuntimeError(
                f"画像種別の不整合を検出しました: {account_name} / 在宅 で `{file_name}` に工場系の語が多く含まれます。"
            )


def validate_image_kind(file_path: Path, task_kind: str, account_name: str) -> None:
    validate_image_kind_text(ocr_text(file_path), task_kind, account_name, file_path.name)


def validate_manifest_task(task: dict) -> None:
    expected = expected_image_filename(task["kind"])
    actual = Path(task["image_relpath"]).name
    if actual != expected:
        raise RuntimeError(f"manifest の画像ファイル名が不正です: {task['account_name']} / {task['kind']} -> {actual} (expected {expected})")


def validate_post_text(task: dict, post_text: str) -> None:
    if "【公式LINEURL】" not in post_text:
        raise RuntimeError(f"投稿文に公式LINEプレースホルダーがありません: {task['account_name']} / {task['label_ja']}")
    if re.search(r"https?://|lin\.ee|line\.me", post_text, flags=re.IGNORECASE):
        raise RuntimeError(f"投稿文に実URLらしき文字列があります: {task['account_name']} / {task['label_ja']}")
    if re.search(r"[#＃*＊]", post_text):
        raise RuntimeError(f"投稿文にMarkdown装飾記号が残っています: {task['account_name']} / {task['label_ja']}")
    if task["kind"] == "factory" and "完全在宅" in post_text:
        raise RuntimeError(f"工場投稿文に在宅系の文言があります: {task['account_name']} / {task['label_ja']}")
    if task["kind"] == "factory":
        expected_region = normalize_prefecture(str(task.get("region") or ""))
        found_regions = detected_prefecture_names(post_text)
        conflicting_regions = [region for region in found_regions if region != expected_region]
        if expected_region and expected_region not in post_text:
            raise RuntimeError(f"工場投稿文にH列の地域がありません: {task['account_name']} / {task['label_ja']} / {expected_region}")
        if conflicting_regions:
            raise RuntimeError(
                f"工場投稿文にH列と違う地域が含まれています: {task['account_name']} / {task['label_ja']} / "
                + "、".join(conflicting_regions)
            )
    if task["kind"] in {"remote1", "remote2"} and "完全在宅" not in post_text:
        raise RuntimeError(f"在宅投稿文に完全在宅の表記がありません: {task['account_name']} / {task['label_ja']}")
    if task["kind"] in {"remote1", "remote2"} and remote_post_has_region_name(post_text, str(task.get("region") or "")):
        raise RuntimeError(f"在宅投稿文に地名が含まれています: {task['account_name']} / {task['label_ja']}")


def validate_task_files(output_root: Path, tasks: list[dict], ocr_workers: int | None = None) -> dict:
    checked = 0
    missing_images = []
    image_validations = load_gui_image_validations()
    ocr_targets: list[tuple[dict, Path]] = []
    skipped_ocr_keys: set[str] = set()
    ocr_text_by_key: dict[str, str] = {}

    emit_progress(4, "投稿文・画像ファイル名を確認中")
    for task in tasks:
        validate_manifest_task(task)
        account_dir = output_root / task["folder_name"]
        image_path = account_dir / Path(task["image_relpath"]).name
        post_path = account_dir / Path(task["post_relpath"]).name
        if not post_path.exists():
            raise FileNotFoundError(f"投稿文章が見つかりません: {post_path}")
        post_text = strip_markdown_markers(post_path.read_text(encoding="utf-8"))
        validate_post_text(task, post_text)
        if image_path.exists():
            if image_ocr_prevalidated(task, image_path, post_text, image_validations):
                skipped_ocr_keys.add(drive_manifest_key(task))
            else:
                ocr_targets.append((task, image_path))
        else:
            missing_images.append(str(image_path))
        checked += 1

    total_ocr = len(ocr_targets)
    skipped_ocr = len(skipped_ocr_keys)
    if total_ocr == 0:
        emit_progress(18, f"OCR検証: 検証OK/確認済み {skipped_ocr}件をスキップ")
        return {
            "checked": checked,
            "missing_images": missing_images,
            "image_ocr_checked": 0,
            "image_ocr_skipped": skipped_ocr,
            "ocr_text_by_key": ocr_text_by_key,
            "skipped_ocr_keys": list(skipped_ocr_keys),
        }

    workers = resolve_ocr_workers(ocr_workers, total_ocr)
    emit_progress(10, f"OCR検証: {skipped_ocr}件スキップ / {total_ocr}件をOCRサブエージェント{workers}並列で確認")

    def run_ocr_target(target: tuple[dict, Path]) -> tuple[str, str]:
        task, image_path = target
        text = ocr_text(image_path)
        validate_image_kind_text(text, task["kind"], task["account_name"], image_path.name)
        return drive_manifest_key(task), text

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_ocr_target, target) for target in ocr_targets]
        for future in as_completed(futures):
            key, text = future.result()
            ocr_text_by_key[key] = text
            completed += 1
            percent = 10 + int((completed / max(total_ocr, 1)) * 28)
            emit_progress(percent, f"OCR検証: {completed}/{total_ocr}完了 / {workers}並列")

    return {
        "checked": checked,
        "missing_images": missing_images,
        "image_ocr_checked": total_ocr,
        "image_ocr_skipped": skipped_ocr,
        "ocr_text_by_key": ocr_text_by_key,
        "skipped_ocr_keys": list(skipped_ocr_keys),
    }


def build_tasks(rows: list[list[str]], prompt_templates_dir: Path = DEFAULT_PROMPT_TEMPLATES_DIR) -> list[Task]:
    tasks: list[Task] = []
    for idx, row in enumerate(rows, start=7):
        account_no = str(row[0]).strip() if len(row) > 0 else ""
        account_name = sanitize_name(str(row[1]).strip() if len(row) > 1 else "")
        if not account_name:
            continue

        factory_region = normalize_prefecture(str(row[FACTORY_REGION_INDEX]).strip() if len(row) > FACTORY_REGION_INDEX else "")
        factory_source_post = str(row[FACTORY_POST_INDEX]).strip() if len(row) > FACTORY_POST_INDEX else ""
        remote_region_raw = str(row[REMOTE_REGION_INDEX]).strip() if len(row) > REMOTE_REGION_INDEX else ""
        remote1_region, remote2_region = split_remote_regions(remote_region_raw)
        remote1_source_post = str(row[REMOTE1_POST_INDEX]).strip() if len(row) > REMOTE1_POST_INDEX else ""
        remote2_source_post = str(row[REMOTE2_POST_INDEX]).strip() if len(row) > REMOTE2_POST_INDEX else ""

        folder_name = f"{account_name}"
        if factory_source_post:
            factory_case_source = choose_factory_case(account_no, idx, factory_source_post)
            factory_post, factory_salary = prepare_existing_post_text("factory", factory_source_post, f"{account_name} 工場")
            factory_template_name, factory_template = choose_prompt_template(
                prompt_templates_dir, "factory", account_no, idx, "工場"
            )
            tasks.append(
                Task(
                    account_no=account_no,
                    account_name=account_name,
                    row_idx=idx,
                    kind="factory",
                    label_ja="工場",
                    image_col=FACTORY_IMAGE_COL,
                    post_col="J",
                    region=factory_region,
                    post_text=factory_post,
                    salary_text=factory_salary,
                    folder_name=folder_name,
                    image_filename="工場.jpg",
                    post_filename=post_filename_for_label("工場"),
                    prompt_filename="工場_画像プロンプト.md",
                    prompt_text=build_banner_prompt(
                        "factory",
                        factory_region,
                        factory_post,
                        account_name,
                        factory_salary,
                        extract_role_phrase(factory_case_source, "factory"),
                        factory_template,
                        factory_template_name,
                        prompt_templates_dir,
                    ),
                    prompt_template_name=factory_template_name,
                    prompt_template=factory_template,
                )
            )
        if remote1_source_post:
            remote1_post, remote1_salary = prepare_existing_post_text("remote1", remote1_source_post, f"{account_name} 在宅1")
            remote1_template_name, remote1_template = choose_prompt_template(
                prompt_templates_dir, "remote1", account_no, idx, "在宅1"
            )
            tasks.append(
                Task(
                    account_no=account_no,
                    account_name=account_name,
                    row_idx=idx,
                    kind="remote1",
                    label_ja="在宅1",
                    image_col=REMOTE1_IMAGE_COL,
                    post_col="S",
                    region=remote1_region,
                    post_text=remote1_post,
                    salary_text=remote1_salary,
                    folder_name=folder_name,
                    image_filename="在宅1.jpg",
                    post_filename=post_filename_for_label("在宅1"),
                    prompt_filename="在宅1_画像プロンプト.md",
                    prompt_text=build_banner_prompt(
                        "remote1",
                        remote1_region,
                        remote1_post,
                        account_name,
                        remote1_salary,
                        extract_role_phrase(remote1_source_post, "remote1"),
                        remote1_template,
                        remote1_template_name,
                        prompt_templates_dir,
                    ),
                    prompt_template_name=remote1_template_name,
                    prompt_template=remote1_template,
                )
            )
        if remote2_source_post:
            remote2_post, remote2_salary = prepare_existing_post_text("remote2", remote2_source_post, f"{account_name} 在宅2")
            remote2_template_name, remote2_template = choose_prompt_template(
                prompt_templates_dir, "remote2", account_no, idx, "在宅2"
            )
            tasks.append(
                Task(
                    account_no=account_no,
                    account_name=account_name,
                    row_idx=idx,
                    kind="remote2",
                    label_ja="在宅2",
                    image_col=REMOTE2_IMAGE_COL,
                    post_col="U",
                    region=remote2_region,
                    post_text=remote2_post,
                    salary_text=remote2_salary,
                    folder_name=folder_name,
                    image_filename="在宅2.jpg",
                    post_filename=post_filename_for_label("在宅2"),
                    prompt_filename="在宅2_画像プロンプト.md",
                    prompt_text=build_banner_prompt(
                        "remote2",
                        remote2_region,
                        remote2_post,
                        account_name,
                        remote2_salary,
                        extract_role_phrase(remote2_source_post, "remote2"),
                        remote2_template,
                        remote2_template_name,
                        prompt_templates_dir,
                    ),
                    prompt_template_name=remote2_template_name,
                    prompt_template=remote2_template,
                )
            )
    return tasks


def write_prepare_output(output_root: Path, tasks: list[Task]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = []
    by_account: dict[str, list[Task]] = {}
    for task in tasks:
        by_account.setdefault(task.folder_name, []).append(task)

    for account_name, account_tasks in by_account.items():
        account_dir = output_root / account_name
        account_dir.mkdir(parents=True, exist_ok=True)

        summary_lines = [f"# {account_name}", ""]
        summary_lines.append("## アカウント情報")
        summary_lines.append("")
        summary_lines.append(f"- アカウント名: {account_name}")
        summary_lines.append(f"- 行番号: {account_tasks[0].row_idx}")
        if account_tasks[0].account_no:
            summary_lines.append(f"- アカウントNo: {account_tasks[0].account_no}")
        summary_lines.append("")

        for task in account_tasks:
            image_path = account_dir / task.image_filename
            post_path = account_dir / task.post_filename
            prompt_path = account_dir / task.prompt_filename

            # 既存の投稿文ファイルがあればその内容を優先して使う
            if post_path.exists():
                raw_existing_text = post_path.read_text(encoding="utf-8")
                existing_text = strip_markdown_markers(raw_existing_text)
                if existing_text != raw_existing_text.strip():
                    post_path.write_text(existing_text + "\n", encoding="utf-8")
                task.post_text = existing_text
                task.salary_text = extract_salary_text(existing_text, task.kind)
                task.prompt_text = build_banner_prompt(
                    task.kind, task.region, existing_text, task.account_name,
                    task.salary_text, extract_role_phrase(existing_text, task.kind),
                    task.prompt_template,
                    task.prompt_template_name,
                    prompt_templates_dir,
                )
            else:
                post_path.write_text(task.post_text, encoding="utf-8")

            prompt_path.write_text(render_prompt_document(task, image_path, task.post_text, task.prompt_text), encoding="utf-8")

            summary_lines.extend(
                [
                    f"## {task.label_ja}",
                    "",
                    f"- 投稿先地域: {task.region or '未設定'}",
                    f"- 画像保存先: `{image_path}`",
                    f"- 投稿文章保存先: `{post_path}`",
                    f"- プロンプトファイル: `{prompt_path.name}`",
                    "",
                    "### 投稿文章",
                    fenced(task.post_text),
                    "",
                    "### 画像プロンプト",
                    fenced(task.prompt_text),
                    "",
                ]
            )

            manifest.append(
                {
                    "account_no": task.account_no,
                    "account_name": task.account_name,
                    "row_idx": task.row_idx,
                    "kind": task.kind,
                    "label_ja": task.label_ja,
                    "image_col": task.image_col,
                    "post_col": task.post_col,
                    "region": task.region,
                    "post_text": task.post_text,
                    "salary_text": task.salary_text,
                    "prompt_text": task.prompt_text,
                    "prompt_template_name": task.prompt_template_name,
                    "folder_name": task.folder_name,
                    "image_relpath": f"{task.folder_name}/{task.image_filename}",
                    "post_relpath": f"{task.folder_name}/{task.post_filename}",
                    "prompt_relpath": f"{task.folder_name}/{task.prompt_filename}",
                }
            )

        (account_dir / "画像プロンプト一覧.md").write_text("\n".join(summary_lines), encoding="utf-8")

    master_lines = ["# JMTY 週次画像プロンプト一覧", ""]
    for item in manifest:
        master_lines.extend(
            [
                f"## {item['account_name']} / {item['label_ja']}",
                "",
                f"- 行番号: {item['row_idx']}",
                f"- 投稿先地域: {item['region'] or '未設定'}",
                f"- 給与表記: {item['salary_text']}",
                f"- 種別: {item['label_ja']}",
                f"- 画像保存先: `{item['image_relpath']}`",
                f"- 投稿文章保存先: `{item['post_relpath']}`",
                "",
                "### 画像プロンプト",
                fenced(item["prompt_text"]),
                "",
            ]
        )

    (output_root / "画像プロンプト一覧.md").write_text("\n".join(master_lines), encoding="utf-8")
    (output_root / "tasks.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(output_root: Path, prompt_templates_dir: Path) -> None:
    rows = read_sheet_rows()
    tasks = build_tasks(rows, prompt_templates_dir=prompt_templates_dir)
    write_prepare_output(output_root, tasks)
    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "prompt_templates_dir": str(prompt_templates_dir),
                "task_count": len(tasks),
            },
            ensure_ascii=False,
        )
    )


def read_tasks(output_root: Path) -> list[dict]:
    tasks_path = output_root / "tasks.json"
    if not tasks_path.exists():
        raise FileNotFoundError(f"tasks.json が見つかりません: {tasks_path}")
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise RuntimeError(f"tasks.json の形式が不正です: {tasks_path}")
    return tasks


def write_image_only_tree(output_root: Path, tasks: list[dict]) -> Path:
    image_root = output_root / IMAGE_ONLY_DIRNAME
    if image_root.exists():
        shutil.rmtree(image_root)
    image_root.mkdir(parents=True, exist_ok=True)

    copied = 0
    for task in tasks:
        account_dir = output_root / task["folder_name"]
        image_path = account_dir / Path(task["image_relpath"]).name
        if not image_path.exists():
            continue
        target_dir = image_root / task["folder_name"]
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_path, target_dir / image_path.name)
        copied += 1

    (image_root / "manifest.json").write_text(
        json.dumps({"image_count": copied, "source_root": str(output_root)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return image_root


def sync_drive(output_root: Path, purge_existing: bool, purge_account_images: bool, ocr_workers: int | None = None) -> None:
    tasks = read_tasks(output_root)
    for task in tasks:
        validate_manifest_task(task)
    validation = validate_task_files(output_root, tasks, ocr_workers=ocr_workers)
    image_only_root = write_image_only_tree(output_root, tasks)
    emit_progress(42, "Driveフォルダを確認中")
    sheet_regions = load_sheet_region_index()
    folder_ids: dict[str, str] = {
        folder["name"]: folder["id"]
        for folder in list_drive_child_folders(PARENT_FOLDER_ID)
    }
    if purge_existing:
        for folder in list_drive_child_folders(PARENT_FOLDER_ID):
            delete_drive_file(folder["id"])
        folder_ids.clear()

    uploaded_account_docs: set[str] = set()
    purged_account_images: set[str] = set()
    existing_files_by_folder: dict[str, dict[str, dict]] = {}
    manifest: dict = {"items": {}}
    uploaded = 0
    deleted_images = 0

    for index, task in enumerate(tasks, start=1):
        account_name = task["account_name"]
        emit_progress(45 + int((index - 1) / max(len(tasks), 1) * 48), f"Drive反映: {index}/{len(tasks)} {account_name} / {task.get('label_ja', '')}")
        if account_name not in folder_ids:
            folder_ids[account_name] = create_drive_folder(account_name, PARENT_FOLDER_ID)
        folder_id = folder_ids[account_name]
        if purge_account_images and account_name not in purged_account_images:
            deleted_images += delete_drive_image_files(folder_id)
            purged_account_images.add(account_name)
            existing_files_by_folder.pop(folder_id, None)
        existing_files = existing_files_by_folder.get(folder_id)
        if existing_files is None:
            existing_files = drive_files_by_name(list_drive_child_files(folder_id))
            existing_files_by_folder[folder_id] = existing_files

        account_dir = output_root / task["folder_name"]
        image_path = account_dir / Path(task["image_relpath"]).name
        post_path = account_dir / Path(task["post_relpath"]).name
        prompt_path = account_dir / Path(task["prompt_relpath"]).name
        summary_path = account_dir / "画像プロンプト一覧.md"

        image_exists = image_path.exists()
        if not post_path.exists():
            raise FileNotFoundError(f"投稿文章が見つかりません: {post_path}")
        raw_post_text = post_path.read_text(encoding="utf-8")
        cleaned_post_text = strip_markdown_markers(raw_post_text)
        if cleaned_post_text != raw_post_text.strip():
            post_path.write_text(cleaned_post_text + "\n", encoding="utf-8")
        account_key = sanitize_name(account_name)
        task["region"] = sheet_regions.get((account_key, task["kind"])) or region_for_kind(task["kind"], str(task.get("region") or ""))
        task["post_text"] = cleaned_post_text
        task["salary_text"] = extract_salary_text(cleaned_post_text, task["kind"])
        task["prompt_text"] = build_banner_prompt(
            task["kind"],
            task["region"],
            cleaned_post_text,
            account_name,
            task["salary_text"],
            extract_role_phrase(cleaned_post_text, task["kind"]),
        )
        validate_post_text(task, cleaned_post_text)
        if image_exists and image_path.name != expected_image_filename(task["kind"]):
            raise RuntimeError(
                f"画像ファイル名が期待値と一致しません: {account_name} / {task['kind']} -> {image_path.name}"
            )
        prompt_path.write_text(render_prompt_document(task, image_path, task["post_text"], task["prompt_text"]), encoding="utf-8")

        if account_name not in uploaded_account_docs and summary_path.exists():
            replace_drive_file(summary_path, folder_id, existing_files)
            uploaded_account_docs.add(account_name)
        replace_drive_file(post_path, folder_id, existing_files)
        if prompt_path.exists():
            replace_drive_file(prompt_path, folder_id, existing_files)

        manifest_item = {
            "account_name": account_name,
            "kind": task["kind"],
            "label_ja": task.get("label_ja", ""),
            "row_idx": task["row_idx"],
            "image_col": task["image_col"],
            "post_col": task["post_col"],
            "folder_id": folder_id,
            "folder_name": task["folder_name"],
            "image_name": image_path.name,
            "image_file_id": "",
            "image_missing": not image_exists,
            "post_path": str(post_path),
        }
        if image_exists:
            file_id = replace_drive_file(image_path, folder_id, existing_files)
            make_public(file_id)
            uploaded += 1
            manifest_item["image_file_id"] = file_id
        else:
            print(f"⚠️ 画像が見つからないためDrive画像アップロードをスキップします: {image_path}")
        manifest["items"][drive_manifest_key(task)] = manifest_item

    write_drive_sync_manifest(output_root, manifest)
    emit_progress(98, "Drive反映結果を保存中")

    print(json.dumps({"output_root": str(output_root), "uploaded": uploaded, "updated_cells": 0, "manifest": str(output_root / DRIVE_SYNC_MANIFEST_FILENAME)}, ensure_ascii=False))

    print(
        json.dumps(
            {
                "validated_tasks": validation["checked"],
                "missing_images": validation["missing_images"],
                "image_only_root": str(image_only_root),
                "deleted_drive_images": deleted_images,
            },
            ensure_ascii=False,
        )
    )


def resolve_drive_image_file_id(task: dict, manifest: dict, folder_ids: dict[str, str]) -> tuple[str, str]:
    item = manifest.get("items", {}).get(drive_manifest_key(task), {}) if isinstance(manifest.get("items"), dict) else {}
    expected_name = Path(task["image_relpath"]).name
    if isinstance(item, dict):
        manifest_file_id = str(item.get("image_file_id") or "").strip()
        manifest_image_name = str(item.get("image_name") or "").strip()
        if manifest_file_id and (not manifest_image_name or manifest_image_name == expected_name):
            if drive_file_available(manifest_file_id, expected_name):
                return manifest_file_id, "manifest"

    account_name = task["account_name"]
    folder_candidates = []
    for candidate in [
        str(item.get("folder_id") or "") if isinstance(item, dict) else "",
        folder_ids.get(account_name, ""),
    ]:
        if candidate and candidate not in folder_candidates:
            folder_candidates.append(candidate)
    if not folder_candidates:
        return "", "folder_missing"

    for folder_id in folder_candidates:
        drive_file = find_drive_file_by_name(folder_id, expected_name)
        if drive_file:
            return str(drive_file["id"]), "drive_search"
    return "", "image_missing"


def sync_sheet(output_root: Path) -> None:
    tasks = read_tasks(output_root)
    for task in tasks:
        validate_manifest_task(task)
    sheet_rows = read_sheet_rows()
    sheet_accounts = current_sheet_account_rows(sheet_rows)

    manifest = load_drive_sync_manifest(output_root)
    folder_ids: dict[str, str] = {
        folder["name"]: folder["id"]
        for folder in list_drive_child_folders(PARENT_FOLDER_ID)
    }
    updates: list[dict] = []
    warnings: list[str] = []
    row_moves: list[dict] = []
    updated_posts = 0
    updated_images = 0

    for task in tasks:
        account_name = sanitize_name(str(task.get("account_name") or task.get("folder_name") or ""))
        current_sheet_row = sheet_accounts.get(account_name)
        if not current_sheet_row:
            raise RuntimeError(
                f"スプレッドシートにアカウント行がないため反映を中止しました: {account_name}。"
                "GUIでシート読込を実行し、削除済みアカウントのローカルフォルダを整理してください。"
            )
        current_row_idx = int(current_sheet_row["row_idx"])
        old_row_idx = int(task.get("row_idx") or 0)
        if old_row_idx and old_row_idx != current_row_idx:
            row_moves.append(
                {
                    "account_name": account_name,
                    "kind": task.get("kind", ""),
                    "label": task.get("label_ja", ""),
                    "old_row_idx": old_row_idx,
                    "new_row_idx": current_row_idx,
                }
            )
            print(
                f"↪ 行移動を検出: {account_name} / {task.get('label_ja', '')} "
                f"{old_row_idx}行 -> {current_row_idx}行",
                flush=True,
            )
        task["row_idx"] = current_row_idx
        account_dir = output_root / task["folder_name"]
        post_path = account_dir / Path(task["post_relpath"]).name
        if not post_path.exists():
            raise FileNotFoundError(f"投稿文章が見つかりません: {post_path}")

        post_text = strip_markdown_markers(post_path.read_text(encoding="utf-8"))
        updates.append(
            {
                "range": f"{SHEET_NAME}!{task['post_col']}{task['row_idx']}",
                "values": [[sheet_post_text(task["kind"], post_text)]],
            }
        )
        updated_posts += 1

        image_file_id, source = resolve_drive_image_file_id(task, manifest, folder_ids)
        if image_file_id:
            updates.append(
                {
                    "range": f"{SHEET_NAME}!{task['image_col']}{task['row_idx']}",
                    "values": [[f'=IMAGE("https://drive.google.com/uc?id={image_file_id}")']],
                }
            )
            updated_images += 1
        else:
            warning = (
                f"画像IDが見つからないため画像セルは維持します: "
                f"{task['account_name']} / {task['label_ja']} / {source}"
            )
            warnings.append(warning)
            print(f"⚠️ {warning}")

    if updates:
        batch_update_sheet(updates)

    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "updated_cells": len(updates),
                "updated_posts": updated_posts,
                "updated_images": updated_images,
                "skipped_images": len(warnings),
                "warnings": warnings,
                "row_moves": row_moves,
            },
            ensure_ascii=False,
        )
    )


def validate_output(output_root: Path, ocr_workers: int | None = None) -> None:
    tasks = read_tasks(output_root)
    validation = validate_task_files(output_root, tasks, ocr_workers=ocr_workers)
    image_only_root = write_image_only_tree(output_root, tasks)
    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "checked": validation["checked"],
                "missing_images": validation["missing_images"],
                "image_ocr_checked": validation.get("image_ocr_checked", 0),
                "image_ocr_skipped": validation.get("image_ocr_skipped", 0),
                "image_only_root": str(image_only_root),
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="JMTY weekly prompt/image bundle helper")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--prompt-templates-dir", default=str(DEFAULT_PROMPT_TEMPLATES_DIR))
    parser.add_argument(
        "--ocr-workers",
        type=int,
        default=int(os.environ.get("JMTY_OCR_WORKERS", "0") or "0"),
        help="画像OCR検証の並列数。0なら自動で決定する",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("prepare")

    rotate_parser = subparsers.add_parser("rotate-sheet")
    rotate_parser.add_argument("--dry-run", action="store_true")

    sync_parser = subparsers.add_parser("sync-drive")
    sync_parser.add_argument("--purge-existing", action="store_true")
    sync_parser.add_argument(
        "--purge-account-images",
        action="store_true",
        help="アカウントフォルダは残し、既存画像ファイルだけ削除してからアップロードする",
    )

    subparsers.add_parser("sync-sheet")

    subparsers.add_parser("validate-output")

    sheet_validate_parser = subparsers.add_parser("validate-sheet-posts")
    sheet_validate_parser.add_argument(
        "--repair",
        action="store_true",
        help="不一致または品質問題がある投稿文セルだけを更新し、再取得して確認する",
    )
    sheet_validate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="更新せず、修正対象候補だけを出力する（--repair 未指定時の既定動作）",
    )
    sheet_validate_parser.add_argument(
        "--drive-ocr",
        action="store_true",
        help="シート画像セルのDrive画像も一時取得してOCRする（通常はローカル画像とプロンプトメタデータを使う）",
    )

    notify_parser = subparsers.add_parser("notify-improvement")
    notify_parser.add_argument("--title", required=True)
    notify_parser.add_argument("--summary", required=True)
    notify_parser.add_argument("--changed-file", action="append", default=[])
    notify_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    output_root = Path(args.output_root).expanduser()

    try:
        if args.command == "prepare":
            prepare(output_root, Path(args.prompt_templates_dir).expanduser())
        elif args.command == "rotate-sheet":
            rotate_sheet(output_root, dry_run=args.dry_run)
        elif args.command == "sync-drive":
            sync_drive(
                output_root,
                purge_existing=args.purge_existing,
                purge_account_images=args.purge_account_images,
                ocr_workers=args.ocr_workers,
            )
        elif args.command == "sync-sheet":
            sync_sheet(output_root)
        elif args.command == "validate-output":
            validate_output(output_root, ocr_workers=args.ocr_workers)
        elif args.command == "validate-sheet-posts":
            validate_sheet_posts(
                output_root,
                repair=bool(args.repair and not args.dry_run),
                include_drive_ocr=bool(args.drive_ocr),
            )
        elif args.command == "notify-improvement":
            lines = [
                "【ジモティ週次処理 改善メモ】",
                f"- 件名: {args.title}",
                f"- 内容: {args.summary}",
            ]
            if args.changed_file:
                lines.append("- 変更ファイル:")
                lines.extend(f"  - `{path}`" for path in args.changed_file)
            content = "\n".join(lines)
            if args.dry_run:
                print(content)
            else:
                post_discord_jmty_message(content)
    except JmtyWeeklyAssetsError as exc:
        record_and_notify_failure(args.command, output_root, exc)
        raise
    except Exception as exc:
        report_path = record_and_notify_failure(args.command, output_root, exc)
        report_text = f" 改善レポート: {report_path}" if report_path else ""
        raise JmtyWeeklyAssetsError(
            f"予期しないエラーが発生しました。{report_text}\n{type(exc).__name__}: {exc}"
        ) from exc

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JmtyWeeklyAssetsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
