import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "amazon.db"


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Products table (Candidate Universe with Tiers & Provenance)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asin TEXT UNIQUE,
        url TEXT,
        keyword TEXT,
        title TEXT,
        brand TEXT DEFAULT '',
        seller TEXT DEFAULT '',
        price REAL DEFAULT 0.0,
        original_price REAL DEFAULT 0.0,
        currency TEXT DEFAULT 'USD',
        rating REAL DEFAULT 0.0,
        reviews_count INTEGER DEFAULT 0,
        bought_past_month INTEGER DEFAULT 0,
        bsr_rank INTEGER DEFAULT 0,
        bsr_category TEXT DEFAULT '',
        is_sponsored INTEGER DEFAULT 0,
        is_best_seller INTEGER DEFAULT 0,
        is_amazons_choice INTEGER DEFAULT 0,
        prime_eligible INTEGER DEFAULT 0,
        image_url TEXT DEFAULT '',
        score REAL DEFAULT 0.0,
        tier TEXT DEFAULT 'COLD',           -- 'COLD', 'WARM', 'HOT'
        tier_reason TEXT DEFAULT 'initial_discovery',
        product_depth TEXT DEFAULT 'SHALLOW', -- 'SHALLOW', 'BASIC', 'FULL'
        review_depth TEXT DEFAULT 'NONE',    -- 'NONE', 'PARTIAL', 'FULL'
        discovery_lane TEXT DEFAULT 'keyword_search', -- 'keyword_search', 'brand_expansion', 'suggestions', 'category', 'related'
        discovered_via_query TEXT DEFAULT '',
        discovered_via_asin TEXT DEFAULT '',
        first_observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        previous_price REAL DEFAULT 0.0,
        price_delta REAL DEFAULT 0.0,
        previous_reviews_count INTEGER DEFAULT 0,
        review_velocity REAL DEFAULT 0.0,   -- reviews added / time period
        promotion_score REAL DEFAULT 0.0,
        variant_count INTEGER DEFAULT 1,
        availability TEXT DEFAULT 'In Stock',
        raw_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Migration for new columns if table existed previously
    cursor.execute("PRAGMA table_info(products)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    new_cols = [
        ("tier", "TEXT DEFAULT 'COLD'"),
        ("tier_reason", "TEXT DEFAULT 'initial_discovery'"),
        ("product_depth", "TEXT DEFAULT 'SHALLOW'"),
        ("review_depth", "TEXT DEFAULT 'NONE'"),
        ("discovery_lane", "TEXT DEFAULT 'keyword_search'"),
        ("discovered_via_query", "TEXT DEFAULT ''"),
        ("discovered_via_asin", "TEXT DEFAULT ''"),
        ("first_observed_at", "TIMESTAMP"),
        ("last_observed_at", "TIMESTAMP"),
        ("previous_price", "REAL DEFAULT 0.0"),
        ("price_delta", "REAL DEFAULT 0.0"),
        ("previous_reviews_count", "INTEGER DEFAULT 0"),
        ("review_velocity", "REAL DEFAULT 0.0"),
        ("promotion_score", "REAL DEFAULT 0.0"),
        ("variant_count", "INTEGER DEFAULT 1"),
        ("availability", "TEXT DEFAULT 'In Stock'"),
        ("enrichment_status", "TEXT DEFAULT 'discovered'"),
        ("parent_asin", "TEXT DEFAULT ''"),
        ("is_parent", "INTEGER DEFAULT 0"),
        ("variation_dimensions_json", "TEXT DEFAULT '{}'"),
        ("child_asins_json", "TEXT DEFAULT '[]'"),
        ("completeness_status", "TEXT DEFAULT 'partial'"),
        ("visible_total_reviews", "INTEGER DEFAULT 0"),
        ("reviews_collected", "INTEGER DEFAULT 0"),
        ("collection_method", "TEXT DEFAULT 'tiered_sample'"),
        ("review_coverage", "TEXT DEFAULT 'unknown'"),
        ("filters_applied", "TEXT DEFAULT ''")
    ]
    for col_name, col_def in new_cols:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
            except Exception as e:
                print(f"[DB Migration Notice] Add {col_name}: {e}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_kw ON products(keyword)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_tier ON products(tier)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_lane ON products(discovery_lane)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_bsr ON products(bsr_rank)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sales ON products(bought_past_month DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_promotion ON products(promotion_score DESC)")

    # 2. Product Snapshots table (Historical observation points)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asin TEXT,
        keyword TEXT,
        price REAL DEFAULT 0.0,
        rating REAL DEFAULT 0.0,
        reviews_count INTEGER DEFAULT 0,
        bought_past_month INTEGER DEFAULT 0,
        bsr_rank INTEGER DEFAULT 0,
        is_sponsored INTEGER DEFAULT 0,
        observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asin) REFERENCES products(asin)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_asin ON product_snapshots(asin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON product_snapshots(observed_at)")

    # 3. Coverage Ledger table (Denominators, Marginal Yield & Discovery Saturation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coverage_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        niche TEXT,
        lane TEXT,                           -- 'keyword_search', 'category', 'brand', 'suggestions', 'related'
        query_or_target TEXT,
        page_number INTEGER DEFAULT 1,
        asins_found_total INTEGER DEFAULT 0,
        asins_new_unique INTEGER DEFAULT 0,
        asins_duplicate INTEGER DEFAULT 0,
        marginal_yield REAL DEFAULT 0.0,    -- asins_new_unique / asins_found_total
        cumulative_unique INTEGER DEFAULT 0,
        status TEXT DEFAULT 'success',       -- 'success', 'blocked', 'empty', 'error'
        strategy_used TEXT DEFAULT 'http_fast', -- 'http_fast', 'playwright_browser'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_niche ON coverage_ledger(niche)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_session ON coverage_ledger(session_id)")

    # 3.1 Niche Products Junction Table (Entity & Membership Decoupled)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS niche_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        niche TEXT NOT NULL,
        asin TEXT NOT NULL,
        tier TEXT DEFAULT 'COLD',
        tier_reason TEXT DEFAULT 'initial_discovery',
        discovery_lane TEXT DEFAULT 'keyword_search',
        discovered_via_query TEXT DEFAULT '',
        score REAL DEFAULT 0.0,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(niche, asin)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_niche_prod_niche ON niche_products(niche)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_niche_prod_asin ON niche_products(asin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_niche_prod_tier ON niche_products(niche, tier)")

    # Auto-populate niche_products from products if empty
    cursor.execute("SELECT COUNT(*) FROM niche_products")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT OR IGNORE INTO niche_products (niche, asin, tier, tier_reason, discovery_lane, discovered_via_query, score, added_at, updated_at)
        SELECT keyword, asin, tier, tier_reason, discovery_lane, discovered_via_query, score, created_at, updated_at
        FROM products
        WHERE keyword IS NOT NULL AND length(keyword) > 0
        """)

    # 3.2 Product Variations Table (Explicit Parent/Child Dimension Mapping)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_variations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_asin TEXT NOT NULL,
        child_asin TEXT NOT NULL,
        dimensions_json TEXT DEFAULT '{}',
        price REAL DEFAULT 0.0,
        availability TEXT DEFAULT 'UNKNOWN',
        image_url TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(parent_asin, child_asin)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variant_parent ON product_variations(parent_asin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_variant_child ON product_variations(child_asin)")

    # 4. Discovery Query Queue (Multi-lane expansion & page-level checkpoint)
    cursor.execute("PRAGMA table_info(discovery_query_queue)")
    q_cols = {row[1] for row in cursor.fetchall()}
    if "next_page" not in q_cols:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS discovery_query_queue_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            niche TEXT NOT NULL,
            lane TEXT DEFAULT 'keyword_search',
            query TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 1,
            target_pages INTEGER DEFAULT 3,
            last_completed_page INTEGER DEFAULT 0,
            next_page INTEGER DEFAULT 1,
            retry_count INTEGER DEFAULT 0,
            last_error TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(niche, query)
        )
        """)
        cursor.execute("""
        INSERT OR IGNORE INTO discovery_query_queue_v2 (id, niche, lane, query, status, priority, created_at)
        SELECT id, niche, lane, query, status, priority, created_at FROM discovery_query_queue
        """)
        cursor.execute("DROP TABLE discovery_query_queue")
        cursor.execute("ALTER TABLE discovery_query_queue_v2 RENAME TO discovery_query_queue")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_queue ON discovery_query_queue(niche, status)")

    # 5. Customer Reviews table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id TEXT UNIQUE,
        asin TEXT,
        keyword TEXT,
        reviewer_name TEXT DEFAULT '',
        star_rating INTEGER DEFAULT 5,
        review_title TEXT DEFAULT '',
        review_text TEXT DEFAULT '',
        review_date TEXT DEFAULT '',
        verified_purchase INTEGER DEFAULT 1,
        helpful_votes INTEGER DEFAULT 0,
        variant_reviewed TEXT DEFAULT '',
        sentiment TEXT DEFAULT 'unknown',
        raw_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asin) REFERENCES products(asin)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_asin ON reviews(asin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_kw ON reviews(keyword)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews(sentiment)")

    # 6. Crawl Jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crawl_jobs (
        job_id TEXT PRIMARY KEY,
        keyword TEXT,
        status TEXT,
        progress INTEGER DEFAULT 0,
        message TEXT,
        new_products_count INTEGER DEFAULT 0,
        new_reviews_count INTEGER DEFAULT 0,
        cumulative_universe_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("PRAGMA table_info(crawl_jobs)")
    existing_job_cols = {row["name"] for row in cursor.fetchall()}
    for col, col_t in [("new_products_count", "INTEGER DEFAULT 0"), ("new_reviews_count", "INTEGER DEFAULT 0"), ("cumulative_universe_count", "INTEGER DEFAULT 0")]:
        if col not in existing_job_cols:
            try:
                cursor.execute(f"ALTER TABLE crawl_jobs ADD COLUMN {col} {col_t}")
            except Exception:
                pass

    # 7. Niche Folders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS niche_folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. Sponsored Ads table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sponsored_ads (
        id TEXT PRIMARY KEY,
        asin TEXT,
        keyword TEXT,
        position INTEGER DEFAULT 0,
        title TEXT,
        price REAL DEFAULT 0.0,
        rating REAL DEFAULT 0.0,
        reviews_count INTEGER DEFAULT 0,
        brand TEXT DEFAULT '',
        image_url TEXT DEFAULT '',
        raw_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 9. Best Sellers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS best_sellers (
        id TEXT PRIMARY KEY,
        asin TEXT,
        category TEXT,
        rank INTEGER DEFAULT 0,
        title TEXT,
        price REAL DEFAULT 0.0,
        rating REAL DEFAULT 0.0,
        reviews_count INTEGER DEFAULT 0,
        image_url TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 10. Master AI Analysis table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS master_analysis (
        keyword TEXT,
        engine TEXT DEFAULT 'gemini',
        summary TEXT,
        product_flaws_json TEXT,
        buying_triggers_json TEXT,
        sourcing_directives_json TEXT,
        listing_blueprint TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (keyword, engine)
    )
    """)

    # 11. VoC Insights Summary table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voc_insights (
        keyword TEXT PRIMARY KEY,
        total_analyzed INTEGER DEFAULT 0,
        critical_count INTEGER DEFAULT 0,
        positive_count INTEGER DEFAULT 0,
        pillars_json TEXT,
        sourcing_recommendations_json TEXT,
        frequent_phrases_json TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 12. Search Observations table (Decoupled Ads vs Organic search card observations)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        niche TEXT,
        asin TEXT NOT NULL,
        query TEXT NOT NULL,
        page INTEGER DEFAULT 1,
        position INTEGER DEFAULT 1,
        placement_type TEXT CHECK(placement_type IN ('SPONSORED', 'ORGANIC', 'UNKNOWN')),
        confidence TEXT DEFAULT 'HIGH', -- 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'
        sponsored_evidence TEXT, -- 'label_observed', 'ad_markup', 'organic_container', 'ambiguous_markup'
        evidence_signals_json TEXT DEFAULT '[]',
        badges_json TEXT,
        coupon TEXT,
        delivery_signal TEXT,
        price REAL DEFAULT 0.0,
        rating REAL DEFAULT 0.0,
        reviews_count INTEGER DEFAULT 0,
        observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asin) REFERENCES products(asin)
    )
    """)
    cursor.execute("PRAGMA table_info(search_observations)")
    existing_obs_cols = {row["name"] for row in cursor.fetchall()}
    for col, col_t in [("confidence", "TEXT DEFAULT 'HIGH'"), ("evidence_signals_json", "TEXT DEFAULT '[]'")]:
        if col not in existing_obs_cols:
            try:
                cursor.execute(f"ALTER TABLE search_observations ADD COLUMN {col} {col_t}")
            except Exception:
                pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_asin ON search_observations(asin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_asin_query ON search_observations(asin, query)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_run ON search_observations(run_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_niche ON search_observations(niche)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_placement ON search_observations(placement_type)")

    # 13. Research Runs table (Tracking runs, query universe, failures, coverage)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS research_runs (
        run_id TEXT PRIMARY KEY,
        niche TEXT NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        queries_executed INTEGER DEFAULT 0,
        unique_asins INTEGER DEFAULT 0,
        brands_count INTEGER DEFAULT 0,
        sellers_count INTEGER DEFAULT 0,
        total_observations INTEGER DEFAULT 0,
        sponsored_observations INTEGER DEFAULT 0,
        organic_observations INTEGER DEFAULT 0,
        unknown_observations INTEGER DEFAULT 0,
        products_enriched INTEGER DEFAULT 0,
        full_detail_count INTEGER DEFAULT 0,
        review_crawled_count INTEGER DEFAULT 0,
        reviews_collected INTEGER DEFAULT 0,
        new_asins_this_run INTEGER DEFAULT 0,
        changed_products INTEGER DEFAULT 0,
        failures_403 INTEGER DEFAULT 0,
        failures_429 INTEGER DEFAULT 0,
        parser_partial INTEGER DEFAULT 0,
        discovery_status TEXT DEFAULT 'running',
        true_market_coverage TEXT DEFAULT 'UNKNOWN',
        summary_json TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_niche ON research_runs(niche)")

    # 14. Brand Entities table (Cross-source hooks to Shopify/TikTok/etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS brand_entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        niche TEXT,
        asin_count INTEGER DEFAULT 0,
        cross_source_hooks_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brands_niche ON brand_entities(niche)")

    # 15. Diagnostics Log table (amkarpe pattern: HTML snapshot & Screenshot dumps)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostics_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        niche TEXT,
        query_or_asin TEXT,
        status TEXT, -- 'captcha_detected', 'zero_cards', 'blocked_403', 'rate_limited_429', 'parser_error'
        reason TEXT,
        html_path TEXT,
        screenshot_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_niche ON diagnostics_log(niche)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_status ON diagnostics_log(status)")

    conn.commit()
    conn.close()


# ---------------------------------------------------------
# Candidate Universe Products Operations
# ---------------------------------------------------------

def get_existing_asins(keyword: Optional[str] = None) -> Tuple[set, set]:
    conn = get_db()
    cursor = conn.cursor()
    if keyword:
        cursor.execute("SELECT p.asin, p.url FROM products p JOIN niche_products np ON p.asin = np.asin WHERE np.niche = ?", (keyword,))
        rows = cursor.fetchall()
        if not rows:
            cursor.execute("SELECT asin, url FROM products WHERE keyword = ?", (keyword,))
            rows = cursor.fetchall()
    else:
        cursor.execute("SELECT asin, url FROM products")
        rows = cursor.fetchall()
    conn.close()
    asins = {r["asin"] for r in rows if r["asin"]}
    urls = {r["url"] for r in rows if "url" in r.keys() and r["url"]}
    return asins, urls


def save_product(p: Dict[str, Any], record_snapshot: bool = True) -> bool:
    """
    Insert or update a candidate product in SQLite.
    Preserves COLD/WARM/HOT tiers, calculates price/review changes, and records snapshots.
    """
    conn = get_db()
    cursor = conn.cursor()
    asin = p.get("asin")
    if not asin:
        conn.close()
        return False

    try:
        # Check if already exists to compute deltas
        cursor.execute("SELECT price, reviews_count, tier, score FROM products WHERE asin = ?", (asin,))
        existing = cursor.fetchone()

        new_price = float(p.get("price") or 0.0)
        new_revs = int(p.get("reviews_count") or 0)

        prev_price = existing["price"] if existing else new_price
        prev_revs = existing["reviews_count"] if existing else new_revs
        existing_tier = existing["tier"] if existing else (p.get("tier") or "COLD")

        price_delta = round(new_price - prev_price, 2)
        rev_delta = max(0, new_revs - prev_revs)

        # Retain higher tier if already promoted
        tier_hierarchy = {"COLD": 1, "WARM": 2, "HOT": 3}
        incoming_tier = p.get("tier") or "COLD"
        final_tier = existing_tier if tier_hierarchy.get(existing_tier, 1) >= tier_hierarchy.get(incoming_tier, 1) else incoming_tier

        raw_json = json.dumps(p, ensure_ascii=False)

        cursor.execute("""
        INSERT INTO products (
            asin, url, keyword, title, brand, seller, price, original_price,
            currency, rating, reviews_count, bought_past_month, bsr_rank,
            bsr_category, is_sponsored, is_best_seller, is_amazons_choice,
            prime_eligible, image_url, score, tier, tier_reason, product_depth,
            review_depth, discovery_lane, discovered_via_query, discovered_via_asin,
            first_observed_at, last_observed_at, previous_price, price_delta,
            previous_reviews_count, review_velocity, promotion_score, variant_count,
            availability, parent_asin, is_parent, variation_dimensions_json, child_asins_json,
            completeness_status, visible_total_reviews, reviews_collected,
            collection_method, review_coverage, filters_applied, raw_json, updated_at
        ) VALUES (
            :asin, :url, :keyword, :title, :brand, :seller, :price, :original_price,
            :currency, :rating, :reviews_count, :bought_past_month, :bsr_rank,
            :bsr_category, :is_sponsored, :is_best_seller, :is_amazons_choice,
            :prime_eligible, :image_url, :score, :tier, :tier_reason, :product_depth,
            :review_depth, :discovery_lane, :discovered_via_query, :discovered_via_asin,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :previous_price, :price_delta,
            :previous_reviews_count, :review_velocity, :promotion_score, :variant_count,
            :availability, :parent_asin, :is_parent, :variation_dimensions_json, :child_asins_json,
            :completeness_status, :visible_total_reviews, :reviews_collected,
            :collection_method, :review_coverage, :filters_applied, :raw_json, CURRENT_TIMESTAMP
        )
        ON CONFLICT(asin) DO UPDATE SET
            keyword=COALESCE(excluded.keyword, products.keyword),
            title=CASE WHEN length(excluded.title) > 0 THEN excluded.title ELSE products.title END,
            brand=CASE WHEN length(excluded.brand) > 0 THEN excluded.brand ELSE products.brand END,
            seller=CASE WHEN length(excluded.seller) > 0 THEN excluded.seller ELSE products.seller END,
            price=CASE 
                WHEN excluded.product_depth = 'FULL' AND excluded.price > 0 THEN excluded.price
                WHEN products.price > 0 THEN products.price
                WHEN excluded.price > 0 THEN excluded.price
                ELSE products.price
            END,
            original_price=CASE 
                WHEN excluded.product_depth = 'FULL' AND excluded.original_price > 0 THEN excluded.original_price
                WHEN products.original_price > 0 THEN products.original_price
                WHEN excluded.original_price > 0 THEN excluded.original_price
                ELSE products.original_price
            END,
            rating=CASE 
                WHEN excluded.product_depth = 'FULL' AND excluded.rating > 0 THEN excluded.rating
                WHEN products.rating > 0 THEN products.rating
                WHEN excluded.rating > 0 THEN excluded.rating
                ELSE products.rating
            END,
            reviews_count=CASE 
                WHEN excluded.product_depth = 'FULL' AND excluded.reviews_count > 0 THEN excluded.reviews_count
                WHEN products.reviews_count > 0 THEN products.reviews_count
                WHEN excluded.reviews_count > 0 THEN excluded.reviews_count
                ELSE products.reviews_count
            END,
            bought_past_month=CASE WHEN excluded.bought_past_month > 0 THEN excluded.bought_past_month ELSE products.bought_past_month END,
            bsr_rank=CASE WHEN excluded.bsr_rank > 0 THEN excluded.bsr_rank ELSE products.bsr_rank END,
            bsr_category=CASE WHEN length(excluded.bsr_category) > 0 THEN excluded.bsr_category ELSE products.bsr_category END,
            is_sponsored=excluded.is_sponsored,
            is_best_seller=CASE WHEN excluded.is_best_seller = 1 THEN 1 ELSE products.is_best_seller END,
            is_amazons_choice=CASE WHEN excluded.is_amazons_choice = 1 THEN 1 ELSE products.is_amazons_choice END,
            prime_eligible=excluded.prime_eligible,
            image_url=CASE WHEN length(excluded.image_url) > 0 THEN excluded.image_url ELSE products.image_url END,
            score=CASE WHEN excluded.score > 0 THEN excluded.score ELSE products.score END,
            tier=CASE WHEN excluded.tier != 'COLD' THEN excluded.tier ELSE products.tier END,
            tier_reason=CASE WHEN excluded.tier != 'COLD' THEN excluded.tier_reason ELSE products.tier_reason END,
            product_depth=CASE WHEN products.product_depth = 'FULL' THEN 'FULL' ELSE excluded.product_depth END,
            availability=CASE WHEN excluded.availability != 'UNKNOWN' THEN excluded.availability ELSE products.availability END,
            last_observed_at=CURRENT_TIMESTAMP,
            previous_price=:previous_price,
            price_delta=:price_delta,
            previous_reviews_count=:previous_reviews_count,
            review_velocity=:review_velocity,
            parent_asin=CASE WHEN length(excluded.parent_asin) > 0 THEN excluded.parent_asin ELSE products.parent_asin END,
            is_parent=CASE WHEN excluded.is_parent = 1 THEN 1 ELSE products.is_parent END,
            variation_dimensions_json=CASE WHEN length(excluded.variation_dimensions_json) > 2 THEN excluded.variation_dimensions_json ELSE products.variation_dimensions_json END,
            child_asins_json=CASE WHEN length(excluded.child_asins_json) > 2 THEN excluded.child_asins_json ELSE products.child_asins_json END,
            completeness_status=COALESCE(excluded.completeness_status, products.completeness_status),
            visible_total_reviews=CASE WHEN excluded.visible_total_reviews > 0 THEN excluded.visible_total_reviews ELSE products.visible_total_reviews END,
            reviews_collected=CASE WHEN excluded.reviews_collected > 0 THEN excluded.reviews_collected ELSE products.reviews_collected END,
            collection_method=COALESCE(excluded.collection_method, products.collection_method),
            review_coverage=COALESCE(excluded.review_coverage, products.review_coverage),
            filters_applied=COALESCE(excluded.filters_applied, products.filters_applied),
            raw_json=excluded.raw_json,
            updated_at=CURRENT_TIMESTAMP
        """, {
            "asin": asin,
            "url": p.get("url") or f"https://www.amazon.com/dp/{asin}",
            "keyword": p.get("keyword") or "default",
            "title": p.get("title") or "",
            "brand": p.get("brand") or "",
            "seller": p.get("seller") or "",
            "price": new_price,
            "original_price": float(p.get("original_price") or new_price),
            "currency": p.get("currency") or "USD",
            "rating": float(p.get("rating") or 0.0),
            "reviews_count": new_revs,
            "bought_past_month": int(p.get("bought_past_month") or 0),
            "bsr_rank": int(p.get("bsr_rank") or 0),
            "bsr_category": p.get("bsr_category") or "",
            "is_sponsored": 1 if p.get("is_sponsored") else 0,
            "is_best_seller": 1 if p.get("is_best_seller") else 0,
            "is_amazons_choice": 1 if p.get("is_amazons_choice") else 0,
            "prime_eligible": 1 if p.get("prime_eligible") else 0,
            "image_url": p.get("image_url") or "",
            "score": float(p.get("score") or 0.0),
            "tier": final_tier,
            "tier_reason": p.get("tier_reason") or "initial_discovery",
            "product_depth": p.get("product_depth") or "SHALLOW",
            "review_depth": p.get("review_depth") or "NONE",
            "discovery_lane": p.get("discovery_lane") or "keyword_search",
            "discovered_via_query": p.get("discovered_via_query") or "",
            "discovered_via_asin": p.get("discovered_via_asin") or "",
            "previous_price": prev_price,
            "price_delta": price_delta,
            "previous_reviews_count": prev_revs,
            "review_velocity": float(p.get("review_velocity") or rev_delta),
            "promotion_score": float(p.get("promotion_score") or 0.0),
            "variant_count": int(p.get("variant_count") or 1),
            "availability": p.get("availability") or "UNKNOWN",
            "parent_asin": p.get("parent_asin") or "",
            "is_parent": int(p.get("is_parent") or 0),
            "variation_dimensions_json": json.dumps(p.get("variation_dimensions") or {}, ensure_ascii=False) if isinstance(p.get("variation_dimensions"), dict) else (p.get("variation_dimensions_json") or "{}"),
            "child_asins_json": json.dumps(p.get("child_asins") or [], ensure_ascii=False) if isinstance(p.get("child_asins"), list) else (p.get("child_asins_json") or "[]"),
            "completeness_status": p.get("completeness_status") or ("complete" if new_price > 0 and new_revs > 0 else "partial"),
            "visible_total_reviews": int(p.get("visible_total_reviews") or new_revs),
            "reviews_collected": int(p.get("reviews_collected") or 0),
            "collection_method": p.get("collection_method") or "tiered_sample",
            "review_coverage": p.get("review_coverage") or "unknown",
            "filters_applied": p.get("filters_applied") or "",
            "raw_json": raw_json
        })

        # Multi-niche membership persistence (Decouple canonical entity from niche)
        niche_name = p.get("keyword") or "default"
        cursor.execute("""
        INSERT INTO niche_products (
            niche, asin, tier, tier_reason, discovery_lane, discovered_via_query, score, updated_at
        ) VALUES (
            :niche, :asin, :tier, :tier_reason, :discovery_lane, :discovered_via_query, :score, CURRENT_TIMESTAMP
        )
        ON CONFLICT(niche, asin) DO UPDATE SET
            tier = CASE WHEN excluded.tier != 'COLD' THEN excluded.tier ELSE niche_products.tier END,
            tier_reason = CASE WHEN excluded.tier != 'COLD' THEN excluded.tier_reason ELSE niche_products.tier_reason END,
            score = CASE WHEN excluded.score > 0 THEN excluded.score ELSE niche_products.score END,
            updated_at = CURRENT_TIMESTAMP
        """, {
            "niche": niche_name,
            "asin": asin,
            "tier": incoming_tier,
            "tier_reason": p.get("tier_reason") or "initial_discovery",
            "discovery_lane": p.get("discovery_lane") or "keyword_search",
            "discovered_via_query": p.get("discovered_via_query") or "",
            "score": float(p.get("score") or 0.0)
        })

        if record_snapshot:
            # Throttle snapshot: only 1 snapshot per ASIN per 6 hours to prevent massive duplicate rows
            cursor.execute("""
            SELECT id FROM product_snapshots 
            WHERE asin = ? AND datetime(observed_at) >= datetime('now', '-6 hours')
            LIMIT 1
            """, (asin,))
            if not cursor.fetchone():
                cursor.execute("""
                INSERT INTO product_snapshots (
                    asin, keyword, price, rating, reviews_count,
                    bought_past_month, bsr_rank, is_sponsored, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    asin,
                    niche_name,
                    new_price,
                    float(p.get("rating") or 0.0),
                    new_revs,
                    int(p.get("bought_past_month") or 0),
                    int(p.get("bsr_rank") or 0),
                    1 if p.get("is_sponsored") else 0
                ))

        conn.commit()
        return True
    except Exception as e:
        print(f"[DB Error] save_product {asin}: {e}")
        return False
    finally:
        conn.close()


def batch_save_products(products: List[Dict[str, Any]], record_snapshot: bool = True) -> int:
    saved = 0
    for p in products:
        if save_product(p, record_snapshot=record_snapshot):
            saved += 1
    return saved


def update_product_tier(asin: str, new_tier: str, reason: str = "", promotion_score: float = None, niche: Optional[str] = None) -> bool:
    """Promote or transition product lifecycle tier (COLD -> WARM -> HOT)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        sql = "UPDATE products SET tier = ?, tier_reason = ?, updated_at = CURRENT_TIMESTAMP"
        params = [new_tier, reason]
        if promotion_score is not None:
            sql += ", promotion_score = ?"
            params.append(promotion_score)
        sql += " WHERE asin = ?"
        params.append(asin)
        cursor.execute(sql, tuple(params))

        if niche:
            n_sql = "UPDATE niche_products SET tier = ?, tier_reason = ?, updated_at = CURRENT_TIMESTAMP"
            n_params = [new_tier, reason]
            if promotion_score is not None:
                n_sql += ", score = ?"
                n_params.append(promotion_score)
            n_sql += " WHERE asin = ? AND niche = ?"
            n_params.extend([asin, niche])
            cursor.execute(n_sql, tuple(n_params))

        conn.commit()
        return True
    except Exception as e:
        print(f"[DB Error] update_product_tier {asin}: {e}")
        return False
    finally:
        conn.close()


def get_product_by_asin(asin: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE asin = ?", (asin.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_products(
    keyword: Optional[str] = None,
    tier: Optional[str] = None,
    discovery_lane: Optional[str] = None,
    sort_by: str = "score DESC",
    min_rating: Optional[float] = None,
    is_sponsored: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()

    params = []
    if keyword:
        sql = """
        SELECT p.*,
               np.tier as niche_tier,
               np.tier_reason as niche_tier_reason,
               np.discovery_lane as niche_discovery_lane,
               np.discovered_via_query as niche_discovered_via_query,
               np.score as niche_score,
               np.niche
        FROM products p
        JOIN niche_products np ON p.asin = np.asin
        WHERE np.niche = ?
        """
        params.append(keyword)

        if tier:
            sql += " AND np.tier = ?"
            params.append(tier)

        if discovery_lane:
            sql += " AND np.discovery_lane = ?"
            params.append(discovery_lane)
    else:
        sql = "SELECT p.* FROM products p WHERE 1=1"
        if tier:
            sql += " AND p.tier = ?"
            params.append(tier)
        if discovery_lane:
            sql += " AND p.discovery_lane = ?"
            params.append(discovery_lane)

    if min_rating is not None:
        sql += " AND p.rating >= ?"
        params.append(min_rating)

    if is_sponsored is not None:
        sql += " AND p.is_sponsored = ?"
        params.append(is_sponsored)

    allowed_sorts = {
        "score DESC": "COALESCE(np.score, p.score) DESC" if keyword else "p.score DESC",
        "bought_past_month DESC": "p.bought_past_month DESC",
        "rating DESC": "p.rating DESC",
        "reviews_count DESC": "p.reviews_count DESC",
        "price ASC": "p.price ASC",
        "price DESC": "p.price DESC",
        "bsr_rank ASC": "p.bsr_rank ASC",
        "promotion_score DESC": "p.promotion_score DESC",
        "review_velocity DESC": "p.review_velocity DESC",
        "created_at DESC": "p.created_at DESC"
    }
    order_clause = allowed_sorts.get(sort_by, "COALESCE(np.score, p.score) DESC" if keyword else "p.score DESC")
    sql += f" ORDER BY {order_clause} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        if keyword:
            d["tier"] = d.pop("niche_tier", d.get("tier"))
            d["tier_reason"] = d.pop("niche_tier_reason", d.get("tier_reason"))
            d["discovery_lane"] = d.pop("niche_discovery_lane", d.get("discovery_lane"))
            d["discovered_via_query"] = d.pop("niche_discovered_via_query", d.get("discovered_via_query"))
            d["score"] = d.pop("niche_score", d.get("score"))
        result.append(d)
    return result


def get_candidate_universe_summary(keyword: str) -> Dict[str, Any]:
    """Returns candidate universe statistics: total discovered, cold/warm/hot counts, lane breakdowns."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            COUNT(*) as total_candidates,
            SUM(CASE WHEN np.tier = 'COLD' THEN 1 ELSE 0 END) as cold_count,
            SUM(CASE WHEN np.tier = 'WARM' THEN 1 ELSE 0 END) as warm_count,
            SUM(CASE WHEN np.tier = 'HOT' THEN 1 ELSE 0 END) as hot_count,
            AVG(p.price) as avg_price,
            AVG(p.rating) as avg_rating,
            SUM(p.bought_past_month) as total_monthly_sales
        FROM products p
        JOIN niche_products np ON p.asin = np.asin
        WHERE np.niche = ?
    """, (keyword,))
    summary_row = cursor.fetchone()

    cursor.execute("""
        SELECT np.discovery_lane, COUNT(*) as count
        FROM niche_products np
        WHERE np.niche = ?
        GROUP BY np.discovery_lane
    """, (keyword,))
    lane_rows = cursor.fetchall()

    conn.close()

    return {
        "keyword": keyword,
        "total_candidates": summary_row["total_candidates"] if summary_row else 0,
        "cold_count": summary_row["cold_count"] if summary_row else 0,
        "warm_count": summary_row["warm_count"] if summary_row else 0,
        "hot_count": summary_row["hot_count"] if summary_row else 0,
        "avg_price": round(summary_row["avg_price"] or 0.0, 2) if summary_row else 0.0,
        "avg_rating": round(summary_row["avg_rating"] or 0.0, 1) if summary_row else 0.0,
        "total_monthly_sales": summary_row["total_monthly_sales"] if summary_row else 0,
        "lanes": {r["discovery_lane"]: r["count"] for r in lane_rows}
    }


# ---------------------------------------------------------
# Coverage Ledger & Discovery Saturation
# ---------------------------------------------------------

def record_coverage_ledger_entry(
    session_id: str,
    niche: str,
    lane: str,
    query_or_target: str,
    page_number: int,
    asins_found_total: int,
    asins_new_unique: int,
    asins_duplicate: int,
    cumulative_unique: int,
    status: str = "success",
    strategy_used: str = "http_fast"
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    marginal_yield = round((asins_new_unique / asins_found_total * 100), 2) if asins_found_total > 0 else 0.0
    cursor.execute("""
    INSERT INTO coverage_ledger (
        session_id, niche, lane, query_or_target, page_number,
        asins_found_total, asins_new_unique, asins_duplicate,
        marginal_yield, cumulative_unique, status, strategy_used
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, niche, lane, query_or_target, page_number,
        asins_found_total, asins_new_unique, asins_duplicate,
        marginal_yield, cumulative_unique, status, strategy_used
    ))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def get_coverage_ledger(niche: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM coverage_ledger
        WHERE niche = ?
        ORDER BY id DESC
        LIMIT ?
    """, (niche, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_saturation_curve(niche: str) -> List[Dict[str, Any]]:
    """Returns chronological data points of cumulative ASINs and marginal yield to render saturation curve."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, lane, query_or_target, page_number, asins_new_unique,
               cumulative_unique, marginal_yield, strategy_used, created_at
        FROM coverage_ledger
        WHERE niche = ?
        ORDER BY id ASC
    """, (niche,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------
# Product Snapshots History
# ---------------------------------------------------------

def get_product_snapshots(asin: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM product_snapshots
        WHERE asin = ?
        ORDER BY observed_at ASC
        LIMIT ?
    """, (asin, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------
# Dynamic Priority Queue & Selection Taxonomy
# ---------------------------------------------------------

def get_priority_candidates(
    keyword: str,
    taxonomy: str = "all",
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Query candidate universe across distinct selection taxonomy:
    - 'top_performers': high sales velocity / BSR
    - 'emerging_winners': high sales with lower review count or high velocity
    - 'review_velocity_outliers': fastest growing review counts
    - 'price_outliers': extreme high or low price points
    - 'high_complaints': high sales but rating <= 3.9 (VoC goldmine)
    - 'ad_active': sponsored products
    - 'long_tail': random representative sample of cold long-tail
    """
    conn = get_db()
    cursor = conn.cursor()

    base_sql = "SELECT * FROM products WHERE keyword = ?"
    params = [keyword]

    if taxonomy == "top_performers":
        base_sql += " ORDER BY bought_past_month DESC, score DESC"
    elif taxonomy == "emerging_winners":
        base_sql += " AND bought_past_month >= 500 AND reviews_count <= 2000 ORDER BY bought_past_month DESC"
    elif taxonomy == "review_velocity_outliers":
        base_sql += " ORDER BY review_velocity DESC, reviews_count ASC"
    elif taxonomy == "price_outliers":
        base_sql += " ORDER BY price DESC"
    elif taxonomy == "high_complaints":
        base_sql += " AND rating <= 3.9 AND bought_past_month >= 300 ORDER BY bought_past_month DESC"
    elif taxonomy == "ad_active":
        base_sql += " AND is_sponsored = 1 ORDER BY score DESC"
    elif taxonomy == "long_tail":
        base_sql += " AND tier = 'COLD' ORDER BY RANDOM()"
    else:
        base_sql += " ORDER BY promotion_score DESC, score DESC"

    base_sql += " LIMIT ?"
    params.append(limit)

    cursor.execute(base_sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------
# Standard Operations (Reviews, Jobs, Folders, Ads, AI)
# ---------------------------------------------------------

def save_reviews(
    asin: str,
    keyword: str,
    reviews_list: List[Dict[str, Any]],
    visible_total_reviews: int = 0,
    collection_method: str = "representative_polarity",
    filters_applied: Optional[List[str]] = None
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    saved = 0
    for r in reviews_list:
        rid = r.get("review_id") or f"{asin}_{hash(r.get('review_text', ''))}"
        stars = int(r.get("star_rating") or 5)
        sentiment = "critical" if stars <= 3 else ("positive" if stars == 5 else "neutral")

        try:
            cursor.execute("""
            INSERT INTO reviews (
                review_id, asin, keyword, reviewer_name, star_rating,
                review_title, review_text, review_date, verified_purchase,
                helpful_votes, variant_reviewed, sentiment, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(review_id) DO UPDATE SET
                reviewer_name=excluded.reviewer_name,
                star_rating=excluded.star_rating,
                review_title=excluded.review_title,
                review_text=excluded.review_text,
                helpful_votes=excluded.helpful_votes,
                sentiment=excluded.sentiment
            """, (
                rid,
                asin,
                keyword,
                r.get("reviewer_name") or "",
                stars,
                r.get("review_title") or "",
                r.get("review_text") or "",
                r.get("review_date") or "",
                1 if r.get("verified_purchase", False) else 0,
                int(r.get("helpful_votes") or 0),
                r.get("variant_reviewed") or "",
                sentiment,
                json.dumps(r, ensure_ascii=False)
            ))
            saved += 1
        except Exception as e:
            print(f"[DB Notice] save review {rid}: {e}")

    # Update Review Collection Policy coverage metadata in products table
    if saved > 0 or len(reviews_list) > 0:
        cursor.execute("SELECT reviews_count FROM products WHERE asin = ?", (asin,))
        p_row = cursor.fetchone()
        vt = visible_total_reviews or (p_row["reviews_count"] if p_row else 0) or len(reviews_list)
        coverage_pct = round((len(reviews_list) / max(1, vt)) * 100, 2)
        coverage_str = f"{len(reviews_list)}/{vt} ({coverage_pct}%)"
        filters_str = json.dumps(filters_applied or ["critical_1_3_star", "positive_5_star"])
        
        target_map = {"discovery_sample": 10, "representative_polarity": 30, "deep_hot_crawl": 60}
        target_for_policy = target_map.get(collection_method, 30)
        if len(reviews_list) >= target_for_policy or (vt > 0 and len(reviews_list) >= vt):
            depth_status = "FULL"
        elif len(reviews_list) > 0:
            depth_status = "PARTIAL"
        else:
            depth_status = "NONE"

        cursor.execute("""
        UPDATE products SET
            visible_total_reviews = ?,
            reviews_collected = ?,
            collection_method = ?,
            review_coverage = ?,
            filters_applied = ?,
            review_depth = ?,
            tier = 'HOT',
            updated_at = CURRENT_TIMESTAMP
        WHERE asin = ?
        """, (vt, len(reviews_list), collection_method, coverage_str, filters_str, depth_status, asin))

    conn.commit()
    conn.close()
    return saved


def get_reviews(
    keyword: Optional[str] = None,
    asin: Optional[str] = None,
    sentiment: Optional[str] = None,
    min_stars: Optional[int] = None,
    max_stars: Optional[int] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT * FROM reviews WHERE 1=1"
    params = []

    if keyword:
        sql += " AND keyword = ?"
        params.append(keyword)
    if asin:
        sql += " AND asin = ?"
        params.append(asin)
    if sentiment:
        sql += " AND sentiment = ?"
        params.append(sentiment)
    if min_stars is not None:
        sql += " AND star_rating >= ?"
        params.append(min_stars)
    if max_stars is not None:
        sql += " AND star_rating <= ?"
        params.append(max_stars)

    sql += " ORDER BY helpful_votes DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_job(job_id: str, keyword: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO crawl_jobs (job_id, keyword, status, progress, message)
    VALUES (?, ?, 'pending', 0, 'Khởi tạo pipeline thu thập dữ liệu...')
    """, (job_id, keyword))
    conn.commit()
    conn.close()


def update_job(
    job_id: str,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    new_products_count: Optional[int] = None,
    new_reviews_count: Optional[int] = None,
    cumulative_universe_count: Optional[int] = None
):
    conn = get_db()
    cursor = conn.cursor()
    updates = ["updated_at = CURRENT_TIMESTAMP"]
    params = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if progress is not None:
        updates.append("progress = ?")
        params.append(progress)
    if message is not None:
        updates.append("message = ?")
        params.append(message)
    if new_products_count is not None:
        updates.append("new_products_count = ?")
        params.append(new_products_count)
    if new_reviews_count is not None:
        updates.append("new_reviews_count = ?")
        params.append(new_reviews_count)
    if cumulative_universe_count is not None:
        updates.append("cumulative_universe_count = ?")
        params.append(cumulative_universe_count)

    params.append(job_id)
    sql = f"UPDATE crawl_jobs SET {', '.join(updates)} WHERE job_id = ?"
    cursor.execute(sql, tuple(params))
    conn.commit()
    conn.close()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crawl_jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_niche_folders() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT keyword as name, COUNT(*) as product_count, 
               MAX(created_at) as last_updated,
               SUM(bought_past_month) as total_sales,
               AVG(price) as avg_price,
               AVG(rating) as avg_rating
        FROM products 
        GROUP BY keyword
    """)
    product_stats = {r["name"]: dict(r) for r in cursor.fetchall()}

    cursor.execute("SELECT * FROM niche_folders ORDER BY name ASC")
    db_folders = cursor.fetchall()
    conn.close()

    result = []
    seen = set()
    for f in db_folders:
        name = f["name"]
        seen.add(name)
        st = product_stats.get(name, {})
        result.append({
            "name": name,
            "description": f["description"] or "",
            "product_count": st.get("product_count", 0),
            "total_sales": st.get("total_sales", 0),
            "avg_price": round(st.get("avg_price") or 0.0, 2),
            "avg_rating": round(st.get("avg_rating") or 0.0, 1),
            "created_at": f["created_at"]
        })

    for kw, st in product_stats.items():
        if kw not in seen:
            result.append({
                "name": kw,
                "description": "",
                "product_count": st.get("product_count", 0),
                "total_sales": st.get("total_sales", 0),
                "avg_price": round(st.get("avg_price") or 0.0, 2),
                "avg_rating": round(st.get("avg_rating") or 0.0, 1),
                "created_at": st.get("last_updated")
            })

    return sorted(result, key=lambda x: x["name"])


def create_niche_folder(name: str, description: str = "") -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO niche_folders (name, description) VALUES (?, ?)", (clean_name, description))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_niche_folder(name: str, delete_data: bool = True) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM niche_folders WHERE name = ?", (name,))
        if delete_data:
            cursor.execute("DELETE FROM products WHERE keyword = ?", (name,))
            cursor.execute("DELETE FROM reviews WHERE keyword = ?", (name,))
            cursor.execute("DELETE FROM master_analysis WHERE keyword = ?", (name,))
            cursor.execute("DELETE FROM voc_insights WHERE keyword = ?", (name,))
            cursor.execute("DELETE FROM sponsored_ads WHERE keyword = ?", (name,))
            cursor.execute("DELETE FROM coverage_ledger WHERE niche = ?", (name,))
            cursor.execute("DELETE FROM discovery_query_queue WHERE niche = ?", (name,))
        conn.commit()
        return True
    finally:
        conn.close()


def rename_niche_folder(old_name: str, new_name: str) -> bool:
    clean_old = old_name.strip()
    clean_new = new_name.strip()
    if not clean_old or not clean_new or clean_old == clean_new:
        return False
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE niche_folders SET name = ? WHERE name = ?", (clean_new, clean_old))
        cursor.execute("UPDATE products SET keyword = ? WHERE keyword = ?", (clean_new, clean_old))
        cursor.execute("UPDATE reviews SET keyword = ? WHERE keyword = ?", (clean_new, clean_old))
        cursor.execute("UPDATE master_analysis SET keyword = ? WHERE keyword = ?", (clean_new, clean_old))
        cursor.execute("UPDATE voc_insights SET keyword = ? WHERE keyword = ?", (clean_new, clean_old))
        cursor.execute("UPDATE sponsored_ads SET keyword = ? WHERE keyword = ?", (clean_new, clean_old))
        cursor.execute("UPDATE coverage_ledger SET niche = ? WHERE niche = ?", (clean_new, clean_old))
        cursor.execute("UPDATE discovery_query_queue SET niche = ? WHERE niche = ?", (clean_new, clean_old))
        conn.commit()
        return True
    finally:
        conn.close()


def merge_niche_folders(source_name: str, target_name: str) -> bool:
    s = source_name.strip()
    t = target_name.strip()
    if not s or not t or s == t:
        return False
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE products SET keyword = ? WHERE keyword = ?", (t, s))
        cursor.execute("UPDATE reviews SET keyword = ? WHERE keyword = ?", (t, s))
        cursor.execute("UPDATE sponsored_ads SET keyword = ? WHERE keyword = ?", (t, s))
        cursor.execute("UPDATE coverage_ledger SET niche = ? WHERE niche = ?", (t, s))
        cursor.execute("DELETE FROM niche_folders WHERE name = ?", (s,))
        conn.commit()
        return True
    finally:
        conn.close()


def save_sponsored_ads(ads: List[Dict[str, Any]], keyword: str = "default") -> int:
    conn = get_db()
    cursor = conn.cursor()
    saved = 0
    for idx, ad in enumerate(ads):
        asin = ad.get("asin")
        if not asin:
            continue
        ad_id = f"{keyword}_{asin}"
        try:
            cursor.execute("""
            INSERT OR REPLACE INTO sponsored_ads (
                id, asin, keyword, position, title, price, rating,
                reviews_count, brand, image_url, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ad_id,
                asin,
                keyword,
                idx + 1,
                ad.get("title") or "",
                float(ad.get("price") or 0.0),
                float(ad.get("rating") or 0.0),
                int(ad.get("reviews_count") or 0),
                ad.get("brand") or "",
                ad.get("image_url") or "",
                json.dumps(ad, ensure_ascii=False)
            ))
            saved += 1
        except Exception as e:
            print(f"[DB Notice] save sponsored ad: {e}")
    conn.commit()
    conn.close()
    return saved


def get_sponsored_ads(keyword: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if keyword:
        cursor.execute("SELECT * FROM sponsored_ads WHERE keyword = ? ORDER BY position ASC LIMIT ?", (keyword, limit))
    else:
        cursor.execute("SELECT * FROM sponsored_ads ORDER BY position ASC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_sponsored_ads(keyword: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    if keyword:
        cursor.execute("DELETE FROM sponsored_ads WHERE keyword = ?", (keyword,))
    else:
        cursor.execute("DELETE FROM sponsored_ads")
    conn.commit()
    conn.close()


def save_best_sellers(items: List[Dict[str, Any]], category: str = "general") -> int:
    conn = get_db()
    cursor = conn.cursor()
    saved = 0
    for it in items:
        asin = it.get("asin")
        rank = int(it.get("rank") or 0)
        item_id = f"{category}_{rank}_{asin}"
        try:
            cursor.execute("""
            INSERT OR REPLACE INTO best_sellers (
                id, asin, category, rank, title, price, rating, reviews_count, image_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                asin,
                category,
                rank,
                it.get("title") or "",
                float(it.get("price") or 0.0),
                float(it.get("rating") or 0.0),
                int(it.get("reviews_count") or 0),
                it.get("image_url") or ""
            ))
            saved += 1
        except Exception as e:
            print(f"[DB Notice] save best seller: {e}")
    conn.commit()
    conn.close()
    return saved


def get_best_sellers(category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if category:
        cursor.execute("SELECT * FROM best_sellers WHERE category = ? ORDER BY rank ASC LIMIT ?", (category, limit))
    else:
        cursor.execute("SELECT * FROM best_sellers ORDER BY rank ASC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_master_analysis(keyword: str, analysis: Dict[str, Any], engine: str = "gemini"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO master_analysis (
        keyword, engine, summary, product_flaws_json, buying_triggers_json,
        sourcing_directives_json, listing_blueprint, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(keyword, engine) DO UPDATE SET
        summary=excluded.summary,
        product_flaws_json=excluded.product_flaws_json,
        buying_triggers_json=excluded.buying_triggers_json,
        sourcing_directives_json=excluded.sourcing_directives_json,
        listing_blueprint=excluded.listing_blueprint,
        updated_at=CURRENT_TIMESTAMP
    """, (
        keyword,
        engine,
        analysis.get("summary") or "",
        json.dumps(analysis.get("product_flaws") or [], ensure_ascii=False),
        json.dumps(analysis.get("buying_triggers") or [], ensure_ascii=False),
        json.dumps(analysis.get("sourcing_directives") or [], ensure_ascii=False),
        analysis.get("listing_blueprint") or ""
    ))
    conn.commit()
    conn.close()


def get_master_analysis(keyword: str, engine: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if engine:
        cursor.execute("SELECT * FROM master_analysis WHERE keyword = ? AND engine = ?", (keyword, engine))
        row = cursor.fetchone()
    else:
        cursor.execute("SELECT * FROM master_analysis WHERE keyword = ? ORDER BY CASE engine WHEN 'gemini' THEN 1 ELSE 2 END", (keyword,))
        row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    d = dict(row)
    for json_col in ["product_flaws_json", "buying_triggers_json", "sourcing_directives_json"]:
        if d.get(json_col):
            try:
                d[json_col.replace("_json", "")] = json.loads(d[json_col])
            except Exception:
                d[json_col.replace("_json", "")] = []
    return d


def save_voc_insights(keyword: str, data: Dict[str, Any]):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO voc_insights (
        keyword, total_analyzed, critical_count, positive_count,
        pillars_json, sourcing_recommendations_json, frequent_phrases_json, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(keyword) DO UPDATE SET
        total_analyzed=excluded.total_analyzed,
        critical_count=excluded.critical_count,
        positive_count=excluded.positive_count,
        pillars_json=excluded.pillars_json,
        sourcing_recommendations_json=excluded.sourcing_recommendations_json,
        frequent_phrases_json=excluded.frequent_phrases_json,
        updated_at=CURRENT_TIMESTAMP
    """, (
        keyword,
        int(data.get("total_analyzed") or 0),
        int(data.get("critical_count") or 0),
        int(data.get("positive_count") or 0),
        json.dumps(data.get("pillars") or {}, ensure_ascii=False),
        json.dumps(data.get("sourcing_recommendations") or [], ensure_ascii=False),
        json.dumps(data.get("frequent_phrases") or [], ensure_ascii=False)
    ))
    conn.commit()
    conn.close()


def get_voc_insights(keyword: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voc_insights WHERE keyword = ?", (keyword,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for k in ["pillars_json", "sourcing_recommendations_json", "frequent_phrases_json"]:
        if d.get(k):
            try:
                d[k.replace("_json", "")] = json.loads(d[k])
            except Exception:
                d[k.replace("_json", "")] = {}
    return d


# ---------------------------------------------------------
# Search Observations Operations (Decoupled Ads vs Organic)
# ---------------------------------------------------------

def record_search_observation(obs: Dict[str, Any]) -> int:
    """
    Records an observation of an ASIN appearing in Amazon search results.
    Preserves exact query, page, position, placement_type (SPONSORED, ORGANIC, UNKNOWN),
    and evidence without overwriting other query observations.
    """
    conn = get_db()
    cursor = conn.cursor()

    asin = obs.get("asin", "").strip()
    query = obs.get("query", "").strip()
    if not asin or not query:
        conn.close()
        return 0

    placement_type = obs.get("placement_type", "UNKNOWN")
    if placement_type not in ("SPONSORED", "ORGANIC", "UNKNOWN"):
        placement_type = "UNKNOWN"

    confidence = obs.get("confidence") or "HIGH"
    evidence_signals = obs.get("evidence_signals") or []
    evidence_signals_json = json.dumps(evidence_signals, ensure_ascii=False) if isinstance(evidence_signals, list) else (obs.get("evidence_signals_json") or "[]")

    badges_json = json.dumps(obs.get("badges") or [], ensure_ascii=False) if isinstance(obs.get("badges"), list) else (obs.get("badges_json") or "[]")

    cursor.execute("""
    INSERT INTO search_observations (
        run_id, niche, asin, query, page, position,
        placement_type, confidence, sponsored_evidence, evidence_signals_json,
        badges_json, coupon, delivery_signal, price, rating, reviews_count,
        observed_at
    ) VALUES (
        :run_id, :niche, :asin, :query, :page, :position,
        :placement_type, :confidence, :sponsored_evidence, :evidence_signals_json,
        :badges_json, :coupon, :delivery_signal, :price, :rating, :reviews_count,
        CURRENT_TIMESTAMP
    )
    """, {
        "run_id": obs.get("run_id") or "",
        "niche": obs.get("niche") or "",
        "asin": asin,
        "query": query,
        "page": int(obs.get("page") or 1),
        "position": int(obs.get("position") or 1),
        "placement_type": placement_type,
        "confidence": confidence,
        "sponsored_evidence": obs.get("sponsored_evidence") or "ambiguous_markup",
        "evidence_signals_json": evidence_signals_json,
        "badges_json": badges_json,
        "coupon": obs.get("coupon") or "",
        "delivery_signal": obs.get("delivery_signal") or "",
        "price": float(obs.get("price") or 0.0),
        "rating": float(obs.get("rating") or 0.0),
        "reviews_count": int(obs.get("reviews_count") or 0),
    })
    obs_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return obs_id


def get_search_observations(
    asin: Optional[str] = None,
    query: Optional[str] = None,
    niche: Optional[str] = None,
    run_id: Optional[str] = None,
    placement_type: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    conditions = []
    params = []

    if asin:
        conditions.append("asin = ?")
        params.append(asin)
    if query:
        conditions.append("query = ?")
        params.append(query)
    if niche:
        conditions.append("niche = ?")
        params.append(niche)
    if run_id:
        conditions.append("run_id = ?")
        params.append(run_id)
    if placement_type:
        conditions.append("placement_type = ?")
        params.append(placement_type)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query_sql = f"""
    SELECT * FROM search_observations
    {where_clause}
    ORDER BY observed_at DESC, page ASC, position ASC
    LIMIT ?
    """
    params.append(limit)

    cursor.execute(query_sql, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_asin_search_matrix(asin: str) -> Dict[str, Any]:
    """
    Returns the comprehensive search observation visibility matrix for an ASIN:
    Every query it appeared in, with position, page, and whether it was SPONSORED vs ORGANIC.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT asin, title, brand, price, rating, reviews_count, tier, image_url FROM products WHERE asin = ?", (asin,))
    prod_row = cursor.fetchone()

    cursor.execute("""
    SELECT id, run_id, query, page, position, placement_type, sponsored_evidence, price, rating, reviews_count, coupon, delivery_signal, observed_at
    FROM search_observations
    WHERE asin = ?
    ORDER BY observed_at DESC, position ASC
    """, (asin,))
    observations = [dict(r) for r in cursor.fetchall()]
    conn.close()

    sponsored_count = sum(1 for o in observations if o["placement_type"] == "SPONSORED")
    organic_count = sum(1 for o in observations if o["placement_type"] == "ORGANIC")
    unknown_count = sum(1 for o in observations if o["placement_type"] == "UNKNOWN")
    queries_seen = sorted(list({o["query"] for o in observations}))

    return {
        "asin": asin,
        "product": dict(prod_row) if prod_row else None,
        "total_observations": len(observations),
        "sponsored_observations": sponsored_count,
        "organic_observations": organic_count,
        "unknown_observations": unknown_count,
        "queries_count": len(queries_seen),
        "queries": queries_seen,
        "observations": observations
    }


# ---------------------------------------------------------
# Research Runs Operations (Step 1 Tracking)
# ---------------------------------------------------------

def create_research_run(run_id: str, niche: str) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO research_runs (
            run_id, niche, started_at, discovery_status
        ) VALUES (?, ?, CURRENT_TIMESTAMP, 'running')
        ON CONFLICT(run_id) DO NOTHING
        """, (run_id, niche))
        conn.commit()
        return True
    finally:
        conn.close()


def update_research_run(run_id: str, **kwargs) -> bool:
    if not kwargs:
        return False
    conn = get_db()
    cursor = conn.cursor()
    set_clauses = []
    params = []
    for k, v in kwargs.items():
        set_clauses.append(f"{k} = ?")
        params.append(v)
    params.append(run_id)

    try:
        sql = f"UPDATE research_runs SET {', '.join(set_clauses)} WHERE run_id = ?"
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_research_run(run_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_research_run(niche: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_runs WHERE niche = ? ORDER BY started_at DESC LIMIT 1", (niche,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------
# Brand Entities (Step 10 Cross-Source Expansion)
# ---------------------------------------------------------

def upsert_brand_entity(name: str, niche: str, asin_count_increment: int = 1) -> bool:
    if not name or len(name.strip()) < 2:
        return False
    bname = name.strip()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO brand_entities (name, niche, asin_count, cross_source_hooks_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            asin_count = brand_entities.asin_count + excluded.asin_count,
            niche = COALESCE(brand_entities.niche, excluded.niche)
        """, (
            bname,
            niche,
            asin_count_increment,
            json.dumps({
                "tiktok_ready": True,
                "shopify_ready": True,
                "meta_ads_ready": True,
                "google_trends_ready": True
            })
        ))
        conn.commit()
        return True
    finally:
        conn.close()


def get_brand_entities(niche: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if niche:
        cursor.execute("SELECT * FROM brand_entities WHERE niche = ? ORDER BY asin_count DESC LIMIT ?", (niche, limit))
    else:
        cursor.execute("SELECT * FROM brand_entities ORDER BY asin_count DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------
# Step 12 Acquisition Summary Dashboard Metrics
# ---------------------------------------------------------

def get_acquisition_dashboard_metrics(niche: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes and aggregates all metrics requested in Step 12:
    - Discovery: queries_executed, unique_asin, brands, sellers
    - Search observations: total, sponsored, organic, unknown
    - Products enriched: total, full_detail, review_crawled, reviews_collected
    - Run deltas: new_asin_this_run, changed_products
    - Failures: 403, 429, parser_partial
    - Coverage: discovery status, product detail status, reviews status, true market coverage
    """
    conn = get_db()
    cursor = conn.cursor()
    n = niche.strip()

    # 1. Discovery & Products counts
    cursor.execute("""
    SELECT 
        COUNT(*) as total_products,
        COUNT(DISTINCT brand) as total_brands,
        COUNT(DISTINCT seller) as total_sellers,
        SUM(CASE WHEN product_depth = 'FULL' THEN 1 ELSE 0 END) as full_detail,
        SUM(CASE WHEN review_depth IN ('PARTIAL', 'FULL') THEN 1 ELSE 0 END) as review_crawled
    FROM products 
    WHERE keyword = ?
    """, (n,))
    r_prod = cursor.fetchone()
    prod_row = dict(r_prod) if r_prod else {}

    # 2. Queries executed from coverage ledger
    cursor.execute("SELECT COUNT(DISTINCT query_or_target) as total_queries FROM coverage_ledger WHERE niche = ?", (n,))
    r_ledger = cursor.fetchone()
    queries_executed = r_ledger["total_queries"] if r_ledger and r_ledger["total_queries"] else 0

    # 3. Observations Breakdown (SPONSORED, ORGANIC, UNKNOWN)
    cursor.execute("""
    SELECT 
        COUNT(*) as total_obs,
        SUM(CASE WHEN placement_type = 'SPONSORED' THEN 1 ELSE 0 END) as sponsored_obs,
        SUM(CASE WHEN placement_type = 'ORGANIC' THEN 1 ELSE 0 END) as organic_obs,
        SUM(CASE WHEN placement_type = 'UNKNOWN' THEN 1 ELSE 0 END) as unknown_obs
    FROM search_observations
    WHERE niche = ?
    """, (n,))
    r_obs = cursor.fetchone()
    obs_row = dict(r_obs) if r_obs else {}

    # 4. Total reviews collected
    cursor.execute("SELECT COUNT(*) as total_reviews FROM reviews WHERE keyword = ?", (n,))
    r_rev = cursor.fetchone()
    rev_row = dict(r_rev) if r_rev else {}

    # 5. Failures from ledger / run
    cursor.execute("""
    SELECT 
        SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked_queries,
        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_queries
    FROM coverage_ledger
    WHERE niche = ?
    """, (n,))
    r_fail = cursor.fetchone()
    fail_row = dict(r_fail) if r_fail else {}

    # 6. Check latest run if available
    run = None
    if run_id:
        cursor.execute("SELECT * FROM research_runs WHERE run_id = ?", (run_id,))
        r_run = cursor.fetchone()
        run = dict(r_run) if r_run else None
    if not run:
        cursor.execute("SELECT * FROM research_runs WHERE niche = ? ORDER BY started_at DESC LIMIT 1", (n,))
        r_run = cursor.fetchone()
        run = dict(r_run) if r_run else None

    conn.close()

    total_obs = obs_row.get("total_obs") or 0
    unique_asins = prod_row.get("total_products") or 0
    brands_count = prod_row.get("total_brands") or 0
    sellers_count = prod_row.get("total_sellers") or 0
    full_detail = prod_row.get("full_detail") or 0
    review_crawled = prod_row.get("review_crawled") or 0

    discovery_status = "approaching saturation" if queries_executed >= 10 or unique_asins >= 100 else "active discovery"
    if run and run.get("discovery_status"):
        discovery_status = run["discovery_status"]

    return {
        "niche": n,
        "run_id": run.get("run_id") if run else "current-session",
        "discovery": {
            "queries_executed": max(queries_executed, run.get("queries_executed", 0) if run else 0),
            "unique_asin": unique_asins,
            "brands": brands_count,
            "sellers": sellers_count
        },
        "search_observations": {
            "total": total_obs,
            "sponsored": obs_row.get("sponsored_obs") or 0,
            "organic": obs_row.get("organic_obs") or 0,
            "unknown": obs_row.get("unknown_obs") or 0
        },
        "products_enriched": {
            "total": unique_asins,
            "full_detail": full_detail,
            "review_crawled": review_crawled,
            "reviews_collected": rev_row.get("total_reviews") or 0
        },
        "run_deltas": {
            "new_asin_this_run": run.get("new_asins_this_run", 0) if run else 0,
            "changed_products": run.get("changed_products", 0) if run else 0
        },
        "failures": {
            "status_403": run.get("failures_403", 0) if run else 0,
            "status_429": run.get("failures_429", 0) if run else (fail_row.get("blocked_queries") or 0),
            "parser_partial": run.get("parser_partial", 0) if run else (fail_row.get("error_queries") or 0)
        },
        "coverage": {
            "discovery": discovery_status,
            "product_detail": "partial" if full_detail < unique_asins else "full",
            "reviews": "partial" if review_crawled < unique_asins else "full",
            "true_market_coverage": "UNKNOWN"
        }
    }



# ---------------------------------------------------------
# Diagnostics & Queue Checkpoint Helpers
# ---------------------------------------------------------

def record_diagnostic_log(
    run_id: str,
    niche: str,
    query_or_asin: str,
    status: str,
    reason: str,
    html_path: str = "",
    screenshot_path: str = ""
) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO diagnostics_log (run_id, niche, query_or_asin, status, reason, html_path, screenshot_path)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, niche, query_or_asin, status, reason, html_path, screenshot_path))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_recent_diagnostics(niche: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if niche:
        cursor.execute("SELECT * FROM diagnostics_log WHERE niche = ? ORDER BY id DESC LIMIT ?", (niche, limit))
    else:
        cursor.execute("SELECT * FROM diagnostics_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def enqueue_discovery_queries(
    niche: str,
    queries: List[Any],
    target_pages: int = 3
) -> int:
    """
    Enqueue queries into discovery_query_queue with composite UNIQUE(niche, query).
    queries: List of (lane, query, priority) or (lane, query, priority, target_pages) or simple str queries.
    """
    conn = get_db()
    cursor = conn.cursor()
    enqueued = 0
    for item in queries:
        if isinstance(item, str):
            lane, query, priority, tp = "keyword_search", item, 10, target_pages
        elif isinstance(item, (tuple, list)):
            if len(item) == 2:
                lane, query, priority, tp = item[0], item[1], 10, target_pages
            elif len(item) == 3:
                lane, query, priority, tp = item[0], item[1], item[2], target_pages
            elif len(item) >= 4:
                lane, query, priority, tp = item[0], item[1], item[2], item[3]
            else:
                continue
        else:
            continue

        try:
            cursor.execute("""
            INSERT INTO discovery_query_queue (niche, lane, query, status, priority, target_pages, last_completed_page, next_page)
            VALUES (?, ?, ?, 'pending', ?, ?, 0, 1)
            ON CONFLICT(niche, query) DO NOTHING
            """, (niche, lane, query, priority, tp))
            if cursor.rowcount > 0:
                enqueued += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return enqueued


def get_pending_discovery_queries(niche: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, niche, lane, query, status, priority, target_pages, last_completed_page, next_page, retry_count, last_error, created_at
    FROM discovery_query_queue
    WHERE niche = ? AND status = 'pending'
    ORDER BY priority ASC, id ASC
    LIMIT ?
    """, (niche, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_next_pending_query(niche: str) -> Optional[Dict[str, Any]]:
    """Pops the next pending discovery query for this niche based on priority."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, niche, lane, query, status, priority, target_pages, last_completed_page, next_page, retry_count, last_error
    FROM discovery_query_queue
    WHERE niche = ? AND status = 'pending'
    ORDER BY priority ASC, id ASC
    LIMIT 1
    """, (niche,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_query_progress(niche: str, query: str, page_num: int, status: str = 'in_progress', error: str = '') -> bool:
    """Update page-level progress in discovery_query_queue for exact recovery."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE discovery_query_queue
    SET status = ?,
        last_completed_page = ?,
        next_page = ?,
        last_error = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE niche = ? AND query = ?
    """, (status, page_num, page_num + 1, error, niche, query))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def mark_discovery_query_status(niche: str, query: str, status: str, error: str = '') -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE discovery_query_queue
    SET status = ?,
        last_error = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE niche = ? AND query = ?
    """, (status, error, niche, query))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def reclaim_stale_in_progress_queries(niche: str, timeout_minutes: int = 15) -> int:
    """Reclaim queries stuck in 'in_progress' after process crash or forced interruption."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE discovery_query_queue
    SET status = 'pending',
        retry_count = retry_count + 1,
        last_error = 'reclaimed_stale_in_progress',
        updated_at = CURRENT_TIMESTAMP
    WHERE niche = ? AND status = 'in_progress'
      AND (strftime('%s', 'now') - strftime('%s', updated_at)) > (? * 60)
    """, (niche, timeout_minutes))
    reclaimed = cursor.rowcount
    conn.commit()
    conn.close()
    return reclaimed


def get_query_queue_checkpoint(niche: str) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        COUNT(*) as total_queries,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_queries,
        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_queries,
        SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_queries,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_queries,
        SUM(CASE WHEN status = 'saturated' THEN 1 ELSE 0 END) as saturated_queries
    FROM discovery_query_queue
    WHERE niche = ?
    """, (niche,))
    row = cursor.fetchone()
    conn.close()
    r = dict(row) if row else {}
    total = r.get("total_queries") or 0
    comp = r.get("completed_queries") or 0
    return {
        "niche": niche,
        "total_queries": total,
        "completed_queries": comp,
        "pending_queries": r.get("pending_queries") or 0,
        "in_progress_queries": r.get("in_progress_queries") or 0,
        "failed_queries": r.get("failed_queries") or 0,
        "saturated_queries": r.get("saturated_queries") or 0,
        "progress_percent": round((comp / total * 100), 1) if total > 0 else 0.0
    }


# ---------------------------------------------------------
# Product Variations & Observation Metrics Helpers
# ---------------------------------------------------------

def save_product_variation(
    parent_asin: str,
    child_asin: str,
    dimensions: Dict[str, Any],
    price: float = 0.0,
    availability: str = "UNKNOWN",
    image_url: str = ""
) -> bool:
    """Stores explicit attribute mapping: child_asin -> {Color: Blue, Size: L}."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        dim_str = json.dumps(dimensions or {}, ensure_ascii=False)
        cursor.execute("""
        INSERT INTO product_variations (
            parent_asin, child_asin, dimensions_json, price, availability, image_url, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(parent_asin, child_asin) DO UPDATE SET
            dimensions_json = excluded.dimensions_json,
            price = CASE WHEN excluded.price > 0 THEN excluded.price ELSE product_variations.price END,
            availability = CASE WHEN excluded.availability != 'UNKNOWN' THEN excluded.availability ELSE product_variations.availability END,
            image_url = CASE WHEN length(excluded.image_url) > 0 THEN excluded.image_url ELSE product_variations.image_url END,
            updated_at = CURRENT_TIMESTAMP
        """, (parent_asin, child_asin, dim_str, price, availability, image_url))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB Error] save_product_variation {parent_asin} -> {child_asin}: {e}")
        return False
    finally:
        conn.close()


def get_product_variations(parent_asin: str) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT pv.*, p.title, p.rating, p.reviews_count
    FROM product_variations pv
    LEFT JOIN products p ON pv.child_asin = p.asin
    WHERE pv.parent_asin = ?
    ORDER BY pv.child_asin ASC
    """, (parent_asin,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["dimensions"] = json.loads(d.get("dimensions_json") or "{}")
        except Exception:
            d["dimensions"] = {}
        result.append(d)
    return result


def get_asin_observation_metrics(asin: str, niche: str) -> Dict[str, Any]:
    """Granular observation statistics from search_observations for Promotion Engine."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        COUNT(*) as total_observations,
        SUM(CASE WHEN placement_type = 'SPONSORED' THEN 1 ELSE 0 END) as sponsored_seen_count,
        COUNT(DISTINCT CASE WHEN placement_type = 'SPONSORED' THEN query END) as sponsored_query_count,
        MIN(CASE WHEN placement_type = 'ORGANIC' THEN position END) as organic_best_position,
        COUNT(DISTINCT CASE WHEN placement_type = 'ORGANIC' THEN query END) as organic_query_coverage
    FROM search_observations
    WHERE asin = ? AND niche = ?
    """, (asin, niche))
    row = cursor.fetchone()
    conn.close()
    r = dict(row) if row else {}
    tot = r.get("total_observations") or 0
    spon = r.get("sponsored_seen_count") or 0
    return {
        "asin": asin,
        "niche": niche,
        "total_observations": tot,
        "sponsored_seen_count": spon,
        "sponsored_query_count": r.get("sponsored_query_count") or 0,
        "sponsored_share": round(spon / tot, 2) if tot > 0 else 0.0,
        "organic_best_position": r.get("organic_best_position"),
        "organic_query_coverage": r.get("organic_query_coverage") or 0
    }


if __name__ == "__main__":
    init_db()
    print("Database initialized & migrated successfully at", DB_PATH)
