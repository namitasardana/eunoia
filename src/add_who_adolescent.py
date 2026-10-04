#!/usr/bin/env python3
"""
Append WHO 'Adolescent mental health' sections to collections.csv
URL: https://www.who.int/news-room/fact-sheets/detail/adolescent-mental-health

Writes one row per disease with columns:
Disease, context, help URL, links
"""

from typing import Optional
import re, sys, argparse, pathlib, json, requests, pandas as pd
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)
CSV_PATH = DATA / "collections.csv"

WHO_URL = "https://www.who.int/news-room/fact-sheets/detail/adolescent-mental-health"

TARGET_SECTIONS = [
    "Behavioural disorders",
    "Eating disorders",
    "Psychosis",
    "Suicide and self-harm",
    "Risk-taking behaviours",
]

ALIASES = {
    "behavioural disorders": ["behavioural disorders", "behavioral disorders"],
    "eating disorders": ["eating disorders"],
    "psychosis": ["psychosis"],
    "suicide and self-harm": ["suicide and self-harm", "suicide & self-harm"],
    "risk-taking behaviours": [
        "risk-taking behaviours",
        "risk taking behaviours",
        "risk-taking behaviors",
    ],
}

# --------- preprocessing ---------
def preprocess_context(txt: str) -> str:
    """Basic cleanup for WHO text."""
    txt = re.sub(r"\s+", " ", (txt or "")).strip()
    # remove bullets like •
    txt = txt.replace("•", " ")
    # remove boilerplate disclaimers if any
    txt = re.sub(r"This fact sheet.*?World Health Organization.*", "", txt, flags=re.I)
    return txt.strip()

# --------- scraping / parsing ---------
def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def fetch_html(url: str, timeout: int = 30) -> str:
    headers = {"User-Agent": "mh-literacy-bot/0.1 (+educational use)"}
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r.text

def parse_sections(html: str) -> dict:
    """Parse h2/h3-headed sections into {heading: text}."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one("main") or soup.body or soup
    nodes = main.select("h2, h3, p, li")

    sections = {}
    current = None
    for n in nodes:
        tag = n.name.lower()
        if tag in ("h2", "h3"):
            head = clean(n.get_text(" "))
            if head:
                current = head
                sections.setdefault(current, [])
        elif tag in ("p", "li") and current:
            txt = clean(n.get_text(" "))
            if txt and not any(bad in txt.lower() for bad in ["cookie", "javascript"]):
                sections[current].append(txt)
    return {h: " ".join(v) for h, v in sections.items() if v}

def match_target(heading: str) -> Optional[str]:
    h = heading.lower()
    for target in TARGET_SECTIONS:
        for alias in ALIASES[target.lower()]:
            if alias in h:
                return target
    return None

def extract_targets(section_map: dict) -> dict:
    out = {}
    for h, text in section_map.items():
        label = match_target(h)
        if label:
            out[label] = (out.get(label, "") + " " + text).strip()
    return out

# --------- dataframe helpers ---------
def normalize_existing_columns(df: pd.DataFrame) -> pd.DataFrame:
    rm = {}
    lower = {c.lower(): c for c in df.columns}
    if "context" not in df.columns:
        if "context" in lower: rm[lower["context"]] = "context"
        elif "Context" in df.columns: rm["Context"] = "context"
    if "help url" not in df.columns:
        if "help url" in lower: rm[lower["help url"]] = "help URL"
        elif "Help URL" in df.columns: rm["Help URL"] = "help URL"
        elif "help_url" in df.columns: rm["help_url"] = "help URL"
    if "links" not in df.columns:
        if "links" in lower: rm[lower["links"]] = "links"
        elif "Links" in df.columns: rm["Links"] = "links"
        elif "URLs" in df.columns: rm["URLs"] = "links"
    if rm:
        df = df.rename(columns=rm)
    for col in ["Disease", "context", "help URL", "links"]:
        if col not in df.columns:
            df[col] = ""
    return df[["Disease", "context", "help URL", "links"]]

# --------- main ---------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=WHO_URL)
    ap.add_argument("--out", default=str(CSV_PATH))
    args = ap.parse_args()

    html = fetch_html(args.url)
    section_map = parse_sections(html)
    targets = extract_targets(section_map)

    rows = []
    for disease in TARGET_SECTIONS:
        ctx = preprocess_context(targets.get(disease, ""))
        rows.append({
            "Disease": disease,
            "context": ctx,
            "help URL": args.url,
            "links": json.dumps({"base": args.url}, ensure_ascii=False),
        })

    df_new = pd.DataFrame(rows, columns=["Disease", "context", "help URL", "links"])

    out_path = pathlib.Path(args.out)
    if out_path.exists():
        df_old = pd.read_csv(out_path)
        df_old = normalize_existing_columns(df_old)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new

    df.to_csv(out_path, index=False)
    print(f"Appended {len(df_new)} WHO rows -> {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())