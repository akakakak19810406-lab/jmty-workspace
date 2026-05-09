import subprocess
import json
import sys
import os
import re

# Spreadsheet ID and Root Folder from Jimoty/Nanobanana context
SPREADSHEET_ID = "1GKBTHwBS6W0D30X_yK7vqsaDRWw3p1tXM7lnFhyb0Uw"
SHEET_NAME = "アカウント情報"
PARENT_FOLDER_ID = "16P5sOzyJHLemwURON6Wf1i7NjodK3WWF"

def run_gws_command(cmd_args):
    """gws.cmd CLI を介して Google Workspace API を呼び出す"""
    cmd = ["gws.cmd"] + cmd_args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return {"error": result.stderr}
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except:
        return {"raw": result.stdout}

def get_sheet_values(range_name):
    """スプレッドシートから画像数式（FORMULA）を含む値を取得する"""
    res = run_gws_command(["sheets", "spreadsheets", "values", "get", "--params", json.dumps({
        "spreadsheetId": SPREADSHEET_ID,
        "range": range_name,
        "valueRenderOption": "FORMULA"
    })])
    if "error" in res:
        print(f"Error getting values: {res['error']}")
        return None
    return res.get("values", [])

def get_account_folders():
    """親フォルダ直下のアカウントフォルダ一覧を取得する"""
    query = f"'{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = run_gws_command(["drive", "files", "list", "--params", json.dumps({"q": query})])
    if "error" in res:
        print(f"Error listing folders: {res['error']}")
        return {}
    return {f["name"]: f["id"] for f in res.get("files", [])}

def get_folder_files(folder_id):
    """指定したフォルダ内のファイル一覧を取得する"""
    if not folder_id: return {}
    query = f"'{folder_id}' in parents and trashed = false"
    res = run_gws_command(["drive", "files", "list", "--params", json.dumps({"q": query})])
    if "error" in res:
        print(f"Error listing files in {folder_id}: {res['error']}")
        return {}
    return {f["id"]: f["name"] for f in res.get("files", [])}

def get_file_info(file_id):
    """ファイルの詳細情報を取得する"""
    res = run_gws_command(["drive", "files", "get", "--params", json.dumps({
        "fileId": file_id,
        "fields": "id, name, parents"
    })])
    return res

def extract_file_id(formula):
    """IMAGE関数などの文字列から Google Drive ファイルIDを抽出する"""
    match = re.search(r'id=([a-zA-Z0-9_-]+)', formula)
    return match.group(1) if match else None

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- Jimoty 画像整合性調査開始 ---")
    
    values = get_sheet_values(f"{SHEET_NAME}!A7:U")
    if not values:
        print("スプレッドシートの読み取りに失敗しました。")
        return

    account_folders = get_account_folders()
    print(f"発見したアカウントフォルダ数: {len(account_folders)}")

    results = []
    
    for i, row in enumerate(values):
        row_idx = i + 7
        if len(row) < 2: continue
        account_name = row[1].strip()
        if not account_name: continue

        folder_id = account_folders.get(account_name)
        folder_files = get_folder_files(folder_id) if folder_id else {}
        
        target_cols = [
            (8, "工場 (I列)", f"Factory_Job_{row_idx:02d}"),
            (17, "在宅1 (R列)", f"Remote1_Job_{row_idx:02d}"),
            (19, "在宅2 (T列)", f"Remote2_Job_{row_idx:02d}")
        ]
        
        for col_idx, label, expected_name_prefix in target_cols:
            status = "OK"
            msg = ""
            file_id_in_sheet = None
            
            if col_idx < len(row):
                formula = row[col_idx]
                if "IMAGE" in formula:
                    file_id_in_sheet = extract_file_id(formula)
            
            if file_id_in_sheet:
                if not folder_id:
                    status = "WRONG_LOCATION"
                    msg = "アカウントフォルダが存在しません"
                elif file_id_in_sheet not in folder_files:
                    # どこにあるか探す
                    info = get_file_info(file_id_in_sheet)
                    if "error" in info:
                        status = "MISSING"
                        msg = "ファイルがDrive上に見つかりません（削除された可能性があります）"
                    else:
                        status = "WRONG_LOCATION"
                        msg = f"ファイルは存在しますがフォルダが違います (現在の親: {info.get('parents', 'Unknown')})"
                else:
                    status = "OK"
            else:
                post_col_idx = {8:9, 17:18, 19:20}[col_idx]
                if post_col_idx < len(row) and row[post_col_idx].strip():
                    status = "EMPTY"
                    msg = "投稿文はあるが画像が未設定です"
                else:
                    status = "SKIP"
                    msg = "投稿文なし"

            results.append({
                "row": row_idx,
                "account": account_name,
                "item": label,
                "status": status,
                "message": msg,
                "file_id": file_id_in_sheet
            })

    # 全部OKか確認
    ng_list = [r for r in results if r["status"] not in ["OK", "SKIP"]]
    if not ng_list:
        print("\n[判定] すべての画像が正しく配置されています。")
    else:
        print(f"\n[判定] {len(ng_list)} 件の不整合が見つかりました。")
        for res in ng_list:
            print(f"  - [行{res['row']:02d}] {res['account']} - {res['item']}: {res['status']} {res['message']}")

    # 結果をJSONで保存（オプション）
    try:
        with open("investigation_result.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    except: pass

if __name__ == "__main__":
    main()
