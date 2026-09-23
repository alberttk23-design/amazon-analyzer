import json
import logging
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db

logger = logging.getLogger("amazon.promotion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def calculate_product_promotion_signals(product: Dict[str, Any], niche: Optional[str] = None) -> Tuple[float, str]:
    """
    Computes viability and priority score based on multi-dimensional market signals:
    - High Complaint Opportunity (+30 pts for high sales & low rating <= 3.9★)
    - Review Velocity (+25 pts for fast review growth)
    - Cross-Query PPC Advertising (+20 pts for multi-query or high-share sponsored observations)
    - Organic Market Leadership (+25 pts for top-5 organic rank across multiple queries)
    - Sales Velocity (+25 pts for high monthly volume)
    - Price Drops (+15 pts for recent discount)
    """
    score = 0.0
    reasons = []

    asin = product.get("asin", "")
    niche_name = niche or product.get("keyword") or product.get("niche") or ""
    price = float(product.get("price") or 0.0)
    orig_price = float(product.get("original_price") or 0.0)
    rating = float(product.get("rating") or 0.0)
    sales = int(product.get("bought_past_month") or 0)
    rev_velocity = float(product.get("review_velocity") or 0.0)

    # 1. Observation Analytics from search_observations
    obs_metrics = db.get_asin_observation_metrics(asin, niche_name) if (asin and niche_name) else {}
    spon_queries = obs_metrics.get("sponsored_query_count", 0)
    spon_share = obs_metrics.get("sponsored_share", 0.0)
    org_best_pos = obs_metrics.get("organic_best_position")
    org_cov = obs_metrics.get("organic_query_coverage", 0)

    # 2. High Complaint Density (VoC Flaw Mining)
    if sales >= 300 and 0.0 < rating <= 3.9:
        score += 30.0
        reasons.append("high_complaint_goldmine")

    # 3. Review Velocity Outliers
    if rev_velocity > 5:
        score += min(rev_velocity * 2.0, 25.0)
        reasons.append("rapid_review_growth")

    # 4. Observation-Based PPC Advertiser (Multi-query or high ad share)
    if spon_queries >= 2 or spon_share >= 0.4:
        score += 20.0
        reasons.append(f"ad_active_cross_query({spon_queries}q)")
    elif spon_queries == 1 or bool(product.get("is_sponsored")):
        score += 10.0
        reasons.append("ad_active_single_query")

    # 5. Observation-Based Organic Market Leader
    if org_best_pos is not None and org_best_pos <= 5 and org_cov >= 2:
        score += 25.0
        reasons.append(f"organic_leader(pos#{org_best_pos})")

    # 6. Sales Velocity
    sales_pts = min(sales / 2000.0, 1.0) * 25.0
    score += sales_pts
    if sales >= 1000:
        reasons.append("high_sales_volume")

    # 7. Price Discount / Drop
    if orig_price > price and price > 0:
        discount_pct = (orig_price - price) / orig_price
        if discount_pct >= 0.15:
            score += 15.0
            reasons.append("recent_price_drop")

    # 8. Relevance Alignment (Core market focus vs accessory opportunity)
    rel_class = product.get("relevance_class") or "UNKNOWN"
    sub_cluster = product.get("sub_cluster") or ""
    if rel_class == "CORE":
        score += 15.0
        reasons.append("core_market_product")
    elif rel_class == "ACCESSORY":
        if sub_cluster:
            reasons.append(f"accessory_opportunity({sub_cluster})")
        else:
            reasons.append("accessory_product")
    elif rel_class == "ADJACENT":
        reasons.append("adjacent_product")
    elif rel_class == "IRRELEVANT":
        score = max(0.0, score - 30.0)
        reasons.append("irrelevant_penalty")

    primary_reason = ", ".join(reasons) if reasons else "baseline_signals"
    return round(score, 1), primary_reason


def compute_and_update_niche_promotions(keyword: str) -> Dict[str, Any]:
    """
    Iterates through all candidates in the niche, computes promotion scores,
    and updates database records so the priority queue reflects real-time market dynamics.
    Prioritizes CORE candidates for HOT promotion.
    """
    candidates = db.get_products(keyword=keyword, limit=5000)
    updated_count = 0
    promoted_to_warm = 0
    promoted_to_hot = 0

    for cand in candidates:
        asin = cand["asin"]
        current_tier = cand.get("tier", "COLD")
        score, reason = calculate_product_promotion_signals(cand, niche=keyword)

        # Decide tier promotion: CORE and UNKNOWN can reach HOT, ACCESSORY/ADJACENT capped at WARM
        new_tier = current_tier
        rel_class = cand.get("relevance_class") or "UNKNOWN"
        if score >= 55.0 and current_tier != "HOT":
            if rel_class in ("CORE", "UNKNOWN"):
                new_tier = "HOT"
                promoted_to_hot += 1
            else:
                new_tier = "WARM"
                promoted_to_warm += 1
        elif score >= 25.0 and current_tier == "COLD":
            new_tier = "WARM"
            promoted_to_warm += 1

        db.update_product_tier(
            asin=asin,
            new_tier=new_tier,
            reason=reason,
            promotion_score=score,
            niche=keyword
        )
        updated_count += 1

    return {
        "keyword": keyword,
        "total_evaluated": updated_count,
        "promoted_to_warm": promoted_to_warm,
        "promoted_to_hot": promoted_to_hot
    }


def get_taxonomy_feed(keyword: str) -> Dict[str, Any]:
    """
    Returns categorized candidates for the Depth Crawl & Priority Queue Dashboard.
    """
    return {
        "top_performers": db.get_priority_candidates(keyword, "top_performers", limit=20),
        "emerging_winners": db.get_priority_candidates(keyword, "emerging_winners", limit=20),
        "review_velocity_outliers": db.get_priority_candidates(keyword, "review_velocity_outliers", limit=20),
        "high_complaints": db.get_priority_candidates(keyword, "high_complaints", limit=20),
        "price_outliers": db.get_priority_candidates(keyword, "price_outliers", limit=20),
        "ad_active": db.get_priority_candidates(keyword, "ad_active", limit=20),
        "long_tail": db.get_priority_candidates(keyword, "long_tail", limit=20)
    }


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    print(f"Testing Promotion Engine for '{kw}'...")
    res = compute_and_update_niche_promotions(kw)
    print("Promotion update result:", json.dumps(res, indent=2))
