#!/usr/bin/env python3
"""
Scrape Beyond Blue pages into a single CSV with columns:
Disease, Context, Help URL, Links

- Uses Playwright to render JS
- Merges multiple rows per Disease into one (concat Context; combine unique Links)
- For Suicide Prevention, keep only the base URL as Help URL
- Links column is JSON mapping { "subpath": url }
"""

import re, sys, time, argparse, pathlib, json
from urllib.parse import urlparse, urljoin
import pandas as pd
import yaml
from tqdm import tqdm
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

# ---------- cleaners ----------
def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def preprocess_context(text: str) -> str:
    """Light cleanup for Beyond Blue context."""
    text = re.sub(r"\s+", " ", text or "")
    # Remove cookie/consent/banner boilerplate
    text = re.sub(r"(accept all cookies|privacy policy|terms of use).*", "", text, flags=re.I)
    # Remove promotional line
    text = re.sub(r"Find a service where you can chat.*?(person|online)", "", text, flags=re.I)
    # Remove footer / funding disclaimers
    text = re.sub(r"Beyond Blue.*(ABN|All rights reserved).*", "", text, flags=re.I)
    return text.strip()

def disease_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    if "suicide" in path: return "Suicide Prevention"
    if "loneliness" in path: return "Loneliness"
    if "depression" in path: return "Depression"
    if "anxiety" in path: return "Anxiety"
    if "stress" in path: return "Stress"
    return path.strip("/").split("/")[-1].replace("-", " ").title() or "Unknown"

def accept_cookies(page) -> None:
    for text in ["Accept all", "Accept All", "I agree", "Allow all", "Got it", "Accept"]:
        try:
            page.get_by_role("button", name=text, exact=False).click(timeout=1200)
            break
        except Exception:
            continue

def extract_context_and_links(page, selectors, base_url, min_chars=30):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        pass
    accept_cookies(page)

    root = None
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            root = el; break
    if not root:
        root = page.query_selector("main") or page.query_selector("body")
    if not root:
        return "", {}

    # extract paragraphs
    nodes = root.query_selector_all("p, li")
    paras = []
    for node in nodes:
        txt = clean(node.inner_text())
        if txt and len(txt) >= min_chars:
            if "javascript" in txt.lower() or "cookie" in txt.lower():
                continue
            paras.append(txt)

    # extract links with labels from path
    link_nodes = root.query_selector_all("a")
    links = {}
    for a in link_nodes:
        try:
            href = a.get_attribute("href")
            if href:
                href = urljoin(base_url, href)
                if href.startswith("http"):
                    path = urlparse(href).path
                    if "mental-health" in path:
                        label = path.split("mental-health/")[-1].strip("/")
                        if label:  # avoid empty
                            links[label] = href
        except Exception:
            continue

    context = preprocess_context(" ".join(paras))
    return context, links

def scrape(play, seeds, selectors, min_chars=30):
    browser = play.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="mh-literacy-bot/0.1 (+edu)")
    page = ctx.new_page()
    rows = []
    for url in tqdm(seeds, desc="Scraping"):
        disease = disease_from_url(url)
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(1.0)
            context, links = extract_context_and_links(page, selectors, url, min_chars)
        except Exception:
            context, links = "", {}
        rows.append({
            "Disease": disease,
            "Context": context,
            "Help URL": url,
            "Links": json.dumps(links, ensure_ascii=False)
        })
    ctx.close(); browser.close()
    return rows

def merge_by_disease(df: pd.DataFrame) -> pd.DataFrame:
    def pick_help_url(disease, urls):
        if disease == "Suicide Prevention":
            for u in urls:
                if u.strip().endswith("/suicide-prevention"):
                    return u
            return urls.iloc[0]
        return urls.iloc[0]

    def merge_links(series):
        merged = {}
        for s in series.dropna():
            try:
                d = json.loads(s)
                merged.update(d)
            except Exception:
                continue
        return json.dumps(merged, ensure_ascii=False)

    merged = (
        df.groupby("Disease", as_index=False)
          .agg({
              "Context": lambda x: preprocess_context(" ".join(str(v) for v in x if pd.notna(v))),
              "Help URL": lambda x: pick_help_url(x.name, x),
              "Links": merge_links
          })
    )
    return merged

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=str(DATA / "collections.csv"))
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    all_rows = []
    with sync_playwright() as p:
        for src in cfg["sources"]:
            seeds = src.get("seeds", [])
            selectors = src.get("content_selectors", []) or ["main article","article"]
            min_chars = int(src.get("min_paragraph_chars", 30))
            all_rows.extend(scrape(p, seeds, selectors, min_chars))

    df = pd.DataFrame(all_rows, columns=["Disease","Context","Help URL","Links"])
    df = merge_by_disease(df)
    df.to_csv(args.out, index=False)
    print(f"Saved {len(df)} unique diseases -> {args.out}")

if __name__ == "__main__":
    sys.exit(main())