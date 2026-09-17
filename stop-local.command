#!/bin/zsh
set -e
USER_ID="$(id -u)"
launchctl kill SIGTERM "gui/$USER_ID/com.international-engineering-kb" >/dev/null 2>&1 || true
launchctl kill SIGTERM "gui/$USER_ID/com.ollama.server" >/dev/null 2>&1 || true
echo "国际工程知识库和 Ollama 已停止。"
