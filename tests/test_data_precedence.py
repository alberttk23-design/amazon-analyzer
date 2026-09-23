import uuid
import pytest
import backend.db as db


def test_source_precedence_detail_over_search_card():
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    test_asin = f"B0PREC_{unique_suffix}"
    niche = f"Precedence_Test_{unique_suffix}"

    # 1. Detail crawl saves FULL verified data
    db.save_product({
        "asin": test_asin,
        "title": "Verified High Quality Product Title",
        "brand": "TrueBrand",
        "price": 49.99,
        "original_price": 59.99,
        "rating": 4.7,
        "reviews_count": 350,
        "keyword": niche,
        "tier": "HOT",
        "product_depth": "FULL",
        "completeness_status": "complete"
    }, record_snapshot=True)

    verified_prod = db.get_product_by_asin(test_asin)
    assert verified_prod["title"] == "Verified High Quality Product Title"
    assert verified_prod["price"] == 49.99
    assert verified_prod["rating"] == 4.7
    assert verified_prod["product_depth"] == "FULL"

    # 2. Subsequent shallow search card crawl (e.g. price is 0.0 or title truncated)
    db.save_product({
        "asin": test_asin,
        "title": "Truncated Title...",
        "brand": "",  # missing brand
        "price": 0.0,  # missing price
        "rating": 0.0,
        "keyword": niche,
        "tier": "COLD",
        "product_depth": "SHALLOW",
        "completeness_status": "partial"
    }, record_snapshot=False)

    after_shallow = db.get_product_by_asin(test_asin)
    # Price must remain 49.99, rating must remain 4.7, brand must remain TrueBrand, depth must remain FULL
    assert after_shallow["price"] == 49.99
    assert after_shallow["rating"] == 4.7
    assert after_shallow["brand"] == "TrueBrand"
    assert after_shallow["product_depth"] == "FULL"


def test_snapshot_rate_limiting():
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    test_asin = f"B0SNAP_{unique_suffix}"
    niche = f"Snapshot_Test_{unique_suffix}"

    # First save with snapshot
    db.save_product({
        "asin": test_asin,
        "title": "Snapshot Test Item",
        "price": 25.00,
        "keyword": niche,
        "product_depth": "FULL"
    }, record_snapshot=True)

    # Immediate second save with snapshot=True should be throttled (< 6 hours)
    db.save_product({
        "asin": test_asin,
        "title": "Snapshot Test Item",
        "price": 25.00,
        "keyword": niche,
        "product_depth": "FULL"
    }, record_snapshot=True)

    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as count FROM product_snapshots WHERE asin = ?", (test_asin,))
    row = cur.fetchone()
    conn.close()

    assert row["count"] == 1  # Throttled to 1 snapshot!
