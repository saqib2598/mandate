"""Command line for ingest, run, score, audit, and retrieval."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from mandate.audit.render import write_html
from mandate.audit.verify import verify_chain
from mandate.kb.ingest import ingest, load_chunks
from mandate.kb.retrieve import Retriever
from mandate.llm import LLMClient
from mandate.paths import EVAL, KB, MANDATES, ROOT, RUNS, SCENARIOS
from mandate.sim.conductor import Conductor
from mandate.sim.scenario import load_scenario


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(prog="mandate", description="MANDATE institutional sandbox")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="Chunk, tag, and write kb/chunks.jsonl")

    retrieve = sub.add_parser("retrieve", help="Hybrid search over the local chunks")
    retrieve.add_argument("query")
    retrieve.add_argument("--role", default=None)
    retrieve.add_argument("--k", type=int, default=6)
    retrieve.add_argument("--embeddings", default=None, help="hashing, ollama, or off")

    run = sub.add_parser("run", help="Run one scenario")
    run.add_argument("scenario")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--llm", default="stub", choices=["stub", "ollama", "openai"])
    run.add_argument("--model", default=None, help="Model name. Live default in the client is qwen3.8:27b.")
    run.add_argument("--out", type=Path, default=None)

    batch = sub.add_parser("run-all", help="Run every scenario for the given seeds")
    batch.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    batch.add_argument("--llm", default="stub", choices=["stub", "ollama", "openai"])
    batch.add_argument("--model", default=None)
    batch.add_argument("--out-dir", type=Path, default=None, help="Directory for run folders. Live runs default to runs-live/.")

    score = sub.add_parser("score", help="Score runs with the vendored scorer")
    score.add_argument("--runs", type=Path, default=RUNS)
    score.add_argument("--strict", action="store_true")

    audit = sub.add_parser("audit")
    audit.add_argument("action", choices=["verify", "render"])
    audit.add_argument("run_dir", type=Path)
    audit.add_argument("--out", type=Path, default=None)

    sub.add_parser("kb-check", help="40-question hit@5 retrieval check")
    sub.add_parser("report", help="Build report/report.docx from the official template")

    args = parser.parse_args(argv)
    if args.cmd == "ingest":
        chunks = ingest()
        print(f"Wrote {len(chunks)} chunks to {KB / 'chunks.jsonl'}")
        return 0
    if args.cmd == "retrieve":
        if args.embeddings:
            import os
            os.environ["MANDATE_EMBEDDINGS"] = args.embeddings
        hits = Retriever(load_chunks()).search(args.query, k=args.k, role=args.role)
        for hit in hits:
            print(f"{hit['score']:.4f}  {hit['chunk_id']}  {hit.get('section_path')}")
        return 0
    if args.cmd == "run":
        return _run_one(args.scenario, args.seed, args.llm, args.out, args.model)
    if args.cmd == "run-all":
        code = 0
        base = args.out_dir
        if base is None:
            base = (ROOT / "runs-live") if args.llm != "stub" else RUNS
        for path in sorted(SCENARIOS.glob("S*.yaml")):
            for seed in args.seeds:
                out = None if base == RUNS else base / f"{path.stem}-seed{seed}"
                code = _run_one(path.stem, seed, args.llm, out, args.model) or code
        return code or _score(base, strict=False)
    if args.cmd == "score":
        return _score(args.runs, args.strict)
    if args.cmd == "audit" and args.action == "verify":
        result = verify_chain(args.run_dir / "audit.jsonl")
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "audit" and args.action == "render":
        out = args.out or (RUNS / "sample" / f"{args.run_dir.name}.html")
        print(write_html(args.run_dir, out))
        return 0
    if args.cmd == "kb-check":
        return _kb_check()
    if args.cmd == "report":
        from report.build_report import build
        print(build())
        return 0
    return 2


def _run_one(scenario_id: str, seed: int, provider: str, out: Path | None, model: str | None = None) -> int:
    scenario = load_scenario(scenario_id)
    retriever = Retriever(load_chunks())
    conductor = Conductor(_load_mandates(), retriever, LLMClient(provider, model=model))
    if out is None:
        base = (ROOT / "runs-live") if provider != "stub" else RUNS
        out = base / f"{scenario_id}-seed{seed}"
    run_dir = out
    conductor.run(scenario, seed, run_dir)
    print(f"Wrote {run_dir}")
    return 0


def _load_mandates() -> dict:
    roles = {}
    for path in sorted(MANDATES.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        powers = {}
        for power in data.get("powers") or []:
            if isinstance(power, str):
                powers[power] = None
                continue
            name = power.get("name") or power.get("type")
            constraint = {k: power[k] for k in ("targets", "requires") if power.get(k)}
            powers[name] = constraint or None
        roles[data.get("role") or path.stem] = {
            "institution": data.get("institution"),
            "may_message": data.get("may_message", True),
            "powers": powers,
            "directive_over": data.get("directive_over") or {},
            "legal_basis": {},
        }
    return roles


def _score(runs: Path, strict: bool) -> int:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(EVAL))
    from score import main as score_main

    argv = [
        "--runs",
        str(runs),
        "--expectations",
        str(EVAL / "expectations.draft.json"),
        "--chunks",
        str(KB / "chunks.jsonl"),
        "--mandates",
        str(MANDATES),
        "--fuzzy-module",
        "mandate.match:best_window_ratio",
        "--out-json",
        str(runs / "score.json"),
        "--out-md",
        str(runs / "score.md"),
    ]
    if strict:
        argv.append("--strict")
    return score_main(argv)


def _kb_check() -> int:
    questions = yaml.safe_load((KB / "retrieval_questions.yaml").read_text(encoding="utf-8"))
    retriever = Retriever(load_chunks())
    hit = 0
    missed = []
    for item in questions:
        found = retriever.search(item["question"], k=5)
        ok = any(row["doc_id"] == item["expect_doc"] for row in found)
        hit += int(ok)
        if not ok:
            missed.append(item["id"])
    total = len(questions)
    print(f"hit@5 {hit}/{total} = {hit / total:.3f}")
    if missed:
        print("missed: " + ", ".join(missed))
    return 0 if hit == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
