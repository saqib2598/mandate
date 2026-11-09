"""Tag chunks with Readiness dimensions and Y.3172 nodes.

Explicit section tags win. Otherwise the document defaults are combined with
keyword hints adapted from the reference router, and with the node-to-dimension
map from the reference use-case agent.
"""
from __future__ import annotations

import json
from pathlib import Path

from mandate.paths import VENDOR


def _load(name: str) -> dict:
    return json.loads((VENDOR / name).read_text(encoding="utf-8"))


def tag_chunk(chunk: dict) -> dict:
    if chunk.get("explicit_tags"):
        chunk["readiness_dims"] = _norm_dims(chunk.get("readiness_dims") or [])
        chunk["y3172_nodes"] = list(chunk.get("y3172_nodes") or [])
        chunk["readiness_factor"] = chunk.get("readiness_factor") or _factor_for(chunk["y3172_nodes"])
        return chunk
    text = (chunk.get("text") or "").casefold()
    dims = set(chunk.get("readiness_dims") or [])
    nodes = set(chunk.get("y3172_nodes") or [])
    hints = _load("keywords.json")["hints"]
    for words, dim_ids in hints:
        if any(word in text for word in words):
            dims.update(f"D{i}" for i in dim_ids)
    node_map = _load("node_map.json")
    for node, mapped in node_map["NODE_TO_DIMENSIONS"].items():
        if node in nodes:
            dims.update(f"D{i}" for i in mapped)
    for node, keywords in _NODE_KEYWORDS.items():
        if any(word in text for word in keywords):
            nodes.add(node)
            dims.update(f"D{i}" for i in node_map["NODE_TO_DIMENSIONS"][node])
    chunk["readiness_dims"] = _norm_dims(dims)
    chunk["y3172_nodes"] = [n for n in node_map["NODE_TO_DIMENSIONS"] if n in nodes]
    chunk["readiness_factor"] = chunk.get("readiness_factor") or _factor_for(chunk["y3172_nodes"])
    return chunk


_NODE_KEYWORDS = {
    "SRC": ("source data", "case record", "citizen quer"),
    "C": ("collector", "event feed", "outage"),
    "PP": ("pre-process", "redact", "prompt injection", "normalis"),
    "M": ("model", "automated decision", "inference"),
    "P": ("policy", "mandate", "human review", "human involvement"),
    "D": ("distribut", "notice", "channel"),
    "SINK": ("decision delivered", "appeal", "recourse"),
    "MLFO": ("orchestrat", "conductor"),
    "Sandbox": ("sandbox", "simulated"),
}


def _norm_dims(values) -> list[str]:
    out = []
    for value in values:
        text = str(value)
        if text.startswith("D"):
            out.append(text)
        else:
            out.append(f"D{text}")
    return sorted(set(out), key=lambda d: int(d[1:]))


def _factor_for(nodes: list[str]) -> str | None:
    mapping = _load("node_map.json")["NODE_TO_FACTORS"]
    for node in nodes:
        if node in mapping:
            return mapping[node]
    return None


def dimension_chunks() -> list[dict]:
    """One chunk per Readiness 2.0 dimension, from the vendored framework file."""
    data = json.loads((VENDOR / "dimensions.json").read_text(encoding="utf-8"))
    factors = {f["id"]: f["name"] for f in data["factors"]}
    chunks = []
    for dim in data["dimensions"]:
        factor_names = ", ".join(factors.get(f, f) for f in dim["mapped_factors"])
        metric_names = "; ".join(m["name"] for m in dim["metrics"][:6])
        text = (
            f"AI Readiness 2.0 dimension D{dim['id']} {dim['name']}. {dim['description']} "
            f"Mapped factors: {factor_names}. Example metrics: {metric_names}."
        )
        text = " ".join(text.split())
        chunks.append(
            {
                "chunk_id": f"ai-ready-2-dimensions:{dim['id']:03d}",
                "doc_id": "ai-ready-2-dimensions",
                "text": text,
                "section_path": f"AI Readiness 2.0 > D{dim['id']} {dim['name']}",
                "page": None,
                "jurisdiction": "global",
                "instrument_type": "standard",
                "domain": "cross",
                "date": "2026-01",
                "licence": "MIT, vendored from ITUAIReadiness dimensions.json",
                "readiness_factor": dim["mapped_factors"][0],
                "readiness_dims": [f"D{dim['id']}"],
                "y3172_nodes": [],
                "chunk_sha": __import__("hashlib").sha256(text.encode()).hexdigest(),
                "explicit_tags": True,
            }
        )
    return chunks
