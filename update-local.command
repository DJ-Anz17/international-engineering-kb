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
  "$SOURCE_DIR/" "$TARGET_DIR/"
chmod +x "$TARGET_DIR/start-kb.command" "$TARGET_DIR/configure-ai.command"
cp "$TARGET_DIR/configure-ai.command" "$HOME/Desktop/配置 AI 模型.command"
chmod +x "$HOME/Desktop/配置 AI 模型.command"
launchctl kickstart -k "gui/$(id -u)/com.international-engineering-kb" >/dev/null 2>&1 || true
echo "更新完成。请打开 http://127.0.0.1:8765，并刷新页面。"
