"""
A/B Incremental Value Benchmark: Baseline Normal vs Baseline + Price Partitioning
Compares coverage, core yield, accessory enrichment, duplicate rate, and observation intelligence.
Saves structured benchmark run data to data/benchmarks/price_partition_ab_results.json.
"""
import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Set, List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db
import backend.breadth_crawler as breadth_crawler
import backend.taxonomy_registry as taxonomy_registry
import backend.relevance_engine as relevance_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark.ab")


def run_ab_benchmark(niche: str = "luggage", max_pages_per_query: int = 1, max_queries: int = 3) -> Dict[str, Any]:
    db.init_db()
    benchmark_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting A/B Incremental Benchmark for niche='{niche}' (id={benchmark_id})")

    # -------------------------------------------------------------
    # Arm A: Baseline (Normal Pagination only)
    # -------------------------------------------------------------
    logger.info("\n=======================================================")
    logger.info(">>> RUNNING ARM A: BASELINE (NORMAL PAGINATION ONLY) <<<")
    logger.info("=======================================================")
    arm_a_niche = f"{niche}_ab_baseline_{benchmark_id}"
    t0_a = time.time()
    res_a = breadth_crawler.run_breadth_discovery_saturation_loop(
        seed_keyword=niche,
        target_niche=arm_a_niche,
        max_queries=max_queries,
        max_pages_per_query=max_pages_per_query,
        enable_price_partition=False
    )
    t_a = round(time.time() - t0_a, 2)

    # Inspect Arm A products and observations
    prods_a = db.get_products(niche=arm_a_niche, limit=5000, relevance_filter="ALL")
    asins_a: Set[str] = {p["asin"] for p in prods_a}
    core_a: Set[str] = {p["asin"] for p in prods_a if p.get("relevance_class") == "CORE"}
    acc_a: Set[str] = {p["asin"] for p in prods_a if p.get("relevance_class") == "ACCESSORY"}
    adj_a: Set[str] = {p["asin"] for p in prods_a if p.get("relevance_class") == "ADJACENT"}

    ledger_a = db.get_coverage_ledger(arm_a_niche, limit=1000)
    pages_a = len(ledger_a)

    logger.info(f"[Arm A Completed] ASINs: {len(asins_a)} | CORE: {len(core_a)} | ACC: {len(acc_a)} | Pages: {pages_a} | Time: {t_a}s")

    # -------------------------------------------------------------
    # Arm B: Baseline + Price Partitioning
    # -------------------------------------------------------------
    logger.info("\n=======================================================")
    logger.info(">>> RUNNING ARM B: BASELINE + PRICE PARTITIONING    <<<")
    logger.info("=======================================================")
    arm_b_niche = f"{niche}_ab_partition_{benchmark_id}"
    t0_b = time.time()
    res_b = breadth_crawler.run_breadth_discovery_saturation_loop(
        seed_keyword=niche,
        target_niche=arm_b_niche,
        max_queries=max_queries + 4,
        max_pages_per_query=max_pages_per_query,
        enable_price_partition=True
    )
    t_b = round(time.time() - t0_b, 2)

    # Inspect Arm B products and observations
    prods_b = db.get_products(niche=arm_b_niche, limit=5000, relevance_filter="ALL")
    asins_b: Set[str] = {p["asin"] for p in prods_b}
    core_b: Set[str] = {p["asin"] for p in prods_b if p.get("relevance_class") == "CORE"}
    acc_b: Set[str] = {p["asin"] for p in prods_b if p.get("relevance_class") == "ACCESSORY"}
    adj_b: Set[str] = {p["asin"] for p in prods_b if p.get("relevance_class") == "ADJACENT"}

    ledger_b = db.get_coverage_ledger(arm_b_niche, limit=1000)
    pages_b = len(ledger_b)

    # Differential Metrics
    new_asins = asins_b - asins_a
    new_core = core_b - core_a
    new_acc = acc_b - acc_a
    new_adj = adj_b - adj_a

    # Search Observations comparison
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM search_observations WHERE niche=?", (arm_a_niche,))
    obs_count_a = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), partition_id FROM search_observations WHERE niche=? GROUP BY partition_id", (arm_b_niche,))
    slice_breakdown_rows = cur.fetchall()
    obs_count_b = sum(r[0] for r in slice_breakdown_rows)
    slice_observations = {r[1]: r[0] for r in slice_breakdown_rows}

    # Transports used in Arm B
    cur.execute("SELECT transport_used, COUNT(*) FROM search_observations WHERE niche=? GROUP BY transport_used", (arm_b_niche,))
    transport_rows = cur.fetchall()
    transport_counts = {r[0]: r[1] for r in transport_rows}

    conn.close()

    # Sub-clusters in Arm B
    sub_clusters_b = db.get_sub_niche_cluster_aggregates(arm_b_niche)
    sub_niches_b = [c["sub_cluster"] for c in sub_clusters_b]

    # Duplicate rate across slices in Arm B
    duplicate_rate_b = round(((obs_count_b - len(asins_b)) / max(1, obs_count_b) * 100), 2)

    report = {
        "benchmark_id": benchmark_id,
        "niche": niche,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "arm_a_baseline": {
            "total_asins": len(asins_a),
            "core_asins": len(core_a),
            "accessory_asins": len(acc_a),
            "adjacent_asins": len(adj_a),
            "search_observations": obs_count_a,
            "pages_requested": pages_a,
            "runtime_seconds": t_a
        },
        "arm_b_partitioned": {
            "total_asins": len(asins_b),
            "core_asins": len(core_b),
            "accessory_asins": len(acc_b),
            "adjacent_asins": len(adj_b),
            "search_observations": obs_count_b,
            "pages_requested": pages_b,
            "runtime_seconds": t_b,
            "duplicate_rate_pct": duplicate_rate_b,
            "slice_observations": slice_observations,
            "transports": transport_counts,
            "sub_niche_clusters": sub_niches_b
        },
        "incremental_delta": {
            "net_unique_asins_gained": len(new_asins),
            "net_core_asins_gained": len(new_core),
            "net_accessory_asins_gained": len(new_acc),
            "net_adjacent_asins_gained": len(new_adj),
            "net_observations_gained": obs_count_b - obs_count_a,
            "core_lift_pct": round((len(core_b) - len(core_a)) / max(1, len(core_a)) * 100, 2),
            "total_lift_pct": round((len(asins_b) - len(asins_a)) / max(1, len(asins_a)) * 100, 2)
        }
    }

    # Print ASCII Report
    print("\n" + "=" * 90)
    print("       A/B INCREMENTAL BENCHMARK: BASELINE vs BASELINE + PRICE PARTITION")
    print("=" * 90)
    print(f"{'Metric':<35} | {'Arm A (Baseline)':<20} | {'Arm B (With Partitions)':<22} | {'Lift / Delta':<10}")
    print("-" * 90)
    print(f"{'Total Unique ASINs':<35} | {len(asins_a):<20} | {len(asins_b):<22} | +{len(new_asins)} ({report['incremental_delta']['total_lift_pct']}%)")
    print(f"{'  - CORE Suitcases':<35} | {len(core_a):<20} | {len(core_b):<22} | +{len(new_core)} ({report['incremental_delta']['core_lift_pct']}%)")
    print(f"{'  - ACCESSORIES (Locks, Tags)':<35} | {len(acc_a):<20} | {len(acc_b):<22} | +{len(new_acc)}")
    print(f"{'  - ADJACENT (Duffels, Packs)':<35} | {len(adj_a):<20} | {len(adj_b):<22} | +{len(new_adj)}")
    print(f"{'Search Observations Stored':<35} | {obs_count_a:<20} | {obs_count_b:<22} | +{obs_count_b - obs_count_a}")
    print(f"{'Duplicate Observation Rate':<35} | {'N/A':<20} | {duplicate_rate_b}%{'':<18} | Cross-slice freq")
    print(f"{'Pages Requested':<35} | {pages_a:<20} | {pages_b:<22} | +{pages_b - pages_a}")
    print(f"{'Runtime (Seconds)':<35} | {t_a}s{'':<17} | {t_b}s{'':<19} | +{round(t_b - t_a, 2)}s")
    print("=" * 90)

    # Save to disk
    out_file = BASE_DIR / "data" / "benchmarks" / "price_partition_ab_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved benchmark results to {out_file}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", type=str, default="luggage")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--queries", type=int, default=2)
    args = parser.parse_args()
    run_ab_benchmark(niche=args.niche, max_pages_per_query=args.pages, max_queries=args.queries)
