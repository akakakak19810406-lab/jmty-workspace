# RULES.md

## 主なフォルダ
- `.agent/skills/jmty/`: ジモティ専用スキル
- `.agent/skills/common/`: Git/CEO/セットアップなどの共通基盤
- `inputs/jmty_factory_cases/`: 工場求人素材
- `inputs/jmty_remote_samples/`: 在宅求人素材
- `outputs/jmty/`: 生成済み投稿文
- `config/`: ローカル設定。秘密情報は Git に含めない

## 禁止
- webhook URL、APIキー、認証情報をコミットしない
- 他リポジトリの remote をこの repo の origin に使い回さない
- JMTY 以外の動画制作・記事制作・Web 制作素材をこの repo に混ぜない
