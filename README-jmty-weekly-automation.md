# ジモティー週次自動化メモ

## 概要
毎週月曜 0:00 に、ジモティー用の投稿文章・画像プロンプト・求人バナー画像を作成する運用です。

## テンプレート編集場所
画像プロンプトテンプレートは次のフォルダに保存します。

`inputs/jmty_image_prompt_templates/`

ファイル名に `factory` / `工場` が入っているものは工場求人、`remote` / `在宅` が入っているものは在宅求人、`common` / `共通` が入っているものは全種別に使われます。

## 主な出力先
`outputs/jmty-weekly/current/`

アカウントごとに次のようなファイルが作られます。

- `工場の投稿文章.md`
- `工場_画像プロンプト.md`
- `工場.jpg`
- `在宅1の投稿文章.md`
- `在宅1_画像プロンプト.md`
- `在宅1.jpg`
- `在宅2の投稿文章.md`
- `在宅2_画像プロンプト.md`
- `在宅2.jpg`

## 実行の考え方
Drive への画像アップロードは `sync-drive`、スプレッドシート反映は `sync-sheet` として分けて実行します。GWS 認証切れなどでDrive反映が失敗した場合だけ、Chrome で Google Drive を開いて行います。
最終一括実行では `sync-sheet` の後に `validate-sheet-posts --repair` を実行し、画像条件と投稿文がずれたセルだけを修正してから再取得確認します。

画像生成は Codex の built-in 画像生成ツールを使います。Python から直接画像生成 API を叩く方式にはしません。

## 次回以降の実行前チェック
この自動化は、次の前提がそろっていると最後まで進められます。

- Codex の writable roots に、このリポジトリ `/Users/tsukinoayaka/Desktop/jimty` を含める
- automation memory を正規保存する場合は、writable roots に `/Users/tsukinoayaka/.codex/automations/jmty-weekly-posts-and-images` も含める
- `gws` を PATH に入れる。別パスの場合は `JMTY_GWS_BIN=/path/to/gws` を指定する
- 画像変更・改善メモの Discord 通知用に `JMTY_DISCORD_JMTY_WEBHOOK_URL` か `config/discord-jmty-webhook.json` を設定する
- Git 更新通知は別設定の `JMTY_DISCORD_GIT_WEBHOOK_URL` / `config/discord-git-webhook.json` を使う
- Chrome で Drive 反映する場合は、Codex Chrome 連携が `drive.google.com` を開ける状態にしておく

不足している場合も、週次スクリプトは `outputs/jmty-weekly/current/_improvement_reports/` に改善レポートを残します。
automation memory に書けない環境では、この改善レポートを当面の代替記録として扱います。

## Mac launchd 定期実行
毎週日曜 23:55 に、Mac の LaunchAgent から週次一括実行を開始する設定を用意しています。
月曜 0:00 までに処理を走らせ始めるため、`StartCalendarInterval` は Sunday 23:55 にしています。

主なファイル:

- `scripts/jmty_weekly_launchd.py`: GUIサーバーを起動せず、既存の `weekly-bulk` と同じ処理を実行するCLIラッパー
- `scripts/run_jmty_weekly_launchd.sh`: launchd から呼ぶ固定エントリポイント
- `launchd/com.deguchishouma.jmty.weekly.plist`: LaunchAgent 設定
- `scripts/install_jmty_weekly_launchd.sh`: `~/Library/LaunchAgents/` への登録補助

登録前チェック:

```bash
python3 scripts/jmty_weekly_launchd.py --preflight-only --skip-auth-login
```

登録:

```bash
zsh scripts/install_jmty_weekly_launchd.sh
```

手動で launchd 実行を試す場合:

```bash
launchctl kickstart -k "gui/$(id -u)/com.deguchishouma.jmty.weekly"
```

ログは次に出ます。

- `outputs/launchd/jmty-weekly.out.log`
- `outputs/launchd/jmty-weekly.err.log`

停止・解除する場合:

```bash
launchctl bootout "gui/$(id -u)/com.deguchishouma.jmty.weekly"
```

### GWS 認証フォールバック
`launchd` 実行前に `gws` 認証状態を確認します。
認証が有効ならそのまま週次一括実行へ進みます。

認証が切れている場合は、JMTY用Discord webhookへ通知したうえで `gws auth login --services drive,sheets` を開始し、Google認証URLを取得できた場合はそのURLもDiscordへ通知します。
Google OAuth はGoogleログイン画面での許可操作が必要なため、保存済み認証情報が完全に失効している場合だけは完全無人復旧できません。
その場合は通知されたURLまたは次のコマンドで再認証し、次回の定期実行または `--resume` 付き手動実行で復旧します。

```bash
gws auth login --services drive,sheets
python3 scripts/jmty_weekly_launchd.py --resume
```

## 投稿文バリエーション
投稿文は `jmty-posts-14-variants` の考え方に合わせて、14種類の訴求軸からアカウント・行・種別ごとに選んで作成します。

公式LINEは実URLを書かず、すべて `【公式LINEURL】` のプレースホルダーにします。

## 地域ランダム割当
週次処理の最初に `rotate-sheet` を実行し、スプレッドシート上の投稿地域と投稿文の担当をランダムに入れ替えます。
工場はH列の地域を正本にして投稿文をAI再作成し、その投稿文を元に画像プロンプトを作ります。
在宅地域はQ列の1セル内で、1行目を在宅1、2行目を在宅2として読み分けます。投稿文作成と画像プロンプト作成でもこの分割を使います。ただし在宅投稿文と在宅画像には地名を出さず、完全在宅の表現に寄せます。

## Google Drive 反映
まず `sync-drive --purge-account-images` で、GWS 経由の Drive 反映を試します。
スプレッドシートには別途 `sync-sheet` を実行し、投稿文とDrive画像URLを反映します。

GWS が使えない場合は、Chrome で次の Google Drive フォルダを開きます。

https://drive.google.com/drive/folders/16P5sOzyJHLemwURON6Wf1i7NjodK3WWF

Google Drive 側では、アカウントフォルダは残したまま既存の画像ファイルだけ削除し、新しい画像をアップロードします。

ローカルにも画像だけのコピーとして、次のフォルダが作られます。

`outputs/jmty-weekly/current/_drive_images/`

この `_drive_images` 配下はアカウント名ごとのフォルダ構成になっているため、Drive 側にも同じ構成でアップロードします。

## Discord 通知
GWS 認証切れ、権限エラー、APIエラーなどで Drive 反映またはスプレッドシート反映が失敗した場合は、Discord デスクトップアプリで次の場所へ通知します。

- サーバー: `AIエキスパート`
- カテゴリー: `管理者`
- チャンネル: `ジモティーメモ`

通知には、失敗理由、Chrome フォールバックに進んだか、未反映のアカウント名・画像パス・必要なセル更新を含めます。

### 自動改善メモ
週次スクリプトでエラーが起きた場合は、次の流れを自動で行います。

1. エラー内容を分類する
2. `outputs/jmty-weekly/current/_improvement_reports/` に改善レポートを保存する
3. Discord のジモティーメモへ、分類・改善済み内容・次の改善案を通知する

画像変更・改善メモの Discord 通知は、環境変数 `JMTY_DISCORD_JMTY_WEBHOOK_URL` または `config/discord-jmty-webhook.json` の `JMTY_DISCORD_JMTY_WEBHOOK_URL` を使います。Git 更新通知は `JMTY_DISCORD_GIT_WEBHOOK_URL` / `config/discord-git-webhook.json` を使うため、画像通知とは別です。
Webhook が未設定の場合、処理本体は止めずに通知だけスキップします。

手動で「今回入れた改善」を送る場合:

```bash
python3 .agent/skills/nanobanana-banner-gen/scripts/jmty_weekly_assets.py notify-improvement \
  --title "自動改善プロセスを追加" \
  --summary "失敗時に改善レポートを作成し、ジモティメモへ通知する仕組みを追加しました。" \
  --changed-file ".agent/skills/nanobanana-banner-gen/scripts/jmty_weekly_assets.py"
```

## 検証
`validate-output` で次を確認します。

- 投稿文に `【公式LINEURL】` がある
- 投稿文に実URLが混ざっていない
- 在宅投稿には `完全在宅` がある
- 工場画像と在宅画像の取り違えがないか OCR で確認する

`validate-sheet-posts` で Google Sheets 反映後の投稿文セルを確認します。

- 既定は dry-run で、修正対象セルと理由だけを JSON で出力する
- `--repair` を付けると、不一致または品質問題がある投稿文セルだけを更新する
- 更新後はシートを再取得し、残件数を `remaining_issue_count` に出力する
- 必要な場合だけ `--drive-ocr` を付け、シート画像セルのDrive画像も一時取得してOCRする
