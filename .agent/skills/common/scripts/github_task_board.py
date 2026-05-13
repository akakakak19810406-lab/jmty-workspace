#!/usr/bin/env python3
"""Register JMTY improvement notes and tasks in GitHub Issues and Projects.

This helper keeps the repo's Task Board workflow repeatable from Codex.
It creates an issue, adds labels, links it to Project V2, and sets fields.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OWNER = "akakakak19810406-lab"
DEFAULT_REPO = "jmty-workspace"
DEFAULT_PROJECT_TITLE = "Task Board"

TYPE_LABELS = {
    "Feature": "type:feature",
    "Bug": "type:bug",
    "Improvement": "type:improvement",
    "Chore": "type:chore",
    "Research": "type:research",
}
PRIORITY_LABELS = {
    "High": "priority:high",
    "Medium": "priority:medium",
    "Low": "priority:low",
}
AREA_LABELS = {
    "Frontend": "area:frontend",
    "Backend": "area:backend",
    "Infra": "area:infra",
    "Docs": "area:docs",
    "Design": "area:design",
    "Ops": "area:ops",
}


@dataclass(frozen=True)
class Config:
    owner: str
    repo: str
    project_title: str
    project_number: str


STATUS_VALUES = ["Backlog", "Todo", "In Progress", "Review", "Done"]


def run(args: list[str], *, input_text: str | None = None) -> str:
    proc = subprocess.run(
        args,
        input=input_text,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or f"command failed: {' '.join(args)}"
        raise RuntimeError(message)
    return proc.stdout.strip()


def load_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        values[key.strip()] = raw_value.strip().strip('"').strip("'")
    return values


def get_config(project_number_arg: str | None = None) -> Config:
    env_file = load_env_file()
    owner = os.environ.get("OWNER") or env_file.get("OWNER") or DEFAULT_OWNER
    repo = os.environ.get("REPO") or env_file.get("REPO") or DEFAULT_REPO
    project_title = os.environ.get("PROJECT_TITLE") or env_file.get("PROJECT_TITLE") or DEFAULT_PROJECT_TITLE
    project_number = project_number_arg or os.environ.get("PROJECT_NUMBER") or env_file.get("PROJECT_NUMBER") or ""
    if not project_number:
        project_number = run(
            [
                "gh",
                "project",
                "list",
                "--owner",
                owner,
                "--format",
                "json",
                "--jq",
                f'.projects[] | select(.title=="{project_title}") | .number',
            ]
        ).splitlines()[0]
    return Config(owner=owner, repo=repo, project_title=project_title, project_number=str(project_number))


def json_command(args: list[str]) -> dict:
    output = run(args)
    return json.loads(output or "{}")


def project_id(config: Config) -> str:
    return run(["gh", "project", "view", config.project_number, "--owner", config.owner, "--format", "json", "--jq", ".id"])


def project_fields(config: Config) -> list[dict]:
    return json_command(["gh", "project", "field-list", config.project_number, "--owner", config.owner, "--format", "json"]).get(
        "fields", []
    )


def project_item_query(config: Config) -> dict:
    return json_command(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"owner={config.owner}",
            "-F",
            f"number={config.project_number}",
            "-f",
            "query=query($owner: String!, $number: Int!) { user(login: $owner) { projectV2(number: $number) { id items(first: 100) { nodes { id content { ... on Issue { id number title url body state repository { nameWithOwner } } ... on PullRequest { id number title url state repository { nameWithOwner } } ... on DraftIssue { id title body } } fieldValues(first: 30) { nodes { ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2SingleSelectField { name } } } } } } } } } }",
        ]
    )


def project_items(config: Config) -> list[dict]:
    data = project_item_query(config)
    project = data.get("data", {}).get("user", {}).get("projectV2") or {}
    items = project.get("items", {}).get("nodes", [])
    normalized = []
    for item in items:
        content = item.get("content") or {}
        fields: dict[str, str] = {}
        for value in item.get("fieldValues", {}).get("nodes", []):
            field = value.get("field") or {}
            name = field.get("name")
            if name and value.get("name"):
                fields[str(name)] = str(value["name"])
        normalized.append(
            {
                "item_id": item.get("id") or "",
                "content_id": content.get("id") or "",
                "number": content.get("number"),
                "title": content.get("title") or "",
                "url": content.get("url") or "",
                "body": content.get("body") or "",
                "state": content.get("state") or "",
                "repository": (content.get("repository") or {}).get("nameWithOwner") or "",
                "status": fields.get("Status", ""),
                "priority": fields.get("Priority", ""),
                "type": fields.get("Type", ""),
                "area": fields.get("Area", ""),
            }
        )
    return normalized


def single_select_field(fields: list[dict], field_name: str, option_name: str) -> tuple[str, str]:
    for field in fields:
        if field.get("name") != field_name:
            continue
        for option in field.get("options", []):
            if option.get("name") == option_name:
                return str(field["id"]), str(option["id"])
    raise RuntimeError(f"Project field option not found: {field_name}={option_name}")


def issue_node_id(config: Config, issue_url: str) -> str:
    owner_repo = f"{config.owner}/{config.repo}"
    number = issue_url.rstrip("/").split("/")[-1]
    return run(["gh", "issue", "view", number, "--repo", owner_repo, "--json", "id", "--jq", ".id"])


def create_issue(config: Config, title: str, body: str, labels: list[str]) -> str:
    args = [
        "gh",
        "issue",
        "create",
        "--repo",
        f"{config.owner}/{config.repo}",
        "--title",
        title,
        "--body",
        body,
    ]
    for label in labels:
        args.extend(["--label", label])
    return run(args)


def add_issue_to_project(project: str, content_id: str) -> str:
    data = json_command(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"projectId={project}",
            "-f",
            f"contentId={content_id}",
            "-f",
            "query=mutation($projectId: ID!, $contentId: ID!) { addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) { item { id } } }",
        ]
    )
    return data["data"]["addProjectV2ItemById"]["item"]["id"]


def set_project_field(project: str, item: str, field: str, option: str) -> None:
    run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"projectId={project}",
            "-f",
            f"itemId={item}",
            "-f",
            f"fieldId={field}",
            "-f",
            f"optionId={option}",
            "-f",
            "query=mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) { updateProjectV2ItemFieldValue(input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: {singleSelectOptionId: $optionId}}) { projectV2Item { id } } }",
        ]
    )


def set_status(config: Config, item_id: str, status: str) -> None:
    project = project_id(config)
    field_id, option_id = single_select_field(project_fields(config), "Status", status)
    set_project_field(project, item_id, field_id, option_id)


def issue_url_for_number(config: Config, number_or_url: str) -> str:
    if number_or_url.startswith("http://") or number_or_url.startswith("https://"):
        return number_or_url
    return run(
        [
            "gh",
            "issue",
            "view",
            str(number_or_url),
            "--repo",
            f"{config.owner}/{config.repo}",
            "--json",
            "url",
            "--jq",
            ".url",
        ]
    )


def find_item(config: Config, number_or_url: str) -> dict:
    target_url = issue_url_for_number(config, str(number_or_url)).rstrip("/")
    for item in project_items(config):
        if str(item.get("url", "")).rstrip("/") == target_url:
            return item
    raise RuntimeError(f"Task Board item not found for issue: {number_or_url}")


def add_issue_comment(config: Config, number_or_url: str, body: str) -> None:
    number = str(number_or_url).rstrip("/").split("/")[-1]
    run(["gh", "issue", "comment", number, "--repo", f"{config.owner}/{config.repo}", "--body", body])


def create_task(args: argparse.Namespace) -> None:
    config = get_config(args.project_number)
    task_type = args.type
    priority = args.priority
    area = args.area
    status = args.status
    labels = [TYPE_LABELS[task_type], PRIORITY_LABELS[priority], AREA_LABELS[area]]
    issue_url = create_issue(config, args.title, args.body, labels)
    project = project_id(config)
    item = add_issue_to_project(project, issue_node_id(config, issue_url))
    fields = project_fields(config)
    for field_name, option_name in (
        ("Status", status),
        ("Priority", priority),
        ("Type", task_type),
        ("Area", area),
    ):
        field_id, option_id = single_select_field(fields, field_name, option_name)
        set_project_field(project, item, field_id, option_id)
    print(
        json.dumps(
            {
                "issue_url": issue_url,
                "project_number": config.project_number,
                "status": status,
                "priority": priority,
                "type": task_type,
                "area": area,
                "labels": labels,
            },
            ensure_ascii=False,
        )
    )


def list_items(args: argparse.Namespace) -> None:
    config = get_config(args.project_number)
    items = project_items(config)[: args.limit]
    print(json.dumps({"items": items, "totalCount": len(items)}, ensure_ascii=False))


def next_item(args: argparse.Namespace) -> None:
    config = get_config(args.project_number)
    candidates = [
        item
        for item in project_items(config)
        if item.get("state") != "CLOSED" and item.get("status") in {"", "Backlog", "Todo"}
    ]
    priority_order = {"High": 0, "Medium": 1, "Low": 2, "": 3}
    status_order = {"Todo": 0, "Backlog": 1, "": 2}
    candidates.sort(key=lambda item: (status_order.get(str(item.get("status")), 9), priority_order.get(str(item.get("priority")), 9), item.get("number") or 0))
    if not candidates:
        print(json.dumps({"item": None, "message": "No executable task found."}, ensure_ascii=False))
        return
    print(json.dumps({"item": candidates[0]}, ensure_ascii=False))


def start_item(args: argparse.Namespace) -> None:
    config = get_config(args.project_number)
    item = find_item(config, args.issue)
    set_status(config, str(item["item_id"]), "In Progress")
    comment = args.comment or "Codexがこのタスクの作業を開始しました。"
    add_issue_comment(config, args.issue, comment)
    item["status"] = "In Progress"
    print(json.dumps({"item": item, "commented": True}, ensure_ascii=False))


def done_item(args: argparse.Namespace) -> None:
    config = get_config(args.project_number)
    item = find_item(config, args.issue)
    set_status(config, str(item["item_id"]), args.status)
    lines = ["Codexがこのタスクの作業を完了しました。"]
    if args.summary:
        lines.extend(["", "完了内容:", args.summary])
    if args.tests:
        lines.extend(["", "確認:", args.tests])
    add_issue_comment(config, args.issue, "\n".join(lines))
    if args.close_issue:
        number = str(args.issue).rstrip("/").split("/")[-1]
        run(["gh", "issue", "close", number, "--repo", f"{config.owner}/{config.repo}", "--comment", "Task Boardで完了にしました。"])
    item["status"] = args.status
    print(json.dumps({"item": item, "commented": True, "closed": bool(args.close_issue)}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register JMTY tasks in GitHub Task Board.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_create_flags(cmd: argparse.ArgumentParser, *, memo_defaults: bool = False) -> None:
        cmd.add_argument("--title", required=True)
        cmd.add_argument("--body", required=True)
        cmd.add_argument("--project-number")
        cmd.add_argument("--type", choices=sorted(TYPE_LABELS), default="Research" if memo_defaults else "Improvement")
        cmd.add_argument("--priority", choices=sorted(PRIORITY_LABELS), default="Medium")
        cmd.add_argument("--area", choices=sorted(AREA_LABELS), default="Ops")
        cmd.add_argument("--status", choices=STATUS_VALUES, default="Backlog")
        cmd.set_defaults(func=create_task)

    add_common_create_flags(sub.add_parser("create", help="Create a task issue and add it to Task Board."))
    add_common_create_flags(sub.add_parser("memo", help="Create an investigation or improvement memo."), memo_defaults=True)

    list_cmd = sub.add_parser("list", help="List Task Board items.")
    list_cmd.add_argument("--project-number")
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.set_defaults(func=list_items)

    next_cmd = sub.add_parser("next", help="Show the next Backlog/Todo task to execute.")
    next_cmd.add_argument("--project-number")
    next_cmd.set_defaults(func=next_item)

    start_cmd = sub.add_parser("start", help="Mark a task In Progress and comment on its issue.")
    start_cmd.add_argument("issue", help="Issue number or URL.")
    start_cmd.add_argument("--project-number")
    start_cmd.add_argument("--comment")
    start_cmd.set_defaults(func=start_item)

    done_cmd = sub.add_parser("done", help="Mark a task done or review and comment with completion details.")
    done_cmd.add_argument("issue", help="Issue number or URL.")
    done_cmd.add_argument("--project-number")
    done_cmd.add_argument("--status", choices=["Review", "Done"], default="Done")
    done_cmd.add_argument("--summary", default="")
    done_cmd.add_argument("--tests", default="")
    done_cmd.add_argument("--close-issue", action="store_true")
    done_cmd.set_defaults(func=done_item)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
