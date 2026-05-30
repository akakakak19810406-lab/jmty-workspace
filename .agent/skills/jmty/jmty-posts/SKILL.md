---
name: jmty-posts
description: JMTY workspace の統合スキル。ジモティ投稿文作成、週次画像素材処理、画像整理、Google Drive 同期をこの入口だけで扱う。
---

# JMTY 統合スキル

## 役割
この repo でジモティ関連の制作・整理を行うときは、原則このスキルだけを読む。
工場求人、在宅求人、14パターン投稿、画像素材、Drive 同期は個別スキルとして探さず、このスキル内の作業タイプで切り替える。

## 作業タイプ

| 依頼内容 | このスキルでの扱い |
|---|---|
| 工場求人の投稿文を作る | `factory` |
| 在宅求人の投稿文を作る | `remote` |
| 案件ファイルから14本の投稿文を作る | `variants` |
| 週次の画像・投稿素材を処理する | `weekly-assets` |
| スプレッドシート画像と Drive フォルダを整理する | `image-organize` |
| 投稿出力を共有ストレージへ同期する | `sync` |

## 共通ルール
- 投稿文作成、再作成、リライトでは `.agent/skills/jmty/no-python-post-writing/SKILL.md` を必ず読む。
- 投稿文本文は Python の固定テンプレートや文字列連結で作らない。Python は入力読取、AIプロンプト組立、保存、検証、反映の補助に限定する。
- 公式LINEの導線は `【公式LINEURL】` を使う。固定URLを本文に直書きしない。
- 会社名や固有案件名は原則出さず、匿名表現にする。
- 「注意事項」見出しは入れない。
- アカウント間で、書き出し、訴求軸、対象人物像、口調、CTA が偏らないようにする。
- 出力は `outputs/` 配下へ置き、入力素材は `inputs/` に混ぜない。
- 画像生成や画像整理で外部 API / Google Drive / Google Sheets を使う場合は、実行前に対象と変更内容を確認する。
- トークン上限による生成の途中停止を防ぐため、複数件の文章を生成する際は一括で行わない。必ず「1件生成 → ファイル保存 → 内容検証 → 次の生成」のサイクルを繰り返すこと。

## 入力
- 工場求人素材: `inputs/jmty_factory_cases/`
- 在宅求人素材: `inputs/jmty_remote_samples/`
- 営業スプレッドシート: `ジモティー営業` の `アカウント情報` シート
- 週次素材処理: `.agent/skills/nanobanana-banner-gen/scripts/jmty_weekly_assets.py`

## 出力
- 週次出力: `outputs/jmty-weekly/current/<アカウント名>/`
- 工場投稿: `outputs/jmty-weekly/current/<アカウント名>/工場の投稿文章.md`
- 在宅投稿: `outputs/jmty-weekly/current/<アカウント名>/在宅1の投稿文章.md` / `在宅2の投稿文章.md`
- 単体出力: `outputs/jmty/factory/` / `outputs/jmty/remote/`
- 汎用14パターン: `outputs/jmty/legacy_variants/<timestamp>/`

## factory: 工場求人投稿
1. `inputs/jmty_factory_cases/` から案件ファイルを選ぶ。
2. `アカウント情報` シートの `J列` に投稿文がある行を対象にする。
3. `H列` の担当エリアを県名として使い、市区町村は人口上位候補から重み付きで選ぶ。
4. 各投稿に `勤務地: 〇〇県〇〇市` と `【公式LINEURL】` を入れる。
5. 保存先は `outputs/jmty-weekly/current/<アカウント名>/工場の投稿文章.md`。

## remote: 在宅求人投稿
0. 先に `.agent/skills/jmty/no-python-post-writing/SKILL.md` を読む。
1. `inputs/jmty_remote_samples/` から見本ファイルを選ぶ。
2. `アカウント情報` シートの `S列` または `U列` に投稿文がある行を対象にする。
3. `Q列` の担当エリアは投稿文には入れない。勤務地は `完全在宅（全国どこからでも応募OK）` の意味が伝わる一般表現にする。
4. 投稿文本文はAI生成で作る。Python固定テンプレートで本文を生成しない。
5. `未経験OK` と `【公式LINEURL】` を必ず入れる。
6. `inputs/jmty_remote_samples/` と `inputs/jmty_post_style_samples/remote/` を参照し、職種・訴求・構成を投稿ごとに変える。

## variants: 汎用14パターン投稿
1. ユーザー指定の案件ファイル、または `inputs/` 配下の候補から1つ選ぶ。
2. 14本を別案件・別会社に見えるように書き分ける。**※一括生成はせず、必ず1パターンごとに生成・保存・内容確認のサイクルを回すこと。**
3. 次の差別化軸を重複させない。
   - 業種、職種、ターゲット、働き方、訴求軸、冒頭フック
4. 出力初期化が必要な場合は内部スクリプトを使う。
   - `.agent/skills/jmty/jmty-posts/jmty-posts-14-variants/scripts/init_output_dirs.py`

## weekly-assets: 週次画像・投稿素材
週次の画像素材、投稿文、Drive 反映までまとめて処理したい場合に使う。

```bash
python "$JMTY_ROOT/.agent/skills/nanobanana-banner-gen/scripts/jmty_weekly_assets.py"
```

このスクリプトは画像生成・Drive 更新・スプレッドシート更新を含み得るため、実行前に対象アカウント、上書き対象、出力先を確認する。

## image-organize: 画像整理
既存画像の場所と名前を整理する。新しい画像生成はしない。

調査のみ:
```bash
python "$JMTY_ROOT/.agent/skills/jmty/jmty-image-organizer/scripts/investigate_spreadsheet.py"
```

整理・修復:
```bash
python "$JMTY_ROOT/.agent/skills/jmty/jmty-image-organizer/scripts/organize_images.py"
```

## sync: 投稿出力同期
`outputs/jmty/factory` と `outputs/jmty/remote` を共有ストレージへ同期する。

```bash
python "$JMTY_ROOT/.agent/skills/jmty/jmty-posts/jmty-posts-gdrive-sync/scripts/sync_jmty_posts_to_gdrive.py"
```

コピー先を指定する場合:
```bash
python "$JMTY_ROOT/.agent/skills/jmty/jmty-posts/jmty-posts-gdrive-sync/scripts/sync_jmty_posts_to_gdrive.py" "/destination/root/absolute/path"
```

## 完了報告
- 実行した作業タイプ
- 入力ファイルまたは対象シート
- 出力先
- 生成・更新・同期した件数
- 追加確認が必要な点
