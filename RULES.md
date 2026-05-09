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
- team-info 本体の remote をこの repo の origin に使い回さない
