import json
import logging
import random
import sys
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import re
from playwright.sync_api import sync_playwright
import backend.db as db
import backend.session_manager as session_manager
import backend.review_crawler as review_crawler
import backend.voc_engine as voc_engine
import backend.ai_engine as ai_engine
import backend.diagnostics as diagnostics

logger = logging.getLogger("amazon.depth")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROFILE_DIR = BASE_DIR / "data" / "browser_profile"


def parse_detail_price(text: str) -> float:
    if not text:
        return 0.0
    m = re.search(r"[\$£€]?\s*([\d,]+\.?\d*)", text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0.0


def scrape_amazon_product_detail_and_variations(
    asin: str,
    niche: str = "",
    page_handle = None
) -> Dict[str, Any]:
    """
    Spigen GCX Automation pattern:
    Scrapes /dp/{asin} product detail, extracts parent/child twister variation mapping,
    feature bullets, stock availability, and preserves child ASINs as first-class entities.
    """
    detail_url = f"https://www.amazon.com/dp/{asin}"
    logger.info(f"[DetailParser] Scraping product detail & variations for ASIN {asin} -> {detail_url}")

    def execute_scrape(page) -> Dict[str, Any]:
        try:
            page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)
            session_manager.ensure_amazon_zip_code(page, "10001")
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(1000)

            html = page.content()
            if "Type the characters you see in this image" in html or "validateCaptcha" in html:
                diagnostics.capture_failure_snapshot(
                    niche=niche, query_or_asin=asin,
                    status="captcha_detected",
                    reason="Product detail page hit Amazon Captcha",
                    html=html, page_handle=page
                )
                return {"status": "failed", "reason": "captcha"}

            data = page.evaluate("""() => {
                // Title
                const tEl = document.querySelector('#productTitle, #title');
                const title = tEl ? tEl.innerText.trim() : '';

                // Brand
                const bEl = document.querySelector('#bylineInfo, .po-brand .po-break-word, #sellerProfileTriggerId');
                let brand = bEl ? bEl.innerText.trim().replace(/^Brand:\\s*/i, '').replace(/^Visit the\\s*/i, '').replace(/\\s*Store$/i, '') : '';

                // Price
                const priceEl = document.querySelector('.apexPriceToPay .a-offscreen, #corePrice_feature_div .a-offscreen, #priceblock_ourprice, .a-price .a-offscreen');
                const priceText = priceEl ? priceEl.innerText.trim() : '';

                // Original / Strike price
                const origEl = document.querySelector('.basisPrice .a-offscreen, #corePriceDisplay_desktop_feature_div .a-text-price .a-offscreen');
                const origText = origEl ? origEl.innerText.trim() : '';

                // Availability
                const availEl = document.querySelector('#availability span, #outOfStock span');
                const availability = availEl ? availEl.innerText.trim() : 'In Stock';

                // Rating & Review Count
                const rEl = document.querySelector('#acrPopover span.a-icon-alt');
                const ratingText = rEl ? rEl.innerText.trim() : '';

                const rcEl = document.querySelector('#acrCustomerReviewText');
                const reviewsCountText = rcEl ? rcEl.innerText.trim() : '';

                // Bullet points
                const bullets = [];
                document.querySelectorAll('#feature-bullets ul li span.a-list-item').forEach(b => {
                    const bt = b.innerText.trim();
                    if (bt && bt.length > 5) bullets.push(bt);
                });

                // BSR
                let bsrRank = 0;
                let bsrCategory = '';
                const bsrEl = document.querySelector('#detailBulletsWrapper_feature_div, #SalesRank');
                if (bsrEl) {
                    const text = bsrEl.innerText;
                    const bsrMatch = text.match(/#([\\d,]+)\\s+in\\s+([^\\n\\(]+)/);
                    if (bsrMatch) {
                        bsrRank = parseInt(bsrMatch[1].replace(/,/g, ''), 10) || 0;
                        bsrCategory = bsrMatch[2].trim();
                    }
                }

                // Parent/Child ASIN & Variation Dimensions (Spigen pattern)
                let parentAsin = '';
                let childAsins = [];
                let dimensions = {};

                const scripts = Array.from(document.querySelectorAll('script'));
                for (const s of scripts) {
                    const txt = s.innerText || '';
                    if (txt.includes('dimensionValuesDisplayData') || txt.includes('asinToDimensionIndexMap')) {
                        try {
                            const dimMatch = txt.match(/"dimensionValuesDisplayData"\\s*:\\s*({[^}]+})/);
                            if (dimMatch) dimensions = JSON.parse(dimMatch[1]);
                        } catch(e) {}
                        try {
                            const asinMapMatch = txt.match(/"asinToDimensionIndexMap"\\s*:\\s*({[^}]+})/);
                            if (asinMapMatch) {
                                const mapObj = JSON.parse(asinMapMatch[1]);
                                childAsins = Object.keys(mapObj);
                            }
                        } catch(e) {}
                        try {
                            const pMatch = txt.match(/"parentAsin"\\s*:\\s*"([A-Z0-9]{10})"/);
                            if (pMatch) parentAsin = pMatch[1];
                        } catch(e) {}
                    }
                }

                // Fallback to DOM variation elements
                if (childAsins.length === 0) {
                    const swatches = document.querySelectorAll('li[data-defaultasin], div[data-defaultasin], li[data-csa-c-item-id]');
                    const cSet = new Set();
                    swatches.forEach(el => {
                        const a = el.getAttribute('data-defaultasin') || el.getAttribute('data-csa-c-item-id');
                        if (a && a.length === 10) cSet.add(a);
                    });
                    childAsins = Array.from(cSet);
                }

                if (Object.keys(dimensions).length === 0) {
                    const dimDivs = document.querySelectorAll('div[id^="variation_"]');
                    dimDivs.forEach(d => {
                        const label = d.querySelector('.a-form-label');
                        const val = d.querySelector('.selection');
                        if (label && val) {
                            dimensions[label.innerText.replace(':', '').trim()] = [val.innerText.trim()];
                        }
                    });
                }

                return {
                    title,
                    brand,
                    priceText,
                    origText,
                    availability,
                    ratingText,
                    reviewsCountText,
                    bullets,
                    bsrRank,
                    bsrCategory,
                    parentAsin,
                    childAsins,
                    dimensions
                };
            """)

            price = parse_detail_price(data.get("priceText", ""))
            original_price = parse_detail_price(data.get("origText", "")) or price

            # Resolve Parent vs Child identity
            parent_asin = data.get("parentAsin") or (asin if data.get("childAsins") else "")
            child_asins = data.get("childAsins") or []
            is_parent = 1 if asin == parent_asin or (child_asins and asin not in child_asins) else 0

            # 1. Update this ASIN in DB
            product_dict = {
                "asin": asin,
                "url": detail_url,
                "keyword": niche or "default",
                "title": data.get("title") or f"Product {asin}",
                "brand": data.get("brand") or "",
                "price": price,
                "original_price": original_price,
                "availability": data.get("availability") or "In Stock",
                "bsr_rank": data.get("bsrRank", 0),
                "bsr_category": data.get("bsrCategory", ""),
                "parent_asin": parent_asin,
                "is_parent": is_parent,
                "variation_dimensions_json": json.dumps(data.get("dimensions", {}), ensure_ascii=False),
                "child_asins_json": json.dumps(child_asins),
                "variant_count": max(1, len(child_asins)),
                "completeness_status": "complete",
                "product_depth": "FULL"
            }
            db.save_product(product_dict, record_snapshot=True)

            # 2. Preserve Child ASINs as First-Class Entities ("Group but do not flatten")
            for child in child_asins:
                if child != asin:
                    db.save_product({
                        "asin": child,
                        "url": f"https://www.amazon.com/dp/{child}",
                        "keyword": niche or "default",
                        "title": f"{data.get('title', '')} (Variant {child})",
                        "brand": data.get("brand") or "",
                        "parent_asin": parent_asin or asin,
                        "is_parent": 0,
                        "tier": "COLD",
                        "completeness_status": "partial",
                        "product_depth": "SHALLOW",
                        "tier_reason": f"child_variant_of_{asin}"
                    }, record_snapshot=False)

            logger.info(f"[DetailParser] Successfully parsed ASIN {asin} | Parent: {parent_asin} | {len(child_asins)} Children")
            return {
                "status": "complete",
                "asin": asin,
                "parent_asin": parent_asin,
                "child_asins_count": len(child_asins),
                "dimensions": data.get("dimensions", {})
            }
        except Exception as e:
            logger.error(f"[DetailParser] Error parsing {detail_url}: {e}")
            diagnostics.capture_failure_snapshot(
                niche=niche, query_or_asin=asin,
                status="parser_error",
                reason=str(e),
                html="", page_handle=page
            )
            return {"status": "failed", "reason": str(e)}

    if page_handle:
        return execute_scrape(page_handle)
    else:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=True,
                viewport={"width": 1440, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
            page = context.pages[0] if context.pages else context.new_page()
            res = execute_scrape(page)
            context.close()
            return res


def select_candidates_for_depth_crawl(
    keyword: str,
    target_count: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Selects a balanced portfolio of candidates for depth crawl using the Acquisition Selection Taxonomy:
    - Top Performers (25%)
    - Emerging & Velocity Outliers (25%)
    - High-Complaint Density (20%) - VoC defect goldmine
    - Price Outliers (15%) - Market gaps
    - Long-Tail Sample (15%) - Prevents top-seller bias
    """
    n_top = max(2, int(target_count * 0.25))
    n_emerging = max(2, int(target_count * 0.25))
    n_complaints = max(2, int(target_count * 0.20))
    n_price = max(1, int(target_count * 0.15))
    n_longtail = max(1, target_count - (n_top + n_emerging + n_complaints + n_price))

    top_items = db.get_priority_candidates(keyword, taxonomy="top_performers", limit=n_top)
    emerging_items = db.get_priority_candidates(keyword, taxonomy="emerging_winners", limit=n_emerging)
    complaint_items = db.get_priority_candidates(keyword, taxonomy="high_complaints", limit=n_complaints)
    price_items = db.get_priority_candidates(keyword, taxonomy="price_outliers", limit=n_price)
    longtail_items = db.get_priority_candidates(keyword, taxonomy="long_tail", limit=n_longtail)

    # Deduplicate while preserving classification category
    seen_asins = set()
    balanced_portfolio = {
        "top_performers": [],
        "emerging_winners": [],
        "high_complaints": [],
        "price_outliers": [],
        "long_tail": []
    }

    groups = [
        ("top_performers", top_items),
        ("emerging_winners", emerging_items),
        ("high_complaints", complaint_items),
        ("price_outliers", price_items),
        ("long_tail", longtail_items)
    ]

    for cat_name, items in groups:
        for it in items:
            asin = it["asin"]
            if asin not in seen_asins:
                seen_asins.add(asin)
                balanced_portfolio[cat_name].append(it)

    return balanced_portfolio


def run_depth_crawl_pipeline(
    keyword: str,
    selected_asins: Optional[List[str]] = None,
    max_candidates: int = 15,
    max_reviews_per_product: int = 30,
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes depth crawl on selected candidates or taxonomy-balanced portfolio:
    - Promotes candidates to HOT
    - Gathers deep customer reviews (Critical 1-3★ & Positive 5★)
    - Updates review_depth and product_depth
    - Re-runs VoC 6-pillar engine and AI blueprint
    """
    niche = keyword.strip()
    if job_id:
        db.update_job(job_id, status="depth_crawling", progress=80, message=f"Đang chuẩn bị danh mục Depth Crawl cho '{niche}'...")

    candidates_to_crawl: List[Dict[str, Any]] = []

    if selected_asins and len(selected_asins) > 0:
        for asin in selected_asins:
            prod = db.get_product_by_asin(asin)
            if prod:
                candidates_to_crawl.append(prod)
    else:
        portfolio = select_candidates_for_depth_crawl(niche, target_count=max_candidates)
        for cat_name, items in portfolio.items():
            for it in items:
                it["depth_category"] = cat_name
                candidates_to_crawl.append(it)

    logger.info(f"[DepthCrawler] Commencing deep review & spec crawl for {len(candidates_to_crawl)} prioritized products...")

    total_reviews_collected = 0
    total_candidates = len(candidates_to_crawl)

    for idx, cand in enumerate(candidates_to_crawl):
        asin = cand["asin"]
        reason = cand.get("depth_category", "priority_selection")

        if job_id:
            prog = 80 + int(((idx + 1) / max(1, total_candidates)) * 15)
            db.update_job(
                job_id,
                progress=min(prog, 95),
                message=f"Đang cào sâu ASIN {asin} ({idx+1}/{total_candidates}) - [{reason}]..."
            )

        # 1. Promote to HOT
        db.update_product_tier(asin, new_tier="HOT", reason=f"depth_crawl_{reason}")

        # 2. Extract full specs & parent/child variations (Spigen GCX automation pattern)
        try:
            detail_res = scrape_amazon_product_detail_and_variations(asin=asin, niche=niche)
            logger.info(f"[DepthCrawler] Detail specs extracted for {asin}: {detail_res.get('status')}")
        except Exception as e:
            logger.error(f"[DepthCrawler] Error parsing detail specs for {asin}: {e}")

        # 3. Crawl deep reviews with 3-Tier Policy ('deep_hot_crawl')
        try:
            revs = review_crawler.crawl_amazon_reviews_for_asin(
                asin=asin,
                keyword=niche,
                policy_tier="deep_hot_crawl",
                max_critical=max_reviews_per_product // 2,
                max_positive=max_reviews_per_product // 2
            )
            total_reviews_collected += len(revs)
        except Exception as e:
            logger.error(f"[DepthCrawler] Error crawling reviews for {asin}: {e}")

        time.sleep(random.uniform(0.4, 0.9))

    # 3. Re-run VoC Intelligence with newly collected evidence
    if job_id:
        db.update_job(job_id, progress=96, message="Đang cập nhật VoC 6 Trụ Cột từ tập dữ liệu chuyên sâu...")
    voc_engine.analyze_voc_deep(keyword=niche)

    # 4. Re-run Master AI Blueprint
    if job_id:
        db.update_job(job_id, progress=98, message="Đang tái cấu trúc Master Sourcing & Listing Blueprint...")
    ai_engine.generate_master_amazon_blueprint(keyword=niche)

    if job_id:
        db.update_job(
            job_id,
            status="completed",
            progress=100,
            message=f"Hoàn thành Depth Crawl toàn diện! Đã bóc tách {total_reviews_collected} reviews từ {total_candidates} sản phẩm mục tiêu."
        )

    return {
        "niche": niche,
        "candidates_crawled_count": total_candidates,
        "total_reviews_collected": total_reviews_collected
    }


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    print(f"Testing Depth Crawler Portfolio for '{kw}'...")
    port = select_candidates_for_depth_crawl(kw, target_count=10)
    for cat, items in port.items():
        print(f"Category: {cat} ({len(items)} items)")
        for it in items:
            print(f"  - [{it['asin']}] {it['title'][:40]} | ${it['price']} | {it['rating']}★")
