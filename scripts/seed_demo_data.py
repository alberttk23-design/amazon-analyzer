import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db
import backend.voc_engine as voc_engine
import backend.ai_engine as ai_engine
import backend.promotion_engine as promotion_engine

def seed():
    db.init_db()
    kw = "portable blender"

    db.create_niche_folder(kw, "Máy xay sinh tố cầm tay mini")
    db.create_niche_folder("olive oil sprayer", "Bình xịt dầu ăn cao cấp")
    db.create_niche_folder("faux olive tree", "Cây ô liu giả decor nội thất")

    # 1. Multi-Lane Coverage Ledger showing Marginal Discovery Saturation
    session_id = str(uuid.uuid4())[:8]
    ledger_steps = [
        {"lane": "keyword_search", "query": "portable blender", "found": 24, "new": 24, "dup": 0, "cumul": 24, "strategy": "http_fast"},
        {"lane": "suggestions", "query": "portable blender for shakes and smoothies", "found": 22, "new": 14, "dup": 8, "cumul": 38, "strategy": "http_fast"},
        {"lane": "keyword_search", "query": "best portable blender", "found": 20, "new": 8, "dup": 12, "cumul": 46, "strategy": "http_fast"},
        {"lane": "brand_expansion", "query": "Ninja portable blender", "found": 18, "new": 4, "dup": 14, "cumul": 50, "strategy": "http_fast"},
        {"lane": "intent_modifiers", "query": "portable blender for travel cordless", "found": 16, "new": 2, "dup": 14, "cumul": 52, "strategy": "http_fast"},
        {"lane": "suggestions", "query": "portable blender usb rechargeable mini", "found": 15, "new": 1, "dup": 14, "cumul": 53, "strategy": "playwright_browser"}
    ]

    for step in ledger_steps:
        db.record_coverage_ledger_entry(
            session_id=session_id,
            niche=kw,
            lane=step["lane"],
            query_or_target=step["query"],
            page_number=1,
            asins_found_total=step["found"],
            asins_new_unique=step["new"],
            asins_duplicate=step["dup"],
            cumulative_unique=step["cumul"],
            status="success",
            strategy_used=step["strategy"]
        )

    # 2. Rich Candidate Universe across COLD, WARM, HOT tiers & selection taxonomy
    candidates = [
        # Top Performer / Hot (Parent ASIN with Child Variations)
        {
            "asin": "B08N5WRWNW", "keyword": kw, "title": "Ninja BC151NV Blast Portable Blender, Cordless 18oz, Leak-Proof Lid - Navy Blue",
            "brand": "Ninja", "seller": "Amazon.com", "price": 49.99, "original_price": 59.99, "rating": 4.6,
            "reviews_count": 14250, "bought_past_month": 4000, "bsr_rank": 3, "is_best_seller": 1, "is_amazons_choice": 1,
            "tier": "HOT", "tier_reason": "top_performer_deep_crawled", "product_depth": "FULL", "review_depth": "FULL",
            "discovery_lane": "keyword_search", "discovered_via_query": "portable blender", "review_velocity": 45.0,
            "image_url": "https://m.media-amazon.com/images/I/71lC6kPuhfL._AC_SX679_.jpg",
            "parent_asin": "B08N5PARENT", "is_parent": 1,
            "variation_dimensions_json": '{"Color": ["Navy Blue", "Matte Black", "Cloud White"], "Capacity": ["18oz"]}',
            "child_asins_json": '["B08N5WRWNW", "B08N5BLCK0", "B08N5WHTE1"]',
            "variant_count": 3, "completeness_status": "complete",
            "visible_total_reviews": 14250, "reviews_collected": 40,
            "collection_method": "representative_polarity", "review_coverage": "40/14250 (0.28%)",
            "filters_applied": '["critical_1_3_star", "positive_5_star"]'
        },
        # Child Variation 1 (Preserved Entity - "Group but do not flatten")
        {
            "asin": "B08N5BLCK0", "keyword": kw, "title": "Ninja BC151BK Blast Portable Blender, Cordless 18oz - Matte Black",
            "brand": "Ninja", "seller": "Ninja Direct", "price": 49.99, "original_price": 59.99, "rating": 4.6,
            "reviews_count": 14250, "bought_past_month": 3200, "bsr_rank": 4, "is_best_seller": 0, "is_amazons_choice": 0,
            "tier": "COLD", "tier_reason": "child_variant_of_B08N5WRWNW", "product_depth": "SHALLOW", "review_depth": "NONE",
            "discovery_lane": "keyword_search", "discovered_via_query": "portable blender", "review_velocity": 38.0,
            "parent_asin": "B08N5PARENT", "is_parent": 0, "completeness_status": "partial"
        },
        # Child Variation 2 (Preserved Entity - "Group but do not flatten")
        {
            "asin": "B08N5WHTE1", "keyword": kw, "title": "Ninja BC151WH Blast Portable Blender, Cordless 18oz - Cloud White",
            "brand": "Ninja", "seller": "Amazon.com", "price": 54.99, "original_price": 59.99, "rating": 4.6,
            "reviews_count": 14250, "bought_past_month": 1800, "bsr_rank": 9, "is_best_seller": 0, "is_amazons_choice": 0,
            "tier": "COLD", "tier_reason": "child_variant_of_B08N5WRWNW", "product_depth": "SHALLOW", "review_depth": "NONE",
            "discovery_lane": "keyword_search", "discovered_via_query": "portable blender", "review_velocity": 22.0,
            "parent_asin": "B08N5PARENT", "is_parent": 0, "completeness_status": "partial"
        },
        # Emerging Winner / Fast Growing Review Velocity
        {
            "asin": "B0D1K98XYZ", "keyword": kw, "title": "AstroBlend Pro Ultra Fast Portable Blender, 22oz Titanium 6-Blade",
            "brand": "AstroBlend", "seller": "AstroBlend Official", "price": 44.95, "original_price": 54.95, "rating": 4.7,
            "reviews_count": 820, "bought_past_month": 2500, "bsr_rank": 11, "is_best_seller": 0, "is_amazons_choice": 1,
            "tier": "HOT", "tier_reason": "emerging_winner_rapid_growth", "product_depth": "FULL", "review_depth": "PARTIAL",
            "discovery_lane": "suggestions", "discovered_via_query": "portable blender for travel cordless", "review_velocity": 85.0,
            "image_url": "https://m.media-amazon.com/images/I/61r5aPqI17L._AC_SX679_.jpg"
        },
        # High Complaints Goldmine (Sales high, rating low -> VoC defect opportunity)
        {
            "asin": "B09X7K98LP", "keyword": kw, "title": "PopBabies Portable Blender Personal USB Rechargeable with Ice Tray",
            "brand": "PopBabies", "seller": "PopBabies Direct", "price": 36.99, "original_price": 42.99, "rating": 3.8,
            "reviews_count": 8920, "bought_past_month": 2000, "bsr_rank": 14, "is_best_seller": 0, "is_amazons_choice": 0,
            "tier": "HOT", "tier_reason": "high_complaint_goldmine", "product_depth": "FULL", "review_depth": "FULL",
            "discovery_lane": "keyword_search", "discovered_via_query": "portable blender", "review_velocity": 12.0,
            "image_url": "https://m.media-amazon.com/images/I/61r5aPqI17L._AC_SX679_.jpg"
        },
        # Ad-Active / Sponsored Challenger
        {
            "asin": "B0B8Y7Z3M2", "keyword": kw, "title": "Hamilton Beach Personal Blender for Smoothies with 14oz Travel Cup",
            "brand": "Hamilton Beach", "seller": "Hamilton Beach", "price": 21.99, "original_price": 24.99, "rating": 4.2,
            "reviews_count": 31500, "bought_past_month": 3000, "bsr_rank": 8, "is_sponsored": 1, "is_best_seller": 0,
            "tier": "WARM", "tier_reason": "ad_active_high_volume", "product_depth": "BASIC", "review_depth": "NONE",
            "discovery_lane": "keyword_search", "discovered_via_query": "best portable blender", "review_velocity": 18.0,
            "image_url": "https://m.media-amazon.com/images/I/71Y8T1b8WUL._AC_SX679_.jpg"
        },
        # Premium Price Outlier
        {
            "asin": "B0CG2K9M12", "keyword": kw, "title": "BlendJet 2 The Original Portable Blender, Waterproof USB-C",
            "brand": "BlendJet", "seller": "BlendJet Store", "price": 64.99, "original_price": 64.99, "rating": 4.1,
            "reviews_count": 6400, "bought_past_month": 1500, "bsr_rank": 25, "is_sponsored": 0, "is_best_seller": 0,
            "tier": "WARM", "tier_reason": "premium_price_outlier", "product_depth": "BASIC", "review_depth": "NONE",
            "discovery_lane": "brand_expansion", "discovered_via_query": "BlendJet portable blender", "review_velocity": 8.0,
            "image_url": "https://m.media-amazon.com/images/I/61qJ+6Y3XyL._AC_SX679_.jpg"
        },
        # Budget Price Outlier (Disruptor)
        {
            "asin": "B0CP112KLM", "keyword": kw, "title": "MiniFast Portable Blender 12oz Travel Cup for Protein Shakes",
            "brand": "MiniFast", "seller": "MiniFast Direct", "price": 14.99, "original_price": 18.99, "rating": 4.0,
            "reviews_count": 420, "bought_past_month": 600, "bsr_rank": 88, "is_sponsored": 0, "is_best_seller": 0,
            "tier": "WARM", "tier_reason": "budget_price_outlier", "product_depth": "SHALLOW", "review_depth": "NONE",
            "discovery_lane": "suggestions", "discovered_via_query": "portable blender for shakes and smoothies", "review_velocity": 5.0,
            "image_url": "https://m.media-amazon.com/images/I/61r5aPqI17L._AC_SX679_.jpg"
        },
        # Long-tail COLD Candidates (Never deleted! Permanently in candidate universe)
        {
            "asin": "B089K12AAA", "keyword": kw, "title": "NutriBullet GO Cordless Blender 13oz Silver Cup", "brand": "NutriBullet",
            "price": 29.99, "rating": 4.3, "reviews_count": 4100, "bought_past_month": 500, "tier": "COLD",
            "discovery_lane": "brand_expansion", "discovered_via_query": "NutriBullet portable blender"
        },
        {
            "asin": "B091M23BBB", "keyword": kw, "title": "Cuisinart RPB-100 EvolutionX Cordless Compact Blender", "brand": "Cuisinart",
            "price": 79.95, "rating": 4.2, "reviews_count": 1200, "bought_past_month": 200, "tier": "COLD",
            "discovery_lane": "keyword_search", "discovered_via_query": "compact portable blender"
        },
        {
            "asin": "B099K34CCC", "keyword": kw, "title": "Tenswall Personal Blender with 2 Tritan Bottles 380ml", "brand": "Tenswall",
            "price": 25.99, "rating": 3.9, "reviews_count": 890, "bought_past_month": 300, "tier": "COLD",
            "discovery_lane": "suggestions", "discovered_via_query": "portable blender usb rechargeable mini"
        },
        {
            "asin": "B077L45DDD", "keyword": kw, "title": "Oster My Blend 250W Personal Blender with 20oz Bottle", "brand": "Oster",
            "price": 24.99, "rating": 4.4, "reviews_count": 18200, "bought_past_month": 1200, "tier": "COLD",
            "discovery_lane": "intent_modifiers", "discovered_via_query": "portable blender for gym"
        },
        {
            "asin": "B088M56EEE", "keyword": kw, "title": "Magic Bullet Mini Personal Blender 4-Piece Set", "brand": "Magic Bullet",
            "price": 22.88, "rating": 4.4, "reviews_count": 21000, "bought_past_month": 2500, "tier": "COLD",
            "discovery_lane": "keyword_search", "discovered_via_query": "mini portable blender"
        },
        {
            "asin": "B099N67FFF", "keyword": kw, "title": "LaHuko Portable Juicer Cup USB Rechargeable Magnetic Charging", "brand": "LaHuko",
            "price": 27.99, "rating": 4.1, "reviews_count": 780, "bought_past_month": 150, "tier": "COLD",
            "discovery_lane": "intent_modifiers", "discovered_via_query": "portable blender gift set"
        },
        {
            "asin": "B088P78GGG", "keyword": kw, "title": "BEAST Mini Blender Plus 12-Piece Complete Kitchen Set", "brand": "BEAST",
            "price": 119.00, "rating": 4.5, "reviews_count": 3100, "bought_past_month": 800, "tier": "COLD",
            "discovery_lane": "keyword_search", "discovered_via_query": "professional portable blender"
        }
    ]

    for cand in candidates:
        cand["url"] = cand.get("url") or f"https://www.amazon.com/dp/{cand['asin']}"
        cand["currency"] = "USD"
        cand["original_price"] = cand.get("original_price") or cand.get("price")
        cand["seller"] = cand.get("seller") or (cand.get("brand") + " Official")
        cand["image_url"] = cand.get("image_url") or "https://m.media-amazon.com/images/I/61r5aPqI17L._AC_SX679_.jpg"
        db.save_product(cand, record_snapshot=True)

    # 3. Customer Reviews for VoC (1-3★ flaws and 5★ triggers)
    sample_reviews = [
        {
            "review_id": "R1_BLND_CRIT1", "asin": "B08N5WRWNW", "reviewer_name": "Sarah Miller", "star_rating": 2,
            "review_title": "Motor burned out after 3 weeks of daily protein shakes",
            "review_text": "I really wanted to love this portable blender for gym shakes. But after 3 weeks, the motor stopped working and smelled like chemical burn. The cheap plastic gear stripped completely when blending frozen blueberries. Very disappointed for a $50 product.",
            "helpful_votes": 64, "verified_purchase": True, "variant_reviewed": "Color: Navy"
        },
        {
            "review_id": "R2_BLND_CRIT2", "asin": "B09X7K98LP", "reviewer_name": "David K.", "star_rating": 1,
            "review_title": "Smaller than expected and leaks everywhere",
            "review_text": "The photos are totally misleading. It is tiny and can barely hold 10oz of liquid once you put fruit inside. Worse, the lid seal leaked all over my car seat on the first commute. Returned it immediately for a refund.",
            "helpful_votes": 42, "verified_purchase": True, "variant_reviewed": "Size: 14oz"
        },
        {
            "review_id": "R3_BLND_CRIT3", "asin": "B0B8Y7Z3M2", "reviewer_name": "Jessica Taylor", "star_rating": 2,
            "review_title": "Arrived with damaged box and missing the travel lid",
            "review_text": "The packaging was crushed upon delivery, and the extra travel lid mentioned in the listing was missing from the box. The instruction manual has tiny font and confusing diagrams. Poor quality control.",
            "helpful_votes": 28, "verified_purchase": True, "variant_reviewed": "Standard Edition"
        },
        {
            "review_id": "R4_BLND_POS1", "asin": "B08N5WRWNW", "reviewer_name": "Michael Chang", "star_rating": 5,
            "review_title": "Game changer for travel and office mornings!",
            "review_text": "Best purchase I have made this year! Super powerful blades crush ice easily. Easy to clean under running water, battery lasts for almost 15 blends on a single USB-C charge. Exceeded my expectations, worth every penny!",
            "helpful_votes": 95, "verified_purchase": True, "variant_reviewed": "Color: Navy"
        },
        {
            "review_id": "R5_BLND_POS2", "asin": "B0CG2K9M12", "reviewer_name": "Emily Watson", "star_rating": 5,
            "review_title": "Perfect gift! Aesthetic, quiet and convenient",
            "review_text": "Bought this as a gift for my sister and ended up getting one for myself too. Beautiful design, very quiet compared to my big kitchen blender, and fits right in my tote bag. Highly recommend!",
            "helpful_votes": 53, "verified_purchase": True, "variant_reviewed": "Mint Green"
        }
    ]
    db.save_reviews("B08N5WRWNW", kw, sample_reviews)

    # 4. Sponsored Ads
    sample_ads = [
        {"asin": "B0B8Y7Z3M2", "title": "Hamilton Beach Personal Blender 14oz Travel Cup", "price": 21.99, "rating": 4.2, "reviews_count": 31500, "brand": "Hamilton Beach", "image_url": "https://m.media-amazon.com/images/I/71Y8T1b8WUL._AC_SX679_.jpg"},
        {"asin": "B09X7K98LP", "title": "PopBabies Personal USB Rechargeable Blender with Ice Tray", "price": 36.99, "rating": 3.8, "reviews_count": 8920, "brand": "PopBabies", "image_url": "https://m.media-amazon.com/images/I/61r5aPqI17L._AC_SX679_.jpg"}
    ]
    db.save_sponsored_ads(sample_ads, keyword=kw)

    # 5. Best Sellers Top 100
    sample_bs = [
        {"asin": "B08N5WRWNW", "rank": 1, "title": "Ninja BC151NV Blast Portable Blender", "price": 49.99, "rating": 4.6, "reviews_count": 14250, "image_url": "https://m.media-amazon.com/images/I/71lC6kPuhfL._AC_SX679_.jpg"},
        {"asin": "B0B8Y7Z3M2", "rank": 2, "title": "Hamilton Beach Personal Blender", "price": 21.99, "rating": 4.2, "reviews_count": 31500, "image_url": "https://m.media-amazon.com/images/I/71Y8T1b8WUL._AC_SX679_.jpg"},
        {"asin": "B09X7K98LP", "rank": 3, "title": "PopBabies Personal USB Blender", "price": 36.99, "rating": 3.8, "reviews_count": 8920, "image_url": "https://m.media-amazon.com/images/I/61r5aPqI17L._AC_SX679_.jpg"}
    ]
    db.save_best_sellers(sample_bs, category="Kitchen & Dining")

    # 6. Seed Search Observations (Decoupled Ads vs Organic across queries)
    sample_observations = [
        # Ninja Blender observations across different queries
        {"run_id": session_id, "niche": kw, "asin": "B08N5WRWNW", "query": "portable blender", "page": 1, "position": 1, "placement_type": "ORGANIC", "sponsored_evidence": "organic_container", "delivery_signal": "FREE delivery Tomorrow, Prime", "price": 49.99, "rating": 4.6, "reviews_count": 14250},
        {"run_id": session_id, "niche": kw, "asin": "B08N5WRWNW", "query": "best portable blender", "page": 1, "position": 2, "placement_type": "SPONSORED", "sponsored_evidence": "ad_url_or_label", "delivery_signal": "FREE delivery Tomorrow", "price": 49.99, "rating": 4.6, "reviews_count": 14250},
        {"run_id": session_id, "niche": kw, "asin": "B08N5WRWNW", "query": "portable blender for travel cordless", "page": 1, "position": 3, "placement_type": "ORGANIC", "sponsored_evidence": "organic_container", "price": 49.99, "rating": 4.6, "reviews_count": 14250},

        # Hamilton Beach: Heavy ads across queries
        {"run_id": session_id, "niche": kw, "asin": "B0B8Y7Z3M2", "query": "portable blender", "page": 1, "position": 2, "placement_type": "SPONSORED", "sponsored_evidence": "ad_url_or_label", "coupon": "Save 10% with coupon", "price": 21.99, "rating": 4.2, "reviews_count": 31500},
        {"run_id": session_id, "niche": kw, "asin": "B0B8Y7Z3M2", "query": "best portable blender", "page": 1, "position": 4, "placement_type": "SPONSORED", "sponsored_evidence": "ad_url_or_label", "price": 21.99, "rating": 4.2, "reviews_count": 31500},
        {"run_id": session_id, "niche": kw, "asin": "B0B8Y7Z3M2", "query": "portable blender for shakes and smoothies", "page": 1, "position": 18, "placement_type": "ORGANIC", "sponsored_evidence": "organic_container", "price": 21.99, "rating": 4.2, "reviews_count": 31500},

        # PopBabies: Flaws / high complaints
        {"run_id": session_id, "niche": kw, "asin": "B09X7K98LP", "query": "portable blender", "page": 1, "position": 5, "placement_type": "ORGANIC", "sponsored_evidence": "organic_container", "price": 36.99, "rating": 3.8, "reviews_count": 8920},
        {"run_id": session_id, "niche": kw, "asin": "B09X7K98LP", "query": "portable blender usb rechargeable mini", "page": 1, "position": 3, "placement_type": "SPONSORED", "sponsored_evidence": "ad_url_or_label", "price": 36.99, "rating": 3.8, "reviews_count": 8920}
    ]
    for obs in sample_observations:
        db.record_search_observation(obs)

    # 7. Seed Research Run Record for Bước 12 Acquisition Summary
    db.create_research_run(session_id, kw)
    db.update_research_run(
        session_id,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        queries_executed=len(ledger_steps),
        unique_asins=len(candidates),
        brands_count=len(set(c["brand"] for c in candidates)),
        sellers_count=len(set(c["brand"] for c in candidates)),
        total_observations=len(sample_observations),
        sponsored_observations=sum(1 for o in sample_observations if o["placement_type"] == "SPONSORED"),
        organic_observations=sum(1 for o in sample_observations if o["placement_type"] == "ORGANIC"),
        unknown_observations=sum(1 for o in sample_observations if o["placement_type"] == "UNKNOWN"),
        products_enriched=len(candidates),
        full_detail_count=3,
        review_crawled_count=3,
        reviews_collected=len(sample_reviews),
        new_asins_this_run=len(candidates),
        changed_products=2,
        failures_403=0,
        failures_429=0,
        parser_partial=0,
        discovery_status="approaching saturation"
    )

    # 8. Seed Second Niche: "Migraine Relief Cap" (User's Exact Example!)
    m_kw = "Migraine Relief Cap"
    db.create_niche_folder(m_kw, "Mũ chườm lạnh giảm đau nửa đầu & căng thẳng")
    m_run_id = str(uuid.uuid4())[:8]

    m_candidates = [
        {
            "asin": "B0829KS7W5", "keyword": m_kw, "title": "TheraICE Form Fitting Gel Ice Headache and Migraine Relief Cap, Cold Therapy Hat",
            "brand": "TheraICE", "seller": "TheraICE Direct", "price": 29.95, "original_price": 39.95, "rating": 4.5,
            "reviews_count": 48200, "bought_past_month": 10000, "bsr_rank": 1, "is_best_seller": 1, "is_amazons_choice": 1,
            "tier": "HOT", "tier_reason": "top_performer_and_ad_leader", "product_depth": "FULL", "review_depth": "FULL",
            "discovery_lane": "keyword_search", "discovered_via_query": "migraine relief cap", "review_velocity": 120.0,
            "image_url": "https://m.media-amazon.com/images/I/71qS+B8WbOL._AC_SX679_.jpg"
        },
        {
            "asin": "B09MG7X112", "keyword": m_kw, "title": "Magic Gel Migraine Ice Head Wrap, Cold Compression Headache Hat",
            "brand": "Magic Gel", "seller": "Magic Gel Store", "price": 19.99, "original_price": 24.99, "rating": 4.4,
            "reviews_count": 8900, "bought_past_month": 3500, "bsr_rank": 5, "is_best_seller": 0, "is_amazons_choice": 0,
            "tier": "WARM", "tier_reason": "challenger_growing", "product_depth": "BASIC", "review_depth": "NONE",
            "discovery_lane": "suggestions", "discovered_via_query": "headache hat", "review_velocity": 34.0,
            "image_url": "https://m.media-amazon.com/images/I/71qS+B8WbOL._AC_SX679_.jpg"
        },
        {
            "asin": "B0BK98LM12", "keyword": m_kw, "title": "ComfiTech Upgraded 360 Degree Cold Therapy Headache Relief Cap",
            "brand": "ComfiTech", "seller": "ComfiTech Official", "price": 22.99, "original_price": 26.99, "rating": 4.6,
            "reviews_count": 14200, "bought_past_month": 4000, "bsr_rank": 3, "is_best_seller": 0, "is_amazons_choice": 1,
            "tier": "HOT", "tier_reason": "rapid_growth_velocity", "product_depth": "FULL", "review_depth": "PARTIAL",
            "discovery_lane": "brand_expansion", "discovered_via_query": "ComfiTech migraine cap", "review_velocity": 78.0,
            "image_url": "https://m.media-amazon.com/images/I/71qS+B8WbOL._AC_SX679_.jpg"
        }
    ]
    for c in m_candidates:
        c["url"] = f"https://www.amazon.com/dp/{c['asin']}"
        c["currency"] = "USD"
        db.save_product(c, record_snapshot=True)

    # TheraICE Multi-Query Observation Matrix (The user's exact specification!)
    m_observations = [
        {"run_id": m_run_id, "niche": m_kw, "asin": "B0829KS7W5", "query": "migraine cap", "page": 1, "position": 4, "placement_type": "SPONSORED", "sponsored_evidence": "label_observed", "coupon": "Save $3.00", "delivery_signal": "FREE delivery Tomorrow", "price": 29.95, "rating": 4.5, "reviews_count": 48200},
        {"run_id": m_run_id, "niche": m_kw, "asin": "B0829KS7W5", "query": "headache hat", "page": 1, "position": 18, "placement_type": "ORGANIC", "sponsored_evidence": "organic_container", "price": 29.95, "rating": 4.5, "reviews_count": 48200},
        {"run_id": m_run_id, "niche": m_kw, "asin": "B0829KS7W5", "query": "ice migraine cap", "page": 2, "position": 61, "placement_type": "ORGANIC", "sponsored_evidence": "organic_container", "price": 29.95, "rating": 4.5, "reviews_count": 48200},
        {"run_id": m_run_id, "niche": m_kw, "asin": "B09MG7X112", "query": "migraine cap", "page": 1, "position": 8, "placement_type": "ORGANIC", "sponsored_evidence": "organic_container", "price": 19.99, "rating": 4.4, "reviews_count": 8900},
        {"run_id": m_run_id, "niche": m_kw, "asin": "B0BK98LM12", "query": "migraine cap", "page": 1, "position": 2, "placement_type": "SPONSORED", "sponsored_evidence": "ad_url_or_label", "price": 22.99, "rating": 4.6, "reviews_count": 14200}
    ]
    for obs in m_observations:
        db.record_search_observation(obs)

    db.create_research_run(m_run_id, m_kw)
    db.update_research_run(
        m_run_id,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        queries_executed=64,
        unique_asins=3142,
        brands_count=187,
        sellers_count=294,
        total_observations=18429,
        sponsored_observations=2730,
        organic_observations=15211,
        unknown_observations=488,
        products_enriched=2936,
        full_detail_count=438,
        review_crawled_count=214,
        reviews_collected=81420,
        new_asins_this_run=73,
        changed_products=91,
        failures_403=12,
        failures_429=4,
        parser_partial=17,
        discovery_status="approaching saturation"
    )

    # 7. Seed Discovery Query Queue for Checkpoint / Resume Demo
    queue_sample = [
        ("keyword_search", "portable blender", 1),
        ("keyword_search", "best portable blender", 1),
        ("suggestions", "portable blender for shakes and smoothies", 2),
        ("intent_modifiers", "portable blender for travel", 3),
        ("suggestions", "portable blender usb rechargeable mini", 2),
        ("intent_modifiers", "portable blender for gym", 3),
        ("brand_expansion", "Ninja portable blender", 4),
        ("brand_expansion", "BlendJet portable blender", 4)
    ]
    db.enqueue_discovery_queries(kw, queue_sample)
    db.mark_discovery_query_status(kw, "portable blender", "completed")
    db.mark_discovery_query_status(kw, "best portable blender", "completed")
    db.mark_discovery_query_status(kw, "portable blender for shakes and smoothies", "completed")

    # 8. Seed Diagnostics Logs (amkarpe pattern)
    debug_dir = BASE_DIR / "data" / "debug" / "html"
    debug_dir.mkdir(parents=True, exist_ok=True)
    sample_html = debug_dir / "20260923_114500_portable_blender_cordless_captcha.html"
    if not sample_html.exists():
        with open(sample_html, "w", encoding="utf-8") as f:
            f.write("<html><body><h1>Amazon Bot Detection - Captcha Challenge</h1><p>Type the characters you see in this image...</p></body></html>")

    db.record_diagnostic_log(
        run_id=session_id,
        niche=kw,
        query_or_asin="portable blender cordless high speed",
        status="captcha_detected",
        reason="Fast HTTP returned Amazon Captcha challenge (Status 200 with validateCaptcha)",
        html_path="data/debug/html/20260923_114500_portable_blender_cordless_captcha.html"
    )
    db.record_diagnostic_log(
        run_id=session_id,
        niche=kw,
        query_or_asin="portable blender 999999_obscure_query",
        status="zero_cards",
        reason="Playwright loaded search page but 0 result cards found",
        html_path=""
    )

    # 9. Run Promotion Signal Update, VoC, and Master AI
    promotion_engine.compute_and_update_niche_promotions(kw)
    voc_engine.analyze_voc_deep(kw)
    ai_engine.generate_master_amazon_blueprint(kw)

    print("Enhanced Acquisition-First Demo Data Seeded Successfully!")

if __name__ == "__main__":
    seed()
