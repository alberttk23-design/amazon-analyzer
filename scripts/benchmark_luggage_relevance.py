import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db
import backend.breadth_crawler as breadth_crawler
import backend.promotion_engine as promotion_engine
import backend.relevance_engine as relevance_engine


def run_luggage_benchmark():
    niche = "luggage"
    print(f"\n==================================================================")
    print(f"🚀 LIVE BENCHMARK: BREADTH ACQUISITION & RELEVANCE CLASSIFICATION")
    print(f"   Target Niche: '{niche}' | Zipcode: 10001 (US East)")
    print(f"   Execution: 2 Queries x 3 Pages Breadth Crawl")
    print(f"==================================================================\n")

    start_time = time.time()
    db.init_db()

    # Step 1: Execute Breadth Acquisition
    print("--- Phase 1: Breadth Acquisition (Candidate Discovery) ---")
    breadth_res = breadth_crawler.run_breadth_discovery_saturation_loop(
        seed_keyword=niche,
        max_queries=2,
        max_pages_per_query=3
    )
    elapsed_breadth = round(time.time() - start_time, 2)
    print(f"✓ Breadth acquisition complete in {elapsed_breadth}s.")
    print(f"  Queries executed: {breadth_res.get('queries_executed')}")
    print(f"  New ASINs discovered: {breadth_res.get('total_new_discovered')}")
    print(f"  Cumulative universe size: {breadth_res.get('final_universe_size')}\n")

    # Step 2: Relevance Classification
    print("--- Phase 2: Multi-Signal Relevance Engine Classification ---")
    rel_summary = relevance_engine.classify_niche_products(niche)
    print(f"✓ Classification complete: {json.dumps(rel_summary, indent=2)}\n")

    # Step 3: Run Promotion Engine
    print("--- Phase 3: Observation-Based Promotion Engine ---")
    promo_res = promotion_engine.compute_and_update_niche_promotions(niche)
    print(f"✓ Promotion evaluation complete: {json.dumps(promo_res, indent=2)}\n")

    # Step 4: Aggregate Metrics from SQLite
    print("--- Phase 4: Relevance & Candidate Universe Metrics ---")
    conn = db.get_db()
    cur = conn.cursor()

    # 4.1 Total products in niche
    cur.execute("SELECT COUNT(*) as count FROM niche_products WHERE niche = ?", (niche,))
    total_candidates = cur.fetchone()["count"]

    # 4.2 Relevance breakdown
    cur.execute("""
    SELECT relevance_class, COUNT(*) as count
    FROM niche_products
    WHERE niche = ?
    GROUP BY relevance_class
    ORDER BY count DESC
    """, (niche,))
    rel_breakdown = {r["relevance_class"]: r["count"] for r in cur.fetchall()}

    # 4.3 Price comparisons
    cur.execute("""
    SELECT 
        AVG(p.price) as overall_avg_price,
        AVG(CASE WHEN np.relevance_class = 'CORE' AND p.price > 0 THEN p.price ELSE NULL END) as core_avg_price,
        AVG(CASE WHEN np.relevance_class = 'ACCESSORY' AND p.price > 0 THEN p.price ELSE NULL END) as acc_avg_price,
        AVG(CASE WHEN np.relevance_class = 'ADJACENT' AND p.price > 0 THEN p.price ELSE NULL END) as adj_avg_price
    FROM products p
    JOIN niche_products np ON p.asin = np.asin
    WHERE np.niche = ?
    """, (niche,))
    price_stats = cur.fetchone()

    # 4.4 Tier distribution
    cur.execute("""
    SELECT tier, COUNT(*) as count
    FROM niche_products
    WHERE niche = ?
    GROUP BY tier
    """, (niche,))
    tier_dist = {r["tier"]: r["count"] for r in cur.fetchall()}

    # 4.5 Sub-Niche Clusters
    clusters = relevance_engine.get_sub_niche_clusters(niche)

    # 4.6 Search Observations
    cur.execute("""
    SELECT placement_type, COUNT(*) as count
    FROM search_observations
    WHERE niche = ?
    GROUP BY placement_type
    """, (niche,))
    obs_dist = {r["placement_type"]: r["count"] for r in cur.fetchall()}

    # 4.7 30-sample qualitative audit
    cur.execute("""
    SELECT 
        p.asin, p.title, p.brand, p.price, p.rating, p.reviews_count, p.bought_past_month,
        np.tier, np.relevance_class, np.sub_cluster, np.relevance_confidence, np.relevance_evidence_json
    FROM products p
    JOIN niche_products np ON p.asin = np.asin
    WHERE np.niche = ?
    ORDER BY p.bought_past_month DESC, p.reviews_count DESC
    LIMIT 30
    """, (niche,))
    sample_rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    total_time = round(time.time() - start_time, 2)

    # Format Output
    print("==================================================================")
    print("📊 BENCHMARK RESULTS SUMMARY")
    print("==================================================================")
    print(f"Total Candidate Universe (Raw Discovered): {total_candidates} items")
    print(f"Relevance Class Distribution:")
    for rc, cnt in rel_breakdown.items():
        pct = round(cnt / total_candidates * 100, 1) if total_candidates > 0 else 0
        print(f"  • {rc:<12}: {cnt:>4} items ({pct}%)")

    print(f"\nPrice Integrity Check:")
    print(f"  • Overall Raw Avg Price : ${round(price_stats['overall_avg_price'] or 0.0, 2)}")
    print(f"  • CORE Market Avg Price : ${round(price_stats['core_avg_price'] or 0.0, 2)}")
    print(f"  • ACCESSORY Avg Price   : ${round(price_stats['acc_avg_price'] or 0.0, 2)}")
    print(f"  • ADJACENT Avg Price    : ${round(price_stats['adj_avg_price'] or 0.0, 2)}")

    print(f"\nLifecycle Tier Distribution:")
    for t, cnt in tier_dist.items():
        print(f"  • {t:<6}: {cnt:>4} items")

    print(f"\nObservations Breakdown:")
    for pt, cnt in obs_dist.items():
        print(f"  • {pt:<10}: {cnt:>4} cards observed")

    print(f"\nSub-Niche Accessory & Adjacent Clusters Discovered ({len(clusters)} clusters):")
    for cl in clusters:
        brands_list = [b if isinstance(b, str) else b.get("brand", "") for b in cl.get("top_brands", [])[:3]]
        brands_str = ", ".join(filter(None, brands_list)) or "N/A"
        print(f"  • [{cl['relevance_class']}] {cl['sub_cluster'].upper()}: {cl['product_count']} items | Avg: ${cl['avg_price']} (range: ${cl['min_price']}-${cl['max_price']}) | Sales/mo: {cl['total_monthly_sales']} | Brands: {brands_str}")

    print("\n------------------------------------------------------------------")
    print("🔬 30-SAMPLE AUDIT (TOP PRODUCTS BY SALES / POPULARITY)")
    print("------------------------------------------------------------------")
    correct_evals = 0
    for idx, row in enumerate(sample_rows, 1):
        asin = row["asin"]
        title = (row["title"] or "")[:70]
        price = row["price"]
        rel = row["relevance_class"]
        cluster = row["sub_cluster"] or "none"
        conf = row["relevance_confidence"]
        ev = json.loads(row["relevance_evidence_json"] or "[]")
        ev_str = ", ".join(ev[:2]) if ev else "no_evidence"

        # Sanity check: suitcases should be CORE, locks/tags/covers/wheels should be ACCESSORY, bags/duffels ADJACENT
        t_lower = title.lower()
        is_accessory_item = any(w in t_lower for w in ["lock", "tag", "cover", "wheel", "strap", "scale", "handle", "protector"])
        is_adjacent_item = any(w in t_lower for w in ["duffel", "duffle", "backpack", "tote", "packing cube"])
        has_embedded_feature = any(f in t_lower for f in ["with tsa lock", "tsa lock", "spinner wheels", "with wheels", "telescoping handle"])
        has_core_phrase = any(c in t_lower for c in ["luggage", "suitcase", "carry-on", "checked", "spinner"])
        
        expected = "CORE"
        if is_accessory_item and not (has_embedded_feature and has_core_phrase):
            expected = "ACCESSORY"
        elif is_adjacent_item and not has_core_phrase:
            expected = "ADJACENT"
        elif not has_core_phrase:
            expected = "UNKNOWN"

        matches = (rel == expected)
        if matches:
            correct_evals += 1
        mark = "✓" if matches else "⚠️"

        print(f"[{idx:02d}] {mark} {asin} | {rel:<9} | {cluster:<12} | ${price:>6.2f} | {title} | {ev_str}")

    precision = round(correct_evals / len(sample_rows) * 100, 1) if sample_rows else 100.0
    print("\n------------------------------------------------------------------")
    print(f"Audit Precision on Top 30 Sample: {correct_evals}/{len(sample_rows)} ({precision}%)")
    print(f"Total Benchmark Runtime: {total_time}s")
    print("==================================================================\n")

    return {
        "niche": niche,
        "total_candidates": total_candidates,
        "relevance_breakdown": rel_breakdown,
        "price_stats": {
            "overall_avg_price": round(price_stats['overall_avg_price'] or 0.0, 2),
            "core_avg_price": round(price_stats['core_avg_price'] or 0.0, 2),
            "acc_avg_price": round(price_stats['acc_avg_price'] or 0.0, 2),
            "adj_avg_price": round(price_stats['adj_avg_price'] or 0.0, 2)
        },
        "clusters_count": len(clusters),
        "clusters": clusters,
        "audit_precision": precision,
        "total_time": total_time
    }


if __name__ == "__main__":
    run_luggage_benchmark()
