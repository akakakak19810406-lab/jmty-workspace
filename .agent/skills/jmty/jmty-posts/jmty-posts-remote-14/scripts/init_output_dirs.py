#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = """# タイトル

## 本文

## 業務内容詳細

## 募集概要
- 職種:
- 雇用形態:
- 勤務地: 完全在宅（全国どこからでも応募OK・出勤不要）
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
    parser.add_argument("--location", default="〇〇県〇〇市")
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)

    for index in range(1, args.count + 1):
        output_file = output_root / f"post{index:02d}.md"
        if not output_file.exists():
            output_file.write_text(TEMPLATE.format(location=args.location), encoding="utf-8")

    print(f"Created {args.count} post files under: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
