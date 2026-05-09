#!/usr/bin/env python3
# Syncs this JMTY workspace's slash-command adapters for Codex, Gemini, and Claude.
# Inputs are the COMMANDS table below; outputs are command adapter files under
# .codex/prompts, .gemini/commands, and .claude/commands.
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMANDS: list[dict[str, str]] = [
    {"name": "team", "description": "チーム開発モードに切り替える", "kind": "mode"},
    {"name": "personal", "description": "個人開発モードに切り替える", "kind": "mode"},
    {"name": "c", "description": "コミットのみを行う", "kind": "git-commit-only"},
    {"name": "git", "description": "git-workflow に従ってコミットと反映を行う", "kind": "skill", "skill_path": ".agent/skills/common/git-workflow/SKILL.md"},
    {"name": "git-nd", "description": "git-workflow に従ってコミットと反映を行う（Discord報告なし）", "kind": "skill", "skill_path": ".agent/skills/common/git-workflow/SKILL.md"},
    {"name": "pull", "description": "origin/main を fetch して pull --rebase する", "kind": "git-pull"},
    {"name": "ceo", "description": "CEO 経由で必要な役割へ振り分ける", "kind": "skill", "skill_path": ".agent/skills/common/agent-org-ceo/SKILL.md"},
    {"name": "setup", "description": "JMTY workspace のセットアップ補助を始める", "kind": "skill", "skill_path": ".agent/skills/common/jmty-setup/SKILL.md"},
    {"name": "jmty", "description": "ジモティー投稿文スキルを起動する", "kind": "skill", "skill_path": ".agent/skills/jmty/jmty-posts/SKILL.md"},
    {"name": "jmty-weekly", "description": "ジモティー週次素材処理を起動する", "kind": "file", "target_path": ".agent/skills/nanobanana-banner-gen/scripts/jmty_weekly_assets.py"},
]


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def prompt_body(command: dict[str, str], placeholder: str) -> str:
    name = command["name"]
    kind = command["kind"]
    lines = [
        "この command は JMTY workspace 専用です。",
        "まずカレントディレクトリに AGENTS.md があることを確認し、その内容を正本として扱ってください。",
        f"AGENTS.md を読み、/{name} のルールを確認してください。",
    ]
    if kind == "skill":
        lines.append(f"次に `{command['skill_path']}` を読み込み、そのスキルとして動作してください。")
    elif kind == "file":
        lines.append(f"次に `{command['target_path']}` を確認し、週次素材処理の文脈として扱ってください。")
    elif kind == "git-commit-only":
        lines.append("Git 操作の詳細は `.agent/skills/common/git-workflow/SKILL.md` に従い、コミットのみ行ってください。")
    elif kind == "git-pull":
        lines.append("git fetch origin の後、更新がある場合だけ pull --rebase を行ってください。")
    elif kind == "mode":
        lines.append("`.dev-mode` を更新し、切り替え後の現在モードをユーザーへ報告してください。")
    else:
        raise ValueError(f"Unsupported kind: {kind}")
    lines.append(f"ユーザーが追加の引数や補足を付けた場合は、それも考慮してください: {placeholder}")
    return "\n".join(lines)


def gemini_content(command: dict[str, str]) -> str:
    return f'description = "{command["description"]}"\nprompt = """\n{prompt_body(command, "{{args}}")}\n"""\n'


def codex_content(command: dict[str, str]) -> str:
    return "---\n" + f'description: "{command["description"]}"\n' + 'argument-hint: "[EXTRA=\\"free-form note\\"]"\n---\n\n' + prompt_body(command, "$ARGUMENTS") + "\n"


def claude_content(command: dict[str, str]) -> str:
    return prompt_body(command, "$ARGUMENTS") + "\n"


def sync() -> None:
    write_if_changed(ROOT / ".gemini" / "settings.json", json.dumps({"contextFileName": "AGENTS.md"}, ensure_ascii=False, indent=2))
    for command in COMMANDS:
        write_if_changed(ROOT / ".gemini" / "commands" / f"{command['name']}.toml", gemini_content(command))
        write_if_changed(ROOT / ".codex" / "prompts" / f"{command['name']}.md", codex_content(command))
        write_if_changed(ROOT / ".claude" / "commands" / f"{command['name']}.md", claude_content(command))


def main() -> int:
    sync()
    print("Synced JMTY workspace command adapters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
