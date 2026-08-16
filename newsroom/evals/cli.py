"""Developer CLI for the evaluation subsystem.

Usage (via ``python -m newsroom.evals``):

    validate                     validate the corpus (exit non-zero on error)
    list                         list case ids, types, and titles
    summary                      taxonomy distribution + v1 baseline summary
    replay <case-id>             deterministic replay of one fixture
    baseline [--json]            score the v1 export against gold
    score <case-id> --prediction <file> [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .corpus import (
    corpus_dir,
    fixtures_dir,
    load_all_cases,
    load_case,
    validate_corpus,
)
from .schema import ValidationError, canonical_json
from .replay import load_fixture, validate_fixture
from .prediction import validate_prediction, Prediction
from .metrics import score, ScoreResult
from .baseline import load_v1_export, run_baseline
from .taxonomy import CASE_TYPES, CASE_TYPE_LABELS


def _print_json(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, sort_keys=True))
    sys.stdout.write("\n")


def _cmd_validate() -> int:
    errors, valid = validate_corpus()
    if errors:
        print(f"corpus INVALID: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"corpus VALID: {len(valid)} case(s)")
    return 0


def _cmd_list() -> int:
    _, valid = validate_corpus()
    for cid in sorted(valid):
        c = valid[cid]
        print(f"{c.case_id}\t{c.case_type}\t{c.title}")
    print(f"\n{len(valid)} case(s)")
    return 0


def _cmd_summary() -> int:
    errors, valid = validate_corpus()
    counts: dict[str, int] = {t: 0 for t in sorted(CASE_TYPES)}
    for c in valid.values():
        counts[c.case_type] = counts.get(c.case_type, 0) + 1
    print(f"corpus: {len(valid)} case(s), {len(errors)} error(s)")
    print("\ntaxonomy distribution:")
    for t in sorted(counts):
        label = CASE_TYPE_LABELS.get(t, t)
        print(f"  {counts[t]:>3}  {t:<28} {label}")
    return 0


def _cmd_replay(case_id: str) -> int:
    path = fixtures_dir() / f"{case_id}.json"
    if not path.is_file():
        print(f"fixture not found: {path}", file=sys.stderr)
        return 1
    try:
        first = load_fixture(str(path))
        second = load_fixture(str(path))
    except ValidationError as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 1

    if first.replay_hash != second.replay_hash:
        print("replay NOT deterministic: replay_hash differs across runs", file=sys.stderr)
        return 1

    print(f"fixture_id : {first.fixture_id}")
    print(f"case_id    : {first.case_id}")
    print(f"channel    : {first.channel}")
    print(f"captured_at: {first.captured_at}")
    print(f"replay_hash: {first.replay_hash}")
    print(f"documents  : {len(first.documents)}")
    for d in first.documents:
        print(f"  - {d.candidate_id}  {d.normalized_url}")
        print(f"      headline: {d.normalized_headline}")
        print(f"      event_key: {d.event_key}")
        print(f"      content_hash: {d.content_hash}")
    print("\ndeterministic: replay_hash stable across two loads")
    return 0


def _score_case(case_id: str, prediction_file: str, as_json: bool) -> int:
    case = load_case(case_id)
    with open(prediction_file, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    preds = data.get("predictions", [data]) if isinstance(data, dict) else data
    results: list[ScoreResult] = []
    for raw in preds:
        pred = validate_prediction(raw)
        if pred.case_id != case_id:
            continue
        results.append(score(case, pred))

    if not results:
        print(f"no prediction for case {case_id} found in {prediction_file}", file=sys.stderr)
        return 1

    if as_json:
        _print_json({"case_id": case_id, "results": [r.as_dict() for r in results]})
    else:
        for r in results:
            print(f"system {r.system}:")
            print(f"  event.precision={r.event.precision:.3f} recall={r.event.recall:.3f} "
                  f"false_merge={r.event.false_merge_count} false_split={r.event.false_split_count}")
            print(f"  claim.important_recall={r.claim.important_claim_recall:.3f} "
                  f"precision={r.claim.claim_precision:.3f}")
            print(f"  evidence.citation_correctness={r.evidence.citation_correctness:.3f} "
                  f"coverage={r.evidence.evidence_coverage:.3f} "
                  f"contradiction={r.evidence.contradiction_detection:.3f}")
    return 0


def _cmd_baseline(as_json: bool) -> int:
    _, valid = validate_corpus()
    export = load_v1_export()
    results = run_baseline(valid, export)

    if as_json:
        _print_json(
            {
                "system": export.system,
                "source_db": export.source_db,
                "results": [r.as_dict() for r in results],
            }
        )
        return 0

    print(f"v1 baseline ({export.system}) — {len(results)} case(s)")
    print(f"source_db: {export.source_db}")
    print(f"note: {export.note}")
    print()
    if not results:
        print("no scored predictions")
        return 0
    for r in results:
        print(f"{r.case_id}:")
        print(f"  event  precision={r.event.precision:.3f} recall={r.event.recall:.3f} "
              f"false_merge={r.event.false_merge_count} false_split={r.event.false_split_count} "
              f"dup_rate={r.event.duplicate_rate:.3f}")
        print(f"  primary_source recall={r.primary_source.primary_source_recall:.3f} "
              f"precision={r.primary_source.primary_source_precision:.3f} "
              f"false_primary={r.primary_source.false_primary_count} "
              f"({r.primary_source.predicted_count}/{r.primary_source.expected_count} pred/expected)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m newsroom.evals",
        description="Newsroom evaluation harness",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate the corpus")
    sub.add_parser("list", help="list cases")
    sub.add_parser("summary", help="taxonomy distribution")

    p_replay = sub.add_parser("replay", help="replay one fixture")
    p_replay.add_argument("case_id")

    p_base = sub.add_parser("baseline", help="score v1 baseline")
    p_base.add_argument("--json", action="store_true")

    p_score = sub.add_parser("score", help="score a prediction against a case")
    p_score.add_argument("case_id")
    p_score.add_argument("--prediction", required=True)
    p_score.add_argument("--json", action="store_true")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return _cmd_validate()
    if args.command == "list":
        return _cmd_list()
    if args.command == "summary":
        return _cmd_summary()
    if args.command == "replay":
        return _cmd_replay(args.case_id)
    if args.command == "baseline":
        return _cmd_baseline(args.json)
    if args.command == "score":
        return _score_case(args.case_id, args.prediction, args.json)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
