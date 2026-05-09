name: git-workflow
description: 変更内容をリモートリポジトリに反映するための Git 操作セット。一本道の履歴を保ち、fetch 先行の同期、スタッシュ管理、競合時の対話を行います。
---

# Git ワークフロースキル

## 絶対パスルール（必須）
- ユーザーに Git コマンドを見せるときは、固定の `/Users/...` ではなく `JMTY_ROOT` を使って絶対パスを組み立てる。
- `git status` のように短く書かず、`git -C "$JMTY_ROOT" status` の形で渡す。
- 新しいパソコンでは、リポジトリルートで `python .agent/skills/common/scripts/jmty_runtime.py setup-local-machine --repo-root .` を 1 回実行して `JMTY_ROOT` を決める。
- オーナー機として使うパソコンだけ、上のコマンドに `--owner` を付ける。
- `cd` を使う場合も、移動先は `"$JMTY_ROOT/..."` の形にする。

## 事前確認 (Pre-flight Check)
スキル実行前に必ず `git -C "$JMTY_ROOT" status` を確認し、未コミットの変更があるか把握すること。

## オーナー機とPR分岐（必須）
- `/git` と `/git-nd` では、push / PR 判断の前に必ず次を実行する。

```bash
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" owner-status
```

- 結果が `owner` のときだけ、`main` へ直接 push してよい。
- 結果が `other` のときは、`main` へ直接 push してはいけない。必ず GitHub アカウント名を含む作業ブランチを push し、`main` 宛てのプルリクエストを作る。
- ユーザーへ「このパソコンがオーナー機か」を聞かない。必ず `owner-status` の結果で機械的に決める。
- `other` のときに未コミット変更が `main` 上にある場合は、コミット前に作業ブランチへ切り替える。未コミット変更はそのまま新しいブランチへ持ち越してよい。
- GitHub アカウント名は `gh api user --jq .login` で取得する。取得できない場合は、GitHub CLI のログインが必要と伝え、PR 作成前に止める。

```bash
GITHUB_ACCOUNT="$(gh api user --jq .login)"
BRANCH_NAME="agent/${GITHUB_ACCOUNT}/$(date +%Y%m%d-%H%M%S)-git"
git -C "$JMTY_ROOT" switch -c "$BRANCH_NAME"
```

- `other` のときにすでに `main` 以外のブランチにいる場合は、ブランチ名に GitHub アカウント名が含まれていれば現在のブランチをそのまま使ってよい。含まれていない場合は、GitHub アカウント名を含む新しい作業ブランチへ切り替える。
- PR 作成には GitHub CLI を使う。`gh` が未ログインなどで失敗した場合は、push 済みのブランチ名を伝え、PR 作成だけ未完了として止める。

## Git LFS 無料枠ルール（必須）
- Git LFS を使う push は、GitHub Free の無料枠を超えそうなら必ず拒否する。
- push の前に、次を実行して結果を確認する。

```bash
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" git-lfs-free-plan-status --remote-name origin
```

- 上のコマンドが非 0 で終わったら、push してはいけない。
- 拒否時は、ユーザーへ次の 3 点を必ず伝える。
  1. 何が原因で止まったか
  2. いまの見込み容量がどれくらいか
  3. どう直せば無料枠のまま進められるか
- `setup-local-machine` 後は `.githooks/pre-push` が自動で有効になる前提で扱う。手元で `git push` しても同じ判定で止まる。
- 同じ GitHub アカウントで他のリポジトリでも LFS を使うときは、予約分を差し引いて判定する。

```bash
git -C "$JMTY_ROOT" config jmty.lfsReservedBytes <バイト数>
```

- 予約分を一時的に環境変数で渡すなら、macOS / Linux は `JMTY_GIT_LFS_RESERVED_BYTES`、Windows は `$env:JMTY_GIT_LFS_RESERVED_BYTES` を使う。

## Discord 報告（任意）
- `/git` の push / プルリクエスト完了後は、ユーザーに Discord 報告を送るか確認する。送ると決まった場合だけ Discord へ報告する。Webhook が未設定の場合のみスキップしてよい。
- `/git-nd` の push / プルリクエスト完了後は、Discord 報告を送らない。
- チームで同じ Webhook を使うときは、`config/discord-git-webhook.json` を Git 共有の正本にしてよい。
- 読み取り順は `--webhook-url` → 環境変数 → `config/discord-git-webhook.json` → ローカル設定 の順にする。

```bash
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-webhook-shared-set --url "<Discord Webhook URL>"
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-webhook-shared-path
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-webhook-set --url "<Discord Webhook URL>"
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-webhook-status
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-webhook-clear
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-webhook-shared-clear
```

- Discord に送る本文は、変更ファイル名を先に出しつつ、「何をしたか」と「何が変わったの？」を分けて、小学生にもわかる短い文へまとめる。
- `/git` では、報告を送る可能性があるので、push / PR の前に、報告対象の基点として `origin/main` の SHA を控えておく。
- `/git-nd` では、基点 SHA を控えなくてよい。
- push / PR が成功したあと、`/git` で報告を送ると決まった場合に、次のどちらかを実行する。

```bash
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-report --event push --base-sha "<push前に控えた origin/main の SHA>" --head-sha HEAD
```

```bash
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-report --event pr --base-sha "<push前に控えた origin/main の SHA>" --head-sha HEAD --pr-title "<PR タイトル>" --pr-url "<PR URL>"
```

- `/git` では、ユーザーが Discord 報告を送ると言ったときだけこのコマンドを実行する。
- `/git-nd` では、このコマンドを実行しない。
- Webhook が未設定なら、Git の処理は成功として進めつつ、「Discord 送信だけスキップした」とユーザーへ伝える。
- Discord 送信だけ失敗した場合も、push / PR 成功と通知失敗を分けて報告する。

## コミットメッセージのルール（厳守）
コミットメッセージは以下のフォーマットで作成すること。

```text
<1行要約: 小学生でもわかる短い言葉で書く>

<詳細: 小学生でもわかる言葉で、何をしたかを細かく書く>
```

### 詳細メッセージの書き方（必須）
- むずかしい専門用語をできるだけ使わない。
- 1文を短くする（目安: 40文字以内）。
- 「どこを変えたか」「何をしたか」「何がよくなるか」をはっきり書く。
- 詳細は 3〜5 行で書く。短すぎる説明で終わらせない。
- 変更したファイル名やフォルダ名を、できるだけそのまま書く。
- `AGENTS.md` や `src/app.ts` のように、実際の名前を出す。
- 「案内の紙」「道具」「場所」などのぼかした言い方だけで済ませない。
- 新しいファイルを足したときは、「`CLAUDE.md` を作った」のように書く。
- できるだけ次の順番で書く。
  1. どこをさわったか
  2. 何を足したか、または直したか
  3. それで何が楽になるか
  4. 必要なら気をつける点
- カタカナ語や省略語をそのまま使わない。
- NG例: `リファクタリング` `依存解決` `最適化` `クロスプラットフォーム対応`
- 言いかえ例:
  - `リファクタリング` → `書き方を整理した`
  - `依存解決` → `足りない道具を入れた`
  - `最適化` → `むだな動きを減らした`
  - `クロスプラットフォーム対応` → `いろいろなパソコンで動きやすくした`

### 詳細メッセージの型（推奨）

```text
<1行要約>

<どこをさわったか>
<何をしたか>
<何がよくなるか>
<必要なら補足>
```

## コミット前の説明と承認 (`git commit`)
- 未コミットの変更がない場合はこのステップをスキップする。
- コミットを実行する前に、以下の手順を踏むこと。
  1. `git -C "$JMTY_ROOT" diff --staged` 等で変更内容を確認する。
  2. ユーザーに対して、今回の変更内容を小学生にもわかるように説明する。
  3. 作成したコミットメッセージ案（要約 + 詳細）を提示する。
  4. 「この内容でコミットして良いですか？」と承認を求める。
- 承認が得られた場合のみ、コミットを実行する。

### コミット前説明の型（必須）

```text
<1行での要約>

全体像:
<この変更が何のためか>
<何がそろうのか、何が良くなるのか>

変更したファイル:
- <ファイル名>: <どのように変えたか>. <どう役立つか>
- <ファイル名>: <どのように変えたか>. <どう役立つか>
- <ファイル名>: <どのように変えたか>. <どう役立つか>
```

## リモートとの同期と反映 (`fetch` / `pull --rebase` / `push` / PR)
手元の変更をリモートへ反映するためのフローです。オーナー機だけは `origin/main` に一本道で繋げ、その他のパソコンでは作業ブランチから `main` へのプルリクエストにします。

**【手順A】まず `fetch` で更新の有無を見る:**
- 最初に `git -C "$JMTY_ROOT" fetch origin` を実行する。
- **【重要: 通信ハングアップ・タイムアウト対策】**
  動画・音声などの巨大なファイルを扱うため、PCのメモリ・通信環境によって過去の巨大な履歴（Packファイル等）のダウンロードで `Operation canceled` や無応答（3分以上など）になることがあります。
  もし応答がない、または巨大ファイル起因で fetch に失敗する兆候を見た場合は、履歴の全取得をやめ、ただちに以下のシャローフェッチ（Shallow Fetch）に切り替えてください。
  `git -C "$JMTY_ROOT" fetch origin main --depth=1`
- `origin/main` に更新がない場合は、`pull --rebase` は省略してよい。
- 更新がある場合だけ、次のスタッシュと `pull --rebase` の手順へ進む。

```bash
# 通常時
git -C "$JMTY_ROOT" fetch origin
# タイムアウト・フェッチ失敗時の緊急回避（シャローフェッチ）
git -C "$JMTY_ROOT" fetch origin main --depth=1
```

**【手順B】pull が必要なときだけ未コミット変更を避難する:**
- `git -C "$JMTY_ROOT" status --porcelain` で未コミットの変更があるか確認する。
- 変更がある場合は、一旦スタッシュに避難させる。

```bash
git -C "$JMTY_ROOT" stash push -u -m "automated git-workflow stash"
```

**【手順C】更新があるときだけ `pull --rebase` する:**
- リモートの更新がある場合だけ `main` ブランチに取り込む。

```bash
git -C "$JMTY_ROOT" pull --rebase origin main
```

- 競合が発生した場合:
  1. どのファイルのどの部分がぶつかっているか、`git diff` 等で確認する。
  2. ユーザーに対し、「ローカルの変更」と「リモートの変更」の内容を簡潔かつ具体的に説明する。
  3. 「どちらを優先しますか？」とユーザーに聞き、指示に従って解決する。
  4. 解決後、`git add` して `rebase --continue` を行う。
- **浅い履歴（Shallow Clone）によるリベースの失敗時**: `--depth=1` で運用中に履歴の深さが足りずリベースができない場合や、巨大ファイル起因で pull が失敗する場合は、全履歴をダウンロード（deepen）しようとせず、ローカルの変更を事前退避（`stash`）した上で `git reset --hard origin/main` で強引に同期し、その後に `stash pop` して変更を復元する手段をユーザーに提案してください。

**【手順D】反映方法を決める:**
- rebase が完了した場合、または `fetch` の時点で更新がなかった場合は、まず `owner-status` を確認する。
- プッシュ前に LFS 容量チェックを行い、エラーがなければ次へ進む。

```bash
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" git-lfs-free-plan-status --remote-name origin
OWNER_STATUS="$(python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" owner-status)"
```

- `OWNER_STATUS` が `owner` の場合:

```bash
git -C "$JMTY_ROOT" push origin main
```

- `OWNER_STATUS` が `other` の場合:
  1. 現在のブランチ名を確認する。
  2. GitHub アカウント名を取得する。
  3. `main` にいる、またはブランチ名に GitHub アカウント名が含まれていないなら、GitHub アカウント名を含む作業ブランチを作る。
  4. 作業ブランチを push する。
  5. `main` 宛てのプルリクエストを作る。
  6. `/git` では、PR URL を入れて Discord に PR 報告する。`/git-nd` では Discord 報告しない。

```bash
CURRENT_BRANCH="$(git -C "$JMTY_ROOT" branch --show-current)"
GITHUB_ACCOUNT="$(gh api user --jq .login)"
if [ "$CURRENT_BRANCH" = "main" ] || ! printf '%s\n' "$CURRENT_BRANCH" | grep -F -q "$GITHUB_ACCOUNT"; then
  CURRENT_BRANCH="agent/${GITHUB_ACCOUNT}/$(date +%Y%m%d-%H%M%S)-git"
  git -C "$JMTY_ROOT" switch -c "$CURRENT_BRANCH"
fi
git -C "$JMTY_ROOT" push -u origin "$CURRENT_BRANCH"
PR_URL="$(gh pr create --base main --head "$CURRENT_BRANCH" --title "<PR タイトル>" --body "<PR 説明>")"
```

- `other` の場合、Discord 報告の event は `pr` とし、PR URL を入れる。`/git` でユーザーが Discord 報告を送ると言った場合だけ次を実行する。

```bash
python "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" discord-git-report --event pr --base-sha "<push前に控えた origin/main の SHA>" --head-sha HEAD --branch "$CURRENT_BRANCH" --pr-title "<PR タイトル>" --pr-url "$PR_URL"
```

**【手順E】避難した変更を戻す:**
- 手順Bでスタッシュした場合は、ここで戻す。

```bash
git -C "$JMTY_ROOT" stash pop
```

- `stash pop` で競合が起きた場合も、差分の違いを説明してからユーザー確認を取る。

## 補足
- 全員まずは `main` ブランチ上にとどまり、そこで変更のステージングとコミットを行う。
- ただし `owner-status` が `other` の場合は、コミット前または反映前に作業ブランチへ切り替え、`main` へ直接 push しない。
- `fetch` の時点で更新がなければ、無理に `pull --rebase` を実行しない。
- push 判断でオーナー確認が必要なときは、`jmty_runtime.py owner-status` の結果で判定する。
