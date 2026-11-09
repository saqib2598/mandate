"""Quote-matching method shared by the MANDATE Citation Validator and the scorer.

TODO(coding-agent): when the shared module is published, point the scorer at it instead of this
file. Set `config.fuzzy_module` in the expectation file, the `--fuzzy-module` CLI flag, or the
MANDATE_FUZZY_MODULE environment variable to "package.module:function". The function must have
the signature `f(quote: str, text: str) -> float`, returning the best window ratio in [0, 1].
The threshold (0.9) and minimum quote length (20) are applied by the scorer, not by `f`.

Interim implementation of the confirmed method:
  1. normalise both strings: casefold, collapse all whitespace runs to one space, strip;
  2. if the normalised quote is a substring of the normalised text, the ratio is 1.0;
  3. otherwise slide a window the length of the quote over the text, anchored at every
     difflib matching block, and return the best SequenceMatcher(None, window, quote).ratio().
"""
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
        sm = SequenceMatcher(None, t[st:st + len(q)], q, autojunk=False)
        if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:  # upper bounds: skip, result unchanged
            continue
        r = sm.ratio()
        if r > best:
            best = r
            if best == 1.0:
                break
    return best
