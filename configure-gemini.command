#!/bin/zsh
set -e
echo "提示：现在也可使用 configure-ai.command 配置 Gemini、Qwen、Kimi、OpenAI 或 GLM。"
echo "Gemini Key 将保存在 macOS 钥匙串，不会写入项目或 Git。"
read -s "GEMINI_KEY?请输入 Gemini API Key："
echo ""
if [ -z "$GEMINI_KEY" ]; then
  echo "未输入 Key，已取消。"
  exit 1
fi
KEY_ACCOUNT="$(/usr/bin/id -un)"
/usr/bin/security add-generic-password -U -a "$KEY_ACCOUNT" -s InternationalEngineeringKB-Gemini -w "$GEMINI_KEY"
unset GEMINI_KEY
launchctl kickstart -k "gui/$(/usr/bin/id -u)/com.international-engineering-kb" >/dev/null 2>&1 || true
echo "Gemini API Key 已安全保存，知识库服务已重启。"
