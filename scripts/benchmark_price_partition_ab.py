"""
A/B Incremental Value Benchmark: Baseline Normal vs Price Partitioning
Compares exact same query on Normal Search (ALL) vs Price Partitions (PRICE_0_25, PRICE_25_60, etc.)
Calculates true net incremental unique ASIN yield per slice without secondary query contamination.
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
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db
import backend.breadth_crawler as breadth_crawler
import backend.taxonomy_registry as taxonomy_registry
import backend.relevance_engine as relevance_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark.ab")


def run_ab_benchmark(niche: str = "luggage", pages_per_slice: int = 1) -> Dict[str, Any]:
    db.init_db()
    benchmark_id = str(uuid.uuid4())[:8]
    session_id = f"bench_{benchmark_id}"
    bench_niche = f"{niche}_ab_bench_{benchmark_id}"
    logger.info(f"Starting Rigorous Price Partition Benchmark for niche='{niche}' (id={benchmark_id})")

    fetcher = breadth_crawler.StrategyLadderFetcher()
    db.create_research_run(session_id, bench_niche)

    # -------------------------------------------------------------
    # PHASE A: Baseline Normal Search (ALL partition)
    # -------------------------------------------------------------
    logger.info("\n" + "=" * 65)
    logger.info(">>> PHASE A: BASELINE NORMAL SEARCH (partition_id='ALL') <<<")
    logger.info("=" * 65)
    t0_a = time.time()
    asins_baseline: Set[str] = set()
    obs_count_baseline = 0

    for page_num in range(1, pages_per_slice + 1):
        url = f"https://www.amazon.com/s?k={quote(niche)}&page={page_num}" if page_num > 1 else f"https://www.amazon.com/s?k={quote(niche)}"
        logger.info(f"[Baseline:ALL] Fetching page {page_num}/{pages_per_slice} -> {url}")
        html, status, strategy_used = fetcher.fetch_page_html(url, query=niche, niche=bench_niche, run_id=session_id)

        if status not in ("success", "zero_cards") or not html:
            logger.warning(f"[Baseline:ALL] Page {page_num} returned status='{status}'.")
            continue

        products, observations = breadth_crawler.extract_cheap_products_from_html(
            html, query=niche, lane="keyword_search", niche=bench_niche, page=page_num,
            run_id=session_id, partition_type="NORMAL", partition_id="ALL",
            strategy_used=strategy_used
        )

        for p in products:
            db.save_product(p, record_snapshot=False)
            asins_baseline.add(p["asin"])

        for obs in observations:
            db.record_search_observation(obs)
            obs_count_baseline += 1

        db.record_coverage_ledger_entry(
            session_id=session_id,
            niche=bench_niche,
            lane="keyword_search",
            query_or_target=niche,
            page_number=page_num,
            asins_found_total=len(products),
            asins_new_unique=len(products),
            asins_duplicate=0,
            cumulative_unique=len(asins_baseline),
            status=status,
            strategy_used=strategy_used,
            partition_type="NORMAL",
            partition_id="ALL"
        )
        time.sleep(0.5)

    t_a = round(time.time() - t0_a, 2)
    logger.info(f"[Baseline Completed] ASINs: {len(asins_baseline)} | Observations: {obs_count_baseline} | Time: {t_a}s")

    # -------------------------------------------------------------
    # PHASE B: Price Partitions (PRICE_0_25, PRICE_25_60, etc.)
    # -------------------------------------------------------------
    logger.info("\n" + "=" * 65)
    logger.info(">>> PHASE B: PRICE PARTITIONS (PRICE SLICES)          <<<")
    logger.info("=" * 65)
    t0_b = time.time()

    # Get semantic buckets
    observed_sample_prices = db.get_observed_prices_for_niche(bench_niche)
    buckets = taxonomy_registry.get_semantic_price_buckets(bench_niche, query=niche, observed_prices=observed_sample_prices)

    slice_incremental_yield: Dict[str, Any] = {}
    slice_observations: Dict[str, int] = {"ALL": obs_count_baseline}
    all_slice_asins: Set[str] = set()

    for bucket in buckets:
        p_id = bucket["partition_id"]
        min_p = bucket["min_price"]
        max_p = bucket["max_price"]
        price_param = taxonomy_registry.build_amazon_price_slice_param(min_p, max_p)

        slice_asins: Set[str] = set()
        slice_obs_count = 0

        logger.info(f"\n--- Crawling Slice [{p_id}] (${min_p} - ${max_p or '+'}) ---")

        for page_num in range(1, pages_per_slice + 1):
            url = f"https://www.amazon.com/s?k={quote(niche)}&page={page_num}{price_param}" if page_num > 1 else f"https://www.amazon.com/s?k={quote(niche)}{price_param}"
            logger.info(f"[{p_id}] Fetching page {page_num}/{pages_per_slice} -> {url}")
            html, status, strategy_used = fetcher.fetch_page_html(url, query=niche, niche=bench_niche, run_id=session_id)

            if status not in ("success", "zero_cards") or not html:
                logger.warning(f"[{p_id}] Page {page_num} returned status='{status}'.")
                continue

            products, observations = breadth_crawler.extract_cheap_products_from_html(
                html, query=niche, lane="price_partition", niche=bench_niche, page=page_num,
                run_id=session_id, partition_type="PRICE", partition_id=p_id,
                min_price=min_p, max_price=max_p, strategy_used=strategy_used
            )

            for p in products:
                db.save_product(p, record_snapshot=False)
                slice_asins.add(p["asin"])
                all_slice_asins.add(p["asin"])

            for obs in observations:
                db.record_search_observation(obs)
                slice_obs_count += 1

            db.record_coverage_ledger_entry(
                session_id=session_id,
                niche=bench_niche,
                lane="price_partition",
                query_or_target=niche,
                page_number=page_num,
                asins_found_total=len(products),
                asins_new_unique=len(slice_asins - asins_baseline),
                asins_duplicate=len(slice_asins & asins_baseline),
                cumulative_unique=len(asins_baseline | all_slice_asins),
                status=status,
                strategy_used=strategy_used,
                partition_type="PRICE",
                partition_id=p_id
            )
            time.sleep(0.5)

        slice_observations[p_id] = slice_obs_count
        net_new_from_slice = slice_asins - asins_baseline
        slice_incremental_yield[p_id] = {
            "label": bucket.get("label", p_id),
            "min_price": min_p,
            "max_price": max_p,
            "observations": slice_obs_count,
            "total_asins_in_slice": len(slice_asins),
            "net_new_unique_vs_baseline": len(net_new_from_slice),
            "duplicate_with_baseline_count": len(slice_asins & asins_baseline)
        }
        logger.info(f"[{p_id} Result] Obs: {slice_obs_count} | Slice ASINs: {len(slice_asins)} | Net New vs Baseline: +{len(net_new_from_slice)}")

    t_b = round(time.time() - t0_b, 2)

    # Relevance classification
    relevance_engine.classify_niche_products(bench_niche)
    all_prods = db.get_products(niche=bench_niche, limit=5000, relevance_filter="ALL")
    core_asins: Set[str] = {p["asin"] for p in all_prods if p.get("relevance_class") == "CORE"}
    acc_asins: Set[str] = {p["asin"] for p in all_prods if p.get("relevance_class") == "ACCESSORY"}
    adj_asins: Set[str] = {p["asin"] for p in all_prods if p.get("relevance_class") == "ADJACENT"}

    # Transports breakdown
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT transport_used, COUNT(*) FROM search_observations WHERE niche=? GROUP BY transport_used", (bench_niche,))
    transport_counts = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()

    # Total combined and genuine incremental
    total_combined_asins = asins_baseline | all_slice_asins
    total_genuine_incremental = all_slice_asins - asins_baseline
    total_all_obs = sum(slice_observations.values())

    report = {
        "benchmark_id": benchmark_id,
        "niche": niche,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages_per_slice": pages_per_slice,
        "baseline_normal": {
            "query": niche,
            "partition_id": "ALL",
            "unique_asins": len(asins_baseline),
            "observations": obs_count_baseline,
            "runtime_seconds": t_a
        },
        "price_partitions_harvest": {
            "total_slices_evaluated": len(buckets),
            "slice_observations": slice_observations,
            "slice_incremental_yield": slice_incremental_yield,
            "total_partition_unique_asins": len(all_slice_asins),
            "runtime_seconds": t_b
        },
        "genuine_incremental_lift": {
            "total_combined_unique_asins": len(total_combined_asins),
            "net_genuine_incremental_asins": len(total_genuine_incremental),
            "incremental_lift_pct": round(len(total_genuine_incremental) / max(1, len(asins_baseline)) * 100, 2),
            "core_asins_count": len(core_asins),
            "accessory_asins_count": len(acc_asins),
            "adjacent_asins_count": len(adj_asins)
        },
        "transports_used": transport_counts
    }

    # Print ASCII Report
    print("\n" + "=" * 95)
    print("          GENUINE PRICE PARTITION A/B BENCHMARK REPORT")
    print("=" * 95)
    print(f"Niche Keyword: {niche} | Pages per Slice: {pages_per_slice} | Benchmark ID: {benchmark_id}")
    print("-" * 95)
    print(f"{'Partition / Slice':<25} | {'Observations':<15} | {'Slice ASINs':<15} | {'Net New vs Baseline':<20}")
    print("-" * 95)
    print(f"{'Baseline: ALL':<25} | {obs_count_baseline:<15} | {len(asins_baseline):<15} | {'(Baseline Reference)':<20}")
    for pid, y in slice_incremental_yield.items():
        print(f"{pid:<25} | {y['observations']:<15} | {y['total_asins_in_slice']:<15} | +{y['net_new_unique_vs_baseline']}")
    print("-" * 95)
    print(f"{'TOTAL COMBINED UNIVERSE':<25} | {total_all_obs:<15} | {len(total_combined_asins):<15} | +{len(total_genuine_incremental)} ({report['genuine_incremental_lift']['incremental_lift_pct']}%)")
    print(f"  - CORE Products: {len(core_asins)} | ACCESSORIES: {len(acc_asins)} | ADJACENT: {len(adj_asins)}")
    print(f"  - Transports: {transport_counts}")
    print(f"  - Baseline Time: {t_a}s | Partitions Time: {t_b}s | Total: {round(t_a + t_b, 2)}s")
    print("=" * 95)

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
    args = parser.parse_args()
    run_ab_benchmark(niche=args.niche, pages_per_slice=args.pages)

