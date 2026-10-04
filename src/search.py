# src/search.py
import faiss, numpy as np, pandas as pd, pickle, json
from pathlib import Path
from src.utils import get_embedding_ollama, generate_with_ollama_stream, ensure_dir

TARGET_DIR = Path("target")
ensure_dir(TARGET_DIR)
COL_IDX_PATH = TARGET_DIR / "collections.index"
Q_IDX_PATH = TARGET_DIR / "questions.index"
COL_MAP = TARGET_DIR / "collections_mapping.pkl"
Q_MAP = TARGET_DIR / "questions_mapping.pkl"
OUT_LOG = TARGET_DIR / "answers.jsonl"

# load index + data
collections_index = faiss.read_index(str(COL_IDX_PATH))
questions_index = faiss.read_index(str(Q_IDX_PATH))
collections = pd.read_csv("data/collections.csv")
questions = pd.read_csv("data/questions.csv")

with open(str(COL_MAP), "rb") as f:
    collections_mapping = pickle.load(f)
with open(str(Q_MAP), "rb") as f:
    questions_mapping = pickle.load(f)

def build_context_from_hits(coll_hits, q_hits, max_sentences_per_hit=1):
    """
    Create a short context block combining collection and Q&A hits.
    """
    lines = []
    for h in coll_hits:
        # h is dict-like from DataFrame iteration
        lines.append(f"[Collection] Disease: {h['Disease']} | Context: {h.get('context', h.get('Context',''))}")
    for h in q_hits:
        lines.append(f"[Q&A] Disease: {h['Disease']} | Q: {h['Question']} | A: {h['Answer']}")
    return "\n".join(lines)

def search_and_generate(query, k=4, embed_model="nomic-embed-text", gen_model="mistral:latest", score_floor=None):
    # embed query
    q_emb = np.array(get_embedding_ollama(query, model=embed_model)).astype("float32").reshape(1, -1)

    # search both indexes
    c_d, c_i = collections_index.search(q_emb, k)
    q_d, q_i = questions_index.search(q_emb, k)

    # prepare results list (filter by score_floor if provided)
    coll_hits = []
    for score, idx in zip(c_d[0].tolist(), c_i[0].tolist()):
        if idx == -1:
            continue
        if score_floor is not None and score < score_floor:
            continue
        row = collections.iloc[idx].to_dict()
        row["_score"] = float(score)
        coll_hits.append(row)

    q_hits = []
    for score, idx in zip(q_d[0].tolist(), q_i[0].tolist()):
        if idx == -1:
            continue
        if score_floor is not None and score < score_floor:
            continue
        row = questions.iloc[idx].to_dict()
        row["_score"] = float(score)
        q_hits.append(row)

    # Build prompt context
    context_block = build_context_from_hits(coll_hits, q_hits)

    # Prepare prompt - strict grounding + fallback instruction
    help_url_sample = coll_hits[0].get("help URL", "") if coll_hits else ""
    prompt = (
        "You are a compassionate, non-clinical mental health literacy assistant for young adults.\n"
        "Answer using ONLY the context given below. If the context is insufficient, respond:\n"
        "\"I don’t have enough information in my sources to answer that. Please consult a professional: {help}\".\n\n"
        "Context:\n"
        f"{context_block}\n\nQuestion: {query}\n\nAnswer in 3-6 sentences:"
    ).format(help=help_url_sample or "https://headspace.org.au/")

    # Call Ollama (streamed)
    try:
        answer_text = generate_with_ollama_stream(prompt, model=gen_model)
    except Exception as e:
        answer_text = f"[ERROR_GENERATION] {e}"

    # Save single-line log for this query
    log_rec = {
        "query": query,
        "k": k,
        "gen_model": gen_model,
        "embed_model": embed_model,
        "coll_hits": [{"Disease": h["Disease"], "score": h["_score"]} for h in coll_hits],
        "q_hits": [{"Disease": h["Disease"], "score": h["_score"]} for h in q_hits],
        "answer": answer_text
    }
    # append to jsonl
    with open(OUT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(log_rec, ensure_ascii=False) + "\n")

    return answer_text

if __name__ == "__main__":
    # quick interactive demo in notebook / terminal
    q = input("Enter question: ").strip()
    out = search_and_generate(q, k=3)
    print("\nGenerated answer:\n", out)
