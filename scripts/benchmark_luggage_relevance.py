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
    print("🔬 100-SAMPLE HUMAN-AUDITED GROUND TRUTH RELEVANCE BENCHMARK")
    print("------------------------------------------------------------------")
    gt_fixture_path = BASE_DIR / "tests" / "fixtures" / "luggage_ground_truth_100.json"
    confusion_matrix: Dict[str, Dict[str, int]] = {}
    class_metrics: Dict[str, Dict[str, float]] = {}
    accuracy = 0.0
    false_core_rate = 0.0
    false_accessory_rate = 0.0

    if gt_fixture_path.exists():
        with open(gt_fixture_path, "r", encoding="utf-8") as f:
            gt_items = json.load(f)

        classes = ["CORE", "ADJACENT", "ACCESSORY", "IRRELEVANT", "UNKNOWN"]
        confusion_matrix = {tc: {pc: 0 for pc in classes} for tc in classes}

        for item in gt_items:
            true_cls = item["true_class"]
            res = relevance_engine.classify_product(item, niche=niche)
            pred_cls = res["relevance_class"]
            confusion_matrix[true_cls][pred_cls] += 1

        total_gt = len(gt_items)
        total_correct = sum(confusion_matrix[c][c] for c in classes)
        accuracy = round((total_correct / total_gt) * 100, 2)

        # False CORE calculation: Non-CORE items classified as CORE
        non_core_count = len([i for i in gt_items if i["true_class"] != "CORE"])
        false_core_count = sum(confusion_matrix[tc]["CORE"] for tc in classes if tc != "CORE")
        false_core_rate = round((false_core_count / non_core_count) * 100, 2) if non_core_count > 0 else 0.0

        # False ACCESSORY calculation: CORE or ADJACENT items classified as ACCESSORY
        core_adj_count = len([i for i in gt_items if i["true_class"] in ("CORE", "ADJACENT")])
        false_acc_count = confusion_matrix["CORE"]["ACCESSORY"] + confusion_matrix["ADJACENT"]["ACCESSORY"]
        false_accessory_rate = round((false_acc_count / core_adj_count) * 100, 2) if core_adj_count > 0 else 0.0

        # Print Confusion Matrix Table
        header = f"{'True \\ Pred':<14} | " + " | ".join(f"{c:>10}" for c in classes) + " | Total"
        sep = "-" * len(header)
        print(f"\n{header}\n{sep}")
        for tc in classes:
            row_str = f"{tc:<14} | " + " | ".join(f"{confusion_matrix[tc][pc]:>10}" for pc in classes)
            row_total = sum(confusion_matrix[tc].values())
            print(f"{row_str} | {row_total:>5}")
        print(sep)

        # Print Per-Class Precision & Recall
        print(f"\n{'Class':<14} | {'Precision':>10} | {'Recall':>10} | {'F1-Score':>10} | {'Support':>8}")
        print("-" * 62)
        for c in classes:
            tp = confusion_matrix[c][c]
            fp = sum(confusion_matrix[oc][c] for oc in classes if oc != c)
            fn = sum(confusion_matrix[c][oc] for oc in classes if oc != c)
            prec = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 100.0
            rec = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 100.0
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
            support = sum(confusion_matrix[c].values())
            class_metrics[c] = {"precision": round(prec, 2), "recall": round(rec, 2), "f1": round(f1, 2), "support": support}
            print(f"{c:<14} | {prec:>9.1f}% | {rec:>9.1f}% | {f1:>9.1f}% | {support:>8}")
        print("-" * 62)

        print(f"\n📊 GROUND TRUTH BENCHMARK SUMMARY (N = {total_gt}):")
        print(f"  • Overall Classification Accuracy : {total_correct}/{total_gt} ({accuracy}%)")
        print(f"  • False CORE Rate (Noise Leaked)  : {false_core_count}/{non_core_count} ({false_core_rate}%)")
        print(f"  • False ACCESSORY Rate (Set Error): {false_acc_count}/{core_adj_count} ({false_accessory_rate}%)")
    else:
        print(f"⚠️ Fixture not found at {gt_fixture_path}")

    # Step 5: Save raw benchmark JSON runs to data/benchmarks/
    benchmarks_dir = BASE_DIR / "data" / "benchmarks"
    benchmarks_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    benchmark_file = benchmarks_dir / f"benchmark_run_{timestamp_str}.json"

    benchmark_data = {
        "timestamp": timestamp_str,
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
        "ground_truth_benchmark": {
            "sample_size": 100,
            "accuracy_pct": accuracy,
            "false_core_rate_pct": false_core_rate,
            "false_accessory_rate_pct": false_accessory_rate,
            "confusion_matrix": confusion_matrix,
            "class_metrics": class_metrics
        },
        "total_time_seconds": total_time
    }

    with open(benchmark_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Saved structured benchmark run to: {benchmark_file}")
    print(f"Total Benchmark Runtime: {total_time}s")
    print("==================================================================\n")

    return benchmark_data


if __name__ == "__main__":
    run_luggage_benchmark()
