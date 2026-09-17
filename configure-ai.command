#!/bin/zsh
set -e
echo "API Key 将保存在 macOS 钥匙串，不会写入项目、日志或 Git。"
echo "1) Gemini   2) Qwen/通义千问   3) Kimi   4) OpenAI   5) GLM/智谱   6) DeepSeek"
read "CHOICE?请选择要配置的服务商 [1-6]："
case "$CHOICE" in
  1) LABEL="Gemini"; SERVICE="InternationalEngineeringKB-Gemini" ;;
  2) LABEL="Qwen"; SERVICE="InternationalEngineeringKB-Qwen" ;;
  3) LABEL="Kimi"; SERVICE="InternationalEngineeringKB-Kimi" ;;
  4) LABEL="OpenAI"; SERVICE="InternationalEngineeringKB-OpenAI" ;;
  5) LABEL="GLM"; SERVICE="InternationalEngineeringKB-GLM" ;;
  6) LABEL="DeepSeek"; SERVICE="InternationalEngineeringKB-DeepSeek" ;;
  *) echo "选择无效，已取消。"; exit 1 ;;
esac
read -s "API_KEY?请输入 $LABEL API Key："
echo ""
if [ -z "$API_KEY" ]; then
  echo "未输入 Key，已取消。"
  exit 1
fi
KEY_ACCOUNT="$(/usr/bin/id -un)"
/usr/bin/security add-generic-password -U -a "$KEY_ACCOUNT" -s "$SERVICE" -w "$API_KEY"
unset API_KEY
launchctl kickstart -k "gui/$(/usr/bin/id -u)/com.international-engineering-kb" >/dev/null 2>&1 || true
echo "$LABEL API Key 已安全保存，知识库服务已重启。请在网页左侧选择相应模型。"
