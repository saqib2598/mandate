"""Post-exercise gap analyst. It may only produce the gap register.

Each gap is grounded in a chunk the analyst actually retrieved. The quote is a
substring of that chunk. Recommendations stay at domain level.
"""
from __future__ import annotations

from mandate.policy.citations import exact_quote


def analyse(scenario: dict, retriever, seed: int) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (retrieved, gaps, actions)."""
    retrieved: list[dict] = []
    seen: set[str] = set()
    chosen: dict[int, dict] = {}
    for index, spec in enumerate(scenario.get("gap_register") or []):
        preferred = retriever.search(spec["query"], k=3, role="gap_analyst", doc_id=spec["prefer_doc"])
        broad = retriever.search(spec["query"], k=4, role="gap_analyst")
        pool = preferred or broad
        if not pool:
            continue
        chosen[index] = pool[0]
        for hit in preferred + broad:
            if hit["chunk_id"] not in seen:
                seen.add(hit["chunk_id"])
                retrieved.append(hit)
    gaps = []
    for index, spec in enumerate(scenario.get("gap_register") or []):
        hit = chosen.get(index)
        if not hit:
            continue
        quote = exact_quote(hit["text"])
        gaps.append(
            {
                "node": spec["node"],
                "dimensions": list(spec["dimensions"]),
                "factor": spec.get("factor"),
                "category": spec["category"],
                "gap": spec["gap"],
                "global_example": {"source_chunk_id": hit["chunk_id"], "quote": quote},
                "severity": spec.get("severity", "high"),
            }
        )
    actions = [
        {
            "type": "produce_gap_register",
            "target": "exercise",
            "args": {"gaps": len(gaps), "seed": seed},
        }
    ]
    return retrieved, gaps, actions
