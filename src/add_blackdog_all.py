#!/usr/bin/env python3
"""
Aggregate Black Dog Institute PDFs into collections.csv
Schema (exact headers): Disease, context, help URL, links
"""

import io, re, sys, pathlib, argparse, requests, pandas as pd, yaml, json
from tqdm import tqdm
from pdfminer.high_level import extract_text

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)
CSV_PATH = DATA / "collections.csv"

# ---------- preprocess ----------
def preprocess_context(txt: str) -> str:
    """Basic cleaning for Black Dog Institute text."""
    txt = re.sub(r"\s+", " ", (txt or "")).strip()
    # remove Black Dog slogan
    txt = re.sub(r"Science\.\s*Compassion\.\s*Action\.\s*", "", txt, flags=re.I)
    # remove common disclaimers
    txt = re.sub(r"This fact sheet.*?Black Dog Institute.*?(©|All rights reserved).*", "", txt, flags=re.I)
    # strip emails, phone numbers
    txt = re.sub(r"\b[\w\.-]+@[\w\.-]+\b", "", txt)
    txt = re.sub(r"\b\d{2,}[- ]?\d{2,}\b", "", txt)
    # remove bullet points like •
    txt = txt.replace("•", " ")
    return txt.strip()

def fetch_pdf_text(url: str, timeout: int = 40) -> str:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return extract_text(io.BytesIO(r.content))

def normalize_existing_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename common variants to the required schema."""
    rename_map = {}
    cols_lower = {c.lower(): c for c in df.columns}

    if "context" not in df.columns:
        if "context" in cols_lower: rename_map[cols_lower["context"]] = "context"
        elif "Context" in df.columns: rename_map["Context"] = "context"

    if "help URL" not in df.columns:
        if "help url" in cols_lower: rename_map[cols_lower["help url"]] = "help URL"
        elif "Help URL" in df.columns: rename_map["Help URL"] = "help URL"
        elif "help_url" in df.columns: rename_map["help_url"] = "help URL"

    if "links" not in df.columns:
        if "links" in cols_lower: rename_map[cols_lower["links"]] = "links"
        elif "Links" in df.columns: rename_map["Links"] = "links"
        elif "URLs" in df.columns: rename_map["URLs"] = "links"

    if rename_map:
        df = df.rename(columns=rename_map)

    for col in ["Disease", "context", "help URL", "links"]:
        if col not in df.columns:
            df[col] = ""

    return df[["Disease", "context", "help URL", "links"]]

# ---------- per-condition processing ----------
def process_condition(cond: dict, max_chars: int = 50000) -> dict:
    disease = cond["disease"]
    help_url = cond.get("help_url", "")
    pdfs = cond.get("pdfs", [])

    contexts = []
    link_map = {}

    for item in tqdm(pdfs, desc=f"{disease} PDFs"):
        url = str(item["url"]).strip()
        label = str(item.get("label", "other")).strip().lower()
        try:
            if url.lower().endswith(".pdf"):
                raw = fetch_pdf_text(url)
                text = preprocess_context(raw)
            else:
                text = f"See resource: {url}"
            if len(text) > max_chars:
                text = text[:max_chars].rsplit(" ", 1)[0] + " ..."
            contexts.append(text)

            if label in link_map:
                if isinstance(link_map[label], list):
                    link_map[label].append(url)
                else:
                    link_map[label] = [link_map[label], url]
            else:
                link_map[label] = url
        except Exception as e:
            print(f"[WARN] Failed {url}: {e}")

    context_all = " ".join(contexts) if contexts else ""
    return {
        "Disease": disease,
        "context": context_all,
        "help URL": help_url,
        "links": json.dumps(link_map, ensure_ascii=False)
    }

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/blackdog_all.yaml")
    ap.add_argument("--out", default=str(CSV_PATH))
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    conditions = cfg.get("conditions", [])
    rows = [process_condition(cond) for cond in conditions]

    df_new = pd.DataFrame(rows, columns=["Disease", "context", "help URL", "links"])

    if pathlib.Path(args.out).exists():
        df_old = pd.read_csv(args.out)
        df_old = normalize_existing_columns(df_old)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new

    df = df[["Disease", "context", "help URL", "links"]]
    df.to_csv(args.out, index=False)
    print(f"Appended {len(df_new)} condition rows -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())