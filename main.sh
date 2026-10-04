#!/usr/bin/env bash
set -euo pipefail

# ensure ollama serve is running before running this script:
echo "Make sure 'ollama serve' is running in another terminal."

# 1) Build indexes and embeddings
python3 src/build_index.py

# 2) Optional: run a quick search interactively
python3 src/search.py

# 3) Evaluate retrieval (recall & fairness)
python3 src/evaluate.py

echo "Pipeline finished. Check target/ for outputs (indexes, embeddings, answers.jsonl, evaluation.json)."
