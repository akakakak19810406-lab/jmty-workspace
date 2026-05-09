from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


JMTY_ROOT_ENV = "JMTY_ROOT"
LOCAL_STATE_FILENAME = "local_state.json"
WORKED_BEFORE_FILENAME = "worked_before_machines.json"
LOCAL_STATE_APP_NAME = "jmty"
DISCORD_GIT_WEBHOOK_URL_ENV = "JMTY_DISCORD_GIT_WEBHOOK_URL"
DISCORD_GIT_WEBHOOK_URL_KEY = "discord_git_webhook_url"
DISCORD_GIT_WEBHOOK_SHARED_RELATIVE_PATH = Path("config") / "discord-git-webhook.json"
DISCORD_GIT_WEBHOOK_SHARED_URL_KEY = "url"
DISCORD_JMTY_WEBHOOK_URL_ENV = "JMTY_DISCORD_JMTY_WEBHOOK_URL"
DISCORD_JMTY_WEBHOOK_SHARED_RELATIVE_PATH = Path("config") / "discord-jmty-webhook.json"
PYTHON_RUNTIME_IMAGE = "jmty/python-skill-runtime:3.11.9"
VOICEVOX_ENGINE_IMAGE = "voicevox/voicevox_engine"
VOICEVOX_ENGINE_CONTAINER = "jmty-voicevox-engine"
CONTAINER_REPO_ROOT = PurePosixPath("/workspace/jmty")
CONTAINER_SHARED_ROOT = PurePosixPath("/workspace/jmty-shared")
CONTAINER_HOME = PurePosixPath("/tmp/jmty-home")
REPO_GIT_HOOKS_DIRNAME = ".githooks"
GIT_LFS_POINTER_VERSION = "version https://git-lfs.github.com/spec/v1"
GITHUB_FREE_GIT_LFS_STORAGE_BYTES = 10 * 1024**3
MAX_GIT_LFS_POINTER_BLOB_BYTES = 2048
GIT_LFS_RESERVED_BYTES_ENV = "JMTY_GIT_LFS_RESERVED_BYTES"
GIT_LFS_FREE_STORAGE_BYTES_ENV = "JMTY_GIT_LFS_FREE_STORAGE_BYTES"


@dataclass(frozen=True)
class GitLfsFreePlanStatus:
    remote_name: str
    remote_url: str | None
    free_storage_bytes: int
    reserved_bytes: int
    available_bytes: int
    current_bytes: int
    incoming_bytes: int
    projected_bytes: int
    current_object_count: int
    incoming_object_count: int
    projected_object_count: int
    has_lfs_content: bool
    git_lfs_installed: bool
    within_budget: bool
    rejection_reason: str | None
    warning: str | None


def get_config_dir(app_name: str) -> Path:
    if sys.platform == "win32":
        base = Path(
            os.environ.get(
                "APPDATA",
                str(Path.home() / "AppData" / "Roaming"),
            )
        )
    else:
        base = Path(
            os.environ.get(
                "XDG_CONFIG_HOME",
                str(Path.home() / ".config"),
            )
        )
    return base / app_name


def get_local_state_path() -> Path:
    return get_config_dir(LOCAL_STATE_APP_NAME) / LOCAL_STATE_FILENAME


def get_worked_before_path() -> Path:
    return get_config_dir(LOCAL_STATE_APP_NAME) / WORKED_BEFORE_FILENAME


def _load_local_state() -> dict[str, str]:
    state_path = get_local_state_path()
    if not state_path.exists():
        return {}

    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(loaded, dict):
        return {}

    state: dict[str, str] = {}
    for key, value in loaded.items():
        if isinstance(key, str) and isinstance(value, str):
            state[key] = value
    return state


def _save_local_state(state: dict[str, str]) -> Path:
    state_path = get_local_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return state_path


def _load_worked_before_state() -> dict[str, dict[str, str]]:
    state_path = get_worked_before_path()
    if not state_path.exists():
        return {}

    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(loaded, dict):
        return {}

    raw_machines = loaded.get("machines")
    if not isinstance(raw_machines, dict):
        return {}

    machines: dict[str, dict[str, str]] = {}
    for machine_id, entry in raw_machines.items():
        if not isinstance(machine_id, str):
            continue
        normalized: dict[str, str] = {}
        if isinstance(entry, dict):
            for key, value in entry.items():
                if isinstance(key, str) and isinstance(value, str):
                    normalized[key] = value
        machines[machine_id] = normalized
    return machines


def _save_worked_before_state(machines: dict[str, dict[str, str]]) -> Path:
    state_path = get_worked_before_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"machines": machines}
    state_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return state_path


def _normalize_path(path: Path) -> Path:
    expanded = path.expanduser()
    try:
        return expanded.resolve(strict=False)
    except OSError:
        return expanded.absolute()


def _looks_like_repo_root(path: Path) -> bool:
    return (path / ".agent" / "skills").is_dir() and (path / "AGENTS.md").is_file()


def _search_repo_root(start: Path) -> Path | None:
    candidate = _normalize_path(start)
    if candidate.is_file():
        candidate = candidate.parent

    for current in (candidate, *candidate.parents):
        if _looks_like_repo_root(current):
            return current
    return None


def _git_reported_repo_root(start: Path) -> Path | None:
    search_base = _normalize_path(start)
    if search_base.is_file():
        search_base = search_base.parent

    try:
        completed = subprocess.run(
            ["git", "-C", str(search_base), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None

    candidate = _normalize_path(Path(completed.stdout.strip()))
    if _looks_like_repo_root(candidate):
        return candidate
    return None


def get_saved_repo_root() -> Path | None:
    saved = _load_local_state().get("repo_root")
    if not saved:
        return None

    candidate = _normalize_path(Path(saved))
    if _looks_like_repo_root(candidate):
        return candidate
    return None


def save_repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root is None:
        candidate = get_repo_root()
    else:
        raw_path = Path(repo_root)
        if not raw_path.is_absolute():
            raw_path = Path.cwd() / raw_path
        candidate = _normalize_path(raw_path)

    if not _looks_like_repo_root(candidate):
        raise RuntimeError(f"Repository root was not found at: {candidate}")

    state = _load_local_state()
    state["repo_root"] = str(candidate)
    _save_local_state(state)
    return candidate


def get_saved_discord_git_webhook_url() -> str | None:
    saved = _load_local_state().get(DISCORD_GIT_WEBHOOK_URL_KEY)
    if saved is None:
        return None
    normalized = saved.strip()
    return normalized or None


def get_shared_discord_git_webhook_path(repo_root: Path | None = None) -> Path:
    resolved_root = repo_root if repo_root is not None else get_repo_root()
    return resolved_root / DISCORD_GIT_WEBHOOK_SHARED_RELATIVE_PATH


def get_shared_discord_git_webhook_url(repo_root: Path | None = None) -> str | None:
    config_path = get_shared_discord_git_webhook_path(repo_root)
    if not config_path.exists():
        return None

    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(loaded, dict):
        return None

    saved = loaded.get(DISCORD_GIT_WEBHOOK_SHARED_URL_KEY)
    if not isinstance(saved, str):
        return None

    normalized = saved.strip()
    return normalized or None


def get_discord_git_webhook_url() -> tuple[str | None, str | None]:
    env_value = os.environ.get(DISCORD_GIT_WEBHOOK_URL_ENV)
    if env_value:
        normalized = env_value.strip()
        if normalized:
            return normalized, "env"

    shared = get_shared_discord_git_webhook_url()
    if shared:
        return shared, "repo-shared"

    saved = get_saved_discord_git_webhook_url()
    if saved:
        return saved, "local-state"

    return None, None


def save_discord_git_webhook_url(url: str) -> Path:
    normalized = url.strip()
    if not normalized:
        raise RuntimeError("Discord webhook URL is empty.")

    state = _load_local_state()
    state[DISCORD_GIT_WEBHOOK_URL_KEY] = normalized
    return _save_local_state(state)


def save_shared_discord_git_webhook_url(
    url: str,
    repo_root: Path | None = None,
) -> Path:
    normalized = url.strip()
    if not normalized:
        raise RuntimeError("Discord webhook URL is empty.")

    config_path = get_shared_discord_git_webhook_path(repo_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {DISCORD_GIT_WEBHOOK_SHARED_URL_KEY: normalized},
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def clear_discord_git_webhook_url() -> bool:
    state = _load_local_state()
    if DISCORD_GIT_WEBHOOK_URL_KEY not in state:
        return False

    state.pop(DISCORD_GIT_WEBHOOK_URL_KEY)
    _save_local_state(state)
    return True


def clear_shared_discord_git_webhook_url(repo_root: Path | None = None) -> bool:
    config_path = get_shared_discord_git_webhook_path(repo_root)
    if not config_path.exists():
        return False

    config_path.unlink()
    return True


def get_discord_jmty_webhook_url() -> tuple[str | None, str | None]:
    """ジモティー画像変更通知用Webhookを返す。env → config/discord-jmty-webhook.json の順で読む。"""
    env_value = os.environ.get(DISCORD_JMTY_WEBHOOK_URL_ENV)
    if env_value:
        normalized = env_value.strip()
        if normalized:
            return normalized, "env"

    repo_root = get_repo_root()
    config_path = repo_root / DISCORD_JMTY_WEBHOOK_SHARED_RELATIVE_PATH
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            url = loaded.get("url", "").strip() if isinstance(loaded, dict) else ""
            if url:
                return url, "repo-shared"
        except (OSError, json.JSONDecodeError):
            pass

    return None, None


def save_discord_jmty_webhook_url(url: str, repo_root: Path | None = None) -> Path:
    """ジモティーWebhook URLを config/discord-jmty-webhook.json に保存する。"""
    normalized = url.strip()
    if not normalized:
        raise RuntimeError("Discord jmty webhook URL is empty.")

    resolved_root = repo_root if repo_root is not None else get_repo_root()
    config_path = resolved_root / DISCORD_JMTY_WEBHOOK_SHARED_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"url": normalized}, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config_path


def get_repo_root() -> Path:
    env_override = os.environ.get(JMTY_ROOT_ENV)
    if env_override:
        env_path = _normalize_path(Path(env_override))
        if _looks_like_repo_root(env_path):
            return env_path

    saved_root = get_saved_repo_root()
    if saved_root is not None:
        return saved_root

    for resolver in (
        lambda: _search_repo_root(Path.cwd()),
        lambda: _git_reported_repo_root(Path.cwd()),
        lambda: _search_repo_root(Path(__file__)),
        lambda: _git_reported_repo_root(Path(__file__)),
    ):
        candidate = resolver()
        if candidate is not None:
            return candidate

    raise RuntimeError(
        "jmty repository root could not be detected. "
        f"Set {JMTY_ROOT_ENV} or run setup-local-machine once."
    )


def resolve_input_path(path_str: str) -> Path:
    candidate = Path(path_str).expanduser()
    if candidate.is_absolute():
        return candidate

    cwd_path = Path.cwd() / candidate
    if cwd_path.exists():
        return cwd_path.resolve()

    return (get_repo_root() / candidate).resolve()


def _bootstrap_python() -> Path:
    current = Path(sys.executable)
    if current.exists():
        return current

    for name in ("python3", "python", "py"):
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)

    raise RuntimeError("Python interpreter was not found.")


def _skill_python_candidates() -> Iterable[Path]:
    repo_root = get_repo_root()
    skill_root = repo_root / "skill-runtime" / ".venv"

    env_override = os.environ.get("JMTY_SKILL_PYTHON")
    if env_override:
        yield Path(env_override).expanduser()

    yield skill_root / "Scripts" / "python.exe"
    yield skill_root / "Scripts" / "python"
    yield skill_root / "bin" / "python3"
    yield skill_root / "bin" / "python"


def get_skill_python() -> Path | None:
    for candidate in _skill_python_candidates():
        if candidate.exists():
            return candidate.expanduser().absolute()
    return None


def ensure_skill_venv() -> Path:
    existing = get_skill_python()
    if existing is not None:
        return existing

    repo_root = get_repo_root()
    skill_root = repo_root / "skill-runtime"
    venv_dir = skill_root / ".venv"
    skill_root.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [str(_bootstrap_python()), "-m", "venv", str(venv_dir)],
        check=True,
        cwd=str(repo_root),
    )

    created = get_skill_python()
    if created is None:
        raise RuntimeError("Failed to create JMTY skill virtual environment.")
    return created


def get_python_runtime_mode() -> str:
    mode = os.environ.get("JMTY_PYTHON_RUNTIME", "docker").strip().lower()
    if mode not in {"docker", "host"}:
        raise RuntimeError(
            "JMTY_PYTHON_RUNTIME must be either 'docker' or 'host'."
        )
    return mode


def get_python_runtime_image() -> str:
    return os.environ.get("JMTY_PYTHON_IMAGE", PYTHON_RUNTIME_IMAGE)


def get_voicevox_engine_image() -> str:
    return os.environ.get("JMTY_VOICEVOX_IMAGE", VOICEVOX_ENGINE_IMAGE)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return _run_command(["docker", "version", "--format", "{{.Server.Version}}"]) is not None


def ensure_docker_available() -> None:
    if _docker_available():
        return
    raise RuntimeError(
        "Docker が必要です。Docker Desktop / Docker Engine を起動してから再実行してください。"
    )


def _docker_image_exists(image: str) -> bool:
    try:
        completed = subprocess.run(
            ["docker", "image", "inspect", image],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return completed.returncode == 0


def build_python_runtime_image() -> str:
    ensure_docker_available()

    repo_root = get_repo_root()
    dockerfile = repo_root / "docker" / "python-skill-runtime" / "Dockerfile"
    if not dockerfile.exists():
        raise RuntimeError(f"Dockerfile was not found: {dockerfile}")

    image = get_python_runtime_image()
    subprocess.run(
        ["docker", "build", "-t", image, "-f", str(dockerfile), str(repo_root)],
        check=True,
        cwd=str(repo_root),
    )
    return image


def ensure_python_runtime_image() -> str:
    image = get_python_runtime_image()
    if _docker_image_exists(image):
        return image
    return build_python_runtime_image()


def pull_voicevox_engine_image() -> str:
    ensure_docker_available()
    image = get_voicevox_engine_image()
    subprocess.run(["docker", "pull", image], check=True)
    return image


def _voicevox_container_name() -> str:
    return os.environ.get("JMTY_VOICEVOX_CONTAINER", VOICEVOX_ENGINE_CONTAINER)


def _container_exists(name: str) -> bool:
    output = _run_command(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"]
    )
    return output == name


def is_voicevox_container_running() -> bool:
    name = _voicevox_container_name()
    output = _run_command(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"]
    )
    return output == name


def get_voicevox_base_url(for_container: bool = False) -> str:
    base_url = (
        os.environ.get("VOICEVOX_API_BASE_URL")
        or os.environ.get("VOICEVOX_BASE")
        or "http://127.0.0.1:50021"
    )
    if not for_container:
        return base_url
    return re.sub(
        r"(?<=://)(?:127\.0\.0\.1|localhost)(?=[:/]|$)",
        "host.docker.internal",
        base_url,
        count=1,
    )


def is_voicevox_available(base_url: str | None = None, timeout: float = 2.0) -> bool:
    target_base = (base_url or get_voicevox_base_url()).rstrip("/")
    target = f"{target_base}/version"
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def start_voicevox_engine_container(wait_seconds: int = 60) -> str:
    ensure_docker_available()

    name = _voicevox_container_name()
    if is_voicevox_container_running():
        return name

    if _container_exists(name):
        subprocess.run(["docker", "start", name], check=True)
    else:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "-p",
                "50021:50021",
                get_voicevox_engine_image(),
            ],
            check=True,
        )

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if is_voicevox_available():
            return name
        time.sleep(1)

    raise RuntimeError(
        "VOICEVOX Engine コンテナは起動しましたが、API の待受確認に失敗しました。"
    )


def stop_voicevox_engine_container() -> str:
    ensure_docker_available()

    name = _voicevox_container_name()
    if not _container_exists(name):
        return "not-found"
    if not is_voicevox_container_running():
        return "stopped"

    subprocess.run(["docker", "stop", name], check=True)
    return "stopped"


def _container_join(root: PurePosixPath, relative: Path) -> str:
    if not relative.parts:
        return str(root)
    return str(root.joinpath(*relative.parts))


def _rewrite_host_path_for_container(
    raw_value: str,
    host_root: Path,
    container_root: PurePosixPath,
) -> str | None:
    try:
        candidate = Path(raw_value).expanduser()
    except (TypeError, ValueError):
        return None

    if not candidate.is_absolute():
        return None

    normalized = _normalize_path(candidate)
    try:
        relative = normalized.relative_to(host_root)
    except ValueError:
        return None

    return _container_join(container_root, relative)


def _rewrite_argument_for_container(
    arg: str,
    repo_root: Path,
    shared_root: Path | None,
) -> str:
    if arg.startswith("--") and "=" in arg:
        key, value = arg.split("=", 1)
        rewritten_value = _rewrite_host_path_for_container(
            value, repo_root, CONTAINER_REPO_ROOT
        )
        if rewritten_value is not None:
            return f"{key}={rewritten_value}"
        if shared_root is not None:
            rewritten_value = _rewrite_host_path_for_container(
                value, shared_root, CONTAINER_SHARED_ROOT
            )
            if rewritten_value is not None:
                return f"{key}={rewritten_value}"
        return arg

    rewritten = _rewrite_host_path_for_container(arg, repo_root, CONTAINER_REPO_ROOT)
    if rewritten is not None:
        return rewritten

    if shared_root is not None:
        rewritten = _rewrite_host_path_for_container(
            arg, shared_root, CONTAINER_SHARED_ROOT
        )
        if rewritten is not None:
            return rewritten

    return arg


def _rewrite_run_args_for_container(run_args: list[str]) -> list[str]:
    repo_root = get_repo_root()
    shared_root = detect_shared_root()
    return [
        _rewrite_argument_for_container(arg, repo_root, shared_root)
        for arg in run_args
    ]


def _requires_voicevox_engine(run_args: list[str]) -> bool:
    if os.environ.get("JMTY_NEEDS_VOICEVOX") == "1":
        return True

    for arg in run_args:
        basename = Path(arg.split("=", 1)[-1]).name
        if basename in {"generate_voice.py", "generate_viral_voice.py"}:
            return True
    return False


def _pip_install_is_mutating(run_args: list[str]) -> bool:
    if len(run_args) < 3:
        return False
    return (
        run_args[0] == "-m"
        and run_args[1] == "pip"
        and run_args[2] in {"install", "uninstall"}
    )


def build_python_runtime_command(run_args: list[str]) -> list[str]:
    repo_root = get_repo_root()
    shared_root = detect_shared_root()
    runtime_image = ensure_python_runtime_image()
    config_dir = get_config_dir(LOCAL_STATE_APP_NAME)
    hf_cache_dir = Path.home() / ".cache" / "huggingface"

    command = ["docker", "run", "--rm"]
    if sys.stdin.isatty():
        command.append("-i")
    if sys.stdin.isatty() and sys.stdout.isatty():
        command.append("-t")

    if os.name != "nt" and hasattr(os, "getuid") and hasattr(os, "getgid"):
        command.extend(["--user", f"{os.getuid()}:{os.getgid()}"])

    if sys.platform not in {"darwin", "win32"}:
        command.extend(["--add-host", "host.docker.internal:host-gateway"])

    command.extend(
        [
            "-w",
            str(CONTAINER_REPO_ROOT),
            "-e",
            f"HOME={CONTAINER_HOME}",
            "-e",
            f"JMTY_ROOT={CONTAINER_REPO_ROOT}",
            "-e",
            "JMTY_IN_DOCKER=1",
            "-e",
            "PYTHONUNBUFFERED=1",
            "-e",
            "MPLCONFIGDIR=/tmp/matplotlib",
            "-e",
            "NUMBA_CACHE_DIR=/tmp/numba-cache",
            "-e",
            "XDG_CACHE_HOME=/tmp/.cache",
            "-e",
            "XDG_CONFIG_HOME=/tmp/.config",
            "-e",
            f"VOICEVOX_API_BASE_URL={get_voicevox_base_url(for_container=True)}",
            "-e",
            f"VOICEVOX_BASE={get_voicevox_base_url(for_container=True)}",
            "-v",
            f"{repo_root}:{CONTAINER_REPO_ROOT}",
            "-v",
            f"{config_dir}:{CONTAINER_HOME}/.config/{LOCAL_STATE_APP_NAME}",
            "-v",
            f"{hf_cache_dir}:{CONTAINER_HOME}/.cache/huggingface",
        ]
    )

    if shared_root is not None:
        command.extend(
            [
                "-e",
                f"JMTY_SHARED_ROOT={CONTAINER_SHARED_ROOT}",
                "-v",
                f"{shared_root}:{CONTAINER_SHARED_ROOT}",
            ]
        )

    command.extend([runtime_image, "python", *_rewrite_run_args_for_container(run_args)])
    return command


def run_skill_python(run_args: list[str]) -> subprocess.CompletedProcess[object]:
    if get_python_runtime_mode() == "host":
        skill_python = ensure_skill_venv()
        return subprocess.run([str(skill_python), *run_args], cwd=str(get_repo_root()))

    if _pip_install_is_mutating(run_args):
        raise RuntimeError(
            "Docker ランタイムでは pip install / uninstall を直接保持できません。"
            " setup/requirements.txt を更新し、"
            " jmty_runtime.py build-skill-python を実行してください。"
        )

    if (
        _requires_voicevox_engine(run_args)
        and os.environ.get("JMTY_AUTO_START_VOICEVOX", "1") != "0"
        and get_voicevox_base_url(for_container=True).startswith(
            "http://host.docker.internal:50021"
        )
    ):
        start_voicevox_engine_container()

    return subprocess.run(build_python_runtime_command(run_args), cwd=str(get_repo_root()))


def _run_command(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None

    stdout = completed.stdout.strip()
    return stdout or None


def _macos_machine_marker() -> str | None:
    ioreg_output = _run_command(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"])
    if ioreg_output:
        match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', ioreg_output)
        if match:
            return match.group(1)

    system_profiler = _run_command(["system_profiler", "SPHardwareDataType"])
    if system_profiler:
        match = re.search(r"Hardware UUID:\s*([A-F0-9-]+)", system_profiler, re.I)
        if match:
            return match.group(1)
    return None


def _linux_machine_marker() -> str | None:
    for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        if not candidate.exists():
            continue
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return None


def _windows_machine_marker() -> str | None:
    reg_output = _run_command(
        [
            "reg",
            "query",
            r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography",
            "/v",
            "MachineGuid",
        ]
    )
    if not reg_output:
        return None

    match = re.search(r"MachineGuid\s+REG_\w+\s+([^\s]+)", reg_output)
    if match:
        return match.group(1)
    return None


def get_machine_fingerprint() -> str:
    marker = os.environ.get("JMTY_MACHINE_ID")

    if not marker:
        if sys.platform == "darwin":
            marker = _macos_machine_marker()
        elif sys.platform == "win32":
            marker = _windows_machine_marker()
        else:
            marker = _linux_machine_marker()

    if not marker:
        marker = f"{platform.system()}|{platform.node()}|{uuid.getnode():012x}"

    return hashlib.sha256(marker.encode("utf-8")).hexdigest()


def get_saved_owner_machine_id() -> str | None:
    return _load_local_state().get("owner_machine_id")


def save_owner_machine(machine_id: str | None = None) -> str:
    owner_machine_id = machine_id or get_machine_fingerprint()
    state = _load_local_state()
    state["owner_machine_id"] = owner_machine_id
    _save_local_state(state)
    return owner_machine_id


def clear_owner_machine() -> None:
    state = _load_local_state()
    if "owner_machine_id" in state:
        state.pop("owner_machine_id")
        _save_local_state(state)


def is_owner_machine() -> bool:
    expected = get_saved_owner_machine_id()
    if not expected:
        return False
    return expected == get_machine_fingerprint()


def has_worked_before(machine_id: str | None = None) -> bool:
    current_machine_id = machine_id or get_machine_fingerprint()
    machines = _load_worked_before_state()
    if current_machine_id in machines:
        return True

    legacy_state = _load_local_state()
    saved_repo_root = legacy_state.get("repo_root")
    saved_owner_machine_id = legacy_state.get("owner_machine_id")

    if saved_repo_root:
        return True

    if saved_owner_machine_id and saved_owner_machine_id == current_machine_id:
        return True

    return False


def mark_worked_before(machine_id: str | None = None) -> Path:
    current_machine_id = machine_id or get_machine_fingerprint()
    machines = _load_worked_before_state()
    now = datetime.now(timezone.utc).isoformat()
    entry = machines.get(current_machine_id, {})
    if "first_marked_at" not in entry:
        entry["first_marked_at"] = now
    entry["last_marked_at"] = now
    machines[current_machine_id] = entry
    return _save_worked_before_state(machines)


def clear_worked_before(machine_id: str | None = None) -> bool:
    current_machine_id = machine_id or get_machine_fingerprint()
    machines = _load_worked_before_state()
    if current_machine_id not in machines:
        return False
    del machines[current_machine_id]
    _save_worked_before_state(machines)
    return True


def _shared_root_candidates() -> Iterable[Path]:
    for env_name in ("JMTY_SHARED_ROOT", "JMTY_GDRIVE_ROOT"):
        env_value = os.environ.get(env_name)
        if env_value:
            yield Path(env_value).expanduser()

    home = Path.home()

    cloud_storage = home / "Library" / "CloudStorage"
    if cloud_storage.exists():
        for provider_root in cloud_storage.glob("GoogleDrive-*"):
            for drive_name in ("My Drive", "マイドライブ"):
                yield provider_root / drive_name / "jmty"
        for provider_root in cloud_storage.glob("OneDrive*"):
            yield provider_root / "jmty"

    for drive_name in ("My Drive", "マイドライブ"):
        yield home / "Google Drive" / drive_name / "jmty"
        yield home / "GoogleDrive" / drive_name / "jmty"

    yield home / "GoogleDrive" / "jmty"
    yield home / "OneDrive" / "jmty"

    for onedrive_root in home.glob("OneDrive*"):
        yield onedrive_root / "jmty"

    yield home / "Dropbox" / "jmty"


def detect_shared_root() -> Path | None:
    checked: set[Path] = set()
    for candidate in _shared_root_candidates():
        expanded = candidate.expanduser()
        try:
            resolved = expanded.resolve(strict=False)
        except OSError:
            resolved = expanded
        if resolved in checked:
            continue
        checked.add(resolved)
        if resolved.exists():
            return resolved
    return None


def get_repo_git_hooks_path(repo_root: Path | None = None) -> Path:
    root = repo_root or get_repo_root()
    return root / REPO_GIT_HOOKS_DIRNAME


def configure_repo_git_hooks(repo_root: Path | None = None) -> Path:
    root = repo_root or get_repo_root()
    hooks_dir = get_repo_git_hooks_path(root)
    if not hooks_dir.is_dir():
        raise RuntimeError(f"Git hooks directory was not found: {hooks_dir}")

    try:
        subprocess.run(
            ["git", "-C", str(root), "config", "core.hooksPath", REPO_GIT_HOOKS_DIRNAME],
            check=True,
        )
    except OSError as exc:
        raise RuntimeError("git command was not found.") from exc
    return hooks_dir


def _git_config_value(repo_root: Path, key: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", key],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _git_config_int(repo_root: Path, key: str) -> int | None:
    value = _git_config_value(repo_root, key)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _git_remote_url(repo_root: Path, remote_name: str) -> str | None:
    if not remote_name:
        return None

    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", remote_name],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None
    remote_url = completed.stdout.strip()
    return remote_url or None


def _git_for_each_ref(repo_root: Path, *patterns: str) -> list[str]:
    if not patterns:
        return []

    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "for-each-ref", "--format=%(refname)", *patterns],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError("git command was not found.") from exc
    if completed.returncode != 0:
        return []

    refs: list[str] = []
    if completed.stdout:
        for line in completed.stdout.splitlines():
            ref_name = line.strip()
            if ref_name:
                refs.append(ref_name)
    return refs


def _git_rev_list_objects(repo_root: Path, refs: list[str]) -> set[str]:
    if not refs:
        return set()

    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-list", "--objects", *refs],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError("git command was not found.") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git rev-list failed"
        raise RuntimeError(message)

    object_ids: set[str] = set()
    if completed.stdout:
        for line in completed.stdout.splitlines():
            if not line:
                continue
            object_id = line.split(" ", 1)[0].strip()
            if object_id:
                object_ids.add(object_id)
    return object_ids


def _git_blob_size_map(repo_root: Path, object_ids: set[str]) -> dict[str, int]:
    if not object_ids:
        return {}

    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "cat-file",
                "--batch-check=%(objectname) %(objecttype) %(objectsize)",
            ],
            check=False,
            capture_output=True,
            text=True,
            input="".join(f"{object_id}\n" for object_id in sorted(object_ids)),
        )
    except OSError as exc:
        raise RuntimeError("git command was not found.") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git cat-file --batch-check failed"
        raise RuntimeError(message)

    blob_sizes: dict[str, int] = {}
    if completed.stdout:
        for line in completed.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) != 3:
                continue
            object_id, object_type, object_size = parts
            if object_type != "blob":
                continue
            try:
                size = int(object_size)
            except ValueError:
                continue
            if size <= MAX_GIT_LFS_POINTER_BLOB_BYTES:
                blob_sizes[object_id] = size
    return blob_sizes


def _git_blob_contents(repo_root: Path, blob_sizes: dict[str, int]) -> dict[str, bytes]:
    if not blob_sizes:
        return {}

    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "--batch"],
            check=False,
            capture_output=True,
            input="".join(f"{object_id}\n" for object_id in sorted(blob_sizes)).encode("ascii"),
        )
    except OSError as exc:
        raise RuntimeError("git command was not found.") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        stdout = completed.stdout.decode("utf-8", errors="replace").strip()
        message = stderr or stdout or "git cat-file --batch failed"
        raise RuntimeError(message)

    payload = completed.stdout
    contents: dict[str, bytes] = {}
    offset = 0
    total = len(payload)
    while offset < total:
        header_end = payload.find(b"\n", offset)
        if header_end < 0:
            break
        header = payload[offset:header_end].decode("ascii", errors="replace")
        offset = header_end + 1

        parts = header.split()
        if len(parts) != 3:
            break
        object_id, object_type, size_text = parts
        if object_type != "blob":
            break
        try:
            size = int(size_text)
        except ValueError:
            break

        blob = payload[offset : offset + size]
        offset += size
        if offset < total and payload[offset : offset + 1] == b"\n":
            offset += 1
        contents[object_id] = blob

    return contents


def _parse_git_lfs_pointer(blob: bytes) -> tuple[str, int] | None:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return None

    normalized = text.replace("\r\n", "\n").strip()
    if not normalized.startswith(GIT_LFS_POINTER_VERSION):
        return None

    pointer_oid: str | None = None
    pointer_size: int | None = None
    for line in normalized.split("\n"):
        stripped = line.strip()
        if stripped.startswith("oid sha256:"):
            candidate_oid = stripped.removeprefix("oid sha256:")
            if re.fullmatch(r"[0-9a-f]{64}", candidate_oid):
                pointer_oid = candidate_oid
        elif stripped.startswith("size "):
            try:
                candidate_size = int(stripped.removeprefix("size "))
            except ValueError:
                continue
            if candidate_size >= 0:
                pointer_size = candidate_size

    if pointer_oid is None or pointer_size is None:
        return None
    return pointer_oid, pointer_size


def _collect_git_lfs_pointer_sizes(repo_root: Path, refs: list[str]) -> dict[str, int]:
    object_ids = _git_rev_list_objects(repo_root, refs)
    blob_sizes = _git_blob_size_map(repo_root, object_ids)
    blob_contents = _git_blob_contents(repo_root, blob_sizes)

    lfs_pointer_sizes: dict[str, int] = {}
    for blob in blob_contents.values():
        pointer = _parse_git_lfs_pointer(blob)
        if pointer is None:
            continue
        pointer_oid, pointer_size = pointer
        lfs_pointer_sizes[pointer_oid] = pointer_size
    return lfs_pointer_sizes


def _is_zero_git_object_id(value: str) -> bool:
    stripped = value.strip()
    return not stripped or set(stripped) == {"0"}


def _resolve_remote_url(repo_root: Path, remote_name: str, remote_url: str | None) -> str | None:
    if remote_url:
        return remote_url
    return _git_remote_url(repo_root, remote_name)


def _is_github_remote(remote_url: str | None) -> bool:
    if not remote_url:
        return False
    lowered = remote_url.lower()
    return (
        "github.com/" in lowered
        or "github.com:" in lowered
        or lowered.startswith("ssh://git@github.com/")
        or lowered.startswith("https://github.com/")
    )


def _git_lfs_installed() -> bool:
    try:
        completed = subprocess.run(
            ["git", "lfs", "version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return completed.returncode == 0


def _git_lfs_free_storage_bytes(repo_root: Path) -> int:
    env_value = os.environ.get(GIT_LFS_FREE_STORAGE_BYTES_ENV)
    if env_value:
        try:
            parsed = int(env_value)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return parsed

    configured = _git_config_int(repo_root, "jmty.lfsFreeStorageBytes")
    if configured is not None and configured > 0:
        return configured
    return GITHUB_FREE_GIT_LFS_STORAGE_BYTES


def _git_lfs_reserved_bytes(repo_root: Path) -> int:
    env_value = os.environ.get(GIT_LFS_RESERVED_BYTES_ENV)
    if env_value:
        try:
            parsed = int(env_value)
        except ValueError:
            parsed = 0
        if parsed >= 0:
            return parsed

    configured = _git_config_int(repo_root, "jmty.lfsReservedBytes")
    if configured is not None and configured >= 0:
        return configured
    return 0


def format_bytes_for_humans(size: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.2f} {units[unit_index]}"


def get_git_lfs_free_plan_status(
    remote_name: str = "origin",
    remote_url: str | None = None,
    pre_push_lines: list[str] | None = None,
) -> GitLfsFreePlanStatus:
    repo_root = get_repo_root()
    resolved_remote_url = _resolve_remote_url(repo_root, remote_name, remote_url)
    free_storage_bytes = _git_lfs_free_storage_bytes(repo_root)
    reserved_bytes = min(_git_lfs_reserved_bytes(repo_root), free_storage_bytes)
    available_bytes = max(free_storage_bytes - reserved_bytes, 0)

    current_refs = _git_for_each_ref(repo_root, f"refs/remotes/{remote_name}", "refs/tags")
    current_pointer_sizes = _collect_git_lfs_pointer_sizes(repo_root, current_refs)

    incoming_refs: list[str] = []
    for line in pre_push_lines or []:
        parts = line.strip().split()
        if len(parts) != 4:
            continue
        local_ref, local_object_id, _remote_ref, _remote_object_id = parts
        if not local_ref or _is_zero_git_object_id(local_object_id):
            continue
        incoming_refs.append(local_object_id)

    incoming_pointer_sizes = _collect_git_lfs_pointer_sizes(repo_root, incoming_refs)
    projected_pointer_sizes = dict(current_pointer_sizes)
    projected_pointer_sizes.update(incoming_pointer_sizes)

    current_bytes = sum(current_pointer_sizes.values())
    projected_bytes = sum(projected_pointer_sizes.values())
    incoming_bytes = sum(
        size
        for pointer_oid, size in incoming_pointer_sizes.items()
        if pointer_oid not in current_pointer_sizes
    )
    has_lfs_content = bool(projected_pointer_sizes)
    git_lfs_installed = _git_lfs_installed()

    rejection_reason: str | None = None
    warning: str | None = None

    if has_lfs_content and not git_lfs_installed:
        rejection_reason = (
            "Git LFS のポインタを検出しましたが、`git lfs` が見つかりません。"
            " `git lfs install --skip-repo` を実行してから push してください。"
        )
    elif has_lfs_content and not _is_github_remote(resolved_remote_url):
        rejection_reason = (
            "GitHub 以外の Git LFS 無料枠は自動判定できません。"
            " 課金を避けるため、この push を止めました。"
        )
    elif has_lfs_content and projected_bytes > available_bytes:
        rejection_reason = (
            "推定される Git LFS 保存量が無料枠を超えます。"
            f" 見込み {format_bytes_for_humans(projected_bytes)} /"
            f" 利用可能 {format_bytes_for_humans(available_bytes)}。"
        )
    elif has_lfs_content and reserved_bytes == 0:
        warning = (
            "この判定は今のリポジトリで見える LFS オブジェクトを基準にしています。"
            " 同じ GitHub アカウントで他の LFS を使うなら、"
            " `jmty.lfsReservedBytes` か"
            f" `{GIT_LFS_RESERVED_BYTES_ENV}` を設定してください。"
        )

    return GitLfsFreePlanStatus(
        remote_name=remote_name,
        remote_url=resolved_remote_url,
        free_storage_bytes=free_storage_bytes,
        reserved_bytes=reserved_bytes,
        available_bytes=available_bytes,
        current_bytes=current_bytes,
        incoming_bytes=incoming_bytes,
        projected_bytes=projected_bytes,
        current_object_count=len(current_pointer_sizes),
        incoming_object_count=len(
            [
                pointer_oid
                for pointer_oid in incoming_pointer_sizes
                if pointer_oid not in current_pointer_sizes
            ]
        ),
        projected_object_count=len(projected_pointer_sizes),
        has_lfs_content=has_lfs_content,
        git_lfs_installed=git_lfs_installed,
        within_budget=rejection_reason is None,
        rejection_reason=rejection_reason,
        warning=warning,
    )
