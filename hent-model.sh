#!/usr/bin/env bash
# Henter basismodellen qwen3.5:9b til Ollama (omkring 6,6 GB - kræver internet).
# Brug:   ./hent-model.sh        (eller: bash hent-model.sh)
set -u
cd "$(dirname "$0")"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama er ikke installeret."
  echo "Installér den fra https://ollama.com/download/linux og kør scriptet igen."
  exit 1
fi

# Start Ollama, hvis den ikke svarer endnu
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starter Ollama i baggrunden ..."
  nohup ollama serve >/dev/null 2>&1 &
  sleep 3
fi

echo "Henter qwen3.5:9b (omkring 6,6 GB) ..."
if ! ollama pull qwen3.5:9b; then
  echo "Download fejlede. Se fejlen ovenfor."
  exit 1
fi

echo "Færdig. Kør nu: ./start-luna.sh"
