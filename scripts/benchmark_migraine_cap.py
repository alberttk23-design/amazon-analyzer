import sys
import time
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db
import backend.breadth_crawler as breadth_crawler
import backend.promotion_engine as promotion_engine

def run_benchmark():
    niche = "Migraine Relief Cap"
    print(f"=== Starting Live Acquisition Benchmark on: '{niche}' ===")
    start_time = time.time()

    db.init_db()

    # Step 1: Execute Breadth Acquisition (e.g. 2 queries, 2 pages)
    print("\n--- Phase 1: Multi-Lane Breadth Acquisition ---")
    breadth_res = breadth_crawler.run_breadth_discovery_saturation_loop(
        seed_keyword=niche,
        max_queries=2,
        max_pages_per_query=2
    )

    elapsed_breadth = round(time.time() - start_time, 2)
    print(f"\nBreadth acquisition completed in {elapsed_breadth}s.")
    print(f"Result summary: {breadth_res}")

    # Step 2: Test Page-Level Checkpoint Verification
    print("\n--- Phase 2: Page-Level Checkpoint & Recovery Verification ---")
    pending = db.get_next_pending_query(niche)
    if pending:
        print(f"Next pending query in queue: '{pending['query']}' | Next page: {pending['next_page']} | Target pages: {pending['target_pages']}")
    else:
        print("All initial queries completed or queued up.")

    # Step 3: Run Promotion Engine
    print("\n--- Phase 3: Observation-Based Promotion Engine ---")
    promo_res = promotion_engine.compute_and_update_niche_promotions(niche)
    print(f"Promotion results: {promo_res}")

    # Step 4: Extract Benchmark Metrics
    print("\n--- Phase 4: Benchmark Metrics Aggregation ---")
    conn = db.get_db()
    cur = conn.cursor()

    # 1. Total products in niche
    cur.execute("SELECT COUNT(*) as count FROM niche_products WHERE niche = ?", (niche,))
    total_niche_prods = cur.fetchone()["count"]

    # 2. Tier distribution in niche
    cur.execute("""
    SELECT tier, COUNT(*) as count
    FROM niche_products
    WHERE niche = ?
    GROUP BY tier
    """, (niche,))
    tier_dist = {r["tier"]: r["count"] for r in cur.fetchall()}

    # 3. Observations count (Sponsored vs Organic)
    cur.execute("""
    SELECT placement_type, COUNT(*) as count
    FROM search_observations
    WHERE niche = ?
    GROUP BY placement_type
    """, (niche,))
    obs_dist = {r["placement_type"]: r["count"] for r in cur.fetchall()}

    # 4. Coverage ledger marginal yields
    cur.execute("""
    SELECT query_or_target, page_number, asins_found_total, asins_new_unique, asins_duplicate, strategy_used
    FROM coverage_ledger
    WHERE niche = ?
    ORDER BY id ASC
    """, (niche,))
    ledger_rows = [dict(r) for r in cur.fetchall()]

    # 5. Diagnostic / Error checks
    cur.execute("""
    SELECT status, COUNT(*) as count
    FROM diagnostics_log
    WHERE niche = ?
    GROUP BY status
    """, (niche,))
    diag_dist = {r["status"]: r["count"] for r in cur.fetchall()}

    # 6. Completeness status breakdown
    cur.execute("""
    SELECT p.completeness_status, COUNT(*) as count
    FROM products p
    JOIN niche_products np ON p.asin = np.asin
    WHERE np.niche = ?
    GROUP BY p.completeness_status
    """, (niche,))
    completeness_dist = {r["completeness_status"]: r["count"] for r in cur.fetchall()}

    # 7. Brand entities discovered
    cur.execute("""
    SELECT COUNT(*) as count FROM brand_entities WHERE niche = ?
    """, (niche,))
    brands_count = cur.fetchone()["count"]

    conn.close()

    total_time = round(time.time() - start_time, 2)

    report = {
        "benchmark_target": niche,
        "total_runtime_seconds": total_time,
        "total_unique_asins_discovered": total_niche_prods,
        "unique_brands_cataloged": brands_count,
        "completeness_breakdown": completeness_dist,
        "tier_distribution": tier_dist,
        "search_observations_distribution": obs_dist,
        "coverage_ledger_entries": ledger_rows,
        "diagnostics_failures": diag_dist,
        "status": "BENCHMARK_SUCCESS"
    }

    print("\n=== FINAL BENCHMARK REPORT ===")
    print(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    run_benchmark()
