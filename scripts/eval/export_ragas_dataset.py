#!/usr/bin/env python
"""
Export case RAGAS dari pipeline rekomendasi (Gemini-only, golden queries pill).

  python scripts/eval/export_ragas_dataset.py --dry-run
  python scripts/eval/export_ragas_dataset.py --limit 18
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden_queries.json"
DEFAULT_OUT = ROOT / "data" / "eval" / "ragas_cases.jsonl"

MAX_CONTEXT_CHUNKS = 12
MAX_CHUNK_CHARS = 400


def _configure_gemini_only_env() -> None:
    """Matikan HF agar probe pipeline memakai Gemini."""
    os.environ["HF_API_TOKEN"] = ""
    os.environ["HF_TOKEN"] = ""
    os.environ.setdefault("COFIND_LLM_RERANK", "true")
    os.environ.setdefault("COFIND_LLM_GROUNDING_CHECK", "true")
    os.environ.setdefault("COFIND_MODAL_QUOTE_LLM", "false")
    os.environ.setdefault("COFIND_LLM_KEYWORD_EXPANSION", "false")


def _load_golden_queries(
    *,
    limit: Optional[int],
    ids: Optional[List[str]],
    pill_only: bool,
) -> List[Dict[str, Any]]:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    queries = data.get("queries") or []
    if pill_only:
        queries = [q for q in queries if q.get("route") == "pill"]
    if ids:
        id_set = set(ids)
        queries = [q for q in queries if q.get("id") in id_set]
    if limit is not None:
        queries = queries[: max(0, limit)]
    return queries


def _quote_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("quote") or item.get("text") or "").strip()
    return str(item or "").strip()


def _collect_contexts(evidence: Dict[str, Any]) -> List[str]:
    seen: Set[str] = set()
    chunks: List[str] = []
    keys = (
        "modal_display_quotes",
        "review_quotes",
        "positive_review_quotes",
    )
    for key in keys:
        for item in evidence.get(key) or []:
            text = _quote_text(item)
            if not text or text in seen:
                continue
            seen.add(text)
            chunks.append(text[:MAX_CHUNK_CHARS])
            if len(chunks) >= MAX_CONTEXT_CHUNKS:
                return chunks
    return chunks


def _build_response(rec: Dict[str, Any]) -> str:
    parts: List[str] = []
    name = rec.get("name") or ""
    if name:
        parts.append(f"Rekomendasi: {name}.")
    fit = rec.get("llm_fit") if isinstance(rec.get("llm_fit"), dict) else {}
    reason = (fit.get("reason") or fit.get("summary") or "").strip()
    if reason:
        parts.append(reason)
    explanation = (rec.get("explanation") or "").strip()
    if explanation:
        parts.append(explanation)
    evidence = rec.get("supporting_evidence") or {}
    for item in (evidence.get("modal_display_quotes") or [])[:3]:
        q = _quote_text(item)
        if q:
            parts.append(f'Bukti: "{q}"')
    return " ".join(parts).strip()


def _user_input_from_query(query: Dict[str, Any]) -> str:
    inp = query.get("input") or {}
    pills = inp.get("pills") or []
    if pills:
        return "Preferensi aktivitas/fasilitas: " + ", ".join(str(p) for p in pills)
    text = (inp.get("query_text") or "").strip()
    return text or str(query.get("id") or "")


def _ground_truth_from_query(query: Dict[str, Any]) -> str:
    expect = query.get("expect") or {}
    notes = (expect.get("notes") or "").strip()
    if notes:
        return notes
    pills = (query.get("input") or {}).get("pills") or []
    return f"Rekomendasi relevan untuk pill: {', '.join(pills)}."


def _run_pipeline(pills: List[str], auth_user: Dict[str, Any]) -> Dict[str, Any]:
    import app

    with app.app.test_request_context():
        for kind, payload in app._recommendation_pipeline_events(pills, auth_user):
            if kind == "result":
                body, status = payload
                return {"status": status, "body": body}
    return {"status": 500, "body": {"recommendations": []}}


def export_case(query: Dict[str, Any], auth_user: Dict[str, Any]) -> Dict[str, Any]:
    inp = query.get("input") or {}
    pills = list(inp.get("pills") or [])
    result = _run_pipeline(pills, auth_user)
    body = result.get("body") or {}
    recs = body.get("recommendations") or []
    row: Dict[str, Any] = {
        "id": query.get("id"),
        "user_input": _user_input_from_query(query),
        "ground_truth": _ground_truth_from_query(query),
        "export_status": result.get("status"),
        "pipeline_message": body.get("message"),
    }
    if not recs:
        row["export_error"] = "no_recommendations"
        row["contexts"] = []
        row["response"] = ""
        return row

    top = recs[0]
    evidence = top.get("supporting_evidence") or {}
    row["contexts"] = _collect_contexts(evidence)
    row["response"] = _build_response(top)
    row["place_id"] = top.get("place_id")
    row["ranking_source"] = top.get("ranking_source")
    llm_pipe = body.get("llm_pipeline") or {}
    deg = llm_pipe.get("degradation") or {}
    row["llm_route"] = deg.get("llm_route") or deg.get("route")
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated golden ids")
    parser.add_argument("--dry-run", action="store_true", help="Hanya 1 query pertama")
    parser.add_argument("--include-free-text", action="store_true")
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    _configure_gemini_only_env()

    id_list = [x.strip() for x in args.ids.split(",")] if args.ids else None
    limit = 1 if args.dry_run else args.limit
    queries = _load_golden_queries(
        limit=limit,
        ids=id_list,
        pill_only=not args.include_free_text,
    )
    if not queries:
        print("Tidak ada golden query.", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    auth_user = {"id": 1}
    written = 0
    with args.out.open("w", encoding="utf-8") as fh:
        for query in queries:
            print(f"Export {query.get('id')} ...", flush=True)
            try:
                row = export_case(query, auth_user)
            except Exception as err:
                row = {
                    "id": query.get("id"),
                    "export_error": str(err)[:500],
                    "user_input": _user_input_from_query(query),
                    "contexts": [],
                    "response": "",
                    "ground_truth": _ground_truth_from_query(query),
                }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1

    print(f"Tulis {written} baris → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
