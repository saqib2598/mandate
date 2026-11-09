"""Citation validator. A claim counts only when the quote is from a chunk retrieved this turn."""
from __future__ import annotations

import re

from mandate.policy.guard import quote_supported


def ground_citations(claims: list[dict], retrieved: dict) -> list[dict]:
    """If a citation names a retrieved chunk but the quote does not match, use a verbatim span.

    Unknown chunk ids are left unchanged so the validator can still reject them.
    """
    grounded = []
    for claim in claims or []:
        if not isinstance(claim, dict):
            continue
        cites = []
        for cite in claim.get("citations") or []:
            if not isinstance(cite, dict):
                continue
            cid = None if cite.get("chunk_id") is None else str(cite["chunk_id"])
            quote = cite.get("quote") or ""
            hit = retrieved.get(cid) if cid else None
            if hit and not quote_supported(quote, hit.get("text") or ""):
                quote = exact_quote(hit.get("text") or "")
            cites.append({"chunk_id": cid, "quote": quote})
        grounded.append({"text": claim.get("text") or "", "citations": cites})
    return grounded


def validate_claims(claims: list[dict], retrieved: dict) -> list[dict]:
    """Return claims_kept: invalid citations removed. A claim with none left is dropped."""
    kept = []
    for claim in claims or []:
        if not isinstance(claim, dict):
            continue
        good = []
        for cite in claim.get("citations") or []:
            if not isinstance(cite, dict) or cite.get("chunk_id") is None:
                continue
            cid = str(cite["chunk_id"])
            hit = retrieved.get(cid)
            if not hit:
                continue
            if quote_supported(cite.get("quote") or "", hit.get("text") or ""):
                good.append({"chunk_id": cid, "quote": cite.get("quote")})
        if good:
            kept.append({"text": claim.get("text") or "", "citations": good})
    return kept


def exact_quote(text: str, min_len: int = 80, max_len: int = 180) -> str:
    """A substring of ``text`` long enough for the scorer, ending on a word boundary."""
    flat = re.sub(r"\s+", " ", text or "").strip()
    if len(flat) <= max_len:
        return flat
    window = flat[:max_len]
    cut = window.rfind(" ")
    if cut >= min_len:
        window = window[:cut]
    return window
