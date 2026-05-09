#!/usr/bin/env python3
"""
Google Drive アップロードツール（rclone 版）
rclone を使って Google Drive の team-info フォルダへファイル/フォルダをアップロードする。
Google Drive for Desktop のローカルマウントパスには依存しない。
"""

import json
import os
import sys
import subprocess
from pathlib import Path

# ── 設定 ──────────────────────────────────────────────
REMOTE_NAME = "gdrive"
GOOGLE_DRIVE_FOLDER_ID = "1QKaUP9fvA46mINkpSR1b2wqrIBE6By0t"
# ──────────────────────────────────────────────────────


def get_team_info_root() -> Path:
    """TEAM_INFO_ROOT 環境変数を取得して Path で返す。未設定なら即終了。"""
    root = os.environ.get("TEAM_INFO_ROOT", "").strip()
    if not root:
        print("✗ TEAM_INFO_ROOT が未設定です。")
        print("  setup-local-machine を実行して環境変数を設定してください。")
        print("  例: export TEAM_INFO_ROOT=/path/to/team-info")
        sys.exit(1)
    p = Path(root)
    if not p.is_dir():
        print(f"✗ TEAM_INFO_ROOT が指すディレクトリが存在しません: {p}")
        sys.exit(1)
    return p


def check_rclone() -> None:
    """rclone コマンドが存在するか確認する。なければ終了。"""
    result = subprocess.run(
        ["rclone", "version"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("✗ rclone が見つかりません。")
        print("  まず /setup を実行して rclone を入れてください。")
        print("  Mac:     brew install rclone")
        print("  Windows: winget install Rclone.Rclone")
        print("  詳細:    https://rclone.org/downloads/")
        sys.exit(1)


def check_gdrive_remote() -> None:
    """gdrive リモートが rclone に設定されているか確認する。なければ自動セットアップする。"""
    result = subprocess.run(
        ["rclone", "listremotes"],
        capture_output=True,
        text=True,
    )
    remotes = result.stdout.splitlines()
    if f"{REMOTE_NAME}:" not in remotes:
        print(f"  '{REMOTE_NAME}' リモートが未設定です。自動セットアップを開始します。")
        print("  ブラウザが開くので Google アカウントでログインしてください。")
        print()

        create_result = subprocess.run(
            ["rclone", "config", "create", REMOTE_NAME, "drive", "scope=drive"],
            capture_output=True,
            text=True,
        )
        if create_result.returncode != 0:
            print(f"✗ リモートの作成に失敗しました:\n{create_result.stderr}")
            sys.exit(1)

        reconnect_result = subprocess.run(
            ["rclone", "config", "reconnect", f"{REMOTE_NAME}:"]
        )
        if reconnect_result.returncode != 0:
            print("✗ Google Drive の認証に失敗しました。")
            print("  手動で設定する場合: rclone config")
            sys.exit(1)

        print(f"\n  ✓ '{REMOTE_NAME}' の設定が完了しました。")


def preflight(team_info_root: Path) -> None:
    """実行前チェックをまとめて行う。"""
    print("  事前チェック中...")
    check_rclone()
    check_gdrive_remote()
    print(f"  ✓ rclone OK / remote '{REMOTE_NAME}' OK")
    print(f"  ✓ TEAM_INFO_ROOT: {team_info_root}")


def pick_source(team_info_root: Path) -> Path:
    """コピー元のパスをユーザーに選ばせる。"""
    while True:
        raw = input(
            "\nコピー元のパスを入力してください\n"
            "（絶対パス、または TEAM_INFO_ROOT からの相対パス）:\n> "
        ).strip()
        if not raw:
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = team_info_root / p
        if p.exists():
            return p
        print(f"  ✗ パスが見つかりません: {p}")


def pick_files_from_dir(directory: Path) -> list[Path]:
    """ディレクトリ内のアイテムを一覧表示し、番号で選ばせる。"""
    items = sorted(directory.iterdir())
    if not items:
        print(f"  ✗ {directory} は空です")
        sys.exit(1)

    print(f"\n{directory} 内のファイル/フォルダ:")
    for i, item in enumerate(items):
        kind = "[フォルダ]" if item.is_dir() else "[ファイル]"
        size = ""
        if item.is_file():
            size = f"  ({item.stat().st_size / 1024:.0f} KB)"
        print(f"  {i + 1:>3}. {kind} {item.name}{size}")

    print("\n番号を入力（複数はカンマ区切り、all で全選択）:")
    raw = input("> ").strip()

    if raw.lower() == "all":
        return list(items)

    selected = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(items):
                selected.append(items[idx])
            else:
                print(f"  ✗ 範囲外の番号: {token}")
        else:
            print(f"  ✗ 無効な入力: {token}")
    return selected


def pick_dest_subdir() -> str:
    """コピー先のサブフォルダ名を入力させる。空のまま Enter で team-info 直下。"""
    print(f"\nコピー先: {REMOTE_NAME}:{GOOGLE_DRIVE_FOLDER_ID}/")
    print("サブフォルダ名を入力（team-info 直下に置く場合は Enter）:")
    sub = input("> ").strip()
    if sub:
        return f"{REMOTE_NAME}:{GOOGLE_DRIVE_FOLDER_ID}/{sub}"
    return f"{REMOTE_NAME}:{GOOGLE_DRIVE_FOLDER_ID}"


def get_gdrive_url(dest_remote: str, item_name: str) -> str | None:
    """アップロード先アイテムの Google Drive URL を返す。取得できなければ None。"""
    result = subprocess.run(
        ["rclone", "lsjson", dest_remote],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        items = json.loads(result.stdout)
        for item in items:
            if item.get("Name") == item_name:
                item_id = item.get("ID", "")
                if item.get("IsDir"):
                    return f"https://drive.google.com/drive/folders/{item_id}"
                else:
                    return f"https://drive.google.com/file/d/{item_id}/view"
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def rclone_upload(src: Path, dest_remote: str, show_progress: bool = True) -> bool:
    """rclone copy で src を dest_remote へアップロードする。成功したら True を返す。"""
    cmd = ["rclone", "copy", str(src), dest_remote]
    if show_progress:
        cmd.append("--progress")

    print(f"\n  アップロード中: {src.name} → {dest_remote}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"  ✗ アップロード失敗: {src.name}")
        print("  詳細確認: rclone copy ... -v")
        print("  権限エラーの場合: rclone config reconnect gdrive:")
        return False

    url = get_gdrive_url(dest_remote, src.name)
    if url:
        print(f"  Google Drive URL: {url}")

    return True


def notify(message: str) -> None:
    """OS ネイティブ通知を送る（macOS のみ）。"""
    if sys.platform == "darwin":
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "Google Drive アップロード"',
            ],
            check=False,
        )


def run_upload(targets: list[Path], dest_remote: str) -> None:
    """targets を dest_remote へアップロードして完了通知する。"""
    success_count = 0
    for t in targets:
        if rclone_upload(t, dest_remote):
            success_count += 1

    fail_count = len(targets) - success_count
    if fail_count == 0:
        msg = f"{success_count} 件を team-info にアップロードしました"
        notify(msg)
        print(f"\n✓ 完了（{success_count} 件）")
    else:
        msg = f"{success_count} 件成功、{fail_count} 件失敗"
        notify(msg)
        print(f"\n⚠ {msg}")
        print("失敗したファイルは rclone copy ... -v で詳細を確認してください。")
        sys.exit(1)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Google Drive アップロードツール（rclone 版）")
    parser.add_argument("--src", help="コピー元のファイルまたはフォルダの絶対パス")
    parser.add_argument("--dest", help="team-info フォルダ直下のコピー先サブパス（例: outputs/アコリエル/）")
    args = parser.parse_args()

    team_info_root = get_team_info_root()
    preflight(team_info_root)

    # ── 引数モード（対話なし）──────────────────────────
    if args.src and args.dest:
        src_path = Path(args.src)
        if not src_path.exists():
            print(f"✗ コピー元が見つかりません: {src_path}")
            sys.exit(1)
        dest_remote = f"{REMOTE_NAME}:{GOOGLE_DRIVE_FOLDER_ID}/{args.dest.strip('/')}"
        run_upload([src_path], dest_remote)
        return

    # ── 対話モード ────────────────────────────────────
    print("=" * 54)
    print("  Google Drive アップロードツール（rclone 版）")
    print(f"  アップロード先: gdrive:team-info")
    print(f"  フォルダID: {GOOGLE_DRIVE_FOLDER_ID}")
    print("=" * 54)

    print("\nコピーモードを選択してください:")
    print("  1. フォルダごとアップロード")
    print("  2. ファイル/フォルダを選んでアップロード")
    while True:
        mode = input("> ").strip()
        if mode in ("1", "2"):
            break
        print("  1 か 2 を入力してください")

    src_path = pick_source(team_info_root)

    if mode == "1":
        if not src_path.is_dir():
            print(f"✗ フォルダではありません: {src_path}")
            sys.exit(1)
        targets = [src_path]
    else:
        targets = pick_files_from_dir(src_path) if src_path.is_dir() else [src_path]

    if not targets:
        print("✗ 選択されたファイルがありません")
        sys.exit(1)

    dest_remote = pick_dest_subdir()

    print("\n--- アップロード内容の確認 ---")
    for t in targets:
        kind = "[フォルダ]" if t.is_dir() else "[ファイル]"
        print(f"  {kind} {t}")
    print(f"→ {dest_remote}")
    print("\n実行しますか？ (y/n)")
    if input("> ").strip().lower() != "y":
        print("キャンセルしました")
        sys.exit(0)

    run_upload(targets, dest_remote)


if __name__ == "__main__":
    main()
