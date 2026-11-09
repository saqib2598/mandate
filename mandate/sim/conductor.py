"""Conductor (Y.3172 MLFO). Releases injects, runs each role, then the gap analyst.

The conductor takes no substantive action. It writes deliver records and enforces
turn order. Escalate verdicts are logged and never executed.
"""
from __future__ import annotations

import json
from pathlib import Path

from mandate.agents.gap_analyst import analyse
from mandate.audit.log import AuditLog, prompt_sha
from mandate.llm import LLMClient
from mandate.policy.citations import ground_citations, validate_claims
from mandate.policy.guard import MESSAGE_TYPES, MandateGuard
from mandate.policy.redact import may_carry_case_id, opaque_tokens, scrub_args, scrub_text
from mandate.sim.scenario import phases_of

ROLE_ORDER = [
    "pre_processor",
    "service_operator",
    "policy_adviser",
    "dpa",
    "ict_regulator",
    "ombudsperson",
]
ROLE_FOCUS = {
    "service_operator": "automated decision human review notice manual channel accessibility outage provenance",
    "policy_adviser": "purpose limitation automated decision administrative fairness guidance",
    "dpa": "personal data breach notification supervisory authority purpose limitation",
    "ict_regulator": "outage data residency hosting content provenance technical directive infrastructure",
    "ombudsperson": "appeal explanation recourse accessibility human review",
    "pre_processor": "prompt injection redact personal data",
    "gap_analyst": "policy gap standard global example",
}


class Conductor:
    def __init__(self, mandates: dict, retriever, llm: LLMClient | None = None):
        self.mandates = mandates
        self.retriever = retriever
        self.llm = llm or LLMClient("stub")
        self.guard = MandateGuard(mandates)

    def run(self, scenario: dict, seed: int, run_dir: Path) -> Path:
        run_id = f"{scenario['id']}-seed{seed}"
        audit = AuditLog(run_id)
        delivered: dict[str, list[str]] = {}
        executed: dict[str, set[str]] = {}
        clock = 0

        for phase in phases_of(scenario):
            injects = [item for item in scenario["injects"] if item["phase"] == phase]
            for inject in injects:
                for role in inject["recipients"]:
                    clock += 1
                    audit.append(
                        {
                            "ts": _ts(clock),
                            "phase": phase,
                            "type": "deliver",
                            "inject_id": inject["id"],
                            "to_role": role,
                            "text": inject["text"].strip(),
                        }
                    )
                    delivered.setdefault(role, []).append(inject["id"])
            for role in ROLE_ORDER:
                if role not in {r for inject in injects for r in inject["recipients"]}:
                    continue
                clock = self._turn(
                    audit, scenario, seed, phase, role, delivered.get(role, []), executed, clock
                )

        clock = self._gap_turn(audit, scenario, seed, executed, clock)
        run_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "scenario_id": scenario["id"],
            "seed": seed,
            "provider": self.llm.provider,
            "model": self.llm.model if self.llm.provider != "stub" else "stub-deterministic",
        }
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        audit.write(run_dir)
        write_gaps(run_dir, getattr(audit, "gaps", []))
        return run_dir

    def _turn(self, audit, scenario, seed, phase, role, seen_ids, executed, clock) -> int:
        events = [item for item in scenario["injects"] if item["id"] in seen_ids and item["phase"] == phase]
        query = " ".join(
            [ROLE_FOCUS.get(role, ""), scenario["title"]] + [item["id"] for item in events]
        )
        retrieved = self.retriever.search(query, k=6, role=role)
        spec = self.mandates.get(role) or {}
        context = {
            "scenario_id": scenario["id"],
            "role": role,
            "phase": phase,
            "seed": seed,
            "institution": spec.get("institution"),
            "may_message": spec.get("may_message", True),
            "directive_over": spec.get("directive_over") or {},
            "powers": sorted(spec.get("powers") or []),
            "events": [{"id": item["id"], "text": item["text"].strip()} for item in events],
            "retrieved": retrieved,
        }
        result = self.llm.complete(context)
        return self._commit(audit, scenario, role, phase, seen_ids, retrieved, context, result, executed, clock)

    def _gap_turn(self, audit, scenario, seed, executed, clock) -> int:
        retrieved, gaps, actions = analyse(scenario, self.retriever, seed)
        spec = self.mandates.get("gap_analyst") or {}
        context = {
            "scenario_id": scenario["id"],
            "role": "gap_analyst",
            "phase": "T5",
            "seed": seed,
            "institution": spec.get("institution"),
            "may_message": False,
            "directive_over": {},
            "powers": ["produce_gap_register"],
            "events": [],
            "retrieved": retrieved,
            "gap_actions": actions,
        }
        if self.llm.provider == "stub":
            result = self.llm.complete(context)
        else:
            result = self.llm.complete(context)
            if not result.get("actions"):
                result["actions"] = actions
        run_dir_gaps = gaps
        clock = self._commit(
            audit, scenario, "gap_analyst", "T5", [], retrieved, context, result, executed, clock, gaps=run_dir_gaps
        )
        return clock

    def _commit(self, audit, scenario, role, phase, seen_ids, retrieved, context, result, executed, clock, gaps=None) -> int:
        clock += 1
        event_text = " ".join(item.get("text") or "" for item in context.get("events") or [])
        banned = opaque_tokens(event_text)
        retrieved_map = {hit["chunk_id"]: hit for hit in retrieved}
        claims_raw = ground_citations(_clean_claims(result.get("claims") or []), retrieved_map)
        for claim in claims_raw:
            claim["text"] = scrub_text(claim.get("text") or "", banned)
        claims_kept = validate_claims(claims_raw, retrieved_map)
        actions = []
        verdicts = []
        done = executed.setdefault(role, set())
        for proposed in result.get("actions") or []:
            target = proposed.get("target")
            action = {
                "action_id": f"{audit.run_id}-{clock:04d}-{len(actions):02d}",
                "type": proposed.get("type"),
                "target": target,
                "args": scrub_args(proposed.get("args") or {}, banned, may_carry_case_id(target)),
            }
            verdict = self.guard.check(role, action, done, scenario)
            if verdict.verdict == "allow":
                basis = verdict.legal_basis or ([retrieved[0]["chunk_id"]] if retrieved else [])
                verdict.legal_basis = basis
            verdicts.append(verdict.as_dict())
            actions.append(action)
            if verdict.verdict == "allow":
                record = {
                    "action_id": action["action_id"],
                    "type": action["type"],
                    "role": role,
                    "target": action["target"],
                    "phase": phase,
                    "args": action["args"],
                }
                if action["type"] in MESSAGE_TYPES:
                    audit.bus.append(record)
                else:
                    audit.sink.append(record)
                done.add(action["type"])
        audit.append(
            {
                "ts": _ts(clock),
                "phase": phase,
                "role": role,
                "event_ids_seen": list(seen_ids),
                "retrieved": [
                    {"chunk_id": hit["chunk_id"], "score": f"{hit['score']:.6f}" if isinstance(hit["score"], float) else hit["score"], "text": hit["text"]}
                    for hit in retrieved
                ],
                "prompt_sha": prompt_sha({"role": role, "phase": phase, "events": [e["id"] for e in context.get("events") or []]}),
                "rationale": result.get("rationale") or {},
                "think": result.get("think") or "",
                "actions": actions,
                "guard_verdicts": verdicts,
                "claims_raw": claims_raw,
                "claims_kept": claims_kept,
            }
        )
        if gaps is not None:
            # Stash on the log object for the caller via a side channel on the audit.
            audit.gaps = gaps
        return clock


def write_gaps(run_dir: Path, gaps: list[dict]) -> None:
    (run_dir / "gaps.json").write_text(json.dumps(gaps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _clean_claims(claims: list[dict]) -> list[dict]:
    cleaned = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        cites = []
        for cite in claim.get("citations") or []:
            if isinstance(cite, dict):
                cites.append({"chunk_id": cite.get("chunk_id"), "quote": cite.get("quote")})
        cleaned.append({"text": claim.get("text") or "", "citations": cites})
    return cleaned


def _ts(index: int) -> str:
    return f"2026-11-07T12:{index // 60:02d}:{index % 60:02d}Z"
