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


def test_api_price_partition_request_models():
    """Verify that AnalyzeRequest and BreadthDiscoverRequest support enable_price_partition."""
    from backend.api import AnalyzeRequest, BreadthDiscoverRequest

    req1 = AnalyzeRequest(keyword="luggage", enable_price_partition=True)
    assert req1.enable_price_partition is True

    req2 = BreadthDiscoverRequest(seed_keyword="luggage", enable_price_partition=True)
    assert req2.enable_price_partition is True


def test_price_partition_priority_before_secondary_keywords():
    """Verify that price partitions are prioritized ahead of secondary keyword variants."""
    db.init_db()
    suffix = uuid.uuid4().hex[:6].upper()
    niche = f"Priority_Order_Test_{suffix}"
    seed = "luggage"

    lanes = breadth_crawler.expand_niche_lanes(seed)
    queue_entries = []

    # 1. Primary Seed Query
    queue_entries.append({
        "lane": "keyword_search",
        "query": seed,
        "priority": 1,
        "target_pages": 3,
        "partition_type": "NORMAL",
        "partition_id": "ALL"
    })

    # 2. Price Partitions (Priority 1)
    buckets = taxonomy_registry.get_semantic_price_buckets(niche, query=seed)
    for b in buckets:
        queue_entries.append({
            "lane": "price_partition",
            "query": seed,
            "priority": 1,
            "target_pages": 3,
            "partition_type": "PRICE",
            "partition_id": b["partition_id"],
            "min_price": b["min_price"],
            "max_price": b["max_price"]
        })

    # 3. Secondary keywords (Priority 2)
    for q in lanes.get("keyword_search", []):
        if q.strip().lower() != seed.lower():
            queue_entries.append(("keyword_search", q, 2))

    # 4. Suggestions (Priority 3)
    for q in lanes.get("suggestions", []):
        if q.strip().lower() != seed.lower():
            queue_entries.append(("suggestions", q, 3))

    db.enqueue_discovery_queries(niche, queue_entries)

    # Pop 1: Must be seed keyword ALL
    item1 = db.get_next_pending_query(niche)
    assert item1["query"] == seed
    assert item1["partition_id"] == "ALL"
    db.mark_discovery_query_status(niche, item1["query"], "completed", partition_id=item1["partition_id"])

    # Next 4 pops: MUST be the price partitions of the seed keyword!
    popped_slices = []
    for _ in range(4):
        item = db.get_next_pending_query(niche)
        assert item is not None
        assert item["partition_type"] == "PRICE", f"Expected PRICE partition before secondary queries, got {item['partition_type']}:{item['query']}"
        popped_slices.append(item["partition_id"])
        db.mark_discovery_query_status(niche, item["query"], "completed", partition_type="PRICE", partition_id=item["partition_id"])

    assert len(popped_slices) == 4
    assert set(popped_slices) == {"PRICE_0_25", "PRICE_25_60", "PRICE_60_150", "PRICE_150_PLUS"}

    # Pop 6: ONLY NOW should secondary keywords appear!
    item_sec = db.get_next_pending_query(niche)
    assert item_sec is not None
    assert item_sec["priority"] == 2
    assert item_sec["query"] != seed


def test_dynamic_percentile_price_buckets_from_observed_prices():
    """Verify dynamic 25/50/75 percentile price bucket derivation from observed prices."""
    db.init_db()
    suffix = uuid.uuid4().hex[:6].upper()
    niche = f"Unknown_Dynamic_Niche_{suffix}"

    # Sample 20 prices: 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 120
    test_prices = [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0,
                   60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0, 100.0, 120.0]

    for idx, p in enumerate(test_prices):
        obs = {
            "run_id": f"run_{suffix}",
            "niche": niche,
            "asin": f"B0DYN{suffix[:4]}{idx:02d}",
            "query": "unknown gadget",
            "page": 1,
            "position": idx + 1,
            "price": p,
            "rating": 4.2,
            "reviews_count": 50,
            "partition_type": "NORMAL",
            "partition_id": "ALL"
        }
        db.record_search_observation(obs)

    observed = db.get_observed_prices_for_niche(niche)
    assert len(observed) == 20

    # Derive buckets
    buckets = taxonomy_registry.get_semantic_price_buckets(niche, query="unknown gadget", observed_prices=observed)
    assert len(buckets) == 4
    # Percentiles: 25th is idx 5 (35.0), 50th is idx 10 (60.0), 75th is idx 15 (85.0)
    p_ids = [b["partition_id"] for b in buckets]
    assert p_ids[0] == "PRICE_0_35"
    assert p_ids[1] == "PRICE_35_60"
    assert p_ids[2] == "PRICE_60_85"
    assert p_ids[3] == "PRICE_85_PLUS"

