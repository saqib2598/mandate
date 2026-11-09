"""Render an audit log as a single-file HTML timeline."""
from __future__ import annotations

import html
import json
from pathlib import Path


def _esc(value) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)


def render_html(run_dir: Path) -> str:
    meta = {}
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    records = []
    for line in (run_dir / "audit.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    title = f"{meta.get('scenario_id', run_dir.name)} seed {meta.get('seed', '')}"
    parts = [
        "<!DOCTYPE html>",
        "<html lang='en'><head><meta charset='utf-8'>",
        f"<title>MANDATE audit {html.escape(str(title))}</title>",
        "<style>",
        "body{font-family:Georgia,serif;margin:2rem;background:#f7f4ee;color:#1c1915;}",
        "h1{font-weight:500;letter-spacing:.02em;} .meta{color:#5c564c;}",
        "article{background:#fff;border:1px solid #e4ddd0;border-radius:10px;padding:1rem 1.2rem;margin:1rem 0;}",
        ".phase{font-size:.8rem;letter-spacing:.08em;text-transform:uppercase;color:#7a5b2e;}",
        ".role{font-size:1.15rem;margin:.2rem 0 .6rem;}",
        ".allow{color:#1d6b3a;} .block{color:#8d1d1d;} .escalate{color:#8a5a00;}",
        "code{font-family:ui-monospace,monospace;font-size:.82rem;}",
        "blockquote{margin:.4rem 0;padding-left:.8rem;border-left:3px solid #e4ddd0;color:#3d3832;}",
        "</style></head><body>",
        f"<h1>Audit timeline</h1><p class='meta'>{html.escape(str(title))} · {html.escape(run_dir.name)} · {len(records)} records</p>",
    ]
    for i, rec in enumerate(records, 1):
        kind = rec.get("type")
        phase = rec.get("phase") or ""
        if kind == "deliver":
            body = (
                f"<p>Released <code>{html.escape(str(rec.get('inject_id')))}</code> "
                f"to <code>{html.escape(str(rec.get('to_role')))}</code>.</p>"
            )
            role = "conductor"
        else:
            role = str(rec.get("role") or "")
            bits = []
            for action, verdict in _pairs(rec):
                v = (verdict or {}).get("verdict") or ""
                bits.append(
                    f"<li><code>{html.escape(str(action.get('type')))}</code> "
                    f"→ {html.escape(str(action.get('target')))} "
                    f"<span class='{html.escape(v)}'>{html.escape(v)}</span> "
                    f"<span class='meta'>{html.escape(str((verdict or {}).get('reason') or ''))}</span></li>"
                )
            claims = []
            for claim in rec.get("claims_kept") or []:
                quotes = " ".join(
                    f"<code>{html.escape(str(c.get('chunk_id')))}</code>"
                    for c in claim.get("citations") or []
                )
                claims.append(f"<blockquote>{html.escape(claim.get('text') or '')} {quotes}</blockquote>")
            body = "<ul>" + "".join(bits) + "</ul>" + "".join(claims)
        digest = str(rec.get("hash") or "")[:12]
        parts.append(
            "<article>"
            f"<div class='phase'>{html.escape(str(phase))} · record {i} · {digest}</div>"
            f"<div class='role'>{html.escape(role)}</div>"
            f"{body}</article>"
        )
    parts.append("</body></html>")
    return "\n".join(parts)


def _pairs(rec):
    verdicts = {str(v.get("action_id")): v for v in rec.get("guard_verdicts") or [] if isinstance(v, dict)}
    for action in rec.get("actions") or []:
        if isinstance(action, dict):
            yield action, verdicts.get(str(action.get("action_id")))


def write_html(run_dir: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(run_dir), encoding="utf-8")
    return out
