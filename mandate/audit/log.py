"""Hash-chained audit records.

Hash = sha256 of the record without the ``hash`` field, JSON with sorted keys,
compact separators, and UTF-8. The first ``prev_hash`` is 64 zeros.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def canonical_bytes(record: dict) -> bytes:
    body = {k: v for k, v in record.items() if k != "hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def record_hash(record: dict) -> str:
    return hashlib.sha256(canonical_bytes(record)).hexdigest()


def prompt_sha(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class AuditLog:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.prev = GENESIS
        self.records: list[dict] = []
        self.sink: list[dict] = []
        self.bus: list[dict] = []

    def append(self, record: dict) -> dict:
        rec = dict(record)
        rec["run_id"] = self.run_id
        rec["prev_hash"] = self.prev
        rec.pop("hash", None)
        rec["hash"] = record_hash(rec)
        self.prev = rec["hash"]
        self.records.append(rec)
        return rec

    def write(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "audit.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in self.records),
            encoding="utf-8",
        )
        (run_dir / "sink.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in self.sink),
            encoding="utf-8",
        )
        (run_dir / "bus.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in self.bus),
            encoding="utf-8",
        )
