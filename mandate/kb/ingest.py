"""Build kb/chunks.jsonl from the manifest and vendored framework files."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from mandate.kb.chunker import chunk_document
from mandate.kb.tagger import dimension_chunks, tag_chunk
from mandate.paths import KB, ROOT, VENDOR


def load_manifest(path: Path | None = None) -> list[dict]:
    path = path or (KB / "manifest.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data["documents"])


def ingest(manifest_path: Path | None = None) -> list[dict]:
    docs = load_manifest(manifest_path)
    ref = yaml.safe_load((KB / "ref_catalog.yaml").read_text(encoding="utf-8"))
    chunks: list[dict] = []
    checksums = {}
    for doc in docs:
        if not doc.get("redistributable"):
            continue
        source = doc.get("source_path")
        if not source:
            continue
        path = ROOT / source
        raw = path.read_text(encoding="utf-8")
        checksums[doc["doc_id"]] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        for chunk in chunk_document(raw, doc):
            chunks.append(tag_chunk(chunk))
    for chunk in dimension_chunks():
        chunks.append(chunk)
    checksums["ai-ready-2-dimensions"] = hashlib.sha256(
        (VENDOR / "dimensions.json").read_bytes()
    ).hexdigest()
    _write_chunks(chunks)
    _write_licences(docs, ref["documents"], checksums)
    _write_coverage(chunks, docs)
    (KB / "checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    return chunks


def _write_chunks(chunks: list[dict]) -> None:
    lines = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks)
    (KB / "chunks.jsonl").write_text(lines, encoding="utf-8")
    export = KB / "export"
    export.mkdir(exist_ok=True)
    (export / "chunks.jsonl").write_text(lines, encoding="utf-8")


def _write_licences(docs: list[dict], ref_docs: list[dict], checksums: dict) -> None:
    lines = [
        "# Licences",
        "",
        "A document is shipped as text only when `redistributable` is true.",
        "Everything else is a manifest entry: title, issuer, URL, and licence. No text.",
        "",
        "| doc_id | redistributable | licence | sha256 |",
        "|---|---|---|---|",
    ]
    for doc in docs:
        digest = checksums.get(doc["doc_id"], "—")
        if digest != "—":
            digest = digest[:16] + "…"
        lines.append(
            f"| {doc['doc_id']} | {str(bool(doc.get('redistributable'))).lower()} | {doc.get('licence', '')} | {digest} |"
        )
    lines += ["", "## Reference repository documents (metadata only)", ""]
    lines.append("Upstream: https://github.com/CrashingGuru/ITUAIReadiness commit 84010da. PDFs are not copied.")
    lines.append("")
    lines.append("| doc_id | title | licence |")
    lines.append("|---|---|---|")
    for doc in ref_docs:
        lines.append(f"| {doc['doc_id']} | {doc['title']} | {doc['licence']} |")
    (KB / "licences.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_coverage(chunks: list[dict], docs: list[dict]) -> None:
    by_type = Counter(c.get("instrument_type") for c in chunks)
    by_dim = Counter()
    for chunk in chunks:
        for dim in chunk.get("readiness_dims") or []:
            by_dim[dim] += 1
    matrix = Counter()
    for chunk in chunks:
        for dim in chunk.get("readiness_dims") or ["—"]:
            matrix[(dim, chunk.get("instrument_type"))] += 1
    shipped = sum(1 for d in docs if d.get("redistributable"))
    held = sum(1 for d in docs if not d.get("redistributable"))
    lines = [
        "# Coverage",
        "",
        f"- Manifest documents added for this project: {len(docs)} ({shipped} with text, {held} metadata only).",
        f"- Chunks shipped in `kb/chunks.jsonl`: {len(chunks)}.",
        "",
        "## Chunks by instrument type",
        "",
    ]
    for key, count in sorted(by_type.items(), key=lambda kv: str(kv[0])):
        lines.append(f"- {key}: {count}")
    lines += ["", "## Chunks by Readiness dimension", ""]
    for dim in [f"D{i}" for i in range(1, 14)]:
        lines.append(f"- {dim}: {by_dim.get(dim, 0)}")
    lines += ["", "## Dimension × instrument type (non-zero)", "", "| Dimension | Instrument | Chunks |", "|---|---|---|"]
    for (dim, kind), count in sorted(matrix.items()):
        lines.append(f"| {dim} | {kind} | {count} |")
    (KB / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_chunks(path: Path | None = None) -> list[dict]:
    path = path or (KB / "chunks.jsonl")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
