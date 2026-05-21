#!/usr/bin/env bash
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODEL="${DEEPSEEK_MODEL:-deepseek-coder:6.7b}"

echo "Checking Ollama at ${OLLAMA_HOST}..."
curl -fsS "${OLLAMA_HOST}/api/tags" >/dev/null

echo "Pulling ${MODEL}. This can take a while."
curl -fsS "${OLLAMA_HOST}/api/pull" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${MODEL}\",\"stream\":false}"

echo
echo "Ollama model ready: ${MODEL}"

