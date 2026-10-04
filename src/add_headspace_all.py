#!/usr/bin/env python3
"""
Append Headspace content into collections.csv
Schema (exact): Disease, context, help URL, links

- Base pages (HTML) -> Playwright -> text -> appended to context
- PDFs -> pdfminer -> text -> appended to context
- links column: JSON mapping {label: url or [urls]}
- Stacks under existing rows (Beyond Blue, Black Dog, WHO, Lifeline) without dropping them
"""

import io, re, sys, time, json, yaml, pathlib, argparse, requests, pandas as pd
from tqdm import tqdm
from pdfminer.high_level import extract_text
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)
CSV_PATH = DATA / "collections.csv"
HELP_URL_OVERRIDE = "https://headspace.org.au/"   # force this for all rows

# ---------- cleaners ----------
def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s

def preprocess_context(text: str) -> str:
    """Extra cleanup for Headspace context."""
    text = re.sub(r"\s+", " ", text)
    # Drop generic intro line
    text = re.sub(
        r"Find a service where you can chat to other people.*?in person",
        "",
        text,
        flags=re.I,
    )
    # Drop copyright/footer & disclaimers
    text = re.sub(r"© headspace.*?\d{4}", "", text)
    text = re.sub(r"headspace National Youth.*?charity", "", text, flags=re.I)
    text = re.sub(r"Last reviewed \d{1,2} \w+ \d{4}", "", text, flags=re.I)
    text = re.sub(r"Fact sheets are for general information.*?advice.", "", text, flags=re.I)
    text = re.sub(
        r"\bheadspace (Clinical|Content) Reference Group.*?(website|resources)",
        "",
        text,
        flags=re.I,
    )
    return text.strip()

def extract_html_text(play, url: str, selectors=None, min_chars: int = 30, throttle: float = 1.0) -> str:
    """Render a page and extract main text."""
    if selectors is None:
        selectors = ["main article", "article", "main", "body"]
    browser = play.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="mh-literacy-bot/0.1 (+edu)")
    page = ctx.new_page()
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass
        # cookie banners
        for label in ["Accept all", "Accept All", "I agree", "Allow all", "Got it", "Accept"]:
            try:
                page.get_by_role("button", name=label, exact=False).click(timeout=1200)
                break
            except Exception:
                continue
        time.sleep(throttle)

        root = None
        for sel in selectors:
            el = page.query_selector(sel)
            if el:
                root = el; break
        if not root:
            return ""

        nodes = root.query_selector_all("p, li")
        paras = []
        for n in nodes:
            try:
                t = n.inner_text()
            except Exception:
                continue
            t = clean_text(t)
            if t and len(t) >= min_chars and not any(x in t.lower() for x in ["javascript", "cookie", "newsletter"]):
                paras.append(t)
        return " ".join(paras)
    finally:
        ctx.close(); browser.close()

def fetch_pdf_text(url: str, timeout: int = 40) -> str:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return extract_text(io.BytesIO(r.content))

def process_condition(play, cond: dict, max_chars_html: int = 40000, max_chars_pdf: int = 40000) -> dict:
    disease = cond["disease"]
    help_url = cond.get("help_url", "")
    resources = cond.get("resources", [])

    context_parts = []
    link_map = {}

    # 1) Base HTML page (scraped for context, link stored separately)
    if help_url:
        try:
            html_text = extract_html_text(play, help_url)
            html_text = clean_text(html_text)
            if len(html_text) > max_chars_html:
                html_text = html_text[:max_chars_html].rsplit(" ", 1)[0] + " ..."
            if html_text:
                context_parts.append(html_text)
            link_map["base"] = help_url
        except Exception as e:
            print(f"[WARN] Base page failed for {disease}: {e}")

    # 2) PDFs / other resources
    for item in tqdm(resources, desc=f"{disease} resources", leave=False):
        url = str(item["url"]).strip()
        label = str(item.get("label", "other")).strip().lower()
        try:
            if url.lower().endswith(".pdf"):
                raw = fetch_pdf_text(url)
                text = clean_text(raw)
                if len(text) > max_chars_pdf:
                    text = text[:max_chars_pdf].rsplit(" ", 1)[0] + " ..."
                if text:
                    context_parts.append(text)
            # build label -> urls mapping
            if label in link_map:
                if isinstance(link_map[label], list):
                    link_map[label].append(url)
                else:
                    link_map[label] = [link_map[label], url]
            else:
                link_map[label] = url
        except Exception as e:
            print(f"[WARN] Failed resource {url}: {e}")

    # preprocess context before returning
    context_all = preprocess_context(" ".join(context_parts))

    return {
        "Disease": disease,
        "context": context_all,
        "help URL": HELP_URL_OVERRIDE,  # always root site
        "links": json.dumps(link_map, ensure_ascii=False)
    }

def normalize_existing_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename to exact headers: Disease, context, help URL, links"""
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/headspace_all.yaml")
    ap.add_argument("--out", default=str(CSV_PATH))
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    conditions = cfg.get("conditions", [])

    with sync_playwright() as play:
        rows = [process_condition(play, cond) for cond in conditions]

    df_new = pd.DataFrame(rows, columns=["Disease", "context", "help URL", "links"])

    # stack under any existing rows
    if pathlib.Path(args.out).exists():
        df_old = pd.read_csv(args.out)
        df_old = normalize_existing_columns(df_old)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new

    df = df[["Disease", "context", "help URL", "links"]]
    df.to_csv(args.out, index=False)
    print(f"Appended {len(df_new)} Headspace rows -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())