#!/bin/zsh
set -e
echo "将安装 Ollama，并下载 qwen3:8b 与 bge-m3。模型会占用数 GB 磁盘。"
read "REPLY?继续吗？输入 YES："
if [ "$REPLY" != "YES" ]; then
  echo "已取消。"
  exit 0
fi
if ! command -v ollama >/dev/null 2>&1; then
  brew install ollama
fi
brew services start ollama
sleep 2
ollama pull qwen3:8b
ollama pull bge-m3
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3)"
fi
"$PYTHON" -m ieg_kb ingest --force --embeddings on
echo "本地 AI 与向量索引已就绪。"
