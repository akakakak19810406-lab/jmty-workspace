#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path


SPREADSHEET_ID = "1GKBTHwBS6W0D30X_yK7vqsaDRWw3p1tXM7lnFhyb0Uw"
ACCOUNT_SHEET_RANGE = "アカウント情報!A7:H1000"


CITY_CANDIDATES = {
    "北海道": [("札幌市", 6), ("旭川市", 3), ("函館市", 2)],
    "青森県": [("青森市", 6), ("八戸市", 3), ("弘前市", 2)],
    "岩手県": [("盛岡市", 6), ("一関市", 3), ("奥州市", 2)],
    "宮城県": [("仙台市", 6), ("石巻市", 3), ("大崎市", 2)],
    "秋田県": [("秋田市", 6), ("横手市", 3), ("大仙市", 2)],
    "山形県": [("山形市", 6), ("鶴岡市", 3), ("酒田市", 2)],
    "福島県": [("いわき市", 6), ("郡山市", 4), ("福島市", 3)],
    "茨城県": [("水戸市", 5), ("つくば市", 4), ("日立市", 3)],
    "栃木県": [("宇都宮市", 6), ("小山市", 3), ("栃木市", 2)],
    "群馬県": [("高崎市", 6), ("前橋市", 4), ("太田市", 3)],
    "埼玉県": [("さいたま市", 6), ("川口市", 4), ("川越市", 3)],
    "千葉県": [("千葉市", 6), ("船橋市", 4), ("松戸市", 3)],
    "東京都": [("世田谷区", 6), ("練馬区", 4), ("大田区", 3)],
    "神奈川県": [("横浜市", 6), ("川崎市", 4), ("相模原市", 3)],
    "新潟県": [("新潟市", 6), ("長岡市", 3), ("上越市", 2)],
    "富山県": [("富山市", 6), ("高岡市", 3), ("射水市", 2)],
    "石川県": [("金沢市", 6), ("白山市", 3), ("小松市", 2)],
    "福井県": [("福井市", 6), ("坂井市", 3), ("越前市", 2)],
    "山梨県": [("甲府市", 6), ("甲斐市", 3), ("南アルプス市", 2)],
    "長野県": [("長野市", 6), ("松本市", 4), ("上田市", 2)],
    "岐阜県": [("岐阜市", 6), ("大垣市", 3), ("各務原市", 2)],
    "静岡県": [("浜松市", 5), ("静岡市", 5), ("富士市", 2)],
    "愛知県": [("名古屋市", 6), ("豊田市", 4), ("岡崎市", 3)],
    "三重県": [("四日市市", 6), ("津市", 4), ("鈴鹿市", 3)],
    "滋賀県": [("大津市", 6), ("草津市", 4), ("長浜市", 2)],
    "京都府": [("京都市", 6), ("宇治市", 3), ("亀岡市", 2)],
    "大阪府": [("大阪市", 6), ("堺市", 4), ("東大阪市", 3)],
    "兵庫県": [("神戸市", 6), ("姫路市", 4), ("尼崎市", 3)],
    "奈良県": [("奈良市", 6), ("橿原市", 3), ("生駒市", 2)],
    "和歌山県": [("和歌山市", 6), ("田辺市", 2), ("橋本市", 2)],
    "鳥取県": [("鳥取市", 6), ("米子市", 4), ("倉吉市", 2)],
    "島根県": [("松江市", 6), ("出雲市", 4), ("浜田市", 2)],
    "岡山県": [("岡山市", 6), ("倉敷市", 4), ("津山市", 2)],
    "広島県": [("広島市", 6), ("福山市", 4), ("呉市", 2)],
    "山口県": [("下関市", 6), ("山口市", 3), ("宇部市", 3)],
    "徳島県": [("徳島市", 6), ("阿南市", 3), ("鳴門市", 2)],
    "香川県": [("高松市", 6), ("丸亀市", 3), ("坂出市", 2)],
    "愛媛県": [("松山市", 6), ("今治市", 3), ("新居浜市", 2)],
    "高知県": [("高知市", 6), ("南国市", 2), ("四万十市", 2)],
    "福岡県": [("福岡市", 6), ("北九州市", 4), ("久留米市", 3)],
    "佐賀県": [("佐賀市", 6), ("唐津市", 3), ("鳥栖市", 2)],
    "長崎県": [("長崎市", 6), ("佐世保市", 4), ("諫早市", 3)],
    "熊本県": [("熊本市", 6), ("八代市", 3), ("天草市", 2)],
    "大分県": [("大分市", 6), ("別府市", 3), ("中津市", 2)],
    "宮崎県": [("宮崎市", 6), ("都城市", 3), ("延岡市", 2)],
    "鹿児島県": [("鹿児島市", 6), ("霧島市", 3), ("鹿屋市", 2)],
    "沖縄県": [("那覇市", 6), ("沖縄市", 3), ("うるま市", 2)],
}


def run_gws_command(cmd_args: list[str]) -> dict:
    params = json.dumps({
        "spreadsheetId": SPREADSHEET_ID,
        "range": ACCOUNT_SHEET_RANGE,
        "valueRenderOption": "FORMULA",
    }, ensure_ascii=False)
    shell_cmd = (
        "export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file; "
        f"gws sheets spreadsheets values get --params '{params}'"
    )
    result = subprocess.run(
        ["/bin/zsh", "-lc", shell_cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"GWS error:\n{result.stderr.strip()}")
    stdout = result.stdout.strip()
    if stdout.startswith("Using keyring backend: file"):
        stdout = stdout.split("\n", 1)[1].strip()
    return json.loads(stdout) if stdout else {}


def lookup_prefecture(account_no: str | None, account_name: str | None) -> str | None:
    data = run_gws_command([])
    rows = data.get("values", [])
    if not rows:
        return None

    for row in rows:
        row_account_no = str(row[0]).strip() if len(row) > 0 else ""
        row_account_name = str(row[2]).strip() if len(row) > 2 else ""
        prefecture = str(row[7]).strip() if len(row) > 7 else ""
        if not prefecture:
            continue
        if account_no and row_account_no == str(account_no).strip():
            return prefecture if prefecture.endswith(("都", "道", "府", "県")) else f"{prefecture}県"
        if account_name and row_account_name == account_name.strip():
            return prefecture if prefecture.endswith(("都", "道", "府", "県")) else f"{prefecture}県"
    return None


def choose_city(prefecture: str, seed: int | None = None) -> str:
    candidates = CITY_CANDIDATES.get(prefecture)
    if not candidates:
        return "〇〇市"

    rng = random.Random(seed)
    cities = [city for city, _ in candidates]
    weights = [weight for _, weight in candidates]
    return rng.choices(cities, weights=weights, k=1)[0]


TEMPLATE = """# タイトル

## 本文

## 仕事内容詳細

## 募集概要
- 職種:
- 雇用形態:
- 勤務地: {location}
- 勤務時間:
- 給与:
- 休日:
- 応募条件:

## 応募導線
公式LINEに登録後、ボタン押すだけ！  
10秒で問い合わせ完了！  
【公式LINEURL】
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    parser.add_argument("--count", type=int, default=14, help="生成するファイル数（デフォルト: 14）")
    parser.add_argument("--prefecture", help="勤務地に使う都道府県名（例: 福岡県）")
    parser.add_argument("--city", help="勤務地に使う市区町村名を固定したい場合に指定")
    parser.add_argument("--seed", type=int, help="重み付きランダムの固定シード")
    parser.add_argument("--account-no", help="アカウント情報シートのアカウントNo")
    parser.add_argument("--account-name", help="アカウント情報シートのアカウント名")
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)

    prefecture = args.prefecture
    if not prefecture and (args.account_no or args.account_name):
        try:
            prefecture = lookup_prefecture(args.account_no, args.account_name)
        except RuntimeError as exc:
            print(
                "Warning: アカウント情報シートから担当エリアを取得できませんでした。"
                " 必要なら --prefecture で直接指定してください。\n"
                f"{exc}",
                file=sys.stderr,
            )

    if args.city and prefecture:
        location = f"{prefecture}{args.city}"
    elif prefecture:
        location = f"{prefecture}{choose_city(prefecture, seed=args.seed)}"
    else:
        location = "〇〇県〇〇市"

    for index in range(1, args.count + 1):
        output_file = output_root / f"post{index:02d}.md"
        if not output_file.exists():
            output_file.write_text(TEMPLATE.format(location=location), encoding="utf-8")

    print(f"Created {args.count} post files under: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
