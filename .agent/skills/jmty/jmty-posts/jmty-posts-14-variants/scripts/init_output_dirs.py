#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = """# タイトル

## 本文

## 募集概要
- 職種:
- 雇用形態:
- 勤務地:
- 勤務時間:
- 給与:
- 休日:
- 応募条件:

## 応募導線
気になる方は公式LINEからご連絡ください。  
【公式LINEURL】

## 注意事項
- 会社名は匿名表現にする（例: 大手製造業、地域密着の物流会社）
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)

    for index in range(1, 15):
        output_dir = output_root / f"{index:02d}_post"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "post.md"
        if not output_file.exists():
            output_file.write_text(TEMPLATE, encoding="utf-8")

    print(f"Created 14 post folders under: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

