"""Hybrid retrieval: BM25 plus embeddings, with BM25 alone as the fallback.

The local embedder is a hashing embedder, so hybrid search runs without a model.
If an Ollama server is reachable, its embedding model is used instead.
Set MANDATE_EMBEDDINGS=off to force BM25 only.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]{2,}")
ROLE_DOMAIN = {
    "dpa": "data_protection",
    "ict_regulator": "telecom",
    "service_operator": "gov_services",
    "policy_adviser": "gov_services",
    "ombudsperson": "gov_services",
    "pre_processor": "data_protection",
}


def tokenize(text: str) -> list[str]:
    return TOKEN.findall((text or "").casefold())


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.n = len(docs)
        self.avg = (sum(len(d) for d in docs) / self.n) if docs else 0.0
        self.df: Counter = Counter()
        for doc in docs:
            for term in set(doc):
                self.df[term] += 1

    def scores(self, query: str) -> list[float]:
        q_terms = tokenize(query)
        out = []
        for doc in self.docs:
            if not doc:
                out.append(0.0)
                continue
            tf = Counter(doc)
            score = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                idf = math.log(1 + (self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * len(doc) / (self.avg or 1))
                score += idf * (freq * (self.k1 + 1)) / denom
            out.append(score)
        return out


def hashing_embed(text: str, dim: int = 256) -> list[float]:
    vec = [0.0] * dim
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class Retriever:
    def __init__(self, chunks: list[dict], embeddings: str | None = None):
        self.chunks = chunks
        self.by_id = {c["chunk_id"]: c for c in chunks}
        self.bm25 = BM25([tokenize(c["text"] + " " + c.get("section_path", "")) for c in chunks])
        mode = embeddings if embeddings is not None else os.environ.get("MANDATE_EMBEDDINGS", "hashing")
        self.backend = "none"
        self._vectors: list[list[float]] | None = None
        if mode == "off":
            return
        if mode == "ollama":
            vectors = _try_ollama([c["text"] for c in chunks])
            if vectors:
                self._vectors = vectors
                self.backend = "ollama"
                return
        self._vectors = [hashing_embed(c["text"]) for c in chunks]
        self.backend = "hashing"

    def search(self, query: str, k: int = 6, role: str | None = None, doc_id: str | None = None) -> list[dict]:
        indexes = list(range(len(self.chunks)))
        if doc_id:
            indexes = [i for i, c in enumerate(self.chunks) if c["doc_id"] == doc_id]
            if not indexes:
                return []
        bm = self.bm25.scores(query)
        ranked_bm = sorted(indexes, key=lambda i: bm[i], reverse=True)
        if self._vectors is None:
            fused = {i: 1.0 / (60 + rank) for rank, i in enumerate(ranked_bm)}
            backend_note = "bm25"
        else:
            qv = hashing_embed(query) if self.backend == "hashing" else _ollama_query(query)
            if qv is None:
                fused = {i: 1.0 / (60 + rank) for rank, i in enumerate(ranked_bm)}
                backend_note = "bm25"
            else:
                sims = [cosine(qv, self._vectors[i]) for i in indexes]
                order = sorted(range(len(indexes)), key=lambda n: sims[n], reverse=True)
                ranked_emb = [indexes[n] for n in order]
                fused = {}
                for rank, i in enumerate(ranked_bm):
                    fused[i] = fused.get(i, 0.0) + 1.0 / (60 + rank)
                for rank, i in enumerate(ranked_emb):
                    fused[i] = fused.get(i, 0.0) + 1.0 / (60 + rank)
                backend_note = self.backend
        domain = ROLE_DOMAIN.get(role or "")
        hits = []
        for i, score in fused.items():
            chunk = self.chunks[i]
            if domain and chunk.get("domain") == domain:
                score *= 1.35
            hits.append((score, chunk))
        hits.sort(key=lambda pair: pair[0], reverse=True)
        out = []
        for score, chunk in hits[:k]:
            out.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "doc_id": chunk["doc_id"],
                    "score": round(float(score), 6),
                    "text": chunk["text"],
                    "section_path": chunk.get("section_path"),
                    "backend": backend_note,
                }
            )
        return out


def _try_ollama(texts: list[str]) -> list[list[float]] | None:
    try:
        return [_ollama_query(t) or [] for t in texts]
    except Exception:
        return None


def _ollama_query(text: str) -> list[float] | None:
    import json
    import urllib.request
    from urllib.parse import urlparse

    base = os.environ.get("MANDATE_OLLAMA_BASE_URL", "http://127.0.0.1:11460").rstrip("/")
    port = urlparse(base).port
    if port in (11434, 11440):
        return None
    model = os.environ.get("MANDATE_EMBED_MODEL", "nomic-embed-text")
    body = json.dumps({"model": model, "prompt": text[:2000]}).encode()
    req = urllib.request.Request(base + "/api/embeddings", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1.5) as resp:
        data = json.loads(resp.read().decode())
    vec = data.get("embedding")
    return vec if isinstance(vec, list) and vec else None
