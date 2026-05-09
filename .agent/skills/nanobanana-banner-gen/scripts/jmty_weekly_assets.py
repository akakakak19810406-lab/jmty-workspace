#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import random
import shutil
import subprocess
import ssl
from dataclasses import dataclass
from pathlib import Path


SPREADSHEET_ID = "1GKBTHwBS6W0D30X_yK7vqsaDRWw3p1tXM7lnFhyb0Uw"
SHEET_NAME = "アカウント情報"
PARENT_FOLDER_ID = "16P5sOzyJHLemwURON6Wf1i7NjodK3WWF"
DEFAULT_OUTPUT_ROOT = Path("outputs/jmty-weekly/current")
FACTORY_CASES_PATH = Path("/Users/deguchishouma/team-info/inputs/jmty_factory_cases/2026-02_案件一覧.md")

FACTORY_REGION_INDEX = 7   # H
FACTORY_IMAGE_COL = "I"
FACTORY_POST_INDEX = 9     # J
REMOTE_REGION_INDEX = 16   # Q
REMOTE1_IMAGE_COL = "R"
REMOTE1_POST_INDEX = 18    # S
REMOTE2_IMAGE_COL = "T"
REMOTE2_POST_INDEX = 20    # U
ROTATION_REPORT_FILENAME = "rotation_report.md"

EXPECTED_IMAGE_FILENAMES = {
    "factory": "工場.jpg",
    "remote1": "在宅1.jpg",
    "remote2": "在宅2.jpg",
}

FACTORY_OCR_HINTS = ("工場", "製造", "月収", "寮", "ライン", "高収入")
REMOTE_OCR_HINTS = ("在宅", "リモート", "自宅", "PC", "文章", "ライター", "オンライン")


CTA_VARIANTS = [
    "公式LINEに登録後、ボタン押すだけ！",
    "LINE追加後、そのままボタンをタップ！",
    "LINE登録だけでOK！あとはボタンを押すだけ！",
    "まずはLINE追加！10秒で問い合わせ完了！",
]


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


def run_gws(args: list[str]) -> dict:
    verify_paths = ssl.get_default_verify_paths()
    shell_cmd = (
        "export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file; "
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
        + " ".join(_shell_quote(part) for part in ["gws", *args])
    )
    result = subprocess.run(
        ["/bin/zsh", "-lc", shell_cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    stdout = result.stdout.strip()
    if stdout.startswith("Using keyring backend: file"):
        stdout = stdout.split("\n", 1)[1].strip()
    return json.loads(stdout) if stdout else {}


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


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


def replace_drive_file(file_path: Path, parent_id: str) -> str:
    delete_drive_files_by_name(parent_id, file_path.name)
    return upload_drive_file(file_path, parent_id)


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

    rotated: dict[int, list[str]] = {}
    for pos, row_idx in enumerate(target_indexes):
        source_idx = target_indexes[pos - 1]
        rotated[row_idx] = old_bundles[source_idx]
    return rotated


def render_rotation_report(rows: list[list[str]], factory_rows: list[int], remote_rows: list[int]) -> str:
    lines = [
        "【地域ローテーション確認】",
        "■ 工場（H列）",
        "| アカウント名 | 担当エリア（ローテーション後） |",
        "|------------|---------------------------|",
    ]
    for row_idx in factory_rows:
        row = rows[row_idx]
        account_name = re.sub(r"\s+", " ", row_value(row, 1)) or "未設定"
        lines.append(f"| {account_name} | {normalize_prefecture(row_value(row, FACTORY_REGION_INDEX)) or '未設定'} |")

    lines.extend(
        [
            "",
            "■ 在宅（Q列）",
            "| アカウント名 | 担当エリア（ローテーション後） |",
            "|------------|---------------------------|",
        ]
    )
    for row_idx in remote_rows:
        row = rows[row_idx]
        account_name = re.sub(r"\s+", " ", row_value(row, 1)) or "未設定"
        lines.append(f"| {account_name} | {normalize_prefecture(row_value(row, REMOTE_REGION_INDEX)) or '未設定'} |")
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


def fenced(text: str) -> str:
    return f"```text\n{text.rstrip()}\n```"


def build_banner_prompt(task_type: str, region: str, post_text: str, account_name: str, salary_text: str, role_phrase: str) -> str:
    region_text = clean_display_text(region)
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
            f"投稿先地域の想定: {region_text or '未設定'}",
            f"職種表記: {role_phrase}",
            f"給与表記: {salary_text}",
            "工場・製造の仕事だとひと目でわかるビジュアル。",
            "寮費無料、高収入、未経験歓迎など、本文から強みを拾って反映する。",
        ]
    else:
        specific = [
            f"カテゴリ: 在宅求人（{task_type}）",
            f"投稿先地域の想定: {region_text or '未設定'}",
            f"職種表記: {role_phrase}",
            f"給与表記: {salary_text}",
            "完全在宅、全国OK、出勤不要だとひと目でわかるビジュアル。",
            "ノートPC、在宅ワーク、チャット、オンライン業務の雰囲気を反映する。",
        ]
    body = "\n".join(common + specific)
    return f"{body}\n\nアカウント名: {account_name}\n\n元の投稿文:\n{post_text.strip()}"


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


def source_text_prefers_image(task_kind: str, image_path: Path, fallback_text: str) -> str:
    if not image_path.exists():
        return fallback_text
    text = ocr_text(image_path)
    if not text:
        return fallback_text
    normalized = re.sub(r"\s+", "", text)
    salary_found = bool(re.search(r"(月収|月給|時給|年収)\s*[\d,]+", normalized))
    if task_kind == "factory":
        hits = sum(1 for hint in FACTORY_OCR_HINTS if hint in normalized)
        if hits >= 1 or salary_found:
            return text
    else:
        hits = sum(1 for hint in REMOTE_OCR_HINTS if hint in normalized)
        if hits >= 1 or salary_found:
            return text
    return fallback_text


def render_prompt_document(task: dict | Task, image_path: Path, post_text: str, prompt_text: str) -> str:
    account_name = task["account_name"] if isinstance(task, dict) else task.account_name
    row_idx = task["row_idx"] if isinstance(task, dict) else task.row_idx
    label_ja = task["label_ja"] if isinstance(task, dict) else task.label_ja
    region = task["region"] if isinstance(task, dict) else task.region
    return "\n".join(
        [
            f"# {label_ja} 画像プロンプト",
            "",
            "## メタ情報",
            f"- アカウント名: {account_name}",
            f"- 行番号: {row_idx}",
            f"- 種別: {label_ja}",
            f"- 投稿先地域: {region or '未設定'}",
            f"- 画像保存先: `{image_path}`",
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
    lines = [line.rstrip() for line in post_text.splitlines()]
    if "## 本文" in lines:
        start = lines.index("## 本文") + 1
        lines = lines[start:]

    body_lines: list[str] = []
    for line in lines:
        if line.startswith("## "):
            break
        if line.startswith("# "):
            continue
        if line.strip() == "":
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    return body or post_text


def build_post_text(task_type: str, region: str, source_text: str, account_name: str) -> tuple[str, str]:
    salary_text = extract_salary_text(source_text, task_type)
    role_phrase = extract_role_phrase(source_text, task_type)
    region_text = clean_display_text(region)

    if task_type == "factory":
        title = f"【工場】未経験OK／{role_phrase}｜{salary_text}"
        body = [
            "「地方でも、しっかり稼ぎたい」",
            "そんな方に向けた製造求人です。",
            "",
            f"{role_phrase}の募集で、{salary_text}を目安にしっかり収入を狙えます。",
            "作業は機械への材料セットやボタン操作が中心。",
            "特別なスキルは不要で、未経験から始めやすい内容です。",
        ]
        if "寮" in source_text or "住" in source_text:
            body.extend(
                [
                    "",
                    "さらに、住まい面のサポートがある案件なら生活費を抑えながら始められます。",
                ]
            )
        body.extend(
            [
                "",
                "教えてもらいながら少しずつ覚えられるので、工場勤務が初めての方でも進めやすい設計です。",
            ]
        )
        details = [
            "## 仕事内容詳細",
            f"- {role_phrase}の製造補助",
            "- マシンオペレーション（材料投入・ボタン操作）",
            "- 工具を使った組立、目視検査",
            "- 部品の運搬・ピッキング",
            "",
            "※配属工程により担当作業が変わります",
            "",
            "## 募集概要",
            f"- 職種: {role_phrase}",
            "- 雇用形態: 派遣（長期）",
            f"- 勤務地: {region_text or '〇〇県〇〇市'}",
            "- 勤務時間: 2交替制（配属先による）",
            f"- 給与: {salary_text}",
            "- 休日: 4勤2休／年間休日141日＋長期休暇",
            "- 応募条件: 未経験OK",
            "- 社会保険あり（けが・病気のときも安心）",
            "",
        ]
        if "寮" in source_text or "住" in source_text:
            details.extend(
                [
                    "",
                    "## 住まいについて",
                    "- 寮費無料（規定あり）",
                    "- 引っ越し代のサポートあり",
                    "- 家具・家電つきの案件もあり",
                ]
            )
        details.extend(
            [
                "",
                "## 応募導線",
                "「高収入の製造求人について聞きたい」という方は、公式LINEにてご連絡ください。",
                "詳しい条件や見学日程をご案内します。",
                "",
                "【公式LINEURL】",
            ]
        )
    else:
        title = f"【在宅】未経験OK／{role_phrase}｜{salary_text}"
        body = [
            "在宅で安定して働きたい方に向けた募集です。",
            f"今回の業務は、{role_phrase}を中心としたデスクワークやオンライン業務が中心。",
            f"{salary_text}を目安に、出勤不要で仕事を進めたい方に相性のよい内容です。",
            "業務はテンプレートや手順書に沿って進めるため、未経験からでも流れを掴みやすい構成です。",
        ]
        details = [
            "## 具体的な業務",
            "- スプレッドシート更新",
            "- 定型文の作成やリライト",
            "- 日程調整、URL手配、連絡文の送付",
            "- 月次資料や進捗の取りまとめ補助",
            "- チーム内タスクの確認や報告",
            "",
            "## サポート体制",
            "- 業務開始時の手順説明",
            "- テンプレ集配布（文面・報告フォーマット）",
            "- チャットで随時質問可能",
            "- 週次で作業レビュー",
            "",
            "## 募集概要",
            f"- 職種: {role_phrase}",
            "- 雇用形態: 契約/業務委託",
            "- 勤務地: 完全在宅（全国どこからでも応募OK・出勤不要）",
            "- 勤務時間: 9:00〜18:00中心（時短相談可）",
            f"- 給与: {salary_text}",
            "- 休日: 土日中心",
            "- 応募条件: **未経験OK**、報連相ができる方",
            "",
            "## FAQ",
            "- PCスキルはどこまで必要？",
            ": 文字入力・表計算の基本操作ができれば開始可能です。",
            "- 研修はありますか？",
            ": あります。実務に直結した内容で進みます。",
            "",
            "## 応募導線",
            "働き方や業務量の相談はLINEで受け付けています。  ",
            "「在宅事務の詳細希望」とご連絡ください。  ",
            "【公式LINEURL】",
            "",
            "## 在宅でも安心して続けやすい理由",
            "この募集は、在宅ワークで起こりやすい「連携不足」「質問しづらさ」「業務の属人化」を避けるため、運用ルールを明確にしています。",
            "日々の連絡はチャット中心で、タスクは優先順位つきで管理。作業開始前にゴールが明確化されるため、迷いながら進める時間を減らせます。",
            "また、報告フォーマットが統一されているため、業務進捗の共有がしやすく、在宅でもチームの一員として動きやすい環境です。",
            "困った際は、自己判断で抱え込まずに相談できる導線が準備されています。",
            "",
            "## 研修・立ち上がりステップ",
            "1. オリエンテーション（業務全体像の説明）",
            "2. ツール設定確認（チャット、管理シート、提出先）",
            "3. サンプル課題（小さな実務を体験）",
            "4. 初回実務（レビューつき）",
            "5. 担当範囲の拡張（習熟度に応じて）",
            "",
            f"本募集は**未経験OK**のため、最初から高難易度の成果だけを求める形ではありません。",
            "まずは正確な対応・期限遵守・報連相の3点を重視し、安定稼働を作ってから次のステップに進みます。",
            "",
            "## 報酬イメージ（目安）",
            "- 初期: 基本業務を安定して実施",
            "- 中期: 対応件数/品質の安定化で単価レンジ拡大",
            "- 上位: 追加業務（改善提案、運用補助、進行管理）を担当",
            "",
            "現在の募集目安は各投稿タイトル・募集概要に記載のとおりです。",
            "稼働時間・担当範囲・成果基準によって実際の報酬は変動しますが、継続稼働により段階的な単価アップを狙える設計です。",
            "",
            "## 応募条件（詳細）",
            "- 在宅での業務時間を確保できる方",
            "- チャット/オンラインMTGでの連絡が可能な方",
            "- 期限を守って納品・報告できる方",
            "- PCの基本操作が可能な方",
            "- 新しい業務を学ぶ意欲がある方",
            "",
            "経験は問いません。**未経験OK**で、実務を通じて習得できる前提です。",
            "",
            "## こんな方に特に向いています",
            "- 通勤時間を減らして、在宅中心で働きたい方",
            "- 1つずつ手順を覚えて仕事の幅を広げたい方",
            "- 長期的にスキルを積み上げたい方",
            "- 指示待ちだけでなく、改善意識を持って働きたい方",
            "",
            "## 選考〜開始までの流れ",
            "1. LINEで応募・希望条件を送信",
            "2. 業務説明と条件確認",
            "3. 適性確認（簡易ヒアリング）",
            "4. 稼働開始日の調整",
            "5. 研修/初回業務スタート",
            "",
            "開始時期は案件状況により調整となります。",
            "「すぐに始めたい」「まずは副業で試したい」など、希望があれば応募時に共有してください。",
            "",
            "## 最後に",
            "本募集はすべて**未経験OK**を前提にしています。",
            "「まずは話を聞いてみたい」という段階でも問題ありません。",
            "ご自身の状況に合った働き方を一緒に整理したい方は、LINEからお問い合わせください。",
            "【公式LINEURL】",
            "",
        ]

    post_text = "\n".join(
        [
            f"# {title}",
            "",
            "## 本文",
            "\n".join(body),
            "",
            *details,
        ]
    )
    return post_text, salary_text


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
    result = subprocess.run(
        ["tesseract", str(file_path), "stdout", "--psm", "6", "-l", "jpn+eng"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def validate_image_kind(file_path: Path, task_kind: str, account_name: str) -> None:
    text = ocr_text(file_path)
    if not text:
        return

    normalized = re.sub(r"\s+", "", text)
    factory_hits = sum(1 for hint in FACTORY_OCR_HINTS if hint in normalized)
    remote_hits = sum(1 for hint in REMOTE_OCR_HINTS if hint in normalized)

    if task_kind == "factory":
        if "在宅" in normalized or "リモート" in normalized or remote_hits >= 2:
            raise RuntimeError(
                f"画像種別の不整合を検出しました: {account_name} / 工場 で `{file_path.name}` に在宅系の語が多く含まれます。"
            )
        if factory_hits == 0 and remote_hits >= 1:
            raise RuntimeError(
                f"画像種別の不整合を検出しました: {account_name} / 工場 で `{file_path.name}` の OCR に工場系語が見当たりません。"
            )
    elif task_kind in {"remote1", "remote2"}:
        if "工場" in normalized or "製造" in normalized or factory_hits >= 2:
            raise RuntimeError(
                f"画像種別の不整合を検出しました: {account_name} / 在宅 で `{file_path.name}` に工場系の語が多く含まれます。"
            )
        if remote_hits == 0 and factory_hits >= 1:
            raise RuntimeError(
                f"画像種別の不整合を検出しました: {account_name} / 在宅 で `{file_path.name}` の OCR に在宅系語が見当たりません。"
            )


def validate_manifest_task(task: dict) -> None:
    expected = expected_image_filename(task["kind"])
    actual = Path(task["image_relpath"]).name
    if actual != expected:
        raise RuntimeError(f"manifest の画像ファイル名が不正です: {task['account_name']} / {task['kind']} -> {actual} (expected {expected})")


def build_tasks(rows: list[list[str]]) -> list[Task]:
    tasks: list[Task] = []
    for idx, row in enumerate(rows, start=7):
        account_no = str(row[0]).strip() if len(row) > 0 else ""
        account_name = sanitize_name(str(row[1]).strip() if len(row) > 1 else "")
        if not account_name:
            continue

        factory_region = normalize_prefecture(str(row[FACTORY_REGION_INDEX]).strip() if len(row) > FACTORY_REGION_INDEX else "")
        factory_source_post = str(row[FACTORY_POST_INDEX]).strip() if len(row) > FACTORY_POST_INDEX else ""
        remote_region = normalize_prefecture(str(row[REMOTE_REGION_INDEX]).strip() if len(row) > REMOTE_REGION_INDEX else "")
        remote1_source_post = str(row[REMOTE1_POST_INDEX]).strip() if len(row) > REMOTE1_POST_INDEX else ""
        remote2_source_post = str(row[REMOTE2_POST_INDEX]).strip() if len(row) > REMOTE2_POST_INDEX else ""

        folder_name = f"{account_name}"
        if factory_source_post:
            factory_case_source = choose_factory_case(account_no, idx, factory_source_post)
            factory_post, factory_salary = build_post_text("factory", factory_region, factory_case_source, account_name)
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
                    prompt_text=build_banner_prompt("factory", factory_region, factory_post, account_name, factory_salary, extract_role_phrase(factory_case_source, "factory")),
                )
            )
        if remote1_source_post:
            remote1_post, remote1_salary = build_post_text("remote1", remote_region, remote1_source_post, account_name)
            tasks.append(
                Task(
                    account_no=account_no,
                    account_name=account_name,
                    row_idx=idx,
                    kind="remote1",
                    label_ja="在宅1",
                    image_col=REMOTE1_IMAGE_COL,
                    post_col="S",
                    region=remote_region,
                    post_text=remote1_post,
                    salary_text=remote1_salary,
                    folder_name=folder_name,
                    image_filename="在宅1.jpg",
                    post_filename=post_filename_for_label("在宅1"),
                    prompt_filename="在宅1_画像プロンプト.md",
                    prompt_text=build_banner_prompt("remote1", remote_region, remote1_post, account_name, remote1_salary, extract_role_phrase(remote1_source_post, "remote1")),
                )
            )
        if remote2_source_post:
            remote2_post, remote2_salary = build_post_text("remote2", remote_region, remote2_source_post, account_name)
            tasks.append(
                Task(
                    account_no=account_no,
                    account_name=account_name,
                    row_idx=idx,
                    kind="remote2",
                    label_ja="在宅2",
                    image_col=REMOTE2_IMAGE_COL,
                    post_col="U",
                    region=remote_region,
                    post_text=remote2_post,
                    salary_text=remote2_salary,
                    folder_name=folder_name,
                    image_filename="在宅2.jpg",
                    post_filename=post_filename_for_label("在宅2"),
                    prompt_filename="在宅2_画像プロンプト.md",
                    prompt_text=build_banner_prompt("remote2", remote_region, remote2_post, account_name, remote2_salary, extract_role_phrase(remote2_source_post, "remote2")),
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
                existing_text = post_path.read_text(encoding="utf-8")
                task.post_text = existing_text
                task.salary_text = extract_salary_text(existing_text, task.kind)
                task.prompt_text = build_banner_prompt(
                    task.kind, task.region, existing_text, task.account_name,
                    task.salary_text, extract_role_phrase(existing_text, task.kind),
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


def prepare(output_root: Path) -> None:
    rows = read_sheet_rows()
    tasks = build_tasks(rows)
    write_prepare_output(output_root, tasks)
    print(json.dumps({"output_root": str(output_root), "task_count": len(tasks)}, ensure_ascii=False))


def sync_drive(output_root: Path, purge_existing: bool) -> None:
    tasks_path = output_root / "tasks.json"
    if not tasks_path.exists():
        raise FileNotFoundError(f"tasks.json が見つかりません: {tasks_path}")

    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    for task in tasks:
        validate_manifest_task(task)
    folder_ids: dict[str, str] = {
        folder["name"]: folder["id"]
        for folder in list_drive_child_folders(PARENT_FOLDER_ID)
    }
    if purge_existing:
        for folder in list_drive_child_folders(PARENT_FOLDER_ID):
            delete_drive_file(folder["id"])
        folder_ids.clear()

    uploaded_account_docs: set[str] = set()
    updates: list[dict] = []
    uploaded = 0

    for task in tasks:
        account_name = task["account_name"]
        if account_name not in folder_ids:
            folder_ids[account_name] = create_drive_folder(account_name, PARENT_FOLDER_ID)
        folder_id = folder_ids[account_name]

        account_dir = output_root / task["folder_name"]
        image_path = account_dir / Path(task["image_relpath"]).name
        post_path = account_dir / Path(task["post_relpath"]).name
        prompt_path = account_dir / Path(task["prompt_relpath"]).name
        summary_path = account_dir / "画像プロンプト一覧.md"

        image_exists = image_path.exists()
        if not post_path.exists():
            raise FileNotFoundError(f"投稿文章が見つかりません: {post_path}")
        if image_exists and image_path.name != expected_image_filename(task["kind"]):
            raise RuntimeError(
                f"画像ファイル名が期待値と一致しません: {account_name} / {task['kind']} -> {image_path.name}"
            )
        if image_exists:
            validate_image_kind(image_path, task["kind"], account_name)
            source_text = source_text_prefers_image(task["kind"], image_path, task["post_text"])
        else:
            source_text = task["post_text"]

        if source_text != task["post_text"]:
            new_post_text, new_salary_text = build_post_text(task["kind"], task["region"], source_text, account_name)
            new_prompt_text = build_banner_prompt(
                task["kind"],
                task["region"],
                new_post_text,
                account_name,
                new_salary_text,
                extract_role_phrase(source_text, task["kind"]),
            )
            post_path.write_text(new_post_text, encoding="utf-8")
            prompt_path.write_text(render_prompt_document(task, image_path, new_post_text, new_prompt_text), encoding="utf-8")
            task["post_text"] = new_post_text
            task["salary_text"] = new_salary_text
            task["prompt_text"] = new_prompt_text
        else:
            prompt_path.write_text(render_prompt_document(task, image_path, task["post_text"], task["prompt_text"]), encoding="utf-8")

        if account_name not in uploaded_account_docs and summary_path.exists():
            replace_drive_file(summary_path, folder_id)
            uploaded_account_docs.add(account_name)
        replace_drive_file(post_path, folder_id)
        if prompt_path.exists():
            replace_drive_file(prompt_path, folder_id)

        if image_exists:
            file_id = replace_drive_file(image_path, folder_id)
            make_public(file_id)
            uploaded += 1
            updates.append(
                {
                    "range": f"{SHEET_NAME}!{task['image_col']}{task['row_idx']}",
                    "values": [[f'=IMAGE("https://drive.google.com/uc?id={file_id}")']],
                }
            )
        else:
            print(f"⚠️ 画像が見つからないため画像列は維持します: {image_path}")
        updates.append(
            {
                "range": f"{SHEET_NAME}!{task['post_col']}{task['row_idx']}",
                "values": [[sheet_post_text(task["kind"], task["post_text"])]],
            }
        )

    if updates:
        batch_update_sheet(updates)

    print(json.dumps({"output_root": str(output_root), "uploaded": uploaded, "updated_cells": len(updates)}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="JMTY weekly prompt/image bundle helper")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("prepare")

    rotate_parser = subparsers.add_parser("rotate-sheet")
    rotate_parser.add_argument("--dry-run", action="store_true")

    sync_parser = subparsers.add_parser("sync-drive")
    sync_parser.add_argument("--purge-existing", action="store_true")

    args = parser.parse_args()
    output_root = Path(args.output_root).expanduser()

    if args.command == "prepare":
        prepare(output_root)
    elif args.command == "rotate-sheet":
        rotate_sheet(output_root, dry_run=args.dry_run)
    elif args.command == "sync-drive":
        sync_drive(output_root, purge_existing=args.purge_existing)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
