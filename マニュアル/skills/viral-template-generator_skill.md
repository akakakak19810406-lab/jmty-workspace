---
name: viral-template-generator
description: バズ動画解析から台本・字幕・Remotion化まで扱う入口スキル。詳細は flow と template profile に分割して読む。
---

# viral-template-generator スキル

## 概要
- `viral-template-generator` は入口スキルです
- 詳細手順は `references/flows/` に分割されています
- テンプレ差分は `references/template-profiles/` に分割されています
- これにより、毎回フルパイプライン全文を読まずに済みます

## 読み方
1. まず親スキルの `SKILL.md` を読む
2. いま進めるフェーズの flow を読む
3. テンプレ差分がある場合だけ、その profile と差分 md を読む

## flow 一覧
- `references/flows/analysis.md`
  - 動画解析と分析バッチ作成
- `references/flows/patterns.md`
  - `analysis.json` 統合と `viral_patterns.md`
- `references/flows/script.md`
  - テーマ提案と `script.md`
- `references/flows/subtitles-voice.md`
  - `script_hiragana.md` `subtitles.json` 音声生成
- `references/flows/materials.md`
  - `materials/README.md` と素材方針
- `references/flows/remotion.md`
  - Remotion 組み込み
- `references/flows/timing.md`
  - jet cut, alignment, render

## template profile 一覧
- `references/template-profiles/standard-short/profile.yaml`
  - 共通の標準プロファイル
- `references/template-profiles/career-listicle/profile.yaml`
  - 転職リスト型の差分プロファイル

## template profile の考え方
- 共通ルールは flow に置く
- テンプレごとの差分だけ profile と override md に置く
- 差分がないフェーズは共通 flow をそのまま使う

## 現在の転職テンプレ差分
- フックは `statement`
- 字幕は `plain_light`
- 名前カードは `1.特徴名`
- Remotion は静かなテンポとクロスフェード中心

## 参照先
- スキル本体: `.agent/skills/viral-template-generator/SKILL.md`
- 概要: `.agent/skills/viral-template-generator/references/pipeline-overview.md`
