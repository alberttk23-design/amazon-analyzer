import uuid
import pytest
import backend.db as db
import backend.taxonomy_registry as taxonomy_registry
import backend.breadth_crawler as breadth_crawler


def test_compound_queue_key_allows_multiple_slices():
    """Verify that (niche, query, partition_type, partition_id) allows multiple price slices for the same query."""
    db.init_db()
    suffix = uuid.uuid4().hex[:6].upper()
    niche = f"Luggage_Queue_Test_{suffix}"
    query = "luggage"

    entries = [
        {"lane": "keyword_search", "query": query, "priority": 1, "target_pages": 3, "partition_type": "NORMAL", "partition_id": "ALL"},
        {"lane": "price_partition", "query": query, "priority": 2, "target_pages": 3, "partition_type": "PRICE", "partition_id": "PRICE_0_25", "min_price": 0.0, "max_price": 25.0},
        {"lane": "price_partition", "query": query, "priority": 2, "target_pages": 3, "partition_type": "PRICE", "partition_id": "PRICE_25_60", "min_price": 25.0, "max_price": 60.0},
        {"lane": "price_partition", "query": query, "priority": 2, "target_pages": 3, "partition_type": "PRICE", "partition_id": "PRICE_60_150", "min_price": 60.0, "max_price": 150.0},
    ]

    enqueued = db.enqueue_discovery_queries(niche, entries)
    assert enqueued == 4, "All 4 slices for the same query must be enqueued independently!"

    pending = db.get_pending_discovery_queries(niche)
    assert len(pending) == 4
    partition_ids = [p["partition_id"] for p in pending]
    assert "ALL" in partition_ids
    assert "PRICE_0_25" in partition_ids
    assert "PRICE_25_60" in partition_ids
    assert "PRICE_60_150" in partition_ids


def test_duplicate_asin_across_slices_stored_in_observations():
    """Verify that when an ASIN appears in multiple slices, each search observation is preserved with partition metadata."""
    db.init_db()
    suffix = uuid.uuid4().hex[:6].upper()
    niche = f"Luggage_Obs_Test_{suffix}"
    test_asin = f"B0TEST{suffix[:4]}"

    # Observation 1: Normal Search ALL, rank #43
    obs_all = {
        "run_id": f"run_{suffix}",
        "niche": niche,
        "asin": test_asin,
        "query": "luggage",
        "page": 2,
        "position": 43,
        "placement_type": "ORGANIC",
        "price": 89.99,
        "rating": 4.5,
        "reviews_count": 1200,
        "partition_type": "NORMAL",
        "partition_id": "ALL",
        "price_min": 0.0,
        "price_max": 0.0,
        "transport_used": "HTTP_FAST"
    }
    id1 = db.record_search_observation(obs_all)
    assert id1 > 0

    # Observation 2: Price Slice $60-$150, rank #4
    obs_slice = {
        "run_id": f"run_{suffix}",
        "niche": niche,
        "asin": test_asin,
        "query": "luggage",
        "page": 1,
        "position": 4,
        "placement_type": "ORGANIC",
        "price": 89.99,
        "rating": 4.5,
        "reviews_count": 1200,
        "partition_type": "PRICE",
        "partition_id": "PRICE_60_150",
        "price_min": 60.0,
        "price_max": 150.0,
        "transport_used": "LOCAL_CDP"
    }
    id2 = db.record_search_observation(obs_slice)
    assert id2 > 0
    assert id1 != id2

    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT partition_type, partition_id, position, transport_used FROM search_observations WHERE niche=? AND asin=?", (niche, test_asin))
    rows = cur.fetchall()
    conn.close()

    assert len(rows) == 2, "Both observations must be stored without deduplication dropping rank intelligence!"
    row_all = next(r for r in rows if r[1] == "ALL")
    row_slice = next(r for r in rows if r[1] == "PRICE_60_150")

    assert row_all[0] == "NORMAL"
    assert row_all[2] == 43
    assert row_all[3] == "HTTP_FAST"

    assert row_slice[0] == "PRICE"
    assert row_slice[2] == 4
    assert row_slice[3] == "LOCAL_CDP"


def test_semantic_price_buckets_generation():
    """Verify semantic price bucket generation and Amazon URL price parameters."""
    # Test taxonomy default buckets for luggage
    buckets = taxonomy_registry.get_semantic_price_buckets("luggage")
    assert len(buckets) == 4
    assert buckets[0]["partition_id"] == "PRICE_0_25"
    assert buckets[0]["max_price"] == 25.0
    assert buckets[1]["partition_id"] == "PRICE_25_60"

    # Test Amazon facet parameter generation (prices in cents)
    assert taxonomy_registry.build_amazon_price_slice_param(0.0, 25.0) == "&rh=p_36%3A-2500"
    assert taxonomy_registry.build_amazon_price_slice_param(25.0, 60.0) == "&rh=p_36%3A2500-6000"
    assert taxonomy_registry.build_amazon_price_slice_param(150.0, 0.0) == "&rh=p_36%3A15000-"

    # Test dynamic percentiles when enough sample prices are provided
    sample_prices = [10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0, 150.0, 200.0, 250.0]
    dynamic_buckets = taxonomy_registry.get_semantic_price_buckets("random_niche_xyz", observed_prices=sample_prices)
    assert len(dynamic_buckets) == 4
    assert dynamic_buckets[0]["min_price"] == 0.0
    assert dynamic_buckets[0]["max_price"] > 0.0
    assert dynamic_buckets[3]["max_price"] == 0.0


def test_captcha_exact_page_resume_preserves_slice_and_page():
    """Verify CAPTCHA interruption flags paused_captcha and preserves exact slice and page."""
    db.init_db()
    suffix = uuid.uuid4().hex[:6].upper()
    niche = f"Luggage_Captcha_Test_{suffix}"
    query = "luggage"

    # Enqueue a price slice
    entry = {"lane": "price_partition", "query": query, "priority": 1, "target_pages": 5, "partition_type": "PRICE", "partition_id": "PRICE_60_150", "min_price": 60.0, "max_price": 150.0}
    db.enqueue_discovery_queries(niche, [entry])

    # Page 1 succeeds
    db.update_query_progress(niche, query, page_num=1, status="in_progress", success=True, partition_type="PRICE", partition_id="PRICE_60_150")

    # Page 2 succeeds
    db.update_query_progress(niche, query, page_num=2, status="in_progress", success=True, partition_type="PRICE", partition_id="PRICE_60_150")

    # Page 3 hits CAPTCHA
    db.update_query_progress(niche, query, page_num=3, status="paused_captcha", error="empty_or_captcha", success=False, partition_type="PRICE", partition_id="PRICE_60_150")

    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT status, last_completed_page, next_page, retry_count FROM discovery_query_queue WHERE niche=? AND partition_id=?", (niche, "PRICE_60_150"))
    row = dict(cur.fetchone())
    conn.close()

    assert row["status"] == "paused_captcha"
    assert row["last_completed_page"] == 2
    assert row["next_page"] == 3, "Must not advance to page 4! Exact retry must target page 3."
    assert row["retry_count"] >= 1


def test_intra_partition_early_exit_preserves_other_partitions():
    """Verify that when one partition stops due to 2 zero-yield pages, other partitions in the queue remain runnable."""
    db.init_db()
    suffix = uuid.uuid4().hex[:6].upper()
    niche = f"Luggage_Intra_Test_{suffix}"
    query = "luggage"

    entries = [
        {"lane": "price_partition", "query": query, "priority": 1, "target_pages": 4, "partition_type": "PRICE", "partition_id": "PRICE_0_25", "min_price": 0.0, "max_price": 25.0},
        {"lane": "price_partition", "query": query, "priority": 2, "target_pages": 4, "partition_type": "PRICE", "partition_id": "PRICE_60_150", "min_price": 60.0, "max_price": 150.0},
    ]
    db.enqueue_discovery_queries(niche, entries)

    # 1. Pop first slice (PRICE_0_25)
    item1 = db.get_next_pending_query(niche)
    assert item1 is not None
    assert item1["partition_id"] == "PRICE_0_25"

    # Simulate PRICE_0_25 early exiting on page 2
    db.mark_discovery_query_status(niche, query, "completed", partition_type="PRICE", partition_id="PRICE_0_25")

    # 2. Pop next slice: PRICE_60_150 MUST still be pending and ready to execute!
    item2 = db.get_next_pending_query(niche)
    assert item2 is not None, "PRICE_60_150 must not be aborted just because PRICE_0_25 exited early!"
    assert item2["partition_id"] == "PRICE_60_150"
    assert item2["status"] == "pending"


def test_transport_planner_cdp_helpers():
    """Verify session_manager CDP liveness check and command generation."""
    import backend.session_manager as session_manager
    # Ping non-existent port should return False without raising exception
    assert session_manager.is_cdp_available(port=64999, timeout=0.1) is False

    cmd = session_manager.get_cdp_launch_command(9222)
    assert "--remote-debugging-port=9222" in cmd
    assert "cdp_research_profile" in cmd
    assert "--user-data-dir=" in cmd
