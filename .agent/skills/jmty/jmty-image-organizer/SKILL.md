---
name: jmty-image-organizer
description: ジモティーのアカウント情報スプレッドシートに紐付いた画像が、Google Drive上の正しいアカウントフォルダ内に格納されているかを確認し、必要に応じて移動・リネームして整理します。
---

# Jimoty 画像整理スキル (jmty-image-organizer)

## 概要
このスキルは、ジモティーの求人投稿用スプレッドシート（アカウント情報）と Google Drive フォルダ間の整合性を保つためのツールです。
シートに設定された画像（IMAGE関数）を解析し、その画像が該当するアカウント専用のフォルダ内に存在するかを確認します。

## 目的
*   画像がアカウントフォルダ外（別のフォルダやルート）にある場合に、正しい場所へ移動する。
*   ファイル名を `Factory_Job_XX.jpg` などの命名規則に則って正規化する。
*   スプレッドシートのリンクと実際のファイル配置の不整合を解消する。

## 使用方法
1.  このスキルを実行する。
2.  「調査のみ」か「調査と整理（移動・リネーム）」かを選択する。
3.  スクリプトが自動的にスプレッドシートを読み込み、Google Drive の整理を実行する。

## スクリプト構成
*   **調査用**: `scripts/investigate_spreadsheet.py`
    *   スプレッドシートを読み取り、現在の Drive 上の配置状況をレポートします。
*   **整理用**: `scripts/organize_images.py`
    *   画像の移動とリネームを実行します（シートのリンクは維持されます）。

## 実行コマンド
### 調査
```bash
python "$TEAM_INFO_ROOT/.agent/skills/jmty/jmty-image-organizer/scripts/investigate_spreadsheet.py"
```

### 整理・修復
```bash
python "$TEAM_INFO_ROOT/.agent/skills/jmty/jmty-image-organizer/scripts/organize_images.py"
```

## 注意事項
*   このスキルは**既存の画像の場所を整理するだけ**であり、新しい画像を生成（再生成）することはありません。
*   画像が完全に欠落している（IDが無効）場合は、エラーとして報告されます。その場合は `nanobanana-banner-gen` スキルで再生成を検討してください。
