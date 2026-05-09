# Operating Model

## 目的
スキル数が増えても、毎回すべてのスキルを読むのではなく、
CEO が仕事を見て必要なメンバーだけを起こす形にして token 消費を抑える。

## 1. 受付
- CEO は依頼を短く言い換える
- 依頼を次のどれかへ分類する
  - 単独領域
  - 複数領域
  - 調査先行
  - 実装先行

## 2. 振り分け
- 単独領域なら 1 メンバーだけ起動する
- 複数領域でも、最初に必要な 1 メンバーから始める
- 並列化は、依存関係がないときだけ行う

## 3. 読み込み境界
- CEO:
  - `AGENTS.md`
  - `skill-finder`
  - `agents/` の役割別 README
- メンバー:
  - 自分の README に列挙された担当スキルだけ
  - 必要なら担当スキルの references や scripts
- 禁止:
  - CEO が毎回全スキルを読むこと
  - メンバーが他領域のスキルまで広く読むこと

## 4. オーナー確認
- 方針、破壊的変更、外部送信、長時間処理、コスト発生だけ確認する
- 実装の細部は CEO が吸収する

## 5. 出力
- メンバーは結論と差分だけ返す
- CEO は全体像、判断理由、次アクションだけ返す
- 長い中間ログは残さない

## 6. 典型パターン

### パターン A: Web 改修
- CEO -> Web Manager
- 必要なら Research Manager
- 最後に Ops Manager が Git を担当

### パターン B: 動画制作
- CEO -> Writing Manager
- CEO -> Media Manager
- 必要なら Automation Manager

### パターン C: GWS 自動化
- CEO -> Automation Manager
- repo 変更が入るなら Ops Manager

## 7. 将来の拡張
- スキルがさらに増えたら、`agents/<member>/README.md` の担当一覧を更新する
- Supabase などへ置く場合も、正本は repo に残し、DB は索引とメタデータに留める
