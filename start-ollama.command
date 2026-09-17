#!/bin/zsh
set -e
if [ -x /opt/homebrew/bin/ollama ]; then
  exec /opt/homebrew/bin/ollama serve
fi
if [ -x /Applications/Ollama.app/Contents/Resources/ollama ]; then
  exec /Applications/Ollama.app/Contents/Resources/ollama serve
fi
echo "找不到 Ollama 可执行文件" >&2
exit 1
