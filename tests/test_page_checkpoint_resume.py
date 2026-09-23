import uuid
import pytest
import backend.db as db


def test_page_checkpoint_and_stale_reclamation():
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    niche = f"Checkpoint_Niche_{unique_suffix}"
    test_query = f"test search query {unique_suffix}"

    # 1. Enqueue query
    db.enqueue_discovery_queries(niche=niche, queries=[test_query], target_pages=3)

    # 2. Get next pending query (should be page 1)
    item = db.get_next_pending_query(niche)
    assert item is not None
    assert item["query"] == test_query
    assert item["last_completed_page"] == 0
    assert item["next_page"] == 1
    assert item["target_pages"] == 3
    assert item["status"] == "pending"

    # 3. Simulate successfully scraping page 1
    db.update_query_progress(niche=niche, query=test_query, page_num=1, status="in_progress")

    # 4. Simulate a crash / timeout while processing page 2
    # Artificially age the row by 30 minutes
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("""
    UPDATE discovery_query_queue
    SET updated_at = datetime('now', '-30 minutes')
    WHERE niche = ? AND query = ?
    """, (niche, test_query))
    conn.commit()
    conn.close()

    # Reclaim stale queries
    reclaimed = db.reclaim_stale_in_progress_queries(niche, timeout_minutes=15)
    assert reclaimed == 1

    # 5. Re-fetch query: must resume from page 2, not restart at page 1!
    resumed = db.get_next_pending_query(niche)
    assert resumed is not None
    assert resumed["query"] == test_query
    assert resumed["last_completed_page"] == 1
    assert resumed["next_page"] == 2
    assert resumed["retry_count"] >= 1

    # 6. Complete remaining pages up to target
    db.update_query_progress(niche=niche, query=test_query, page_num=2, status="in_progress")
    db.update_query_progress(niche=niche, query=test_query, page_num=3, status="completed")

    # Queue should now be empty for this niche
    finished = db.get_next_pending_query(niche)
    assert finished is None
