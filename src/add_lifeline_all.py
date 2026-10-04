#!/usr/bin/env python3
"""
Append Lifeline PDFs into collections.csv
Schema (exact): Disease, context, help URL, links

- Extracts PDF text via pdfminer
- Preprocesses text (remove boilerplate, normalize whitespace)
- Stacks under existing rows without dropping old ones
"""

import io, re, sys, pathlib, argparse, requests, pandas as pd, yaml, json
from tqdm import tqdm
from pdfminer.high_level import extract_text

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)
CSV_PATH = DATA / "collections.csv"
HELP_URL_OVERRIDE = "https://www.lifeline.org.au"

# ---------- cleaners ----------
def clean_text(txt: str) -> str:
    txt = re.sub(r"\s+", " ", (txt or "")).strip()
    # remove common Lifeline boilerplate
    txt = re.sub(r"Lifeline Australia.*?www\.lifeline\.org\.au.*", "", txt, flags=re.I)
    txt = re.sub(r"©\s*Lifeline.*", "", txt, flags=re.I)
    return txt

def fetch_pdf_text(url: str, timeout: int = 40) -> str:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return extract_text(io.BytesIO(r.content))



#  per-condition processing 
def process_condition(cond: dict, max_chars: int = 40000) -> dict:
    disease = cond["disease"]
    resources = cond.get("resources", [])

    contexts = []
    link_map = {}

    for item in tqdm(resources, desc=f"{disease} PDFs", leave=False):
        url = str(item["url"]).strip()
        label = str(item.get("label", "other")).strip().lower()
        try:
            raw = fetch_pdf_text(url)
            text = clean_text(raw)
            if len(text) > max_chars:
                text = text[:max_chars].rsplit(" ", 1)[0] + " ..."
            if text:
                contexts.append(text)

            # build label -> urls mapping
            if label in link_map:
                if isinstance(link_map[label], list):
                    link_map[label].append(url)
                else:
                    link_map[label] = [link_map[label], url]
            else:
                link_map[label] = url
        except Exception as e:
            print(f"[WARN] Failed {url}: {e}")

    context_all = " ".join(contexts)
    return {
        "Disease": disease,
        "context": context_all,
        "help URL": HELP_URL_OVERRIDE,
        "links": json.dumps(link_map, ensure_ascii=False)
    }

# ---------- CSV normalization ----------
def normalize_existing_columns(df: pd.DataFrame) -> pd.DataFrame:
    rm = {}
    lower = {c.lower(): c for c in df.columns}
    if "context" not in df.columns and "Context" in df.columns:
        rm["Context"] = "context"
    if "help url" not in df.columns and "Help URL" in df.columns:
        rm["Help URL"] = "help URL"
    if "links" not in df.columns:
        if "Links" in df.columns:
            rm["Links"] = "links"
        elif "URLs" in df.columns:
            rm["URLs"] = "links"
    if rm:
        df = df.rename(columns=rm)
    for col in ["Disease","context","help URL","links"]:
        if col not in df.columns: 
            df[col] = ""
    return df[["Disease","context","help URL","links"]]

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/lifeline_all.yaml")
    ap.add_argument("--out", default=str(CSV_PATH))
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    conditions = cfg.get("conditions", [])
    rows = [process_condition(c) for c in conditions]

    df_new = pd.DataFrame(rows, columns=["Disease","context","help URL","links"])

    if pathlib.Path(args.out).exists():
        df_old = pd.read_csv(args.out)
        df_old = normalize_existing_columns(df_old)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new

    df.to_csv(args.out, index=False)
    print(f"Appended {len(df_new)} Lifeline rows -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())