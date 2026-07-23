"""
Compare the full pipeline output (parse → verify → retry → prioritize)
against golden reference labels.

Uses subset matching: pipeline's predictions should be a subset of the golden's
(golden is the more capable model, so pipeline's correct predictions should
appear in the golden's output). This separates precision from recall.

Processes samples concurrently via asyncio.Semaphore for speed.
"""

import asyncio
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from rakshak_edge.config import settings
from rakshak_edge.graph import graph
from rakshak_edge.state import TriageState
from rakshak_edge.utils.logger import setup_logger

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

setup_logger()
logger = logging.getLogger(__name__)

_CONCURRENCY = 4


def load_golden(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


async def triage_message(message: str) -> dict:
    initial: TriageState = {"message": message, "retry_count": 0}
    try:
        result = await graph.ainvoke(initial)
        out = result["output"]
        return {
            "intent": out.intent,
            "hazards": set(h.name for h in out.hazards),
            "resources": set(r.name for r in out.resources),
            "hazard_details": {h.name: h.severity.value for h in out.hazards},
            "resource_details": {r.name: r.severity.value for r in out.resources},
            "priority": out.priority_level.name,
            "retry_count": result.get("retry_count", 0),
        }
    except Exception as e:
        logger.warning("Pipeline failed for message: %s — %s", message[:60], e)
        return {
            "intent": "ERROR",
            "hazards": set(),
            "resources": set(),
            "hazard_details": {},
            "resource_details": {},
            "priority": "LOW",
            "retry_count": 3,
        }


async def _compare_one(sample: dict, sem: asyncio.Semaphore, idx: int, total: int) -> dict:
    """Run pipeline on one sample, return comparison result dict."""
    text = sample["input_text"]
    ref = sample["reference"]

    async with sem:
        pipe = await triage_message(text)

    ref_h = {h["type"] for h in ref.get("hazards", [])}
    ref_r = {r["type"] for r in ref.get("resources", [])}

    result = {
        "idx": idx,
        "text": text,
        "pipe": pipe,
        "ref": ref,
        "ref_h": ref_h,
        "ref_r": ref_r,
    }
    return result


async def compare(golden_path: Path):
    golden = load_golden(golden_path)
    samples = golden["samples"]

    pipeline_model = settings["llm"]["model_name"]
    logger.info("Comparing %s samples from %s", len(samples), golden_path.name)
    logger.info(
        "Pipeline model: %s | Golden model: %s (concurrency=%s)",
        pipeline_model, golden["model"], _CONCURRENCY,
    )

    sem = asyncio.Semaphore(_CONCURRENCY)
    tasks = [_compare_one(s, sem, i, len(samples)) for i, s in enumerate(samples, 1)]
    results = await asyncio.gather(*tasks)

    # --- Aggregate ---
    e_intent = e_hazard = e_resource = 0
    s_intent = s_hazard = s_resource = 0

    intent_diffs = []
    hazard_diffs = []
    resource_diffs = []
    retry_counts = []

    hazard_tp: Counter[str] = Counter()
    hazard_fp: Counter[str] = Counter()
    hazard_fn: Counter[str] = Counter()
    resource_tp: Counter[str] = Counter()
    resource_fp: Counter[str] = Counter()
    resource_fn: Counter[str] = Counter()

    for r in sorted(results, key=lambda x: x["idx"]):
        pipe = r["pipe"]
        text = r["text"]
        ref_h = r["ref_h"]
        ref_r = r["ref_r"]
        idx = r["idx"]

        retry_counts.append(pipe["retry_count"])

        if pipe["intent"] == "ERROR":
            logger.warning("  Skipping message %d — pipeline error: %s", idx, text[:60])
            print(f"[{idx}/{len(samples)}] ERR r={pipe['retry_count']} | {text[:60]}")
            continue

        # Intent
        i_exact = pipe["intent"] == r["ref"]["intent"]
        if i_exact:
            e_intent += 1
            s_intent += 1
        else:
            intent_diffs.append({
                "text": text[:80],
                "pipeline": pipe["intent"],
                "ref": r["ref"]["intent"],
                "retries": pipe["retry_count"],
            })

        # Hazards
        h_exact = pipe["hazards"] == ref_h
        h_subset = pipe["hazards"] <= ref_h
        if h_exact:
            e_hazard += 1
        if h_subset:
            s_hazard += 1
        if not h_subset:
            hazard_diffs.append({
                "text": text[:80],
                "pipeline": sorted(pipe["hazards"]),
                "ref": sorted(ref_h),
                "subset": h_subset,
                "retries": pipe["retry_count"],
            })

        for h in pipe["hazards"]:
            if h in ref_h:
                hazard_tp[h] += 1
            else:
                hazard_fp[h] += 1
        for h in ref_h:
            if h not in pipe["hazards"]:
                hazard_fn[h] += 1

        # Resources
        r_exact = pipe["resources"] == ref_r
        r_subset = pipe["resources"] <= ref_r
        if r_exact:
            e_resource += 1
        if r_subset:
            s_resource += 1
        if not r_subset:
            resource_diffs.append({
                "text": text[:80],
                "pipeline": sorted(pipe["resources"]),
                "ref": sorted(ref_r),
                "subset": r_subset,
                "retries": pipe["retry_count"],
            })

        for r_cat in pipe["resources"]:
            if r_cat in ref_r:
                resource_tp[r_cat] += 1
            else:
                resource_fp[r_cat] += 1
        for r_cat in ref_r:
            if r_cat not in pipe["resources"]:
                resource_fn[r_cat] += 1

        status = f"{'✓' if i_exact else '✗'}i "
        status += f"{'✓' if h_exact else ('~' if h_subset else '✗')}h "
        status += f"{'✓' if r_exact else ('~' if r_subset else '✗')}r"
        print(f"[{idx}/{len(samples)}] {status} r={pipe['retry_count']} | {text[:60]}")

    total = len(samples)
    avg_retries = sum(retry_counts) / len(retry_counts) if retry_counts else 0
    msgs_with_retries = sum(1 for r in retry_counts if r > 0)
    msgs_exhausted = sum(1 for r in retry_counts if r >= 3)

    print()
    print(f"=== RESULTS ({total} messages) ===")
    print("              Exact    Subset")
    print(
        f"Intent:      {e_intent:>2}/{total} ({100 * e_intent // total:>2}%)    {s_intent:>2}/{total} ({100 * s_intent // total:>2}%)"
    )
    print(
        f"Hazards:     {e_hazard:>2}/{total} ({100 * e_hazard // total:>2}%)    {s_hazard:>2}/{total} ({100 * s_hazard // total:>2}%)"
    )
    print(
        f"Resources:   {e_resource:>2}/{total} ({100 * e_resource // total:>2}%)    {s_resource:>2}/{total} ({100 * s_resource // total:>2}%)"
    )
    print(
        f"Avg retries: {avg_retries:.1f} | With retries: {msgs_with_retries} | Exhausted: {msgs_exhausted}"
    )

    # Per-category precision/recall
    if hazard_tp or hazard_fp or hazard_fn:
        print("\n--- Hazard per-category ---")
        all_h_types = sorted(set(list(hazard_tp) + list(hazard_fp) + list(hazard_fn)))
        print(f"  {'Type':25s} {'TP':>3} {'FP':>3} {'FN':>3} {'Prec':>5} {'Rec':>5}")
        for ht in all_h_types:
            tp = hazard_tp.get(ht, 0)
            fp = hazard_fp.get(ht, 0)
            fn = hazard_fn.get(ht, 0)
            prec = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
            rec = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
            print(f"  {ht:25s} {tp:>3} {fp:>3} {fn:>3} {prec:>4.0f}% {rec:>4.0f}%")

    if resource_tp or resource_fp or resource_fn:
        print("\n--- Resource per-category ---")
        all_r_types = sorted(set(list(resource_tp) + list(resource_fp) + list(resource_fn)))
        print(f"  {'Type':25s} {'TP':>3} {'FP':>3} {'FN':>3} {'Prec':>5} {'Rec':>5}")
        for rt in all_r_types:
            tp = resource_tp.get(rt, 0)
            fp = resource_fp.get(rt, 0)
            fn = resource_fn.get(rt, 0)
            prec = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
            rec = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
            print(f"  {rt:25s} {tp:>3} {fp:>3} {fn:>3} {prec:>4.0f}% {rec:>4.0f}%")

    if intent_diffs:
        print(f"\n--- Intent disagreements ({len(intent_diffs)}) ---")
        for d in intent_diffs:
            print(f"  pipeline={d['pipeline']} ref={d['ref']} (r={d['retries']}) | {d['text']}")

    if hazard_diffs:
        print(f"\n--- Hazard disagreements ({len(hazard_diffs)}) ---")
        for d in hazard_diffs:
            subset_label = "subset✓" if d["subset"] else "subset✗"
            print(f"  [{subset_label}] pipeline={d['pipeline']} ref={d['ref']} (r={d['retries']}) | {d['text']}")

    if resource_diffs:
        print(f"\n--- Resource disagreements ({len(resource_diffs)}) ---")
        for d in resource_diffs[:8]:
            subset_label = "subset✓" if d["subset"] else "subset✗"
            print(f"  [{subset_label}] pipeline={d['pipeline']} ref={d['ref']} (r={d['retries']}) | {d['text']}")
        if len(resource_diffs) > 8:
            print(f"  ... and {len(resource_diffs) - 8} more")

    def pct(num: int) -> float:
        return round(100 * num / total, 1)

    report = {
        "pipeline_model": settings["llm"]["model_name"],
        "golden_model": golden.get("model", "unknown"),
        "total": total,
        "exact_match": {
            "intent": e_intent, "intent_pct": pct(e_intent),
            "hazard": e_hazard, "hazard_pct": pct(e_hazard),
            "resource": e_resource, "resource_pct": pct(e_resource),
        },
        "subset_match": {
            "intent": s_intent, "intent_pct": pct(s_intent),
            "hazard": s_hazard, "hazard_pct": pct(s_hazard),
            "resource": s_resource, "resource_pct": pct(s_resource),
        },
        "hazard_category": {
            k: {
                "tp": hazard_tp.get(k, 0),
                "fp": hazard_fp.get(k, 0),
                "fn": hazard_fn.get(k, 0),
                "precision": round(hazard_tp.get(k, 0) / (hazard_tp.get(k, 0) + hazard_fp.get(k, 0)) * 100, 1)
                if (hazard_tp.get(k, 0) + hazard_fp.get(k, 0)) > 0 else 0,
                "recall": round(hazard_tp.get(k, 0) / (hazard_tp.get(k, 0) + hazard_fn.get(k, 0)) * 100, 1)
                if (hazard_tp.get(k, 0) + hazard_fn.get(k, 0)) > 0 else 0,
            }
            for k in sorted(set(list(hazard_tp) + list(hazard_fp) + list(hazard_fn)))
        },
        "resource_category": {
            k: {
                "tp": resource_tp.get(k, 0),
                "fp": resource_fp.get(k, 0),
                "fn": resource_fn.get(k, 0),
                "precision": round(resource_tp.get(k, 0) / (resource_tp.get(k, 0) + resource_fp.get(k, 0)) * 100, 1)
                if (resource_tp.get(k, 0) + resource_fp.get(k, 0)) > 0 else 0,
                "recall": round(resource_tp.get(k, 0) / (resource_tp.get(k, 0) + resource_fn.get(k, 0)) * 100, 1)
                if (resource_tp.get(k, 0) + resource_fn.get(k, 0)) > 0 else 0,
            }
            for k in sorted(set(list(resource_tp) + list(resource_fp) + list(resource_fn)))
        },
        "avg_retries": round(avg_retries, 2),
        "messages_with_retries": msgs_with_retries,
        "retries_exhausted": msgs_exhausted,
        "intent_disagreements": intent_diffs,
        "hazard_disagreements": hazard_diffs,
        "resource_disagreements": resource_diffs,
    }

    output_path = golden_path.with_suffix(".comparison.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report: {output_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/golden/golden_validation_50.json"
    asyncio.run(compare(Path(path)))
