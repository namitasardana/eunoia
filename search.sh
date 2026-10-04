#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: ./search.sh 'your question here'"
  exit 1
fi

QUESTION="$1"
python3 - <<PY
from src.search import search_and_generate
ans = search_and_generate("$QUESTION", k=4)
print(ans)
PY
