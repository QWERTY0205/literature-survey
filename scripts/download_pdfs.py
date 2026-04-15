#!/usr/bin/env python3
"""
Multi-threaded PDF downloader for arXiv and conference papers.
Skips existing files, retries failures.

Usage:
    # Download arXiv papers (from arxiv_candidates.json)
    python3 download_pdfs.py --workspace /data/paper/<topic>/ --mode arxiv

    # Download conference papers (from <venue>_raw.json files)
    python3 download_pdfs.py --workspace /data/paper/<topic>/ --mode conf

arxiv_candidates.json format: [{"arxiv_id": "2604.02317", "title": "..."}]
Conference raw JSONs are produced by search_conferences.py (have pdf_url field).
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}
TIMEOUT = 60
MAX_RETRIES = 3


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:150] or "paper"


def download_one(url: str, target: Path, referer: str = "") -> tuple:
    """Download a single PDF with retries."""
    if target.exists() and target.stat().st_size > 10000:
        return ("skip", "")
    headers = {**HEADERS, "Referer": referer} if referer else HEADERS
    last_err = ""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=headers, stream=True)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            tmp = target.with_suffix(".pdf.part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(65536):
                    if chunk:
                        f.write(chunk)
            tmp.rename(target)
            return ("ok", "")
        except Exception as e:
            last_err = str(e)[:150]
            time.sleep(2 * (attempt + 1))
    return ("err", last_err)


def download_arxiv(workspace: Path):
    candidates_file = workspace / "arxiv_candidates.json"
    if not candidates_file.exists():
        print(f"Missing {candidates_file}. Write one in the format:")
        print('  [{"arxiv_id":"2604.02317","title":"..."},...]')
        return
    candidates = json.load(open(candidates_file))

    pdf_dir = workspace / "pdfs"
    pdf_dir.mkdir(exist_ok=True)

    def job(p):
        aid = p["arxiv_id"]
        title = p.get("title", aid)
        url = f"https://arxiv.org/pdf/{aid}"
        target = pdf_dir / f"{sanitize(f'{aid}_{title}')}.pdf"
        status, err = download_one(url, target)
        return aid, status, target if status in ("ok", "skip") else None

    print(f"Downloading {len(candidates)} arxiv PDFs...")
    ok = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(job, p): p for p in candidates}
        for i, fut in enumerate(as_completed(futs), 1):
            aid, status, path = fut.result()
            if status in ("ok", "skip"):
                ok += 1
            if i % 10 == 0 or i == len(candidates):
                print(f"  {i}/{len(candidates)}: ok={ok}")


def download_conf(workspace: Path):
    pdf_dir = workspace / "pdfs_conf"
    pdf_dir.mkdir(exist_ok=True)

    # Collect all conference papers from <venue>_raw.json
    all_papers = []
    for f in workspace.glob("*_raw.json"):
        try:
            d = json.load(open(f))
            for p in d:
                p["_venue_file"] = f.name
            all_papers.extend(d)
        except Exception as e:
            print(f"  skip {f}: {e}")

    if not all_papers:
        print("No *_raw.json files found. Run search_conferences.py first.")
        return

    def job(p):
        url = p.get("pdf_url", "")
        if not url:
            return (None, "no-url", "")
        tag = p["_venue_file"].replace("_raw.json", "")
        title = p.get("title", "paper")
        target = pdf_dir / f"{tag}_{sanitize(title)}.pdf"
        status, err = download_one(url, target, p.get("source_url", ""))
        return (target, status, err)

    print(f"Downloading {len(all_papers)} conf PDFs (dedup may reduce the actual count)...")
    ok = 0
    seen = set()
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = []
        for p in all_papers:
            title_k = p.get("title", "").strip().lower()
            if title_k in seen:
                continue
            seen.add(title_k)
            futs.append(ex.submit(job, p))
        for i, fut in enumerate(as_completed(futs), 1):
            target, status, err = fut.result()
            if status in ("ok", "skip"):
                ok += 1
            if i % 10 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)}: ok={ok}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--mode", choices=["arxiv", "conf", "both"], default="both")
    args = ap.parse_args()

    workspace = Path(args.workspace)
    if args.mode in ("arxiv", "both"):
        download_arxiv(workspace)
    if args.mode in ("conf", "both"):
        download_conf(workspace)

    print("\nDone.")


if __name__ == "__main__":
    main()
