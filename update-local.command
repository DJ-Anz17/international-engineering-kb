#!/bin/zsh
set -e
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/Library/Application Support/InternationalEngineeringKB"
echo "正在更新本地国际工程知识库（保留资料、索引、虚拟环境和日志）…"
mkdir -p "$TARGET_DIR"
rsync -a \
  --exclude library \
  --exclude data \
  --exclude .venv \
  --exclude .logs \
  --exclude .git \
  --exclude 本地资料库 \
  --exclude kb_config.json \
  "$SOURCE_DIR/" "$TARGET_DIR/"
chmod +x "$TARGET_DIR/start-kb.command" "$TARGET_DIR/configure-ai.command"
cp "$TARGET_DIR/configure-ai.command" "$HOME/Desktop/配置 AI 模型.command"
chmod +x "$HOME/Desktop/配置 AI 模型.command"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
cp "$TARGET_DIR/deploy/com.international-engineering-kb.plist" "$LAUNCH_AGENTS_DIR/com.international-engineering-kb.plist"
cp "$TARGET_DIR/deploy/com.ollama.server.plist" "$LAUNCH_AGENTS_DIR/com.ollama.server.plist"
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS_DIR/com.ollama.server.plist" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS_DIR/com.international-engineering-kb.plist" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$(id -u)/com.ollama.server" >/dev/null 2>&1 || true
if launchctl kickstart -k "gui/$(id -u)/com.international-engineering-kb" >/dev/null 2>&1; then
  echo "更新完成，后台服务已重启。请打开 http://127.0.0.1:8765，并刷新页面。"
else
  echo "代码和运行副本已更新，但后台服务未能自动重启。请先双击 stop-local.command，再双击 run.command，然后刷新 http://127.0.0.1:8765。"
fi
