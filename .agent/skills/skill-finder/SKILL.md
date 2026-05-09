---
name: skill-finder
description: 利用可能なスキルをカテゴリ別に一覧表示し、タスクに適したスキルを特定する。スキルが見つからない・どれを使うか迷ったときに使う。
---

# skill-finder スキル

## 役割
ユーザーがやりたいことを聞いて、最適なスキルとその場所（SKILL.mdのパス）を提示する。

## 保守ルール
- このファイルを `.agent/skills/` 配下スキルの索引の正本として扱う。
- スキルを追加・更新・削除したときは、必ずこのファイルのスキル一覧とガイドを実態に合わせて更新する。

## 新規スキル作成ルール（必須）

新しいスキルを作成するときは、以下のルールを必ず守る。

### Google Drive コピールール
- **ファイル・動画・テキストなど「生成物」が出るスキルは、必ずGoogle Driveへのアップロード手順を含める。**
- コピー先は `team-info/outputs/` 以下に、チャンネルや用途に合ったサブフォルダを設ける。
- コピーコマンドは「ユーザーに提示するだけ・Claude自身は実行しない」形式にする。
- Google Drive for Desktop のローカルパスには依存しない。rclone + フォルダID で統一する。

**コピーコマンドのテンプレート（SKILL.md に記載する形式）：**
```bash
rclone copy "$TEAM_INFO_ROOT/[出力ファイルパス]" "gdrive:1QKaUP9fvA46mINkpSR1b2wqrIBE6By0t/outputs/[フォルダ名]/" --progress
```
- rclone が未設定の場合は `.agent/skills/common/git-workflow/gdrive-copy/SKILL.md` の初回セットアップ手順を案内する文言をセットで記載する。

**既存の Google Drive フォルダ（outputs/ 直下）：**
| フォルダ名 | 用途 |
|-----------|------|
| `アコリエル/` | acoriel チャンネルのレンダリング動画 |
| `アコリエル/概要欄/` | acoriel チャンネルの YouTube 概要欄 MD |
| `insta-company/` | Instagram AI会社のログ・調査メモ・投稿案 |
| `jmty_posts/` | ジモティー投稿テキスト |
| `loom-calendar-rename/` | Loom の仮タイトル動画と Google カレンダー照合の判定メモ |
| `営業台本/` | 面接文字起こしから生成したクロージング台本 |
| `寝ながらトラベル/` | sleep_travel チャンネルのレンダリング動画 |
| `note記事/` | 愛され女子あゆみ の note 記事 MD |
| `gws-dashboard/` | gws CLI で取得したスプレッドシート可視化HTML |
| `X長文記事/` | X長文記事・スレッド記事のMarkdown下書き |

新規チャンネル・新規用途の場合は上記に追加し、このテーブルも更新すること。

## 使い方
1. ユーザーのやりたいことを確認する（例: 「ジモティー投稿を作りたい」「アコリエルの動画を作りたい」）
2. 下記のカテゴリ一覧からマッチするスキルを探す
3. 該当スキルの SKILL.md を読み込み、そのスキルとして動作する

## 画像ダウンロード系の選択ルール
- 画像ダウンロード / イラスト取得系スキルが2つ以上候補に上がる場合は、自動選択しない。
- 候補の違いを短く説明したうえで、どれを使うか必ずユーザーに確認する。
現在の代表例:
- `themeisle-illustration-fetcher`: 汎用のWebサイト向け、SaaS / LP 向け、SVG を活かしやすい海外テイスト
- `tyoudoii-illust-fetcher`: 日本語サイト向け、親しみやすい国内イラスト

---

## スキル一覧

### 🎸 remotion/video-production/acoriel/
| スキル名 | 概要 | パス |
|---------|------|------|
| remotion-template-acoriel-acoustic-cover | アコリエルのリリックビデオをRemotionで制作する | `.agent/skills/remotion/video-production/acoriel/remotion-template-acoriel-acoustic-cover/SKILL.md` |
| acoriel-video-description | アコリエルのYouTube概要欄を生成する | `.agent/skills/remotion/video-production/acoriel/acoriel-video-description/SKILL.md` |

---

### 📹 remotion/video-production/
| スキル名 | 概要 | パス |
|---------|------|------|
| remotion-video-production | Remotionチャンネル・テンプレ選択の起点スキル | `.agent/skills/remotion/video-production/SKILL.md` |
| remotion-template-sleep-travel-long-knowledge-relax | 寝ながらトラベル・長尺知識リラックス動画 | `.agent/skills/remotion/video-production/remotion-template-sleep-travel-long-knowledge-relax/SKILL.md` |
| remotion-template-sleep-travel-short-digest | 寝ながらトラベル・短尺ダイジェスト動画 | `.agent/skills/remotion/video-production/remotion-template-sleep-travel-short-digest/SKILL.md` |
| lyric-video-production | 音声・歌詞からLRC生成→Remotionリリックアニメーション制作 | `.agent/skills/remotion/video-production/lyric-emotion-mapper/SKILL.md` |
| voice-script-launcher | 台本ファイルから音声を一括生成する | `.agent/skills/remotion/video-production/voice-script-launcher/SKILL.md` |
| script-writing-accounts-aware | アカウントごとのトーンで台本を作成する | `.agent/skills/remotion/video-production/script-writing-accounts-aware/SKILL.md` |
| remotion-unified-output-routing | 出力先を `outputs/` 配下へ統一する運用 | `.agent/skills/remotion/video-production/remotion-unified-output-routing/SKILL.md` |
| remotion-short-sound-design | 縦ショート動画に効果音を追加し、字幕/画像/場面転換のテンポと改行品質をテンプレ別基準でチェックする | `.agent/skills/remotion/video-production/remotion-short-sound-design/SKILL.md` |

---

### 📋 jmty/jmty-posts/
| スキル名 | 概要 | パス |
|---------|------|------|
| jmty-posts | ジモティー投稿作成の起点スキル（工場/在宅を選択） | `.agent/skills/jmty/jmty-posts/SKILL.md` |
| jmty-posts-factory-14 | 工場系案件から、アカウント情報シートの担当エリアに合わせた投稿文を14本作成する | `.agent/skills/jmty/jmty-posts/jmty-posts-factory-14/SKILL.md` |
| jmty-posts-remote-14 | 在宅系見本から、アカウント情報シートの担当エリアに合わせた投稿文を14本作成する | `.agent/skills/jmty/jmty-posts/jmty-posts-remote-14/SKILL.md` |
| jmty-posts-14-variants | 汎用的に投稿文を14本作成する | `.agent/skills/jmty/jmty-posts/jmty-posts-14-variants/SKILL.md` |
| jmty-posts-gdrive-sync | 投稿出力をGoogleドライブへ同期する | `.agent/skills/jmty/jmty-posts/jmty-posts-gdrive-sync/SKILL.md` |
| jmty-image-organizer | スプレッドシート画像とドライブフォルダを整理・同期する | `.agent/skills/jmty/jmty-image-organizer/SKILL.md` |

---

### 🔧 common/
| スキル名 | 概要 | パス |
|---------|------|------|
| git-workflow | Gitの運用フロー（ブランチ/コミット/PR と Git LFS 無料枠ガード） | `.agent/skills/common/git-workflow/SKILL.md` |
| team-info-setup | team-info の初回セットアップや再セットアップを始める。core setup と lazy bootstrap 方針の入口 | `.agent/skills/common/team-info-setup/SKILL.md` |
| agent-reach | team-info 向けに取り込んだ Agent-Reach。初回は自動 bootstrap しつつ、OpenClaw / Codex から Web・SNS・動画・RSS・GitHub を横断調査する | `.agent/skills/common/agent-reach/SKILL.md` |
| repo-adapted-tool-import | 外部リポジトリ、CLI、AI skill、MCP サーバーなどを team-info の運用に合わせて取り込む。現在の repo を優先して衝突を吸収する | `.agent/skills/common/team-info-setup/repo-adapted-tool-import/SKILL.md` |
| obsidian-claudian | official Obsidian CLI、Claudian、各PCの `personal/<account>/obsidian/claude-obsidian/` を team-info 向けに導入・更新し、Codex / Claude Code 共通で使う個人用 Obsidian 知識ベースを整える | `.agent/skills/common/team-info-setup/obsidian-claudian/SKILL.md` |
| shared-agent-assets | 複数 repo で共有するルール・スキル資産を team-info 流儀で同期する。`AGENTS.md` と `.agent/skills` を正本のまま維持する | `.agent/skills/common/team-info-setup/shared-agent-assets/SKILL.md` |
| repo-information-architecture | repo 全体のフォルダ構成・ファイル配置・スキル配置を整理し、重複役割の統合、検索性向上、トークン節約まで見据えて情報設計を見直す起点スキル | `.agent/skills/common/repo-information-architecture/SKILL.md` |
| markmap-markdown-writer | Markmap 拡張で崩れにくい Markdown を作る。説明資料や設定メモを mindmap 向けの見出し構造へ整理する | `.agent/skills/common/markmap-markdown-writer/SKILL.md` |
| vscode-extension-workflow | VS Code 系エディタの拡張機能を作る・改造する・ローカル反映する作業を、環境差分で迷わず進める | `.agent/skills/common/vscode-extension-workflow/SKILL.md` |
| gdrive-copy | 出力ファイルを Google Drive へコピーする | `.agent/skills/common/git-workflow/gdrive-copy/SKILL.md` |
| youtube-auto-upload | YouTubeに動画を自動アップロード・公開予約する | `.agent/skills/common/youtube-auto-upload/SKILL.md` |
| gws-sheets-html-dashboard | gws CLI で Google スプレッドシートURLからシート一覧を見ながら対話的に要件を深掘りし、テンプレート保存とテンプレートグループ一括実行も使って HTML のグラフや簡易ダッシュボードを作る起点スキル | `.agent/skills/personal/deguchishouma/gws-sheets-html-dashboard/SKILL.md` |
| gws-sheets-duplicate-checker | gws CLI で Google スプレッドシートのシート一覧を見ながら、重複判定列と書き込み先列を対話的に選び、初回を除いた重複だけをマークする。`1S` 列へ書く場合は非重複の空欄を `1S予定` に補完する | `.agent/skills/common/gws-sheets-duplicate-checker/SKILL.md` |
| gws-calendar-booking-reply | gws CLI で Google カレンダーの空き状況を確認し、候補日時メッセージから最適な枠を選ぶ。平日候補と休日候補の仮予約を複数作成し、返信文生成と返答後の本予約化まで行う | `.agent/skills/personal/deguchishouma/gws-calendar-booking-reply/SKILL.md` |
| gws-appscript-webapp-deployer | gws CLI でローカルの `Code.gs` と `appsscript.json` を Apps Script Web アプリへ配備し、Apps Script API 有効化確認、OAuth 再認証、全文のデプロイ URL 回収と配備一覧 Markdown 更新まで行う | `.agent/skills/personal/deguchishouma/gws-appscript-webapp-deployer/SKILL.md` |
| proline-gas-builder | NotebookLM MCP のプロラインフリーマニュアルを最優先の正本として確認し、`personal/deguchishouma/gas/proline/` 配下へ、友だち追加、ブロック、解除、フォーム送信、紹介者コード連携などの GAS を設計・実装し、デプロイ後は配備台帳も更新し、全文のデプロイ URL と完成形 URL 例まで返す | `.agent/skills/personal/deguchishouma/proline-gas-builder/SKILL.md` |
| agent-org-ceo | オーナー配下に CEO と役割別メンバーを置き、必要なスキルだけを読む形で token 消費を抑えながら仕事を振り分ける | `.agent/skills/common/agent-org-ceo/SKILL.md` |

---

### 🖼️ lp-design/（LP・マーケ資料画像生成系）
| スキル名 | 概要 | パス |
|---------|------|------|
| image-prompt-generator | LP・スライド・SNS用の画像プロンプトをnanobanana pro形式で生成する | `.agent/skills/personal/deguchishouma/lp-design/image-prompt-generator/SKILL.md` |
| lp-version-creator | LP原稿をコピーし、ビジュアルスタイル（文字仕様 or 参考画像）を元にセクション別nanobanana pro画像プロンプトを生成・保存する | `.agent/skills/personal/deguchishouma/lp-design/lp-version-creator/SKILL.md` |
| nanobanana-slide-planner | 商品情報からnanobanana pro向けスライドプロンプトを生成する | `.agent/skills/personal/deguchishouma/presentation/nanobanana-slide-planner/SKILL.md` |

---

### 🌐 web-design/frontend-design/
| スキル名 | 概要 | パス |
|---------|------|------|
| frontend-design | 高品質なフロントエンドUIを制作する | `.agent/skills/web-design/frontend-design/SKILL.md` |
| figma-lp-design | Figma MCP を使ってLPデザインをFigma上で直接制作する（ヒアリング→構成→デザイン→エクスポート） | `.agent/skills/web-design/figma-lp-design/SKILL.md` |
| gsap-awwwards-website | GSAPスクロール演出付きLPを開発/保守する | `.agent/skills/web-design/frontend-design/gsap-awwwards-website/SKILL.md` |
| clone-website | browser automation を使ってサイトを pixel-perfect に再構築する。global setup へ依存を載せず、bundled Next.js 16 テンプレを初期化して複製作業に入る | `.agent/skills/web-design/frontend-design/clone-website/SKILL.md` |
| tyoudoii-illust-fetcher | tyoudoii-illust.com の無料イラストを REST API 経由で検索・取得し、Webプロジェクトへ組み込む | `.agent/skills/web-design/frontend-design/tyoudoii-illust-fetcher/SKILL.md` |
| themeisle-illustration-fetcher | Themeisle Illustrations の PNG / SVG を選び、Webプロジェクトへ組み込む | `.agent/skills/web-design/frontend-design/themeisle-illustration-fetcher/SKILL.md` |
| team-info-daily-dev-memo | 当日のGit変更から team-info メンバー共有用の作業報告を作る | `.agent/skills/common/team-info-daily-dev-memo/SKILL.md` |
| macos-intel-compatibility | macOS Intel環境の互換性パッチ対応 | `.agent/skills/common/macos-intel-compatibility/SKILL.md` |
| note-article-ayumi | 「愛され女子あゆみ」のnote記事を作成する | `.agent/skills/common/note-article-ayumi/SKILL.md` |
| note-thumbnail-ayumi | 「愛され女子あゆみ」のnoteサムネイル（1280×670px）を生成する | `.agent/skills/common/note-thumbnail-ayumi/SKILL.md` |
| daily-calendar-summary | 当日のGoogleカレンダー予定を取得しZoom URLを付与してLINE送信とDiscordへの朝サマリー送信を行う | `.agent/skills/common/daily-calendar-summary/SKILL.md` |
| md-to-docx | Markdownファイルを Word(.docx) に変換する。見出し・太字・箇条書き・水平線に対応 | `.agent/skills/common/md-to-docx/SKILL.md` |
| insta-company-secretary-log | insta-company の秘書ログを作成し、社長メモ・ToDo・引き継ぎ事項を整理する | `.agent/skills/common/insta-company-secretary-log/SKILL.md` |
| insta-company-research-brief | Instagram 運用向けの競合・バズ・トレンド調査ログを作る | `.agent/skills/common/insta-company-research-brief/SKILL.md` |
| insta-company-post-idea-generator | 秘書ログとリサーチログから Instagram 投稿案を content ログへ生成する | `.agent/skills/common/insta-company-post-idea-generator/SKILL.md` |
| monthly-kpi-planner | 今月のKPIをmarkdownで一覧化し、先月比/KPI比を軸にした評価・ファネル転換率の再計算・週次アクションスケジュール・Notion共有用のKPI Hub作成を行う | `.agent/skills/personal/deguchishouma/monthly-kpi-planner/SKILL.md` |
| jmty-kpi-update | あおぞら入金履歴とユーザー情報の月間流入数、form_8 生データを見て、ピボットと照合しながら JMTY の KPI 関連 Markdown 4ファイルを順番に更新する | `.agent/skills/personal/deguchishouma/jmty-kpi-update/SKILL.md` |

---

### 💬 discord/（Discord連携系）
| スキル名 | 概要 | パス |
|---------|------|------|
| discord-role-checker | Discord サーバーのメンバーとロールを取得し、Markmap（マインドマップ）形式の Markdown を自動生成する | `.agent/skills/discord/discord-role-checker/SKILL.md` |

---

### 🤖 personal/deguchishouma/automation/（個人自動化運用系）
| スキル名 | 概要 | パス |
|---------|------|------|
| daily-summary-zoom-account-manager | 毎朝8時の daily-calendar-summary で使う Zoom URL 発行アカウントを追加・更新し、タイトル接頭辞の振り分け設定と資格情報テンプレートを整える | `.agent/skills/personal/deguchishouma/daily-summary-zoom-account-manager/SKILL.md` |

---

### 🎤 personal/deguchishouma/seminar/（セミナー制作系）
| スキル名 | 概要 | パス |
|---------|------|------|
| seminar-script-creator | 伝えたいメッセージを受け取り、markmap→ZOOMセミナー台本→6審査員採点改善ループ→スライド番号対応→GPTimage2での画像化まで一気通貫で作成する | `.agent/skills/personal/deguchishouma/seminar-script-creator/SKILL.md` |

---

### 🎥 personal/deguchishouma/loom/（Loom整理系）
| スキル名 | 概要 | パス |
|---------|------|------|
| loom-calendar-rename | Loom の `Meeting Recording - 日付` 仮タイトル動画を、録画日時を JST に直して Google カレンダー予定と照合し、最も近い面談名へリネームする。rename が失敗したときは判定メモまで残す | `.agent/skills/personal/deguchishouma/loom-calendar-rename/SKILL.md` |

---

### 🎨 canva/（Canva連携系）
| スキル名 | 概要 | パス |
|---------|------|------|
| canva-slideshow-video | 台本から構造化 manifest を作り、Remotion で見せ方を出し分けるスライドショー動画を生成する | `.agent/skills/canva/canva-slideshow-video/SKILL.md` |
| canva-slide-design-extender | Canva のテンプレや既存デザインを崩さずに、新しいスライドを追加・増築する | `.agent/skills/canva/canva-slide-design-extender/SKILL.md` |

---

### 🚀 viral-template-generator/（バズ動画系）
| スキル名 | 概要 | パス |
|---------|------|------|
| viral-template-generator | ショート動画を3層解析しRemotionバズ動画テンプレートを自動生成する | `.agent/skills/viral-template-generator/SKILL.md` |

---

### 🐦 x-post-writer/（X投稿生成系）
| スキル名 | 概要 | パス |
|---------|------|------|
| x-post-writer | アカウント情報・競合投稿・テンプレートを活用してXの投稿文を自動生成し、投稿の型を蓄積する | `.agent/skills/x-post-writer/SKILL.md` |
| x-long-article-writer | セミナー台本・Obsidianノート・既存記事を、アカウント別トンマナに合わせてX長文記事・スレッド記事へ再構成しMarkdown保存する | `.agent/skills/x-long-article-writer/SKILL.md` |
| x-vertical-infographic-creator | X投稿用の縦型9:16図解・インフォグラフィック画像を設計・日本語プロンプト化する。アカウントごとのキャラクター情報を管理し、scheduled_draft_pipeline.py と統合して画像プロンプトを自動生成する | `.agent/skills/x-vertical-infographic-creator/SKILL.md` |

---

### 💼 sales/（営業コーチング・販売台本系）
| スキル名 | 概要 | パス |
|---------|------|------|
| sales-coaching | ジモティー営業（1S・面接）の文字起こしを Loom から取得し、候補者名検索→video_id特定→transcript保存→担当者抽出→Neon(Postgres) 登録まで行える。その後の分析・改善トーク生成・比較レポートまで対応 | `.agent/skills/sales/sales-coaching/SKILL.md` |
| interview-product-sales | 採用面接の文字起こしから候補者プロファイルを抽出し、商品テンプレート（価格・ベネフィット・ピッチ構造）と組み合わせて、既存保存済み台本と同じフォーマットで面接クロージング時の販売戦略と台本を生成する。二次面接では、引き継ぎ済みの文脈と一次担当者からの前向きな推薦コメントを冒頭へ自然に入れられ、未指定時は代表の出口が話す前提で生成される | `.agent/skills/sales/interview-product-sales/SKILL.md` |
| calendar-interview-closing | Google Calendar の当日予定から「面接」「2回目」または 90 分以上の候補を抽出し、Loom transcript 特定からクロージング台本保存まで一気通貫で進める起点スキル | `.agent/skills/personal/deguchishouma/calendar-interview-closing/SKILL.md` |

---

### 🍌 nanobanana-banner-gen/（バナー自動生成系）
| スキル名 | 概要 | パス |
|---------|------|------|
| nanobanana-banner-gen | スプレッドシートから投稿文を読み取り、工場は案件一覧の正本ファイルを参照しつつ、Codex CLI では GPT Image 2 / それ以外では Nanobanana Pro でバナー画像を生成し、Drive 同期前に画像 OCR とファイル名を検証して、画像優先で投稿文章も再生成する | `.agent/skills/nanobanana-banner-gen/SKILL.md` |

---

## ガイド：やりたいこと別

| やりたいこと | 使うスキル |
|------------|----------|
| アコリエルの動画を作りたい | `remotion-template-acoriel-acoustic-cover` |
| アコリエルの概要欄を作りたい | `acoriel-video-description` |
| 寝ながらトラベルの動画を作りたい | `remotion-video-production`（起点）→ テンプレ選択 |
| 歌詞字幕・カラオケ動画を作りたい | `lyric-video-production` |
| 台本から音声を生成したい | `voice-script-launcher` |
| YouTube台本を書きたい | `script-writing-accounts-aware` |
| Remotionの縦ショートに効果音を入れたい | `remotion-short-sound-design` |
| 縦ショートの改行・余白・字幕位置・画像テンポをチェックしたい | `remotion-short-sound-design` |
| ジモティー投稿を作りたい（工場） | `jmty-posts-factory-14` |
| ジモティー投稿を作りたい（在宅） | `jmty-posts-remote-14` |
| ジモティー投稿をGドライブに同期したい | `jmty-posts-gdrive-sync` |
| ジモティーの画像をアカウントフォルダに整理・移動したい | `jmty-image-organizer` |
| note記事（あゆみ）を書きたい | `note-article-ayumi` |
| noteサムネイルを作りたい（あゆみ） | `note-thumbnail-ayumi` |
| team-info をセットアップしたい | `team-info-setup` |
| CEO 配下に役割別メンバーを作ってスキル探索を軽くしたい | `agent-org-ceo` |
| X / Reddit / YouTube / GitHub / 小紅書などを横断調査したい | `agent-reach` |
| OpenClaw に team-info 版 Agent-Reach を入れたい | `agent-reach` |
| 外部ツールや外部 repo を team-info 向けに取り込みたい | `repo-adapted-tool-import` |
| 何かを導入するとき、今の repo 優先で書き換えて入れたい | `repo-adapted-tool-import` |
| 毎朝8時の calendar summary に新しい Zoom 発行アカウントを追加したい | `daily-summary-zoom-account-manager` |
| official Obsidian CLI と Claudian を入れたい | `obsidian-claudian` |
| Obsidian の active vault に Claudian を入れたい | `obsidian-claudian` |
| 複数 repo で共有ルール・共有スキルを一元管理したい | `shared-agent-assets` |
| SessionStart Hook で shared repo を自動更新したい | `shared-agent-assets` |
| Markmap 用の Markdown を作りたい | `markmap-markdown-writer` |
| VS Code / Cursor / antigravity の拡張機能を作りたい | `vscode-extension-workflow` |
| 拡張機能のソース repo と実際の反映先フォルダがどこか迷う | `vscode-extension-workflow` |
| 既存拡張をローカルで改造して読み込ませたい | `vscode-extension-workflow` |
| gws CLI でスプレッドシートURLから対話的に条件を決めて HTML グラフを作りたい | `gws-sheets-html-dashboard` |
| gws CLI でシートの重複行を調べて既存列や新規列へ `重複` を書きたい | `gws-sheets-duplicate-checker` |
| gws CLI で候補日時メッセージに合わせて予定を決めたい。平日候補と休日候補を仮押さえし、返信文を作って返答後に本予約だけ残したい | `gws-calendar-booking-reply` |
| gws CLI で Apps Script をデプロイして Web アプリ URL を返したい | `gws-appscript-webapp-deployer` |
| プロラインフリーのマニュアルを元に NotebookLM 参照つきで GAS を作りたい | `proline-gas-builder` |
| 今日の team-info 開発メモを Git から作りたい | `team-info-daily-dev-memo` |
| Instagram AI会社の秘書ログを作りたい | `insta-company-secretary-log` |
| Instagram の競合・バズ調査ログを作りたい | `insta-company-research-brief` |
| Instagram の投稿ネタや構成案を出したい | `insta-company-post-idea-generator` |
| 今月のKPIを整理して進捗を確認したい | `monthly-kpi-planner` |
| ジモティーKPIを銀行入金と月間流入数、form_8 生データから更新したい | `jmty-kpi-update` |
| 営業の文字起こしを分析・改善トークスクリプトを作りたい（1S・面接） | `sales-coaching` |
| 面接の文字起こしから商品販売の戦略・台本を、既存の販売台本フォーマット維持で作りたい | `interview-product-sales` |
| 今日のカレンダーから面接や2回目予定を拾って、Loom 文字起こし取得からクロージング台本保存までまとめてやりたい | `calendar-interview-closing` |
| 出口と菅下の営業スタイルを比較したい | `sales-coaching` |
| KPIから今月のスケジュールを組みたい | `monthly-kpi-planner` |
| Git操作をしたい | `git-workflow` |
| repo 全体のフォルダ構成を整理したい | `repo-information-architecture` |
| 重複した役割のフォルダを減らしたい | `repo-information-architecture` |
| 検索性を上げて AI の探索トークンを節約したい | `repo-information-architecture` |
| LP用の画像プロンプトを作りたい | `image-prompt-generator` |
| LPの新しいデザインバージョンを作りたい（原稿コピー＋セクション別プロンプト生成） | `lp-version-creator` |
| nanobanana proでスライドや画像を作りたい | `image-prompt-generator` / `nanobanana-slide-planner` |
| FigmaでLPをデザインしたい | `figma-lp-design` |
| WebサイトやLPを作りたい | `frontend-design` / `gsap-awwwards-website` |
| 既存サイトをそっくり Next.js で作り直したい | `clone-website` |
| サイトを pixel-perfect に複製したい | `clone-website` |
| LPの絵文字や仮アイコンを、ちょうどいいイラストの画像に差し替えたい | `themeisle-illustration-fetcher` |
| Themeisle のイラストをダウンロードしてサイトに使いたい | `themeisle-illustration-fetcher` |
| 日本語テイストのやわらかいイラストに差し替えたい | `tyoudoii-illust-fetcher` |
| ZOOMセミナーのトークスクリプトを作りたい | `seminar-script-creator` |
| セミナーの台本を採点して120点まで改善したい | `seminar-script-creator` |
| Loom の `Meeting Recording - 日付` を面談名へ直したい | `loom-calendar-rename` |
| CanvaやRemotionで台本からスライドショー動画を作りたい | `canva-slideshow-video` |
| Canvaのテンプレや既存資料を維持して、新しいページを足したい | `canva-slide-design-extender` |
| バズるショート動画テンプレを作りたい | `viral-template-generator` |
| X(Twitter)の投稿を作りたい | `x-post-writer` |
| X投稿用の縦型図解・インフォグラフィック画像を設計・プロンプト化したい | `x-vertical-infographic-creator` |
| ぐーたらAI社長キャラクターを使った図解プロンプトを作りたい | `x-vertical-infographic-creator` |
| 下書きパイプラインの画像プロンプトを縦型図解ルールで強化したい | `x-vertical-infographic-creator` |
| スプレッドシートからバナー画像を自動生成したい | `nanobanana-banner-gen` |
| YouTubeに動画をアップロードしたい | `youtube-auto-upload` |
| 動画の公開予約をしたい | `youtube-auto-upload` |
