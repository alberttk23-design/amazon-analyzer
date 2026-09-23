import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright
import backend.db as db
import backend.session_manager as session_manager

PROFILE_DIR = BASE_DIR / "data" / "browser_profile"


def parse_price(text: str) -> float:
    """Parse price string like '$29.99' or '29.99' into float."""
    if not text:
        return 0.0
    match = re.search(r"[\$£€]?\s*([\d,]+\.?\d*)", text)
    if match:
        val = match.group(1).replace(",", "")
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0


def parse_rating(text: str) -> float:
    """Parse rating text like '4.6 out of 5 stars' or '4.6' into float."""
    if not text:
        return 0.0
    match = re.search(r"([\d\.]+)\s*(?:out of|\/)\s*5", text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    match_num = re.search(r"^([\d\.]+)$", text.strip())
    if match_num:
        try:
            return float(match_num.group(1))
        except ValueError:
            pass
    return 0.0


def parse_count(text: str) -> int:
    """Parse count strings like '12,450', '2.5K', '1M' into integer."""
    if not text:
        return 0
    t = text.lower().replace(",", "").replace("+", "").strip()
    match_k = re.search(r"([\d\.]+)\s*k", t)
    if match_k:
        try:
            return int(float(match_k.group(1)) * 1000)
        except ValueError:
            pass
    match_m = re.search(r"([\d\.]+)\s*m", t)
    if match_m:
        try:
            return int(float(match_m.group(1)) * 1000000)
        except ValueError:
            pass
    match_digits = re.search(r"(\d+)", t)
    if match_digits:
        try:
            return int(match_digits.group(1))
        except ValueError:
            pass
    return 0


def parse_bought_past_month(text: str) -> int:
    """Parse '2K+ bought in past month' or '500+ bought in past month'."""
    if not text:
        return 0
    match = re.search(r"([\d\.]+)\s*k\+?\s*bought in past month", text, re.IGNORECASE)
    if match:
        try:
            return int(float(match.group(1)) * 1000)
        except ValueError:
            pass
    match_num = re.search(r"(\d+)\+?\s*bought in past month", text, re.IGNORECASE)
    if match_num:
        try:
            return int(match_num.group(1))
        except ValueError:
            pass
    return 0


def calculate_amazon_product_score(
    rating: float,
    reviews_count: int,
    bought_past_month: int,
    is_best_seller: bool,
    is_amazons_choice: bool
) -> float:
    """
    Calculate composite Product Viability Score (0 - 100):
    - Monthly Velocity (0 - 45 pts, 2K+ monthly sales = 45 pts)
    - Review Volume & Social Proof (0 - 25 pts, 5k+ reviews = 25 pts)
    - Star Rating Quality (0 - 20 pts, 4.5+ stars = 20 pts)
    - Badges (0 - 10 pts for Best Seller / Amazon's Choice)
    """
    sales_score = min(bought_past_month / 2000.0, 1.0) * 45.0
    reviews_score = min(reviews_count / 5000.0, 1.0) * 25.0
    rating_norm = max(0.0, min((rating - 3.5) / 1.5, 1.0)) * 20.0
    badge_score = (6.0 if is_best_seller else 0.0) + (4.0 if is_amazons_choice else 0.0)

    score = round(sales_score + reviews_score + rating_norm + badge_score, 1)
    return max(5.0, min(score, 100.0))


def generate_amazon_search_vectors(base_keyword: str) -> list:
    """Generate search vector variations to explore deep niche products."""
    kw = base_keyword.strip()
    return [
        kw,
        f"best {kw}",
        f"{kw} prime",
        f"top rated {kw}",
        f"{kw} deals"
    ]


def crawl_amazon_products(keyword: str, target_count: int = 20, job_id: str = None, target_folder: str = None) -> List[dict]:
    """
    Search Amazon US products using Playwright persistent browser context,
    enforces delivery Zip Code 10001 (New York), extracts key product data (ASIN, price, BSR, sales),
    deduplicates against SQLite, and stores to database.
    """
    pool_keyword = (target_folder or keyword).strip()
    if job_id:
        db.update_job(job_id, status="crawling_products", progress=10, message=f"Đang kiểm tra lịch sử ngách '{pool_keyword}'...")

    existing_asins, _ = db.get_existing_asins()
    print(f"[AmazonCrawler] Found {len(existing_asins)} existing ASINs in DB.")

    discovered_products = {}
    search_vectors = generate_amazon_search_vectors(keyword)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        print(f"[AmazonCrawler] Launching Chromium with persistent profile {PROFILE_DIR}...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()

        # Step 1: Check and set Zip Code 10001
        if job_id:
            db.update_job(job_id, progress=15, message="Đang xác minh địa chỉ giao hàng US Zip Code 10001 (New York)...")

        try:
            page.goto("https://www.amazon.com", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)
            session_manager.ensure_amazon_zip_code(page, "10001")
        except Exception as e:
            print(f"[AmazonCrawler Notice] Zip code check initial nav: {e}")

        # Step 2: Search across vectors until target_count new products are gathered
        for v_idx, query_str in enumerate(search_vectors):
            if len(discovered_products) >= target_count:
                break

            search_url = f"https://www.amazon.com/s?k={quote(query_str)}"
            print(f"[AmazonCrawler] Searching vector {v_idx+1}/{len(search_vectors)}: '{query_str}' -> {search_url}")

            if job_id:
                prog = 20 + int((len(discovered_products) / target_count) * 40)
                db.update_job(job_id, progress=min(prog, 60), message=f"Đang cào sản phẩm Amazon theo vector '{query_str}' ({len(discovered_products)}/{target_count})...")

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(2500)
                # Scroll down to load all lazy-loaded cards
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1000)
                page.evaluate("window.scrollBy(0, 2000)")
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"[AmazonCrawler] Error loading search page for '{query_str}': {e}")
                continue

            # Parse search result cards using evaluate
            cards_data = page.evaluate("""() => {
                const results = [];
                const items = document.querySelectorAll('div[data-component-type="s-search-result"]');
                
                items.forEach(el => {
                    const asin = el.getAttribute('data-asin');
                    if (!asin) return;

                    // Title
                    const titleEl = el.querySelector('h2 a span, h2 span');
                    const title = titleEl ? titleEl.innerText.trim() : '';

                    // URL
                    const linkEl = el.querySelector('h2 a');
                    const href = linkEl ? linkEl.getAttribute('href') : '';
                    const url = href ? (href.startsWith('http') ? href : 'https://www.amazon.com' + href) : '';

                    // Price
                    const priceOff = el.querySelector('.a-price .a-offscreen');
                    const priceText = priceOff ? priceOff.innerText.trim() : '';

                    // Original / Strike price
                    const origOff = el.querySelector('.a-text-price .a-offscreen, .a-price[data-a-strike="true"] .a-offscreen');
                    const origPriceText = origOff ? origOff.innerText.trim() : '';

                    // Star rating
                    const starEl = el.querySelector('.a-icon-star-small .a-icon-alt, .a-icon-alt');
                    const ratingText = starEl ? starEl.innerText.trim() : '';

                    // Reviews count
                    const revEl = el.querySelector('a[href*="#customerReviews"] span, span[aria-label*="ratings"]');
                    const reviewsText = revEl ? revEl.innerText.trim() : '';

                    // Bought past month
                    const boughtEl = el.querySelector('.a-row .a-size-base.a-color-secondary');
                    const boughtText = boughtEl ? boughtEl.innerText.trim() : '';

                    // Badges
                    const isBestSeller = Boolean(el.querySelector('.a-badge-text, span:has-text("Best Seller")') && el.innerText.includes('Best Seller'));
                    const isChoice = Boolean(el.innerText.includes("Amazon's Choice") || el.innerText.includes("Overall Pick"));
                    const isSponsored = Boolean(el.innerText.includes('Sponsored') || el.querySelector('.puis-sponsored-label-text, [data-component-type="sp-sponsored-result"]'));
                    const isPrime = Boolean(el.querySelector('.a-icon-prime'));

                    // Image
                    const imgEl = el.querySelector('img.s-image');
                    const imgUrl = imgEl ? (imgEl.getAttribute('src') || '') : '';

                    // Brand/Seller
                    const brandEl = el.querySelector('h5 .a-size-base-plus, .a-row.a-size-base.a-color-secondary .a-size-base');
                    const brand = brandEl ? brandEl.innerText.trim() : '';

                    results.push({
                        asin,
                        title,
                        url,
                        priceText,
                        origPriceText,
                        ratingText,
                        reviewsText,
                        boughtText,
                        isBestSeller,
                        isChoice,
                        isSponsored,
                        isPrime,
                        imgUrl,
                        brand
                    });
                });
                return results;
            }""")

            print(f"[AmazonCrawler] Extracted {len(cards_data)} raw product cards from page.")

            for raw in cards_data:
                asin = raw.get("asin")
                if not asin or asin in existing_asins or asin in discovered_products:
                    continue

                price = parse_price(raw.get("priceText"))
                orig_price = parse_price(raw.get("origPriceText")) or price
                rating = parse_rating(raw.get("ratingText")) or 0.0
                reviews_cnt = parse_count(raw.get("reviewsText"))
                bought_month = parse_bought_past_month(raw.get("boughtText"))
                is_bs = bool(raw.get("isBestSeller"))
                is_choice = bool(raw.get("isChoice"))
                is_spon = bool(raw.get("isSponsored"))

                score = calculate_amazon_product_score(
                    rating=rating,
                    reviews_count=reviews_cnt,
                    bought_past_month=bought_month,
                    is_best_seller=is_bs,
                    is_amazons_choice=is_choice
                )

                prod_record = {
                    "asin": asin,
                    "url": raw.get("url") or f"https://www.amazon.com/dp/{asin}",
                    "keyword": pool_keyword,
                    "title": raw.get("title") or "",
                    "brand": raw.get("brand") or "",
                    "seller": raw.get("seller") or "",
                    "price": price,
                    "original_price": orig_price,
                    "currency": "USD",
                    "rating": rating,
                    "reviews_count": reviews_cnt,
                    "bought_past_month": bought_month,
                    "bsr_rank": 0,  # Updated during deep review crawl or detail view
                    "bsr_category": pool_keyword,
                    "is_sponsored": 1 if is_spon else 0,
                    "is_best_seller": 1 if is_bs else 0,
                    "is_amazons_choice": 1 if is_choice else 0,
                    "prime_eligible": 1 if raw.get("isPrime") else 0,
                    "image_url": raw.get("imgUrl") or "",
                    "score": score
                }

                # Save to DB
                db.save_product(prod_record)
                discovered_products[asin] = prod_record

                if len(discovered_products) >= target_count:
                    break

        context.close()

    print(f"[AmazonCrawler] Done crawling products. Discovered and saved {len(discovered_products)} products.")
    if job_id:
        db.update_job(
            job_id,
            progress=65,
            message=f"Đã thu thập thành công {len(discovered_products)} sản phẩm cho '{pool_keyword}'.",
            new_products_count=len(discovered_products)
        )

    return list(discovered_products.values())


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    print(f"Testing Amazon crawler for '{kw}'...")
    res = crawl_amazon_products(kw, target_count=5)
    print(f"Results: {len(res)} products collected.")
    for p in res[:3]:
        print(f" - [{p['asin']}] {p['title'][:50]} | ${p['price']} | {p['rating']}★ | {p['bought_past_month']} sales/mo")
