"""Load a scenario and check that each fact token lives in only one inject."""
from __future__ import annotations

from pathlib import Path

import yaml

from mandate.paths import SCENARIOS


def load_scenario(scenario_id: str, directory: Path | None = None) -> dict:
    path = (directory or SCENARIOS) / f"{scenario_id}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_scenario(data)
    return data


def validate_scenario(data: dict) -> None:
    seen: dict[str, str] = {}
    for inject in data["injects"]:
        text = inject["text"].casefold()
        for token in inject.get("fact_tokens") or []:
            if token.casefold() not in text:
                raise ValueError(f"{inject['id']} does not contain its fact token {token!r}")
            if token in seen:
                raise ValueError(f"Fact token {token!r} is in both {seen[token]} and {inject['id']}")
            seen[token] = inject["id"]
        for other in data["injects"]:
            if other["id"] == inject["id"]:
                continue
            other_text = other["text"].casefold()
            for token in inject.get("fact_tokens") or []:
                if token.casefold() in other_text:
                    raise ValueError(f"Fact token {token!r} also appears in {other['id']}")


def phases_of(data: dict) -> list[str]:
    order = []
    for inject in data["injects"]:
        if inject["phase"] not in order:
            order.append(inject["phase"])
    return order
