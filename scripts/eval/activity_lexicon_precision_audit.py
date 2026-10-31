#!/usr/bin/env python
"""
Audit presisi proxy per istilah leksikon aktivitas terhadap ulasan DB.

Metode:
  - Untuk setiap term (review_keywords, extra_phrases, whole_words), cari ulasan yang match.
  - TP jika kalimat match lolos penolakan (_sentence_has_rejection_phrase) DAN
    activity_text_score dengan matcher mini term >= 0.6 (frasa) atau whole_word.
  - FP = match - TP.

Usage:
  python scripts/eval/activity_lexicon_precision_audit.py
  python scripts/eval/activity_lexicon_precision_audit.py --min-precision 0.55 --apply-prune
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

MIN_REVIEW_CHARS = 8
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|[\n;]+")


def _sentences(text: str) -> List[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(str(text or "")) if p.strip()]
    return parts or [str(text or "").strip()]


def _term_matches_sentence(term: str, sentence: str) -> bool:
    t = str(term or "").strip().lower()
    s = str(sentence or "").lower()
    if not t or not s:
        return False
    if " " in t:
        return t in s
    tokens = set(re.findall(r"[a-z0-9]+", s, flags=re.IGNORECASE))
    return t in tokens


def _load_reviews() -> List[dict]:
    from db_backend import get_connection

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, place_id, review_text FROM reviews WHERE review_text IS NOT NULL"
    ).fetchall()
    conn.close()
    out = []
    for rid, pid, text in rows:
        body = str(text or "").strip()
        if len(body) >= MIN_REVIEW_CHARS:
            out.append({"id": rid, "place_id": pid, "text": body})
    return out


def _audit_term(
    pill: str,
    term: str,
    term_kind: str,
    reviews: Sequence[dict],
    *,
    rejection_fn,
    mini_score_fn,
) -> dict[str, Any]:
    matches: List[dict] = []
    for row in reviews:
        for sent in _sentences(row["text"]):
            if not _term_matches_sentence(term, sent):
                continue
            matches.append({"review_id": row["id"], "sentence": sent[:300]})
            break

    if not matches:
        return {
            "pill": pill,
            "term": term,
            "kind": term_kind,
            "match_count": 0,
            "tp": 0,
            "fp": 0,
            "precision": None,
            "samples_fp": [],
        }

    tp = 0
    fp_samples: List[str] = []
    for m in matches:
        sent = m["sentence"]
        if rejection_fn(sent):
            fp_samples.append(sent[:200])
            continue
        if mini_score_fn(pill, term, term_kind, sent) >= 0.55:
            tp += 1
        else:
            fp_samples.append(sent[:200])

    fp = len(matches) - tp
    prec = tp / len(matches) if matches else None
    return {
        "pill": pill,
        "term": term,
        "kind": term_kind,
        "match_count": len(matches),
        "tp": tp,
        "fp": fp,
        "precision": round(prec, 4) if prec is not None else None,
        "samples_fp": fp_samples[:3],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lexicon", type=Path, default=ROOT / "data" / "lexicon" / "activity_lexicon.json")
    parser.add_argument("--min-precision", type=float, default=0.5)
    parser.add_argument("--min-matches", type=int, default=3, help="Min match sebelum term bisa di-prune")
    parser.add_argument("--apply-prune", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "eval" / "activity_lexicon_precision_audit.json")
    args = parser.parse_args()

    from activity_lexicon import reload_activity_lexicon_cache
    from hybrid_retrieval import (
        _sentence_has_rejection_phrase,
        activity_text_score,
        compile_activity_matcher,
    )
    from pill_config import PILL_LABELS, PILL_MAPPING

    lex = json.loads(args.lexicon.read_text(encoding="utf-8"))
    reviews = _load_reviews()
    if not reviews:
        print("Tidak ada ulasan.", file=sys.stderr)
        return 1

    def mini_score(pill: str, term: str, kind: str, sentence: str) -> float:
        matcher = compile_activity_matcher(
            [pill], pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        if kind == "whole_words":
            mini = {
                "pills": [pill],
                "phrases": [term.lower()] if " " in term else [],
                "words": frozenset({term.lower()}),
                "acronyms": matcher.get("acronyms") or frozenset(),
                "stop_tokens": matcher.get("stop_tokens") or frozenset(),
                "bm25_tokens": [],
            }
            return activity_text_score(sentence, mini)
        return activity_text_score(sentence, matcher)

    rows: List[dict] = []
    pills = lex.get("pills") or {}
    for pill, spec in sorted(pills.items()):
        if not isinstance(spec, dict):
            continue
        for kw in spec.get("review_keywords") or []:
            rows.append(_audit_term(pill, str(kw), "review_keywords", reviews,
                                    rejection_fn=_sentence_has_rejection_phrase, mini_score_fn=mini_score))
        for ph in spec.get("extra_phrases") or []:
            rows.append(_audit_term(pill, str(ph), "extra_phrases", reviews,
                                    rejection_fn=_sentence_has_rejection_phrase, mini_score_fn=mini_score))
        for ww in spec.get("whole_words") or []:
            rows.append(_audit_term(pill, str(ww), "whole_words", reviews,
                                    rejection_fn=_sentence_has_rejection_phrase, mini_score_fn=mini_score))

    prune: List[Tuple[str, str, str]] = []
    for r in rows:
        mc = int(r.get("match_count") or 0)
        prec = r.get("precision")
        if mc >= args.min_matches and prec is not None and prec < args.min_precision:
            prune.append((r["pill"], r["kind"], r["term"]))

    if args.apply_prune and prune:
        for pill, kind, term in prune:
            lst = pills.get(pill, {}).get(kind)
            if not isinstance(lst, list):
                continue
            pills[pill][kind] = [x for x in lst if str(x).strip().lower() != str(term).strip().lower()]
        args.lexicon.write_text(json.dumps(lex, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reload_activity_lexicon_cache()
        from activity_lexicon import apply_activity_lexicon_to_mapping
        from pill_config import PILL_MAPPING as PM

        apply_activity_lexicon_to_mapping(PM)

    payload = {
        "review_count": len(reviews),
        "min_precision": args.min_precision,
        "min_matches": args.min_matches,
        "pruned": [{"pill": p, "kind": k, "term": t} for p, k, t in prune],
        "terms": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    low = [r for r in rows if r.get("precision") is not None and r["precision"] < args.min_precision
           and (r.get("match_count") or 0) >= args.min_matches]
    print(f"Ulasan={len(reviews)} term={len(rows)} low_precision={len(low)} pruned={len(prune) if args.apply_prune else 0}")
    print(f"Laporan: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
