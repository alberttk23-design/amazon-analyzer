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


def test_page_failure_checkpoint_preserves_failed_page():
    """When a page fails (CAPTCHA, 503, etc.), next_page must stay on failed page to retry."""
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    niche = f"FailCheck_Niche_{unique_suffix}"
    test_query = f"fail query test {unique_suffix}"

    # 1. Enqueue query with 3 target pages
    db.enqueue_discovery_queries(niche=niche, queries=[test_query], target_pages=3)

    # 2. Page 1 succeeds
    db.update_query_progress(niche=niche, query=test_query, page_num=1, status="in_progress", success=True)
    
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT last_completed_page, next_page, status, retry_count FROM discovery_query_queue WHERE niche=? AND query=?", (niche, test_query))
    row = dict(cur.fetchone())
    conn.close()

    assert row["last_completed_page"] == 1
    assert row["next_page"] == 2
    assert row["status"] == "in_progress"

    # 3. Page 2 fails with CAPTCHA or error
    db.update_query_progress(niche=niche, query=test_query, page_num=2, status="failed", error="empty_or_captcha", success=False)

    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("SELECT last_completed_page, next_page, status, retry_count, last_error FROM discovery_query_queue WHERE niche=? AND query=?", (niche, test_query))
    row_failed = dict(cur.fetchone())
    conn.close()

    # Crucial assertion: failed page must NOT advance last_completed_page or next_page!
    assert row_failed["last_completed_page"] == 1
    assert row_failed["next_page"] == 2, "next_page must remain 2 so retry hits the failed page, not 3!"
    assert row_failed["retry_count"] >= 1
    assert row_failed["status"] == "failed"
    assert "captcha" in row_failed["last_error"]


def test_paused_captcha_to_resume_exact_page_end_to_end():
    """Verify that a paused_captcha query is safely held, unpaused upon user action, and resumes on exact failed page."""
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    niche = f"CaptchaResume_Niche_{unique_suffix}"
    test_query = f"captcha test {unique_suffix}"

    # 1. Enqueue query targeting 5 pages
    db.enqueue_discovery_queries(niche=niche, queries=[test_query], target_pages=5)

    # 2. Pages 1 and 2 complete successfully
    db.update_query_progress(niche=niche, query=test_query, page_num=1, status="in_progress", success=True)
    db.update_query_progress(niche=niche, query=test_query, page_num=2, status="in_progress", success=True)

    # 3. Page 3 hits Amazon CAPTCHA -> crawler records page 3 failure and marks it paused_captcha
    db.update_query_progress(
        niche=niche,
        query=test_query,
        page_num=3,
        status="paused_captcha",
        error="Amazon Bot Check Captcha encountered",
        success=False
    )

    # 4. Checkpoint records paused query
    checkpoint = db.get_query_queue_checkpoint(niche)
    assert checkpoint["paused_captcha_queries"] == 1

    # 5. Normal queue fetch MUST NOT pick up paused_captcha query while waiting for user action!
    item = db.get_next_pending_query(niche)
    assert item is None, "A paused_captcha query must not be popped by workers before user action/resume!"

    # 6. User resolves CAPTCHA / calls resume API
    resumed_count = db.resume_partition_after_user_action(niche=niche, query=test_query)
    assert resumed_count == 1, "Exactly 1 query should be transitioned back to pending"

    # 7. Queue now pops the resumed query with EXACT failed page preserved
    resumed_item = db.get_next_pending_query(niche)
    assert resumed_item is not None
    assert resumed_item["status"] == "pending"
    assert resumed_item["last_completed_page"] == 2
    assert resumed_item["next_page"] == 3, "Resumed query MUST restart at page 3, not page 1!"

    # 8. Crawler simulates executing from next_page (page 3)
    start_page = resumed_item["next_page"]
    assert start_page == 3
    db.update_query_progress(niche=niche, query=test_query, page_num=3, status="in_progress", success=True)
    db.update_query_progress(niche=niche, query=test_query, page_num=4, status="in_progress", success=True)
    db.update_query_progress(niche=niche, query=test_query, page_num=5, status="completed", success=True)

    # Verify query is now completed
    assert db.get_next_pending_query(niche) is None
    final_checkpoint = db.get_query_queue_checkpoint(niche)
    assert final_checkpoint["completed_queries"] == 1
    assert final_checkpoint["paused_captcha_queries"] == 0


