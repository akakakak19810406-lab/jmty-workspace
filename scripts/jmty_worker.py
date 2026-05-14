#!/usr/bin/env python3
# JMTY Control からジョブを取得するMac常駐ワーカーです。
# Vercel側APIを定期ポーリングし、ローカルで処理して結果を返します。
# まずは test ジョブで疎通確認し、重い処理は後続でここへ接続します。
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import platform
import subprocess
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_OUTPUT_ROOT = ROOT / "outputs/jmty-weekly/current"
APPROVALS_PATH = ROOT / "outputs/jmty-gui/approvals.json"
IMAGE_VALIDATION_PATH = ROOT / "outputs/jmty-gui/image_validation.json"
SHEET_CACHE_PATH = ROOT / "outputs/jmty-gui/sheet_cache.json"
FACTORY_CASES_DIR = ROOT / "inputs/jmty_factory_cases"
REMOTE_SAMPLES_DIR = ROOT / "inputs/jmty_remote_samples"
POST_STYLE_SAMPLES_DIR = ROOT / "inputs/jmty_post_style_samples"
IMAGE_PROMPT_TEMPLATES_DIR = ROOT / "inputs/jmty_image_prompt_templates"
LOCAL_GUI_BASE_URL = os.environ.get("JMTY_LOCAL_GUI_BASE_URL", "http://127.0.0.1:8787")
LOCAL_GUI_JOB_TIMEOUT_SECONDS = int(os.environ.get("JMTY_LOCAL_GUI_JOB_TIMEOUT_SECONDS", "1800"))
LOCAL_GUI_JOB_POLL_SECONDS = int(os.environ.get("JMTY_LOCAL_GUI_JOB_POLL_SECONDS", "5"))
GIT_HISTORY_LIMIT = max(1, int(os.environ.get("JMTY_GIT_HISTORY_LIMIT", "12")))
GIT_SAVE_BRANCHES = {
    "post": "script-save",
    "image": "image-save",
}
SLOT_DEFS = [
    ("factory", "工場", "工場の投稿文章.md", "工場_画像プロンプト.md", ["工場.jpg", "工場.png", "工場.jpeg"]),
    ("remote1", "在宅1", "在宅1の投稿文章.md", "在宅1_画像プロンプト.md", ["在宅1.jpg", "在宅1.png", "在宅1.jpeg"]),
    ("remote2", "在宅2", "在宅2の投稿文章.md", "在宅2_画像プロンプト.md", ["在宅2.jpg", "在宅2.png", "在宅2.jpeg"]),
]


@dataclass(frozen=True)
class WorkerConfig:
    base_url: str
    token: str | None
    worker_id: str
    interval_seconds: int
    once: bool
    dry_run: bool


class ApiError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except json.JSONDecodeError:
        return fallback


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def file_updated_at(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    except OSError:
        return ""


def preview_text(text: str, limit: int = 180) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "..."


def rel_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def git_run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"git exited with {result.returncode}").strip())
    return result


def git_ref_exists(ref: str) -> bool:
    return git_run(["rev-parse", "--verify", ref], check=False).returncode == 0


def git_blob_text(commit: str, rel_path: str) -> str:
    if not rel_path:
        return ""
    result = git_run(["show", f"{commit}:{rel_path}"], check=False)
    return result.stdout if result.returncode == 0 else ""


def list_git_history(history_type: str, path: Path | None, limit: int = GIT_HISTORY_LIMIT) -> list[dict[str, Any]]:
    if path is None:
        return []
    branch = GIT_SAVE_BRANCHES.get(history_type)
    if not branch:
        return []
    try:
        rel_path = rel_to_root(path)
    except Exception:
        return []
    branch_ref = f"refs/heads/{branch}"
    if not git_ref_exists(branch_ref):
        return []
    result = git_run(["log", f"--max-count={limit}", "--format=%H%x00%cI%x00%s", branch_ref, "--", rel_path], check=False)
    if result.returncode != 0:
        return []
    entries: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\x00", 2)
        if len(parts) != 3:
            continue
        commit, committed_at, subject = parts
        entry = {
            "type": history_type,
            "branch": branch,
            "commit": commit,
            "shortCommit": commit[:12],
            "committedAt": committed_at,
            "subject": subject,
            "path": rel_path,
        }
        if history_type == "post":
            text = git_blob_text(commit, rel_path)
            entry["title"] = next((item.strip() for item in text.splitlines() if item.strip()), "")
            entry["preview"] = preview_text(text, 140)
        entries.append(entry)
    return entries


def split_remote_regions(value: Any) -> tuple[str, str]:
    parts = [line.strip() for line in str(value or "").replace("\r", "\n").split("\n") if line.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], parts[1]


def region_for_slot(kind: str, value: Any) -> str:
    if kind == "remote1":
        return split_remote_regions(value)[0]
    if kind == "remote2":
        return split_remote_regions(value)[1]
    return str(value or "").strip()


def normalize_account_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_task_index(output_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    raw_tasks = read_json(output_root / "tasks.json", [])
    tasks = raw_tasks if isinstance(raw_tasks, list) else []
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        kind = str(task.get("kind") or "")
        for name_key in ("folder_name", "account_name"):
            account_name = normalize_account_name(task.get(name_key))
            if account_name and kind:
                index[(account_name, kind)] = task
    return index


def sheet_value(values: dict[str, Any], key: str) -> str:
    item = values.get(key, {}) if isinstance(values, dict) else {}
    return str(item.get("value") or "").strip() if isinstance(item, dict) else ""


def build_sheet_region_index() -> dict[tuple[str, str], str]:
    cache = read_json(SHEET_CACHE_PATH, {})
    accounts = cache.get("accounts", []) if isinstance(cache, dict) else []
    index: dict[tuple[str, str], str] = {}
    for account in accounts:
        if not isinstance(account, dict):
            continue
        account_name = normalize_account_name(account.get("account_name"))
        values = account.get("values") if isinstance(account.get("values"), dict) else {}
        if not account_name:
            continue
        remote1_region, remote2_region = split_remote_regions(sheet_value(values, "remote_region"))
        index[(account_name, "factory")] = sheet_value(values, "factory_region")
        index[(account_name, "remote1")] = sheet_value(values, "remote1_region") or remote1_region
        index[(account_name, "remote2")] = sheet_value(values, "remote2_region") or remote2_region
    return index


def list_text_files(base: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    if not base.exists():
        return files
    for path in sorted([*base.glob("*.md"), *base.glob("*.txt")]):
        if not path.is_file():
            continue
        files.append(
            {
                "name": path.name,
                "path": rel_to_root(path),
                "text": read_text(path),
                "updatedAt": file_updated_at(path),
            }
        )
    return files


def list_project_samples() -> dict[str, Any]:
    return {
        "groups": [
            {"label": "工場案件素材", "category": "factory", "files": list_text_files(FACTORY_CASES_DIR)},
            {"label": "在宅案件素材", "category": "remote", "files": list_text_files(REMOTE_SAMPLES_DIR)},
        ]
    }


def list_post_style_samples() -> dict[str, Any]:
    return {
        "groups": [
            {
                "label": "工場投稿文スタイル見本",
                "category": "factory",
                "files": list_text_files(POST_STYLE_SAMPLES_DIR / "factory"),
            },
            {
                "label": "在宅投稿文スタイル見本",
                "category": "remote",
                "files": list_text_files(POST_STYLE_SAMPLES_DIR / "remote"),
            },
        ]
    }


def list_image_prompt_templates() -> dict[str, Any]:
    return {"files": list_text_files(IMAGE_PROMPT_TEMPLATES_DIR)}


def first_existing_json(paths: list[Path]) -> Any:
    for path in paths:
        if path.exists():
            return read_json(path, {})
    return {}


def image_data_uri(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    try:
        with tempfile.NamedTemporaryFile(suffix=path.suffix or ".jpg", delete=False) as temp:
            temp_path = Path(temp.name)
        try:
            subprocess.run(["sips", "-Z", "420", str(path), "--out", str(temp_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            raw = temp_path.read_bytes()
            mime = mimetypes.guess_type(temp_path.name)[0] or mime
        finally:
            try:
                temp_path.unlink()
            except OSError:
                pass
    except Exception:
        raw = path.read_bytes() if path.stat().st_size <= 900_000 else b""
    if not raw:
        return ""
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def approval_key(account_name: str, kind: str) -> str:
    return f"{account_name}::{kind}"


def build_jmty_snapshot(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    approvals = read_json(APPROVALS_PATH, {})
    validation = read_json(IMAGE_VALIDATION_PATH, {})
    post_rules = first_existing_json(
        [
            ROOT / "inputs/jmty_post_generation_rules.json",
            ROOT / "outputs/jmty-gui/post_rules.json",
            ROOT / "inputs/jmty_post_rules.json",
            ROOT / "inputs/jmty_post_rules/rules.json",
        ]
    )
    image_rules = first_existing_json(
        [
            ROOT / "outputs/jmty-gui/image_rules.json",
            ROOT / "inputs/jmty_image_rules.json",
            ROOT / "inputs/jmty_image_prompt_rules.json",
        ]
    )
    task_index = build_task_index(output_root)
    sheet_region_index = build_sheet_region_index()
    accounts: list[dict[str, Any]] = []

    if not output_root.exists():
        return {
            "syncedAt": now_iso(),
            "sourceRoot": str(output_root),
            "workerStatus": {"status": "online", "lastSeenAt": now_iso()},
            "gwsStatus": {"label": "未確認", "ok": False},
            "syncSummary": {"dirtyCount": 0, "items": []},
            "accountCount": 0,
            "accounts": [],
            "postRules": post_rules,
            "imageRules": image_rules,
            "projectSamples": list_project_samples(),
            "postStyleSamples": list_post_style_samples(),
            "imagePromptTemplates": list_image_prompt_templates(),
            "logsSummary": [],
        }

    for account_dir in sorted([item for item in output_root.iterdir() if item.is_dir()], key=lambda item: item.name):
        if account_dir.name.startswith("_"):
            continue
        slots: list[dict[str, Any]] = []
        for kind, label, post_name, prompt_name, image_names in SLOT_DEFS:
            post_text = read_text(account_dir / post_name)
            prompt_text = read_text(account_dir / prompt_name)
            image_path = next((account_dir / name for name in image_names if (account_dir / name).exists()), None)
            history_image_path = image_path or account_dir / (image_names[1] if len(image_names) > 1 else image_names[0])
            normalized_account_name = normalize_account_name(account_dir.name)
            task = task_index.get((normalized_account_name, kind), {})
            task_region = region_for_slot(kind, task.get("region", "") if isinstance(task, dict) else "")
            region = sheet_region_index.get((normalized_account_name, kind)) or task_region
            key = approval_key(account_dir.name, kind)
            validation_item = validation.get(key, {}) if isinstance(validation, dict) else {}
            validation_status = str(validation_item.get("status") or "") if isinstance(validation_item, dict) else ""
            validation_message = str(validation_item.get("message") or validation_item.get("summary") or "") if isinstance(validation_item, dict) else ""
            slots.append(
                {
                    "kind": kind,
                    "label": label,
                    "accountName": account_dir.name,
                    "rowNumber": task.get("row_idx", "") if isinstance(task, dict) else "",
                    "region": region,
                    "salary": task.get("salary_text", "") if isinstance(task, dict) else "",
                    "postText": post_text,
                    "localPostText": post_text,
                    "sheetPostText": "",
                    "postPreview": preview_text(post_text),
                    "postSyncStatus": "local_only" if post_text else "missing",
                    "promptText": prompt_text,
                    "promptPreview": preview_text(prompt_text, 120),
                    "hasPost": bool(post_text),
                    "hasPrompt": bool(prompt_text),
                    "hasImage": image_path is not None,
                    "imageFile": image_path.name if image_path else None,
                    "imageThumbnailBase64": image_data_uri(image_path),
                    "approved": bool(approvals.get(key, {}).get("approved")) if isinstance(approvals, dict) else False,
                    "validationStatus": validation_status,
                    "validationMessage": validation_message,
                    "postHistory": list_git_history("post", account_dir / post_name),
                    "imageHistory": list_git_history("image", history_image_path),
                    "updatedAt": file_updated_at(account_dir / post_name) if post_text else "",
                }
            )
        accounts.append({"accountName": account_dir.name, "slots": slots})

    return {
        "syncedAt": now_iso(),
        "sourceRoot": str(output_root),
        "workerStatus": {"status": "online", "lastSeenAt": now_iso()},
        "gwsStatus": {"label": "未確認", "ok": False},
        "syncSummary": {"dirtyCount": 0, "items": []},
        "accountCount": len(accounts),
        "accounts": accounts,
        "postRules": post_rules,
        "imageRules": image_rules,
        "projectSamples": list_project_samples(),
        "postStyleSamples": list_post_style_samples(),
        "imagePromptTemplates": list_image_prompt_templates(),
        "logsSummary": [],
    }


def request_json(config: WorkerConfig, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{config.base_url.rstrip('/')}{path}"
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if config.token:
        headers["Authorization"] = f"Bearer {config.token}"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        raise ApiError(f"{method} {url} failed: {error.code} {raw}") from error
    except urllib.error.URLError as error:
        raise ApiError(f"{method} {url} failed: {error.reason}") from error


def claim_job(config: WorkerConfig) -> dict[str, Any] | None:
    response = request_json(config, "POST", "/api/jobs/claim", {"workerId": config.worker_id})
    job = response.get("job")
    return job if isinstance(job, dict) else None


def complete_job(
    config: WorkerConfig,
    job: dict[str, Any],
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    logs: list[str] | None = None,
) -> None:
    job_id = str(job["id"])
    request_json(
        config,
        "POST",
        f"/api/jobs/{job_id}/result",
        {
            "workerId": config.worker_id,
            "status": status,
            "result": result or {},
            "error": error,
            "logs": logs or [],
        },
    )


def handle_test_job(job: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    result = {
        "message": "test job processed on Mac worker",
        "payload": payload,
        "cwd": str(ROOT),
        "python": sys.version.split()[0],
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "processedAt": now_iso(),
    }
    return result, [f"Handled test job locally at {now_iso()}"]


def handle_known_placeholder(job: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    job_type = str(job.get("type"))
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    result = {
        "message": f"{job_type} is queued correctly, but local implementation is not connected yet",
        "payload": payload,
        "processedAt": now_iso(),
    }
    return result, [f"Placeholder handler completed for {job_type} at {now_iso()}"]


def local_gui_path_for_job(job_type: str) -> tuple[str, dict[str, Any]]:
    if job_type == "generate_image":
        return "/api/image-generate", {}
    if job_type == "validate_image":
        return "/api/image-validate", {}
    if job_type == "sync_drive":
        return "/api/job", {"command": "sync-drive"}
    if job_type == "sync_sheet":
        return "/api/job", {"command": "sync-sheet"}
    if job_type == "rotate_sheet":
        return "/api/job", {"command": "rotate-sheet"}
    if job_type == "prepare_posts":
        return "/api/post-generate", {"scope": "all"}
    if job_type == "save_post":
        return "/api/post", {}
    if job_type == "sync_post_to_sheet":
        return "/api/post/sheet-sync", {}
    if job_type == "sync_all_dirty_posts_to_sheet":
        return "/api/post/sheet-sync-all", {}
    if job_type == "restore_post_history":
        return "/api/history/restore", {"history_type": "post"}
    if job_type == "restore_image_history":
        return "/api/history/restore", {"history_type": "image"}
    if job_type == "rewrite_post_with_style":
        return "/api/post-generate", {}
    if job_type == "rewrite_all_posts_with_style":
        return "/api/post-generate", {"scope": "all"}
    if job_type == "rewrite_failed_validation_posts":
        return "/api/post-generate", {"scope": "validation_failed"}
    if job_type == "save_image_prompt":
        return "/api/prompt", {}
    if job_type == "cancel_image":
        return "/api/image/cancel", {}
    if job_type == "approve_image":
        return "/api/approve", {}
    if job_type == "save_project_sample":
        return "/api/project-samples/save", {}
    if job_type == "save_post_style_sample":
        return "/api/post-style-sample/save", {}
    if job_type == "delete_post_style_sample":
        return "/api/post-style-sample/delete", {}
    if job_type == "save_post_rules":
        return "/api/post-rules", {}
    if job_type == "save_image_rules":
        return "/api/image-rules", {}
    if job_type == "reload_sheet":
        return "/api/sheet/reload", {}
    if job_type == "save_sheet_mapping":
        return "/api/sheet/mapping", {}
    raise ValueError(f"Unsupported bridge job type: {job_type}")


def request_local_gui(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{LOCAL_GUI_BASE_URL.rstrip('/')}{path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        raise ApiError(f"local GUI {path} failed: {error.code} {raw}") from error
    except urllib.error.URLError as error:
        raise ApiError(
            f"local GUI {path} failed: {error.reason}. Start local GUI with `jmty` or set JMTY_LOCAL_GUI_BASE_URL."
        ) from error


def request_local_gui_get(path: str) -> dict[str, Any]:
    url = f"{LOCAL_GUI_BASE_URL.rstrip('/')}{path}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        raise ApiError(f"local GUI {path} failed: {error.code} {raw}") from error
    except urllib.error.URLError as error:
        raise ApiError(
            f"local GUI {path} failed: {error.reason}. Start local GUI with `jmty` or set JMTY_LOCAL_GUI_BASE_URL."
        ) from error


def wait_for_local_gui_job(response: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    job = response.get("job") if isinstance(response.get("job"), dict) else {}
    job_id = str(job.get("id") or "")
    if not job_id or str(job.get("status") or "") != "running":
        return response, []

    deadline = time.monotonic() + LOCAL_GUI_JOB_TIMEOUT_SECONDS
    logs = [f"Waiting for local GUI job {job_id} at {now_iso()}"]
    last_job = job
    last_state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        time.sleep(max(1, LOCAL_GUI_JOB_POLL_SECONDS))
        state_response = request_local_gui_get("/api/state")
        state = state_response.get("state") if isinstance(state_response.get("state"), dict) else {}
        last_state = state
        local_jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
        matching = next((item for item in local_jobs if isinstance(item, dict) and str(item.get("id")) == job_id), None)
        if not matching:
            continue
        last_job = matching
        if str(matching.get("status") or "") != "running":
            logs.append(f"Local GUI job {job_id} finished with {matching.get('status')} at {now_iso()}")
            break
    else:
        raise TimeoutError(f"local GUI job {job_id} did not finish within {LOCAL_GUI_JOB_TIMEOUT_SECONDS} seconds")

    final_response = {**response, "job": last_job, "state": last_state}
    if str(last_job.get("status") or "") == "failed":
        raise ApiError(str(last_job.get("stderr") or last_job.get("stdout") or f"local GUI job {job_id} failed"))
    return final_response, logs


def handle_local_gui_bridge_job(job: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    job_type = str(job.get("type"))
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    path, defaults = local_gui_path_for_job(job_type)
    bridged_payload = {**defaults, **payload}
    response = request_local_gui(path, bridged_payload)
    wait_logs: list[str] = []
    if isinstance(response.get("job"), dict):
        response, wait_logs = wait_for_local_gui_job(response)
    snapshot = build_jmty_snapshot()
    result = {
        "message": f"{job_type} completed through local JMTY GUI bridge",
        "changed": True,
        "warnings": [],
        "localGuiResponse": response,
        "snapshot": snapshot,
        "processedAt": now_iso(),
    }
    return result, [f"Forwarded {job_type} to {LOCAL_GUI_BASE_URL}{path} at {now_iso()}", *wait_logs]


def handle_sync_state_job() -> tuple[dict[str, Any], list[str]]:
    snapshot = build_jmty_snapshot()
    result = {
        "message": "JMTY GUI state snapshot synced from Mac",
        "snapshot": snapshot,
        "processedAt": now_iso(),
    }
    return result, [f"Synced {snapshot['accountCount']} accounts at {now_iso()}"]


def process_job(config: WorkerConfig, job: dict[str, Any]) -> None:
    job_type = str(job.get("type"))
    print(f"[{now_iso()}] claimed {job.get('id')} type={job_type}", flush=True)

    if config.dry_run:
        result = {"message": "dry run: job was claimed but not executed", "type": job_type}
        complete_job(config, job, "done", result=result, logs=[f"Dry run completed at {now_iso()}"])
        return

    try:
        if job_type == "test":
            result, logs = handle_test_job(job)
        elif job_type == "sync_state":
            result, logs = handle_sync_state_job()
        elif job_type in {
            "generate_image",
            "validate_image",
            "sync_drive",
            "sync_sheet",
            "rotate_sheet",
            "prepare_posts",
            "save_post",
            "sync_post_to_sheet",
            "sync_all_dirty_posts_to_sheet",
            "restore_post_history",
            "restore_image_history",
            "rewrite_post_with_style",
            "rewrite_all_posts_with_style",
            "rewrite_failed_validation_posts",
            "save_image_prompt",
            "cancel_image",
            "approve_image",
            "save_project_sample",
            "save_post_style_sample",
            "delete_post_style_sample",
            "save_post_rules",
            "save_image_rules",
            "reload_sheet",
            "save_sheet_mapping",
        }:
            result, logs = handle_local_gui_bridge_job(job)
        else:
            raise ValueError(f"Unsupported job type: {job_type}")
        complete_job(config, job, "done", result=result, logs=logs)
        print(f"[{now_iso()}] completed {job.get('id')}", flush=True)
    except Exception as error:
        complete_job(config, job, "failed", error=str(error), logs=[f"Failed locally at {now_iso()}"])
        print(f"[{now_iso()}] failed {job.get('id')}: {error}", flush=True)


def run_loop(config: WorkerConfig) -> None:
    print(
        f"[{now_iso()}] worker started worker_id={config.worker_id} base_url={config.base_url} interval={config.interval_seconds}s",
        flush=True,
    )
    while True:
        try:
            job = claim_job(config)
            if job:
                process_job(config, job)
            else:
                print(f"[{now_iso()}] no queued job", flush=True)
        except ApiError as error:
            print(f"[{now_iso()}] API error: {error}", flush=True)

        if config.once:
            return
        time.sleep(config.interval_seconds)


def parse_args() -> WorkerConfig:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Poll JMTY Control jobs from Vercel and run them on this Mac.")
    parser.add_argument("--base-url", default=os.environ.get("JMTY_CONTROL_BASE_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--token", default=os.environ.get("JMTY_WORKER_TOKEN"))
    parser.add_argument("--worker-id", default=os.environ.get("JMTY_WORKER_ID") or f"mac-{socket.gethostname()}")
    parser.add_argument("--interval", type=int, default=int(os.environ.get("JMTY_WORKER_INTERVAL", DEFAULT_INTERVAL_SECONDS)))
    parser.add_argument("--once", action="store_true", help="Run one polling cycle and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Claim and complete jobs without executing handlers.")
    args = parser.parse_args()

    return WorkerConfig(
        base_url=args.base_url,
        token=args.token,
        worker_id=args.worker_id,
        interval_seconds=max(5, args.interval),
        once=args.once,
        dry_run=args.dry_run,
    )


def main() -> int:
    config = parse_args()
    run_loop(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
