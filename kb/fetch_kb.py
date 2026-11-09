#!/usr/bin/env python3
"""Check local knowledge-base files and list documents that are not shipped.

Redistributable sources are already in the repository. This script verifies
their sha256 against kb/checksums.json when that file exists. It prints the
URL of every document whose text is not redistributed. It does not download
those documents.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manifest = yaml.safe_load((ROOT / "kb" / "manifest.yaml").read_text(encoding="utf-8"))
    checksums_path = ROOT / "kb" / "checksums.json"
    checksums = json.loads(checksums_path.read_text(encoding="utf-8")) if checksums_path.exists() else {}
    failed = 0
    for doc in manifest["documents"]:
        if not doc.get("redistributable"):
            print(f"METADATA ONLY  {doc['doc_id']}\n  {doc.get('url')}")
            continue
        source = doc.get("source_path")
        if not source:
            print(f"GENERATED      {doc['doc_id']}")
            continue
        path = ROOT / source
        if not path.exists():
            print(f"MISSING        {doc['doc_id']}  {source}")
            failed += 1
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = checksums.get(doc["doc_id"])
        if expected and expected != digest:
            print(f"HASH MISMATCH  {doc['doc_id']}")
            failed += 1
        else:
            print(f"OK             {doc['doc_id']}  {digest[:16]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
