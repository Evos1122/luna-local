#!/usr/bin/env bash
# Luna Local: starter Ollama (hvis den ikke allerede kører) og chatten.
# Brug:   ./start-luna.sh        (eller: bash start-luna.sh)
# Stop:   Ctrl+C i dette vindue
set -u
cd "$(dirname "$0")"

echo "== Luna Local =="

# 1) Ollama skal være installeret
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama er ikke installeret."
  echo "Installér den fra https://ollama.com/download/linux og kør scriptet igen."
  exit 1
fi

# 2) Kører Ollama allerede (fx som systemd-tjeneste på Linux Mint)?
ollama_oppe() { curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; }

if ! ollama_oppe; then
  mkdir -p "$HOME/.cache"
  echo "Starter Ollama i baggrunden ... (log: $HOME/.cache/luna-ollama.log)"
  nohup ollama serve >"$HOME/.cache/luna-ollama.log" 2>&1 &
  venter=0
  until ollama_oppe || [ "$venter" -ge 30 ]; do
    sleep 1
    venter=$((venter + 1))
  done
  if ! ollama_oppe; then
    echo "Ollama svarer ikke efter 30 sekunder. Se loggen: $HOME/.cache/luna-ollama.log"
    exit 1
  fi
fi
echo "Ollama svarer på http://127.0.0.1:11434."

# 3) Python
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "Python mangler. Installér Python 3.10 eller nyere (på Linux Mint: sudo apt install python3)."
  exit 1
fi

# 4) Åbn chatten i browseren, og kør serveren i Dette vindue
( sleep 2
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://127.0.0.1:5000 >/dev/null 2>&1
  fi
) &

echo "Starter Luna på http://127.0.0.1:5000 ..."
exec "$PY" server.py
