"""Split documents on article and section boundaries, then pack long sections.

Target size is about 400 whitespace tokens with 50 tokens of overlap.
Short sections stay whole so a legal clause is not cut mid-sentence.
"""
from __future__ import annotations

import hashlib
import re

HEADING = re.compile(
    r"^(?:(?P<md>#{1,3})\s+(?P<title>.+)|(?P<legal>(?:Article|Section|Annex|Appendix)\s+[0-9A-Za-z][^\n]{0,120}))\s*$",
    re.M,
)
TAG_LINE = re.compile(
    r"<!--\s*tags:\s*(?P<body>.*?)\s*-->",
    re.I,
)
TOKEN = re.compile(r"\S+")
MAX_TOKENS = 400
OVERLAP = 50


def _tokens(text: str) -> list[str]:
    return TOKEN.findall(text)


def parse_tags(body: str) -> dict:
    dims, nodes, factor, domain = [], [], None, None
    for part in body.split("|"):
        part = part.strip()
        if part.upper().startswith("D") and re.fullmatch(r"(?:D\d{1,2}\s*)+", part.replace(",", " ")):
            dims = re.findall(r"D\d{1,2}", part)
        elif "nodes:" in part.lower() or part.lower().startswith("nodes"):
            nodes = [n for n in re.split(r"[\s,]+", part.split(":", 1)[-1]) if n]
        elif part.lower().startswith("factor"):
            factor = part.split(":", 1)[-1].strip()
        elif part.lower().startswith("domain"):
            domain = part.split(":", 1)[-1].strip()
        else:
            found = re.findall(r"D\d{1,2}", part)
            if found and not dims:
                dims = found
    return {"readiness_dims": dims, "y3172_nodes": nodes, "readiness_factor": factor, "domain": domain}


def split_sections(text: str, doc_title: str) -> list[dict]:
    matches = list(HEADING.finditer(text))
    if not matches:
        return [{"section_path": doc_title, "text": text.strip(), "tags": {}}]
    sections = []
    stack: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        title = (match.group("title") or match.group("legal") or "").strip()
        level = len(match.group("md")) if match.group("md") else 2
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        tags = {}
        tag_match = TAG_LINE.search(body)
        if tag_match:
            tags = parse_tags(tag_match.group("body"))
            body = TAG_LINE.sub("", body)
        path = " > ".join([doc_title] + [name for _, name in stack])
        cleaned = body.strip()
        if cleaned:
            sections.append({"section_path": path, "text": cleaned, "tags": tags})
    return sections


def pack_section(section: dict) -> list[dict]:
    words = _tokens(section["text"])
    if len(words) <= MAX_TOKENS:
        return [dict(section)]
    packed = []
    start = 0
    while start < len(words):
        end = min(len(words), start + MAX_TOKENS)
        chunk_words = words[start:end]
        packed.append({**section, "text": " ".join(chunk_words)})
        if end == len(words):
            break
        start = max(0, end - OVERLAP)
    return packed


def chunk_document(text: str, doc: dict) -> list[dict]:
    title = doc["title"]
    out = []
    index = 0
    for section in split_sections(text, title):
        for piece in pack_section(section):
            body = re.sub(r"\s+", " ", piece["text"]).strip()
            if len(body) < 40:
                continue
            chunk_id = f"{doc['doc_id']}:{index:03d}"
            index += 1
            out.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc["doc_id"],
                    "text": body,
                    "section_path": piece["section_path"],
                    "page": doc.get("page"),
                    "jurisdiction": doc.get("jurisdiction"),
                    "instrument_type": doc.get("instrument_type"),
                    "domain": piece["tags"].get("domain") or doc.get("domain"),
                    "date": doc.get("date"),
                    "licence": doc.get("licence"),
                    "readiness_factor": piece["tags"].get("readiness_factor") or doc.get("readiness_factor"),
                    "readiness_dims": piece["tags"].get("readiness_dims") or list(doc.get("readiness_dims") or []),
                    "y3172_nodes": piece["tags"].get("y3172_nodes") or list(doc.get("y3172_nodes") or []),
                    "chunk_sha": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "explicit_tags": bool(piece["tags"].get("readiness_dims") or piece["tags"].get("y3172_nodes")),
                }
            )
    return out
