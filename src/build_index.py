# src/build_index.py
import pandas as pd
import numpy as np
import faiss
import pickle
from pathlib import Path
from tqdm import tqdm
from src.utils import get_embedding_ollama, ensure_dir

# CONFIG
TARGET_DIR = Path("target")
ensure_dir(TARGET_DIR)
COLL_PATH = "data/collections.csv"
QUEST_PATH = "data/questions.csv"
COL_IDX_PATH = TARGET_DIR / "collections.index"
Q_IDX_PATH = TARGET_DIR / "questions.index"
COL_EMB_PATH = TARGET_DIR / "collections_embeddings.npy"
Q_EMB_PATH = TARGET_DIR / "questions_embeddings.npy"
COL_MAP = TARGET_DIR / "collections_mapping.pkl"
Q_MAP = TARGET_DIR / "questions_mapping.pkl"
BATCH_SIZE = 16

def make_text_for_collection(row):
    # adjust to CSV field names — you used lowercase 'context' / 'help URL' / 'links' earlier
    return f"Disease: {row['Disease']}\nContext: {row.get('context', row.get('Context',''))}\nHelp URL: {row.get('help URL', row.get('Help URL',''))}\nLinks: {row.get('links','')}"

def make_text_for_question(row):
    return f"Disease: {row['Disease']}\nQuestion: {row['Question']}\nAnswer: {row['Answer']}"

def embed_texts(texts, model="nomic-embed-text"):
    embs = []
    for t in tqdm(texts):
        e = get_embedding_ollama(t, model=model)
        if e is None:
            # fallback to zeros (shouldn't happen if Ollama works)
            e = [0.0]*768
        embs.append(e)
    return np.array(embs, dtype="float32")

def main():
    # load CSVs
    coll = pd.read_csv(COLL_PATH)
    quest = pd.read_csv(QUEST_PATH)

    # build text lists
    coll_texts = [make_text_for_collection(r) for _, r in coll.iterrows()]
    quest_texts = [make_text_for_question(r) for _, r in quest.iterrows()]

    # embeddings (sequential; could batch/parallelise)
    print("Embedding collections...")
    coll_emb = embed_texts(coll_texts, model="nomic-embed-text")
    print("Embedding questions...")
    quest_emb = embed_texts(quest_texts, model="nomic-embed-text")

    dim = coll_emb.shape[1]
    print("Building FAISS indexes dim:", dim)
    col_index = faiss.IndexFlatL2(dim)
    col_index.add(coll_emb)
    faiss.write_index(col_index, str(COL_IDX_PATH))
    np.save(str(COL_EMB_PATH), coll_emb)

    q_index = faiss.IndexFlatL2(quest_emb.shape[1])
    q_index.add(quest_emb)
    faiss.write_index(q_index, str(Q_IDX_PATH))
    np.save(str(Q_EMB_PATH), quest_emb)

    # saving mapping (row->text) for quick inspection
    with open(str(COL_MAP), "wb") as f:
        pickle.dump({i: t for i, t in enumerate(coll_texts)}, f)
    with open(str(Q_MAP), "wb") as f:
        pickle.dump({i: t for i, t in enumerate(quest_texts)}, f)

    # also saving cleaned copies of CSVs into target for reproducibility
    coll.to_csv(TARGET_DIR / "collections.csv", index=False)
    quest.to_csv(TARGET_DIR / "questions.csv", index=False)
    print("Index, embeddings and mappings saved to target/")

if __name__ == "__main__":
    main()
