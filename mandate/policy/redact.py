"""Strip opaque identifiers copied out of an event.

A case number or canary that arrived in untrusted text may be repeated only
in an action aimed at the data-protection authority. This is applied to every
scenario. It does not know the evaluation file.
"""
from __future__ import annotations

import re

# Uppercase tokens that contain a digit and at least one hyphen, e.g. a case id.
_OPAQUE = re.compile(r"\b(?=[A-Z0-9-]*\d)[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){1,}\b")
_DPA_TARGETS = {"dpa"}


def opaque_tokens(source: str) -> set[str]:
    return set(_OPAQUE.findall(source or ""))


def scrub_text(text: str, banned: set[str]) -> str:
    if not text or not banned:
        return text
    for token in banned:
        text = text.replace(token, "")
    return re.sub(r"\s{2,}", " ", text).strip()


def scrub_args(args: dict, banned: set[str], keep: bool) -> dict:
    if keep or not isinstance(args, dict) or not banned:
        return args if isinstance(args, dict) else {}
    cleaned = {}
    for key, value in args.items():
        if isinstance(value, str):
            cleaned[key] = scrub_text(value, banned)
        else:
            cleaned[key] = value
    return {key: value for key, value in cleaned.items() if value != ""}


def may_carry_case_id(target) -> bool:
    return target in _DPA_TARGETS
