import json
import random
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright
import backend.db as db

PROFILE_DIR = BASE_DIR / "data" / "browser_profile"


def parse_star_rating(text: str) -> int:
    """Extract integer star rating (1-5) from text like '1.0 out of 5 stars'."""
    if not text:
        return 3
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:out of|\/)\s*5", text, re.IGNORECASE)
    if match:
        try:
            return int(round(float(match.group(1))))
        except ValueError:
            pass
    return 3


def parse_helpful_votes(text: str) -> int:
    """Parse '45 people found this helpful' or 'One person found this helpful'."""
    if not text:
        return 0
    t = text.lower().strip()
    if "one person" in t:
        return 1
    match = re.search(r"([\d,]+)\s*people found this helpful", t)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0


def parse_visible_review_count(text: str) -> int:
    """Extract total review count from 'Showing 1-10 of 1,245 reviews' or header text."""
    if not text:
        return 0
    m = re.search(r"of\s+([\d,]+)\s+(?:global\s+)?reviews?", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    m = re.search(r"([\d,]+)\s+with\s+reviews?", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    m = re.search(r"([\d,]+)\s+total\s+ratings?", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0


def crawl_amazon_reviews_for_asin(
    asin: str,
    keyword: str,
    policy_tier: str = "representative_polarity",  # "discovery_sample", "representative_polarity", "deep_hot_crawl"
    max_critical: Optional[int] = None,
    max_positive: Optional[int] = None,
    page_handle = None
) -> List[Dict[str, Any]]:
    """
    Crawl customer reviews for a single ASIN following the 3-Tier Review Collection Policy:
    - Tier 1: discovery_sample (5 critical + 5 positive, quick triage)
    - Tier 2: representative_polarity (15 critical + 15 positive, balanced VoC sample)
    - Tier 3: deep_hot_crawl (30 critical + 30 positive, deep Hot-tier dive)
    Tracks coverage metadata (visible_total, reviews_collected, review_coverage, filters_applied).
    """
    if max_critical is None or max_positive is None:
        if policy_tier == "discovery_sample":
            target_crit = 5
            target_pos = 5
        elif policy_tier == "deep_hot_crawl":
            target_crit = 30
            target_pos = 30
        else:
            target_crit = 15
            target_pos = 15
    else:
        target_crit = max_critical
        target_pos = max_positive

    def scrape_review_page(page, url: str, expected_sentiment: str):
        page_reviews = []
        visible_count = 0
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollBy(0, 1200)")
            page.wait_for_timeout(1000)

            eval_res = page.evaluate("""() => {
                const list = [];
                const filterInfoEl = document.querySelector('div[data-hook="cr-filter-info-review-rating-count"], #filter-info-section, [data-hook="total-review-count"]');
                const filterInfoText = filterInfoEl ? filterInfoEl.innerText.trim() : '';

                const cards = document.querySelectorAll('div[data-hook="review"]');
                cards.forEach(el => {
                    const id = el.getAttribute('id') || '';
                    const nameEl = el.querySelector('.a-profile-name');
                    const reviewer = nameEl ? nameEl.innerText.trim() : '';

                    const starEl = el.querySelector('i[data-hook="review-star-rating"] span, i[data-hook="cmps-review-star-rating"] span, .a-icon-alt');
                    const starsText = starEl ? starEl.innerText.trim() : '';

                    const titleEl = el.querySelector('a[data-hook="review-title"] span, span[data-hook="review-title"]');
                    const title = titleEl ? titleEl.innerText.trim() : '';

                    const bodyEl = el.querySelector('span[data-hook="review-body"] span, [data-hook="review-body"]');
                    const text = bodyEl ? bodyEl.innerText.trim() : '';

                    const dateEl = el.querySelector('span[data-hook="review-date"]');
                    const dateText = dateEl ? dateEl.innerText.trim() : '';

                    const verifiedEl = el.querySelector('span[data-hook="avp-badge"]');
                    const isVerified = Boolean(verifiedEl);

                    const helpfulEl = el.querySelector('span[data-hook="helpful-vote-statement"]');
                    const helpfulText = helpfulEl ? helpfulEl.innerText.trim() : '';

                    const variantEl = el.querySelector('a[data-hook="format-strip"]');
                    const variant = variantEl ? variantEl.innerText.trim() : '';

                    if (text && text.length > 5) {
                        list.push({
                            id,
                            reviewer,
                            starsText,
                            title,
                            text,
                            dateText,
                            isVerified,
                            helpfulText,
                            variant
                        });
                    }
                });
                return { cards: list, filterInfoText };
            }""")

            raw_cards = eval_res.get("cards", [])
            visible_count = parse_visible_review_count(eval_res.get("filterInfoText", ""))

            for item in raw_cards:
                stars = parse_star_rating(item.get("starsText"))
                votes = parse_helpful_votes(item.get("helpfulText"))
                review_obj = {
                    "review_id": item.get("id") or f"{asin}_{hash(item.get('text'))}",
                    "asin": asin,
                    "keyword": keyword,
                    "reviewer_name": item.get("reviewer") or "Amazon Customer",
                    "star_rating": stars,
                    "review_title": item.get("title") or "",
                    "review_text": item.get("text") or "",
                    "review_date": item.get("dateText") or "",
                    "verified_purchase": bool(item.get("isVerified")),
                    "helpful_votes": votes,
                    "variant_reviewed": item.get("variant") or "",
                    "sentiment": expected_sentiment
                }
                page_reviews.append(review_obj)
        except Exception as e:
            print(f"[ReviewCrawler] Notice scraping {url}: {e}")

        return page_reviews, visible_count

    def execute_with_page(page):
        critical_visible_found = 0
        positive_visible_found = 0

        # 1. Critical Reviews (1-3 stars)
        crit_reviews = []
        seen_crit_ids = set()
        max_crit_pages = max(1, (target_crit + 9) // 10)
        for p_num in range(1, max_crit_pages + 2):
            if len(crit_reviews) >= target_crit:
                break
            crit_url = f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_sr?filterByStar=critical&pageNumber={p_num}&sortBy=recent"
            page_revs, vis_count = scrape_review_page(page, crit_url, "critical")
            if vis_count and not critical_visible_found:
                critical_visible_found = vis_count
            new_added = 0
            for r in page_revs:
                if r["review_id"] not in seen_crit_ids:
                    seen_crit_ids.add(r["review_id"])
                    crit_reviews.append(r)
                    new_added += 1
                    if len(crit_reviews) >= target_crit:
                        break
            if new_added == 0:
                break
            time.sleep(random.uniform(0.3, 0.6))

        # 2. Positive Reviews (5 stars)
        pos_reviews = []
        seen_pos_ids = set()
        max_pos_pages = max(1, (target_pos + 9) // 10)
        for p_num in range(1, max_pos_pages + 2):
            if len(pos_reviews) >= target_pos:
                break
            pos_url = f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_sr?filterByStar=positive&pageNumber={p_num}&sortBy=helpful"
            page_revs, vis_count = scrape_review_page(page, pos_url, "positive")
            if vis_count and not positive_visible_found:
                positive_visible_found = vis_count
            new_added = 0
            for r in page_revs:
                if r["review_id"] not in seen_pos_ids:
                    seen_pos_ids.add(r["review_id"])
                    pos_reviews.append(r)
                    new_added += 1
                    if len(pos_reviews) >= target_pos:
                        break
            if new_added == 0:
                break
            time.sleep(random.uniform(0.3, 0.6))

        final_crit = crit_reviews[:target_crit]
        final_pos = pos_reviews[:target_pos]
        all_collected = final_crit + final_pos
        return all_collected, critical_visible_found, positive_visible_found, len(final_crit), len(final_pos)

    if page_handle:
        collected, crit_vis, pos_vis, crit_cnt, pos_cnt = execute_with_page(page_handle)
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
            collected, crit_vis, pos_vis, crit_cnt, pos_cnt = execute_with_page(page)
            context.close()

    # Save to SQLite with Review Collection Policy provenance metadata
    saved_count = db.save_reviews(
        asin=asin,
        keyword=keyword,
        reviews_list=collected,
        collection_method=policy_tier,
        filters_applied=["critical_1_3_star", "positive_5_star"],
        critical_visible_reviews=crit_vis,
        positive_visible_reviews=pos_vis,
        critical_collected=crit_cnt,
        positive_collected=pos_cnt
    )
    print(f"[ReviewCrawler] ASIN {asin} ({policy_tier}): Collected {len(collected)} reviews ({saved_count} saved, crit_vis: {crit_vis}, pos_vis: {pos_vis}).")
    return collected


def crawl_niche_reviews(keyword: str, top_n_products: int = 5, max_reviews_per_product: int = 40, job_id: str = None) -> int:
    """
    Crawl customer reviews for top products in a niche folder.
    """
    products = db.get_products(keyword=keyword, limit=top_n_products)
    if not products:
        print(f"[ReviewCrawler] No products found for '{keyword}' to crawl reviews.")
        return 0

    total_crawled = 0
    total_prods = len(products)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()

        for idx, prod in enumerate(products):
            asin = prod.get("asin")
            if not asin:
                continue

            if job_id:
                prog = 65 + int(((idx + 1) / total_prods) * 20)
                db.update_job(
                    job_id,
                    status="crawling_reviews",
                    progress=min(prog, 85),
                    message=f"Đang bóc tách Review khách hàng cho ASIN {asin} ({idx+1}/{total_prods})..."
                )

            reviews = crawl_amazon_reviews_for_asin(
                asin=asin,
                keyword=keyword,
                max_critical=max_reviews_per_product // 2,
                max_positive=max_reviews_per_product // 2,
                page_handle=page
            )
            total_crawled += len(reviews)
            time.sleep(random.uniform(0.5, 1.2))

        context.close()

    if job_id:
        db.update_job(
            job_id,
            progress=85,
            message=f"Đã thu thập {total_crawled} Customer Reviews thực tế từ Amazon.",
            new_reviews_count=total_crawled
        )

    return total_crawled


if __name__ == "__main__":
    test_asin = sys.argv[1] if len(sys.argv) > 1 else "B08N5WRWNW"
    print(f"Testing Amazon review crawler for ASIN {test_asin}...")
    revs = crawl_amazon_reviews_for_asin(test_asin, keyword="test", max_critical=5, max_positive=5)
    print(f"Collected {len(revs)} reviews:")
    for r in revs[:3]:
        print(f" - [{r['star_rating']}★] {r['review_title']}: {r['review_text'][:80]}...")
