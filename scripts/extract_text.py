#!/usr/bin/env python3
"""
Extract full text from all PDFs in workspace using pdftotext -layout.

Usage:
    python3 extract_text.py --workspace /data/paper/<topic>/

Outputs:
    <workspace>/texts/*.txt      (for arxiv PDFs)
    <workspace>/texts_conf/*.txt (for conference PDFs)
    <workspace>/manifest.json         (arxiv {arxiv_id, title, pdf_path, txt_path})
    <workspace>/confs_manifest.json   (conf   {venue, title, pdf_path, txt_path, source_url})
"""
import argparse
import json
import re
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def extract(pdf_path: Path, txt_dir: Path) -> str:
    txt_path = txt_dir / (pdf_path.stem + ".txt")
    if txt_path.exists() and txt_path.stat().st_size > 0:
        return str(txt_path)
    try:
        subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
            check=True, timeout=120, capture_output=True,
        )
        return str(txt_path)
    except Exception as e:
        return ""


def build_arxiv_manifest(workspace: Path) -> list:
    pdf_dir = workspace / "pdfs"
    txt_dir = workspace / "texts"
    txt_dir.mkdir(exist_ok=True)
    if not pdf_dir.exists():
        return []

    candidates = {}
    try:
        cfg = json.load(open(workspace / "arxiv_candidates.json"))
        for p in cfg:
            candidates[p["arxiv_id"]] = p.get("title", "")
    except Exception:
        pass

    pdfs = list(pdf_dir.glob("*.pdf"))
    print(f"Extracting {len(pdfs)} arxiv PDFs...")
    manifest = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(extract, p, txt_dir): p for p in pdfs}
        for fut in as_completed(futs):
            p = futs[fut]
            txt = fut.result()
            if not txt:
                continue
            # Parse arxiv_id from filename (first token before _)
            m = re.match(r"(\d{4}\.\d{4,5})_", p.name)
            aid = m.group(1) if m else ""
            manifest.append({
                "arxiv_id": aid,
                "title": candidates.get(aid, p.stem),
                "pdf_path": str(p),
                "txt_path": txt,
            })
    return manifest


def build_conf_manifest(workspace: Path) -> list:
    pdf_dir = workspace / "pdfs_conf"
    txt_dir = workspace / "texts_conf"
    txt_dir.mkdir(exist_ok=True)
    if not pdf_dir.exists():
        return []

    # Build title -> paper metadata from raw json files
    title_meta = {}
    for f in workspace.glob("*_raw.json"):
        try:
            d = json.load(open(f))
            venue = f.name.replace("_raw.json", "")
            for p in d:
                title_k = p.get("title", "").strip().lower()
                if title_k:
                    title_meta[title_k] = {
                        "venue": venue,
                        "title": p.get("title", ""),
                        "source_url": p.get("source_url", ""),
                        "pdf_url": p.get("pdf_url", ""),
                    }
        except Exception:
            pass

    pdfs = list(pdf_dir.glob("*.pdf"))
    print(f"Extracting {len(pdfs)} conf PDFs...")
    manifest = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(extract, p, txt_dir): p for p in pdfs}
        for fut in as_completed(futs):
            p = futs[fut]
            txt = fut.result()
            if not txt:
                continue
            # Try to match title from filename (after first underscore)
            stem = p.stem
            title_guess = stem.split("_", 1)[1] if "_" in stem else stem
            meta = title_meta.get(title_guess.lower(), {})
            manifest.append({
                "venue": meta.get("venue", ""),
                "title": meta.get("title", title_guess),
                "pdf_path": str(p),
                "txt_path": txt,
                "source_url": meta.get("source_url", ""),
            })
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    args = ap.parse_args()
    workspace = Path(args.workspace)

    arxiv_manifest = build_arxiv_manifest(workspace)
    conf_manifest = build_conf_manifest(workspace)

    json.dump(arxiv_manifest, open(workspace / "manifest.json", "w"),
              ensure_ascii=False, indent=2)
    json.dump(conf_manifest, open(workspace / "confs_manifest.json", "w"),
              ensure_ascii=False, indent=2)

    print(f"\n✓ arXiv manifest: {len(arxiv_manifest)} papers")
    print(f"✓ Conf manifest: {len(conf_manifest)} papers")
    print(f"  Total: {len(arxiv_manifest) + len(conf_manifest)} papers")


if __name__ == "__main__":
    main()
