# outputs/ — 共有生成物の出力先

ここは **共有で扱う AI 生成物・レンダリング結果の出力先**。
個人専用の成果物は `personal/<account>/outputs/` へ置く。素材・入力ファイルは `inputs/` へ。このフォルダに入力素材を置かないこと。

## サブフォルダ構造

| フォルダ | 用途 | 対応スキル |
|---|---|---|
| `acoriel/` | アコリエルチャンネル 動画レンダリング出力（.mp4） | `remotion-template-acoriel-*` |
| `acoriel/descriptions/` | アコリエル YouTube 概要欄（.md ファイル） | `acoriel-video-description` |
| `common/` | 汎用スクリプト・共通出力 | — |
| `common/airthmate/` | AirthMate のプレビュー・納品用 HTML / PDF | — |
| `jmty/` | ジモティー投稿文（.txt / .md） | `jmty-posts-*` |
| `note/` | note 記事（.md） | `note-article-ayumi` |
| `sleep_travel/` | 寝ながらトラベル 動画出力 | `remotion-template-sleep-travel-*` |
| `viral-analysis/` | バズ動画解析結果（動画ごとにサブフォルダ） | `viral-template-generator` |

## viral-analysis 出力構造

```
outputs/viral-analysis/
└── {動画ファイル名}/
    ├── analysis.json      3層解析結果（Layer1/2/3）
    ├── frames/            抽出フレーム画像（一時）
    └── remotion/          生成された Remotion テンプレート
        └── src/
            └── ViralVideo.tsx  Claude が analysis.json から生成するメインコンポーネント
```

## 概要欄（acoriel/descriptions）の構成

各 `.md` ファイルは以下の形式:
- 1行目: キーワード行（YouTube SEO用、200文字以内）
- 2行目以降: 概要欄本文
- チャプター行（`0:00 イントロ` 形式）を含む

## 注意

- レンダリング済み動画（.mp4）は Git 管理外（.gitignore 参照）
- 個人専用のレポートや素材は `personal/<account>/outputs/` に置き、ここへ混ぜない
