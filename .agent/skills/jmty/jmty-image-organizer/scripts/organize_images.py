import subprocess
import json
import sys
import os
import re

SPREADSHEET_ID = "1GKBTHwBS6W0D30X_yK7vqsaDRWw3p1tXM7lnFhyb0Uw"
SHEET_NAME = "アカウント情報"
PARENT_FOLDER_ID = "16P5sOzyJHLemwURON6Wf1i7NjodK3WWF"

def run_gws_command(cmd_args):
    cmd = ["gws.cmd"] + cmd_args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return {"error": result.stderr}
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except:
        return {"raw": result.stdout}

def get_sheet_values(range_name):
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
    query = f"'{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res = run_gws_command(["drive", "files", "list", "--params", json.dumps({"q": query})])
    if "error" in res:
        print(f"Error listing folders: {res['error']}")
        return {}
    return {f["name"]: f["id"] for f in res.get("files", [])}

def create_account_folder(name):
    res = run_gws_command(["drive", "files", "create", "--params", json.dumps({
        "resource": {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [PARENT_FOLDER_ID]
        }
    })])
    if "error" in res:
        print(f"Error creating folder {name}: {res['error']}")
        return None
    return res.get("id")

def get_file_info(file_id):
    res = run_gws_command(["drive", "files", "get", "--params", json.dumps({
        "fileId": file_id,
        "fields": "id, name, parents"
    })])
    return res

def update_file_parents(file_id, new_parent_id, current_parents):
    params = {
        "fileId": file_id,
        "addParents": new_parent_id
    }
    if current_parents:
        params["removeParents"] = ",".join(current_parents)
    
    res = run_gws_command(["drive", "files", "update", "--params", json.dumps(params)])
    return res

def rename_file(file_id, new_name):
    res = run_gws_command(["drive", "files", "update", "--params", json.dumps({"fileId": file_id}), "--json", json.dumps({"name": new_name})])
    return res

def extract_file_id(formula):
    match = re.search(r'id=([a-zA-Z0-9_-]+)', formula)
    return match.group(1) if match else None

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Jimoty 画像整理・修復処理を開始します ===")

    values = get_sheet_values(f"{SHEET_NAME}!A7:U")
    if not values:
        print("スプレッドシートの読み取りに失敗しました。")
        return

    account_folders = get_account_folders()
    
    for i, row in enumerate(values):
        row_idx = i + 7
        if len(row) < 2: continue
        account_name = row[1].strip()
        if not account_name: continue

        print(f"\n[行{row_idx:02d}] アカウント: {account_name}")
        
        if account_name not in account_folders:
            print(f"  - フォルダ '{account_name}' を作成中...")
            folder_id = create_account_folder(account_name)
            if folder_id:
                account_folders[account_name] = folder_id
            else:
                continue
        
        target_folder_id = account_folders[account_name]
        
        target_cols = [
            (8, "Factory", f"Factory_Job_{row_idx:02d}.jpg"),
            (17, "Remote1", f"Remote1_Job_{row_idx:02d}.jpg"),
            (19, "Remote2", f"Remote2_Job_{row_idx:02d}.jpg")
        ]
        
        for col_idx, label, expected_name in target_cols:
            if col_idx >= len(row): continue
            formula = row[col_idx]
            if "IMAGE" not in formula: continue
            
            file_id = extract_file_id(formula)
            if not file_id: continue
            
            print(f"  - {label} (ID: {file_id}) の整理中...")
            
            info = get_file_info(file_id)
            if "error" in info:
                print(f"    ! ファイルが見つかりません")
                continue
            
            current_parents = info.get("parents", [])
            current_name = info.get("name", "")
            
            if target_folder_id not in current_parents:
                print(f"    -> 正しいフォルダへ移動中...")
                update_res = update_file_parents(file_id, target_folder_id, current_parents)
                if "error" in update_res:
                    print(f"      ! 移動失敗")
                else:
                    print("      DONE: 移動完了")
            
            if expected_name not in current_name:
                print(f"    -> 名前を '{expected_name}' に変更中...")
                rename_res = rename_file(file_id, expected_name)
                if "error" in rename_res:
                    print(f"      ! リネーム失敗")
                else:
                    print("      DONE: リネーム完了")
            else:
                print("    - 名前と場所は正しいです。")

    print("\n=== すべての整理処理が完了しました ===")

if __name__ == "__main__":
    main()
