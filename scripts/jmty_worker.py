#!/usr/bin/env python3
# JMTY Control からジョブを取得するMac常駐ワーカーです。
# Vercel側APIを定期ポーリングし、ローカルで処理して結果を返します。
# まずは test ジョブで疎通確認し、重い処理は後続でここへ接続します。
from __future__ import annotations

import argparse
import base64
import hashlib
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
FACTORY_CASES_DIR = ROOT / "inputs/jmty_factory_cases"
REMOTE_SAMPLES_DIR = ROOT / "inputs/jmty_remote_samples"
POST_STYLE_SAMPLES_DIR = ROOT / "inputs/jmty_post_style_samples"
IMAGE_PROMPT_TEMPLATES_DIR = ROOT / "inputs/jmty_image_prompt_templates"
LOCAL_GUI_BASE_URL = os.environ.get("JMTY_LOCAL_GUI_BASE_URL", "http://127.0.0.1:8787")
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
    return hashlib.sha256(f"{account_name}:{kind}".encode("utf-8")).hexdigest()


def build_jmty_snapshot(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    approvals = read_json(APPROVALS_PATH, {})
    validation = read_json(IMAGE_VALIDATION_PATH, {})
    post_rules = first_existing_json(
        [
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
            key = approval_key(account_dir.name, kind)
            validation_item = validation.get(key, {}) if isinstance(validation, dict) else {}
            validation_status = str(validation_item.get("status") or "") if isinstance(validation_item, dict) else ""
            validation_message = str(validation_item.get("message") or validation_item.get("summary") or "") if isinstance(validation_item, dict) else ""
            slots.append(
                {
                    "kind": kind,
                    "label": label,
                    "accountName": account_dir.name,
                    "rowNumber": "",
                    "region": "",
                    "salary": "",
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
    if job_type == "rotate_sheet":
        return "/api/job", {"command": "rotate-sheet"}
    if job_type == "prepare_posts":
        return "/api/job", {"command": "prepare"}
    if job_type == "save_post":
        return "/api/post", {}
    if job_type == "sync_post_to_sheet":
        return "/api/post/sheet-sync", {}
    if job_type == "sync_all_dirty_posts_to_sheet":
        return "/api/post/sheet-sync-all", {}
    if job_type in {"rewrite_post_with_style", "rewrite_all_posts_with_style"}:
        return "/api/post-rewrite", {"all": job_type == "rewrite_all_posts_with_style"}
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


def handle_local_gui_bridge_job(job: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    job_type = str(job.get("type"))
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    path, defaults = local_gui_path_for_job(job_type)
    bridged_payload = {**defaults, **payload}
    response = request_local_gui(path, bridged_payload)
    snapshot = build_jmty_snapshot()
    result = {
        "message": f"{job_type} completed through local JMTY GUI bridge",
        "changed": True,
        "warnings": [],
        "localGuiResponse": response,
        "snapshot": snapshot,
        "processedAt": now_iso(),
    }
    return result, [f"Forwarded {job_type} to {LOCAL_GUI_BASE_URL}{path} at {now_iso()}"]


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
            "rotate_sheet",
            "prepare_posts",
            "save_post",
            "sync_post_to_sheet",
            "sync_all_dirty_posts_to_sheet",
            "rewrite_post_with_style",
            "rewrite_all_posts_with_style",
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
