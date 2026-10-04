# src/evaluate.py
import pandas as pd
from collections import defaultdict
from src.search import search_and_generate, collections_index, questions_index, collections, questions
import numpy as np
import json
from pathlib import Path
from src.utils import ensure_dir

TARGET_DIR = Path("target")
ensure_dir(TARGET_DIR)
RESULTS_FILE = TARGET_DIR / "evaluation.json"

def recall_at_k(k=4):
    qdf = pd.read_csv("data/questions.csv")
    total = 0
    correct = 0
    per_disease = defaultdict(lambda: {"total": 0, "correct": 0})

    for _, row in qdf.iterrows():
        question = row["Question"]
        gold_disease = str(row["Disease"]).strip()
        total += 1
        per_disease[gold_disease]["total"] += 1

        # We will use FAISS retrieval (not generation) to compute recall: check if any top-k retrieved collection has same disease
        # Embed + search (reuse collections_index)
        import numpy as np
        from src.utils import get_embedding_ollama
        q_emb = np.array(get_embedding_ollama(question, model="nomic-embed-text")).astype("float32").reshape(1, -1)
        D, I = collections_index.search(q_emb, k)
        retrieved_diseases = [collections.iloc[idx]["Disease"] for idx in I[0] if idx != -1]
        if gold_disease in retrieved_diseases:
            correct += 1
            per_disease[gold_disease]["correct"] += 1

    recall = correct / max(1, total)
    per_recall = {d: (per_disease[d]["correct"] / per_disease[d]["total"]) if per_disease[d]["total"]>0 else None for d in per_disease}
    return recall, per_recall

def fairness_metrics(per_recall: dict):
    vals = [v for v in per_recall.values() if v is not None]
    if not vals:
        return {"gap": None, "std": None, "min": None, "max": None}
    gap = float(max(vals) - min(vals))
    std = float(np.std(vals))
    return {"gap": gap, "std": std, "min": float(min(vals)), "max": float(max(vals))}

def main(k=4):
    recall, per_recall = recall_at_k(k=k)
    fair = fairness_metrics(per_recall)
    result = {
        "Recall@k": recall,
        "PerDiseaseRecall": per_recall,
        "Fairness": fair
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("Saved evaluation to", RESULTS_FILE)
    return result

if __name__ == "__main__":
    main(k=4)
