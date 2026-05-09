# JMTY workspace 用エイリアスをシェル設定に登録するスクリプト。
# Claude SessionStart hook / bootstrap.sh / ~/.zshrc の自動チェックから呼ばれ、
# 不足しているエイリアスがある場合のみ書き込む（冪等）。引数でリポジトリルートを渡せる。
# macOS/Linux は ~/.config/jmty/env.sh、Windows は PowerShell プロファイルに追記する。

import json
import os
import pathlib
import platform
import sys

ALIASES = [
    ("jmty-setup", 'python3 "{root}/.agent/skills/common/scripts/jmty_runtime.py" setup-local-machine --repo-root "{root}"'),
    ("jmty-sync-commands", 'python3 "{root}/scripts/sync_cross_cli_commands.py"'),
    ("jmty-status", 'git -C "{root}" status --short'),
]

PS_FUNCTIONS = [
    ("jmty-setup", 'py -3 "{root}\\.agent\\skills\\common\\scripts\\jmty_runtime.py" setup-local-machine --repo-root "{root}" --shell powershell'),
    ("jmty-sync-commands", 'py -3 "{root}\\scripts\\sync_cross_cli_commands.py"'),
    ("jmty-status", 'git -C "{root}" status --short'),
]

REGISTERED_FLAG = pathlib.Path.home() / ".config" / "jmty" / "aliases-registered"

# ~/.zshrc などに仕込む「ターミナル起動時の自動チェック行」のテンプレート
# JMTY_ROOT が未設定でも動くようにスクリプト絶対パスを直接埋め込む
_ZSHRC_HOOK_MARKER = "jmty alias auto-check"
_ZSHRC_HOOK_TMPL = (
    "\n# {marker}\n"
    "[ -f \"{script}\" ] && python \"{script}\" --root \"{root}\" 2>/dev/null\n"
)


def _ensure_zshrc_hook(root: pathlib.Path, home: pathlib.Path) -> bool:
    """Interactive shell rc files に自動チェック行を追加する（Gemini/Codex 向け）。"""
    script = root / ".agent" / "skills" / "common" / "scripts" / "register_aliases.py"
    changed = False
    for rc in [home / ".zshrc", home / ".bashrc"]:
        if not rc.exists():
            continue
        content = rc.read_text(encoding="utf-8")
        hook_line = _ZSHRC_HOOK_TMPL.format(
            marker=_ZSHRC_HOOK_MARKER,
            script=script,
            root=root,
        )
        lines = content.splitlines()
        filtered_lines = []
        skip_next = False
        for line in lines:
            if skip_next:
                skip_next = False
                continue
            if _ZSHRC_HOOK_MARKER in line:
                skip_next = True
                continue
            filtered_lines.append(line)
        new_content = "\n".join(filtered_lines).rstrip() + hook_line
        if new_content != content:
            rc.write_text(new_content, encoding="utf-8")
            changed = True

    return changed


def register_mac(root: pathlib.Path, home: pathlib.Path) -> bool:
    env_dir = home / ".config" / "jmty"
    env_file = env_dir / "env.sh"
    env_dir.mkdir(parents=True, exist_ok=True)

    existing = env_file.read_text(encoding="utf-8") if env_file.exists() else ""

    # 古いエイリアス行を除去してから書き直す
    kept = [
        l for l in existing.splitlines()
        if not any(k in l for k in ("alias jmty-setup", "alias jmty-sync-commands", "alias jmty-status", "JMTY workspace"))
    ]
    while kept and not kept[-1].strip():
        kept.pop()
    new_lines = [
        "",
        "# JMTY workspace エイリアス (register_aliases.py により自動登録)",
    ]
    for name, cmd in ALIASES:
        new_lines.append(f"alias {name}='{cmd.format(root=root)}'")

    new_content = "\n".join(kept + new_lines).strip() + "\n"
    changed = new_content != existing
    if changed:
        env_file.write_text(new_content, encoding="utf-8")

    # shell RC から env.sh を source する行を追加
    profile_line = f'[ -f "{env_file}" ] && source "{env_file}"'
    for rc in [home / ".zshrc", home / ".zprofile", home / ".bashrc", home / ".bash_profile"]:
        if not rc.exists():
            continue
        rc_content = rc.read_text(encoding="utf-8")
        if str(env_file) not in rc_content:
            with rc.open("a", encoding="utf-8") as f:
                f.write(f"\n{profile_line}\n")
            changed = True

    return changed


def register_windows(root: pathlib.Path, home: pathlib.Path) -> bool:
    ps_profile_env = os.environ.get("PROFILE", "")
    profile = pathlib.Path(ps_profile_env) if ps_profile_env else (
        home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
    )
    profile.parent.mkdir(parents=True, exist_ok=True)

    existing = profile.read_text(encoding="utf-8") if profile.exists() else ""
    managed_names = {name for name, _ in PS_FUNCTIONS}
    kept = [
        line for line in existing.splitlines()
        if not any(line.strip().startswith(f"function {name}") for name in managed_names)
        and "JMTY workspace エイリアス" not in line
    ]

    new_lines = [
        "",
        "# JMTY workspace エイリアス (register_aliases.py により自動登録)",
    ]
    for name, cmd in PS_FUNCTIONS:
        new_lines.append(f'function {name} {{ {cmd.format(root=root)} }}')

    new_content = "\n".join(kept + new_lines).strip() + "\n"
    if new_content == existing:
        return False

    profile.write_text(new_content, encoding="utf-8")

    return True


def main() -> None:
    # リポジトリルートの取得（引数 > CLAUDE_PROJECT_DIR の優先順）
    root_str = ""
    if len(sys.argv) >= 3 and sys.argv[1] == "--root":
        root_str = sys.argv[2]
    if not root_str:
        root_str = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not root_str:
        sys.exit(0)

    root = pathlib.Path(root_str)
    home = pathlib.Path.home()

    if platform.system() == "Windows":
        registered = register_windows(root, home)
    else:
        registered = register_mac(root, home)
        # Gemini / Codex 向けに zshrc へ自動チェック行を仕込む
        registered = _ensure_zshrc_hook(root, home) or registered

    if registered:
        REGISTERED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        REGISTERED_FLAG.touch()
        msg = "エイリアス自動登録完了 (jmty-setup / jmty-sync-commands / jmty-status) — 新しいターミナルで使えます"
        print(json.dumps({"systemMessage": msg}))


if __name__ == "__main__":
    main()
