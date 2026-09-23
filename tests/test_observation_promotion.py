import uuid
import pytest
import backend.db as db
from backend.promotion_engine import calculate_product_promotion_signals


def test_observation_metrics_and_promotion_engine():
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    test_asin = f"B0OBS_{unique_suffix}"
    niche = f"Obs_Niche_{unique_suffix}"

    # 1. Record search observations
    # Sponsored in Query 1
    db.record_search_observation({
        "asin": test_asin,
        "niche": niche,
        "query": f"{niche} best",
        "page": 1,
        "position": 2,
        "placement_type": "SPONSORED",
        "sponsored_evidence": "label_observed"
    })
    # Sponsored in Query 2
    db.record_search_observation({
        "asin": test_asin,
        "niche": niche,
        "query": f"{niche} reviews",
        "page": 1,
        "position": 4,
        "placement_type": "SPONSORED",
        "sponsored_evidence": "badge_observed"
    })
    # Organic in Query 3 (Top 3)
    db.record_search_observation({
        "asin": test_asin,
        "niche": niche,
        "query": f"{niche} upgrade",
        "page": 1,
        "position": 3,
        "placement_type": "ORGANIC",
        "sponsored_evidence": "none"
    })
    # Organic in Query 4 (Top 5)
    db.record_search_observation({
        "asin": test_asin,
        "niche": niche,
        "query": f"{niche} for women",
        "page": 1,
        "position": 5,
        "placement_type": "ORGANIC",
        "sponsored_evidence": "none"
    })

    # 2. Check observation metrics
    metrics = db.get_asin_observation_metrics(test_asin, niche)
    assert metrics["sponsored_seen_count"] == 2
    assert metrics["sponsored_query_count"] == 2
    assert metrics["organic_best_position"] == 3
    assert metrics["organic_query_coverage"] == 2

    # 3. Create product and calculate promotion signals
    product_dict = {
        "asin": test_asin,
        "title": "Observation Test Cap",
        "brand": "ActiveBrand",
        "price": 29.99,
        "rating": 4.6,
        "reviews_count": 500,
        "bought_past_month": 100,
        "bsr_rank": 850,
        "keyword": niche,
        "tier": "COLD",
        "product_depth": "SHALLOW"
    }
    db.save_product(product_dict)

    cand = db.get_product_by_asin(test_asin)
    score, reasons_str = calculate_product_promotion_signals(cand, niche=niche)

    assert score > 0.0
    # Reasons should contain cross-query ad activity and organic rank leadership
    assert "ad_active_cross_query(2q)" in reasons_str
    assert "organic_leader(pos#3)" in reasons_str


def test_review_depth_status_and_verified_strict():
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    test_asin = f"B0REV_{unique_suffix}"
    niche = f"Rev_Niche_{unique_suffix}"

    db.save_product({
        "asin": test_asin,
        "title": "Review Depth Test Item",
        "price": 19.99,
        "keyword": niche,
        "product_depth": "FULL"
    })

    # Save reviews under representative_polarity policy (target = 30)
    fake_reviews = [
        {
            "review_id": f"R_{unique_suffix}_{i}",
            "asin": test_asin,
            "star_rating": 1 if i % 2 == 0 else 5,
            "review_title": f"Review {i}",
            "review_text": f"This is detailed text for review {i}",
            "verified_purchase": True if i == 0 else False
        }
        for i in range(12)
    ]

    saved = db.save_reviews(
        asin=test_asin,
        keyword=niche,
        reviews_list=fake_reviews,
        visible_total_reviews=120,
        collection_method="representative_polarity"
    )
    assert saved == 12

    prod = db.get_product_by_asin(test_asin)
    # Since 12 < 30 and 12 < 120, depth must be 'PARTIAL', not the collection method string!
    assert prod["review_depth"] == "PARTIAL"
    assert prod["collection_method"] == "representative_polarity"
    assert prod["tier"] == "HOT"
