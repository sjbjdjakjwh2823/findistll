#!/usr/bin/env bash
set -euo pipefail

OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
LLM_MODEL="${LOCAL_LLM_MODEL:-qwen2.5:7b-instruct-q4_K_M}"
EMBED_MODEL="${LOCAL_EMBED_MODEL:-BAAI/bge-small-en-v1.5}"

echo "[1/4] Checking Ollama endpoint: ${OLLAMA_URL}"
if ! curl -fsS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  echo "Ollama is not responding. Trying to start local Ollama service..."
  if command -v ollama >/dev/null 2>&1; then
    nohup ollama serve >/tmp/preciso-ollama.log 2>&1 &
    for _ in {1..20}; do
      if curl -fsS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
  fi
fi

curl -fsS "${OLLAMA_URL}/api/tags" >/dev/null

echo "[2/4] Pulling LLM model: ${LLM_MODEL}"
ollama pull "${LLM_MODEL}"

echo "[3/4] Installing sentence-transformers and caching embedding model: ${EMBED_MODEL}"
/Users/leesangmin/Desktop/preciso/venv/bin/pip install -q sentence-transformers
/Users/leesangmin/Desktop/preciso/venv/bin/python - <<PY
from sentence_transformers import SentenceTransformer
SentenceTransformer("${EMBED_MODEL}")
print("embedding model cached")
PY

echo "[4/4] Recommended env"
cat <<EOF
OPENAI_BASE_URL=${OLLAMA_URL}/v1
OPENAI_API_KEY=local-dev-key
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=${EMBED_MODEL}
EMBEDDING_DIM=384
OLLAMA_BASE_URL=${OLLAMA_URL}
FINROBOT_MODEL=${LLM_MODEL}
EOF

echo "Local RAG models are ready."
