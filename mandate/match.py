"""Quote matching shared by the Mandate Guard, the citation validator, and the scorer.

The scorer calls ``best_window_ratio(quote, text) -> float`` and applies the
threshold (0.9) and the minimum quote length (20) itself.

Method:
  1. Casefold both strings and collapse whitespace.
  2. An exact substring scores 1.0.
  3. Otherwise take the best ``difflib.SequenceMatcher`` ratio over windows the
     length of the quote, anchored at each matching block. Quick-ratio upper
     bounds prune windows without changing the result.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

THRESHOLD = 0.9
MIN_QUOTE_CHARS = 20


def normalise(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).casefold().strip()


def best_window_ratio(quote: str, text: str) -> float:
    q, t = normalise(quote), normalise(text)
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    if len(q) >= len(t):
        return SequenceMatcher(None, t, q, autojunk=False).ratio()
    best, tried = 0.0, set()
    for b in SequenceMatcher(None, t, q, autojunk=False).get_matching_blocks():
        if not b.size:
            continue
        st = max(0, min(len(t) - len(q), b.a - b.b))
        if st in tried:
            continue
        tried.add(st)
        sm = SequenceMatcher(None, t[st : st + len(q)], q, autojunk=False)
        if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:
            continue
        r = sm.ratio()
        if r > best:
            best = r
            if best == 1.0:
                break
    return best
