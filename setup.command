#!/bin/zsh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ieg_kb init
.venv/bin/python -m ieg_kb ingest
echo ""
echo "基础环境已完成。双击 run.command 启动知识库。"
