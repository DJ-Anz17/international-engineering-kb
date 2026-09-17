#!/bin/zsh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
KEY_ACCOUNT="$(/usr/bin/id -un)"
load_key() {
  local service="$1"
  local env_name="$2"
  local value="$(/usr/bin/security find-generic-password -a "$KEY_ACCOUNT" -s "$service" -w 2>/dev/null || true)"
  if [ -n "$value" ]; then
    export "$env_name=$value"
  fi
  unset value
}
load_key InternationalEngineeringKB-Gemini GEMINI_API_KEY
load_key InternationalEngineeringKB-Qwen DASHSCOPE_API_KEY
load_key InternationalEngineeringKB-Kimi MOONSHOT_API_KEY
load_key InternationalEngineeringKB-OpenAI OPENAI_API_KEY
load_key InternationalEngineeringKB-GLM ZAI_API_KEY
load_key InternationalEngineeringKB-DeepSeek DEEPSEEK_API_KEY
PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3)"
fi
"$PYTHON" -m ieg_kb init
"$PYTHON" -m ieg_kb ingest
exec "$PYTHON" -m ieg_kb serve
