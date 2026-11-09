"""Re-check a hash chain. Independent of the scorer, same canonicalisation."""
from __future__ import annotations

import json
from pathlib import Path

from mandate.audit.log import GENESIS, record_hash


def verify_chain(path: Path) -> dict:
    prev = GENESIS
    breaks = []
    n = 0
    run_ids = set()
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        n += 1
        rec = json.loads(line)
        run_ids.add(rec.get("run_id"))
        if rec.get("prev_hash") != prev:
            breaks.append({"line": i, "reason": "prev_hash_mismatch"})
        if rec.get("hash") != record_hash(rec):
            breaks.append({"line": i, "reason": "hash_mismatch"})
        prev = rec.get("hash")
    return {
        "records": n,
        "ok": not breaks and n > 0 and len(run_ids) <= 1,
        "breaks": breaks,
        "run_ids": sorted(x for x in run_ids if x is not None),
    }
