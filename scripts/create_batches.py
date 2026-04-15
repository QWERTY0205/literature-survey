#!/usr/bin/env python3
"""
Split the merged manifest (arxiv + conf) into batches of 3 papers each.

Usage:
    python3 create_batches.py --workspace /data/paper/<topic>/ --batch-size 3

Output: <workspace>/batches/b_NN.json files.
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--batch-size", type=int, default=3,
                    help="Papers per batch. Default 3. Larger risks sub-agent context overflow.")
    args = ap.parse_args()

    workspace = Path(args.workspace)

    # Merge manifests into unified records
    records = []
    try:
        for p in json.load(open(workspace / "manifest.json")):
            records.append({
                "source": "arxiv",
                "arxiv_id": p.get("arxiv_id", ""),
                "title": p.get("title", ""),
                "txt_path": p["txt_path"],
                "pdf_path": p.get("pdf_path", ""),
            })
    except FileNotFoundError:
        pass

    try:
        for p in json.load(open(workspace / "confs_manifest.json")):
            records.append({
                "source": "conf",
                "venue": p.get("venue", ""),
                "title": p.get("title", ""),
                "txt_path": p["txt_path"],
                "pdf_path": p.get("pdf_path", ""),
                "url": p.get("source_url", ""),
            })
    except FileNotFoundError:
        pass

    print(f"Total records: {len(records)}")

    # Drop any without txt_path
    records = [r for r in records if r.get("txt_path")]
    print(f"With txt_path: {len(records)}")

    # Dedup by title (case-insensitive)
    seen = set()
    deduped = []
    for r in records:
        k = r.get("title", "").strip().lower()
        if k and k not in seen:
            seen.add(k)
            deduped.append(r)
    print(f"After dedup: {len(deduped)}")

    # Create batches
    batch_dir = workspace / "batches"
    batch_dir.mkdir(exist_ok=True)
    for f in batch_dir.glob("b_*.json"):
        f.unlink()

    bs = args.batch_size
    for i in range(0, len(deduped), bs):
        batch = deduped[i:i + bs]
        bn = i // bs + 1
        (batch_dir / f"b_{bn:02d}.json").write_text(
            json.dumps(batch, ensure_ascii=False, indent=2))

    n_batches = (len(deduped) + bs - 1) // bs
    print(f"\n✓ Created {n_batches} batches of up to {bs} papers")
    print(f"  Batch dir: {batch_dir}")
    print(f"  Now launch {max(3, n_batches // 6)} parallel sub-agents to analyze them.")


if __name__ == "__main__":
    main()
