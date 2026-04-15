#!/usr/bin/env python3
"""
Search top conferences for papers matching given keywords using papers-cool-downloader.

Usage:
    python3 search_conferences.py \
        --workspace /data/paper/<topic>/ \
        --keywords "streaming video" "video LLM" "online video" \
        --venues CVPR.2025 ICCV.2025 NeurIPS.2025 ICLR.2026 AAAI.2026 ACL.2025 ICML.2025

Output: <workspace>/<venue_tag>_raw.json per venue.
"""
import argparse
import subprocess
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PAPERS_COOL_DIR = Path("/tmp/papers-cool-downloader")


def ensure_scraper():
    if not PAPERS_COOL_DIR.exists():
        subprocess.run([
            "git", "clone", "https://github.com/QWERTY0205/papers-cool-downloader",
            str(PAPERS_COOL_DIR)
        ], check=True)
        subprocess.run(["pip", "install", "requests", "-q"], check=True)


def venue_to_tag(venue: str) -> str:
    # CVPR.2025 -> cvpr25
    name, year = venue.split(".")
    return f"{name.lower()}{year[-2:]}"


def search_venue(venue: str, keywords, workspace: Path):
    """Invoke papers-cool-downloader for one venue."""
    conf_name, year = venue.split(".")
    tag = venue_to_tag(venue)
    out = workspace / f"{tag}_raw.json"

    cmd = ["python3", "scraper.py",
           "--venue", conf_name, "--year", year,
           "--match-mode", "any", "--search-fields", "both",
           "--format", "json",
           "--output", str(out),
           "--max-print", "0"]
    for kw in keywords:
        cmd.extend(["--keyword", kw])

    try:
        result = subprocess.run(cmd, cwd=PAPERS_COOL_DIR, capture_output=True,
                                text=True, timeout=900)
        if result.returncode != 0:
            return venue, 'err', result.stderr[-500:]
        return venue, 'ok', str(out)
    except subprocess.TimeoutExpired:
        return venue, 'timeout', ''
    except Exception as e:
        return venue, 'err', str(e)[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="Output workspace dir")
    ap.add_argument("--keywords", nargs="+", required=True, help="Keywords (space-separated)")
    ap.add_argument("--venues", nargs="+",
                    default=["CVPR.2025", "ICCV.2025", "NeurIPS.2025",
                             "ICLR.2026", "AAAI.2026", "ACL.2025", "ICML.2025"],
                    help="Venues as <Conf>.<Year>")
    args = ap.parse_args()

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    ensure_scraper()

    print(f"Searching {len(args.venues)} venues for {len(args.keywords)} keywords...")
    with ThreadPoolExecutor(max_workers=len(args.venues)) as ex:
        futs = [ex.submit(search_venue, v, args.keywords, workspace)
                for v in args.venues]
        for fut in as_completed(futs):
            venue, status, info = fut.result()
            if status == 'ok':
                # count papers
                try:
                    import json
                    n = len(json.load(open(info)))
                    print(f"  {venue}: {n} papers -> {info}")
                except Exception:
                    print(f"  {venue}: {status} -> {info}")
            else:
                print(f"  {venue}: {status} {info}")

    print("\nDone. Inspect the JSON files in the workspace.")


if __name__ == "__main__":
    main()
