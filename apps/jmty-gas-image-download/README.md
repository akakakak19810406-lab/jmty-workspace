# JMTY GAS Image Download Web App

スプレッドシート上の画像セルをスマホから開くための、GASだけで完結するWebアプリです。

既存のPC運用で入れている `=IMAGE("https://drive.google.com/uc?id=...")` を読み取り、アカウント選択画面から画像を保存できます。

`/exec` だけで開くと、アカウント一覧と画像種別選択画面を表示します。URLに `row` を手入力する必要はありません。

## URL Parameters

任意:

- `row`: 対象行番号。指定しない場合はアカウント選択画面を表示
- `kind`: `factory` / `remote1` / `remote2`
- `imageKey`: 画像列キー。アプリ内部で使う値
- `sheet`: シート名。未指定時は `アカウント情報`

例:

```text
https://script.google.com/macros/s/DEPLOYMENT_ID/exec
https://script.google.com/macros/s/DEPLOYMENT_ID/exec?kind=factory&row=7
https://script.google.com/macros/s/DEPLOYMENT_ID/exec?kind=remote1&row=7
```

## Spreadsheet Formula

デプロイ後、スプレッドシートのセルには次のように置けます。

```text
=HYPERLINK("https://script.google.com/macros/s/DEPLOYMENT_ID/exec","画像DL")
```

開いた画面でアカウントを検索し、保存対象を選択します。

## Deploy With gws

現在の `gws` 認証にApps Script権限がない場合は、先に再認証します。

```bash
gws auth login --full
```

その後、次の補助スクリプトで作成からデプロイまで実行できます。

```bash
apps/jmty-gas-image-download/deploy.sh
```

手動で実行する場合:

```bash
gws script projects create --json '{"title":"JMTY Image Download Web App"}'
gws script +push --script SCRIPT_ID --dir apps/jmty-gas-image-download
gws script projects versions create --params '{"scriptId":"SCRIPT_ID"}' --json '{"description":"initial"}'
gws script projects deployments create --params '{"scriptId":"SCRIPT_ID"}' --json '{"versionNumber":1,"manifestFileName":"appsscript","description":"JMTY image download web app"}'
```

デプロイ結果の `entryPoints[].webApp.url` が、スプレッドシートに入れるURLです。
