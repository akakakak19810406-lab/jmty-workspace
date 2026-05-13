#!/usr/bin/env bash
# JMTY画像ダウンロード用GAS Web Appのデプロイ補助スクリプトです。
# Apps Scriptプロジェクト作成、ローカルファイルpush、version作成、Web App deployment作成を行います。
# 成功時はスプレッドシートに貼るWeb App URLを標準出力へ表示します。
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_ID="${JMTY_GAS_SCRIPT_ID:-}"
SCRIPT_ID_FILE="${APP_DIR}/.script-id"
TITLE="${JMTY_GAS_TITLE:-JMTY Image Download Web App}"

json_extract() {
  local mode="$1"
  local input
  input="$(cat)"
  GWS_JSON_INPUT="$input" python3 - "$mode" <<'PY'
import json
import os
import sys

mode = sys.argv[1]
text = os.environ.get("GWS_JSON_INPUT", "")
starts = [idx for idx in (text.find("{"), text.find("[")) if idx >= 0]
if not starts:
    raise SystemExit("gws output did not contain JSON")
data = json.loads(text[min(starts):])

if mode == "scriptId":
    print(data.get("scriptId", ""))
elif mode == "versionNumber":
    print(data.get("versionNumber", ""))
elif mode == "webAppUrl":
    deployments = data.get("deployments") if isinstance(data, dict) else None
    candidates = deployments if isinstance(deployments, list) else [data]
    for deployment in candidates:
        for entry in deployment.get("entryPoints", []) or []:
            url = (entry.get("webApp") or {}).get("url")
            if url:
                print(url)
                raise SystemExit(0)
    print("")
else:
    raise SystemExit(f"unknown mode: {mode}")
PY
}

json_for_create() {
  TITLE="$TITLE" python3 - <<'PY'
import json
import os

print(json.dumps({"title": os.environ["TITLE"]}, ensure_ascii=False))
PY
}

json_for_params() {
  SCRIPT_ID="$SCRIPT_ID" python3 - <<'PY'
import json
import os

print(json.dumps({"scriptId": os.environ["SCRIPT_ID"]}))
PY
}

json_for_version() {
  DESCRIPTION="deploy $(date '+%Y-%m-%d %H:%M:%S %z')" python3 - <<'PY'
import json
import os

print(json.dumps({"description": os.environ["DESCRIPTION"]}, ensure_ascii=False))
PY
}

json_for_deployment() {
  VERSION_NUMBER="$1" python3 - <<'PY'
import json
import os

print(json.dumps({
    "versionNumber": int(os.environ["VERSION_NUMBER"]),
    "manifestFileName": "appsscript",
    "description": "JMTY image download web app",
}, ensure_ascii=False))
PY
}

if [[ -z "$SCRIPT_ID" && -f "$SCRIPT_ID_FILE" ]]; then
  SCRIPT_ID="$(tr -d '[:space:]' < "$SCRIPT_ID_FILE")"
fi

if [[ -z "$SCRIPT_ID" ]]; then
  create_output="$(gws script projects create --json "$(json_for_create)")"
  SCRIPT_ID="$(printf '%s' "$create_output" | json_extract scriptId)"
  if [[ -z "$SCRIPT_ID" ]]; then
    echo "Apps Script project ID could not be read from gws output." >&2
    exit 1
  fi
  printf '%s\n' "$SCRIPT_ID" > "$SCRIPT_ID_FILE"
fi

params="$(json_for_params)"
(cd "$APP_DIR" && gws script +push --script "$SCRIPT_ID" --dir . >/dev/null)

version_output="$(gws script projects versions create --params "$params" --json "$(json_for_version)")"
version_number="$(printf '%s' "$version_output" | json_extract versionNumber)"
if [[ -z "$version_number" ]]; then
  echo "Apps Script version number could not be read from gws output." >&2
  exit 1
fi

deployment_output="$(gws script projects deployments create --params "$params" --json "$(json_for_deployment "$version_number")")"
web_app_url="$(printf '%s' "$deployment_output" | json_extract webAppUrl)"
if [[ -z "$web_app_url" ]]; then
  list_output="$(gws script projects deployments list --params "$params")"
  web_app_url="$(printf '%s' "$list_output" | json_extract webAppUrl)"
fi

printf 'SCRIPT_ID=%s\n' "$SCRIPT_ID"
printf 'VERSION=%s\n' "$version_number"
printf 'WEB_APP_URL=%s\n' "$web_app_url"
