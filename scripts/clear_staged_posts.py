#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# このスクリプトは、ジモティー営業管理用スプレッドシートの投稿文セルを一時的にすべて空（クリア）にします。
# 実行時に元の投稿文データをローカルにバックアップ保存し、後から復元できるようにします。
# 

import os
import sys
import json
from pathlib import Path

# パスの追加
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

import jmty_gui

BACKUP_PATH = ROOT / "outputs/jmty-gui/sheet_posts_backup.json"

def main():
    print("スプレッドシートの投稿文クリア処理を開始します...")
    
    # 最新のスプレッドシート状態を取得
    print("現在のスプレッドシート状態をロード中...")
    state = jmty_gui.reload_sheet_state()
    
    accounts = state.get("accounts", [])
    if not accounts:
        print("アカウント情報が見つかりませんでした。処理を終了します。")
        return
        
    print(f"{len(accounts)} 件のアカウントデータを処理します。")
    
    # バックアップ用データの構築
    backup_data = []
    updates = []
    
    mapping = jmty_gui.load_sheet_mapping()
    fields = mapping["fields"]
    sheet_name = jmty_gui.SHEET_NAME
    
    target_keys = ["factory_post", "remote1_post", "remote2_post"]
    
    for account in accounts:
        row = account["row_number"]
        name = account["account_name"]
        
        # バックアップ用のデータを集約
        acct_backup = {
            "row_number": row,
            "account_name": name,
            "posts": {}
        }
        
        has_post = False
        for key in target_keys:
            val_meta = account["values"].get(key, {})
            val = val_meta.get("value", "")
            acct_backup["posts"][key] = val
            if val.strip():
                has_post = True
                # 更新用パラメータの構築（空文字に更新）
                column = fields[key]
                updates.append({
                    "range": f"{sheet_name}!{column}{row}",
                    "values": [[""]]
                })
        
        if has_post:
            backup_data.append(acct_backup)
            
    if not backup_data:
        print("現在スプレッドシート上に登録されている投稿文はありません（すでに空です）。")
        return
        
    # バックアップを保存
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BACKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    print(f"元の投稿文データをバックアップファイルに保存しました: {BACKUP_PATH}")
    
    # スプレッドシートを更新
    print(f"{len(updates)} セルの投稿文をクリアしています...")
    jmty_gui.batch_update_sheet(updates)
    
    # キャッシュを更新
    print("ローカルキャッシュをリロード中...")
    jmty_gui.reload_sheet_state()
    
    print("スプレッドシートの投稿文クリアが完了しました！明日以降の自動投稿は一時停止されます。")

if __name__ == "__main__":
    main()
