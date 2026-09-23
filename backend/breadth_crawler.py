import json
import logging
import random
import re
import sys
import time
import uuid
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db
import backend.session_manager as session_manager
import backend.diagnostics as diagnostics
import backend.relevance_engine as relevance_engine
from datetime import datetime

logger = logging.getLogger("amazon.breadth")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
]


# ---------------------------------------------------------
# Multi-Lane Query Expansion
# ---------------------------------------------------------

def fetch_amazon_search_suggestions(seed_keyword: str) -> List[str]:
    """Lane B: Query Amazon's live search suggestion autocomplete API for consumer search vectors."""
    clean = seed_keyword.strip()
    url = f"https://completion.amazon.com/api/2017/suggestions?prefix={quote(clean)}&mid=ATVPDKIKX0DER&alias=aps"
    try:
        res = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            suggestions = [s.get("value") for s in data.get("suggestions", []) if s.get("value")]
            return suggestions[:10]
    except Exception as e:
        logger.debug(f"Search suggestions notice: {e}")
    return []


def expand_niche_lanes(seed_keyword: str) -> Dict[str, List[str]]:
    """
    Generate multi-lane query vectors across:
    - Lane A (Semantic Keywords)
    - Lane B (Live Amazon Suggestions)
    - Lane C (Use-Case & Buyer Intent)
    """
    kw = seed_keyword.strip()

    # Lane A: Semantic variations
    lane_a = [
        kw,
        f"best {kw}",
        f"{kw} prime",
        f"top rated {kw}",
        f"heavy duty {kw}",
        f"{kw} deals",
        f"compact {kw}",
        f"professional {kw}"
    ]

    # Lane B: Live Search Suggestions from Amazon
    lane_b = fetch_amazon_search_suggestions(kw)

    # Lane C: Buyer Intent / Use-cases (Domain-Agnostic E-Commerce Intent Vectors)
    lane_c = [
        f"best {kw}",
        f"{kw} for women",
        f"{kw} for men",
        f"{kw} reviews",
        f"top rated {kw}",
        f"{kw} gift",
        f"{kw} upgrade",
        f"heavy duty {kw}"
    ]

    return {
        "keyword_search": lane_a,
        "suggestions": [s for s in lane_b if s not in lane_a],
        "intent_modifiers": [s for s in lane_c if s not in lane_a]
    }


STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "in", "on", "of", "to", "by", "at", "from",
    "pack", "set", "pcs", "piece", "pieces", "black", "white", "blue", "red", "green", "pink",
    "inch", "inches", "oz", "ml", "lb", "portable", "new", "upgraded", "2024", "2025", "2026"
}

def extract_dynamic_query_candidates(seed_keyword: str, discovered_titles: List[str], max_tokens: int = 5) -> List[str]:
    """
    Learns high-frequency 2-word phrase patterns from product titles in this specific niche.
    Adaptive query learning: discovers actual vocabulary used by top sellers.
    """
    word_counts: Dict[str, int] = {}
    seed_tokens = set(seed_keyword.lower().split())
    for t in discovered_titles:
        clean_t = re.sub(r"[^a-zA-Z0-9\s]", " ", t.lower())
        words = [w for w in clean_t.split() if len(w) > 2 and w not in STOPWORDS and w not in seed_tokens]
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            word_counts[phrase] = word_counts.get(phrase, 0) + 1

    sorted_phrases = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [f"{p[0]} {seed_keyword}" for p in sorted_phrases[:max_tokens]]


# ---------------------------------------------------------
# Strategy Ladder HTML Parser
# ---------------------------------------------------------

def parse_price(text: str) -> float:
    if not text:
        return 0.0
    match = re.search(r"[\$£€]?\s*([\d,]+\.?\d*)", text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0.0


def parse_rating(text: str) -> float:
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


def extract_cheap_products_from_html(
    html_content: str,
    query: str,
    lane: str,
    niche: str,
    page: int = 1,
    run_id: str = ""
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extracts cheap fields for all ASINs appearing on the Amazon search result page.
    Returns:
      (products, observations)
      - products: candidate entity records for products table
      - observations: granular search observations (placement_type: SPONSORED/ORGANIC/UNKNOWN, page, position)
    """
    soup = BeautifulSoup(html_content, "html.parser")
    product_cards = soup.select('div[data-component-type="s-search-result"]')
    products = []
    observations = []

    for card_idx, card in enumerate(product_cards, start=1):
        asin = card.get("data-asin")
        if not asin or len(asin) != 10:
            continue

        # Title & Brand
        all_h2 = [h.get_text(strip=True) for h in card.find_all("h2") if h.get_text(strip=True)]
        img_el = card.select_one("img.s-image")
        img_alt = img_el.get("alt", "").strip() if img_el else ""

        card_brand = all_h2[0] if len(all_h2) >= 2 else ""
        raw_title = all_h2[1] if len(all_h2) >= 2 else (all_h2[0] if all_h2 else "")

        if img_alt and len(img_alt) > len(raw_title) and not img_alt.startswith("Sponsored"):
            title = img_alt
        elif card_brand and not raw_title.lower().startswith(card_brand.lower()):
            title = f"{card_brand} {raw_title}"
        elif not raw_title and img_alt:
            title = img_alt
        else:
            title = raw_title or f"Amazon Product {asin}"

        # URL
        link_el = card.select_one("h2 a, a.a-link-normal.s-no-outline, a[href*='/dp/']")
        href = link_el.get("href") if link_el else f"/dp/{asin}"
        url = urljoin("https://www.amazon.com", href)

        # Price
        price_off = card.select_one(".a-price .a-offscreen")
        price = parse_price(price_off.get_text(strip=True)) if price_off else 0.0

        # Original / Strike price
        orig_off = card.select_one(".a-text-price .a-offscreen, .a-price[data-a-strike='true'] .a-offscreen")
        orig_price = parse_price(orig_off.get_text(strip=True)) if orig_off else price

        # Rating
        star_el = card.select_one(".a-icon-star-small .a-icon-alt, .a-icon-alt")
        rating = parse_rating(star_el.get_text(strip=True)) if star_el else 0.0

        # Reviews Count
        rev_el = card.select_one("a[href*='#customerReviews'] span, span[aria-label*='ratings']")
        reviews_count = parse_count(rev_el.get_text(strip=True)) if rev_el else 0

        # Bought past month
        bought_el = card.select_one(".a-row .a-size-base.a-color-secondary")
        bought_text = bought_el.get_text(strip=True) if bought_el else ""
        bought_month = parse_bought_past_month(bought_text)

        # Badges
        card_text = card.get_text()
        is_best_seller = 1 if "Best Seller" in card_text else 0
        is_choice = 1 if "Amazon's Choice" in card_text or "Overall Pick" in card_text else 0
        prime_eligible = 1 if card.select_one(".a-icon-prime") else 0

        # Sponsored placement recognition with evidence
        has_ad_url = ("sspa/click" in href) or ("/slredirect/" in href)
        has_ad_label = bool(card.select_one(".puis-sponsored-label-text, [data-component-type='sp-sponsored-result']")) or ("Sponsored" in card_text)

        if has_ad_url or has_ad_label:
            placement_type = "SPONSORED"
            sponsored_evidence = "ad_url_or_label"
        elif card.has_attr("data-asin") and not has_ad_label and not has_ad_url:
            placement_type = "ORGANIC"
            sponsored_evidence = "organic_container"
        else:
            placement_type = "UNKNOWN"
            sponsored_evidence = "ambiguous_markup"

        # Coupon detection
        coupon_el = card.select_one(".s-coupon-unclipped, [data-action='s-coupon-action'], .s-coupon-clipped, span.a-color-discount")
        coupon_text = coupon_el.get_text(strip=True) if coupon_el else ""

        # Delivery signal
        deliv_el = card.select_one("span[aria-label*='delivery'], .a-row.a-size-base .a-color-base.a-text-bold, .a-row:has(.a-icon-prime)")
        deliv_text = deliv_el.get_text(strip=True) if deliv_el else ""

        # Image
        img_el = card.select_one("img.s-image")
        image_url = img_el.get("src") if img_el else ""

        # Brand
        brand_el = card.select_one("h5 .a-size-base-plus, .a-row.a-size-base.a-color-secondary .a-size-base")
        brand = card_brand or (brand_el.get_text(strip=True) if brand_el else "")
        if not brand and title:
            first_w = title.split()[0]
            if len(first_w) > 2 and not first_w.isdigit():
                brand = first_w

        # Score calculation (Sales 45%, Reviews 25%, Rating 20%, Badges 10%)
        sales_score = min(bought_month / 2000.0, 1.0) * 45.0
        reviews_score = min(reviews_count / 5000.0, 1.0) * 25.0
        rating_norm = max(0.0, min((rating - 3.5) / 1.5, 1.0)) * 20.0 if rating > 0 else 0.0
        badge_score = (6.0 if is_best_seller else 0.0) + (4.0 if is_choice else 0.0)
        score = round(max(5.0, min(sales_score + reviews_score + rating_norm + badge_score, 100.0)), 1)

        product_record = {
            "asin": asin,
            "url": url,
            "keyword": niche,
            "title": title,
            "brand": brand,
            "seller": "",
            "price": price,
            "original_price": orig_price,
            "currency": "USD",
            "rating": rating,
            "reviews_count": reviews_count,
            "bought_past_month": bought_month,
            "bsr_rank": 0,
            "bsr_category": niche,
            "is_sponsored": 1 if placement_type == "SPONSORED" else 0,
            "is_best_seller": is_best_seller,
            "is_amazons_choice": is_choice,
            "prime_eligible": prime_eligible,
            "image_url": image_url,
            "score": score,
            "tier": "COLD",
            "tier_reason": f"discovered_via_{lane}",
            "product_depth": "SHALLOW",
            "review_depth": "NONE",
            "discovery_lane": lane,
            "discovered_via_query": query,
            "enrichment_status": "enriched" if price > 0 and rating > 0 else "discovered"
        }
        products.append(product_record)

        obs_record = {
            "run_id": run_id,
            "niche": niche,
            "asin": asin,
            "query": query,
            "page": page,
            "position": card_idx,
            "placement_type": placement_type,
            "sponsored_evidence": sponsored_evidence,
            "coupon": coupon_text,
            "delivery_signal": deliv_text,
            "price": price,
            "rating": rating,
            "reviews_count": reviews_count,
            "badges": [b for b in ["Best Seller" if is_best_seller else "", "Amazon's Choice" if is_choice else ""] if b]
        }
        observations.append(obs_record)

    return products, observations


# ---------------------------------------------------------
# Strategy Ladder (Fast HTTP -> Local Browser)
def check_has_next_page(html: str) -> bool:
    """Check if search results page has an active next page button (s-pagination-next)."""
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    next_btn = soup.select_one('.s-pagination-next')
    if not next_btn:
        return False
    classes = next_btn.get("class", [])
    if "s-pagination-disabled" in classes or next_btn.get("aria-disabled") == "true":
        return False
    return True


# ---------------------------------------------------------
# Adaptive Strategy Ladder Fetcher
# ---------------------------------------------------------

class StrategyLadderFetcher:
    """
    Tiered fallback scraping strategy:
    - Level 1: Fast direct HTTP requests with randomized headers.
    - Check response: Captcha? Blocked? Empty?
    - If blocked/captcha: Automatically switch to Playwright local browser session.
    - On failure/zero-cards: Capture HTML dump and screenshot for diagnostics.
    """
    def __init__(self):
        self.session = requests.Session()
        self.browser_context = None
        self.playwright_instance = None

    def fetch_page_html(self, url: str, query: str = "", niche: str = "", run_id: str = "") -> Tuple[str, str, str]:
        """Returns (html_content, status_str, strategy_used)."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.amazon.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

        # Level 1: Fast HTTP
        try:
            res = self.session.get(url, headers=headers, timeout=12)
            if res.status_code == 200:
                html = res.text
                if "Type the characters you see in this image" in html or "validateCaptcha" in html:
                    logger.info("[StrategyLadder] Fast HTTP encountered Captcha! Capturing snapshot & switching to Playwright...")
                    diagnostics.capture_failure_snapshot(
                        niche=niche, query_or_asin=query or url,
                        status="captcha_detected",
                        reason="Fast HTTP returned Amazon Captcha challenge",
                        html=html, run_id=run_id
                    )
                elif 'data-component-type="s-search-result"' in html:
                    return html, "success", "http_fast"
                else:
                    logger.debug("[StrategyLadder] Fast HTTP returned 0 search result cards. Trying Playwright...")
            elif res.status_code in (403, 429, 503):
                logger.warning(f"[StrategyLadder] Fast HTTP blocked with status {res.status_code}. Switching to Playwright...")
                diagnostics.capture_failure_snapshot(
                    niche=niche, query_or_asin=query or url,
                    status=f"blocked_{res.status_code}",
                    reason=f"Fast HTTP returned HTTP status {res.status_code}",
                    html=res.text if res else "", run_id=run_id
                )
            else:
                logger.warning(f"[StrategyLadder] Fast HTTP got status {res.status_code}. Switching to Playwright...")
        except Exception as e:
            logger.debug(f"[StrategyLadder] Fast HTTP notice: {e}. Switching to Playwright...")

        # Level 2: Playwright Local Browser
        return self._fetch_via_playwright(url, query=query, niche=niche, run_id=run_id)

    def _fetch_via_playwright(self, url: str, query: str = "", niche: str = "", run_id: str = "") -> Tuple[str, str, str]:
        from playwright.sync_api import sync_playwright
        profile_dir = BASE_DIR / "data" / "browser_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=True,
                    viewport={"width": 1440, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                    user_agent=random.choice(USER_AGENTS)
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(2000)
                session_manager.ensure_amazon_zip_code(page, "10001")
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1000)
                html = page.content()

                is_captcha = "Type the characters you see in this image" in html or "validateCaptcha" in html
                has_cards = 'data-component-type="s-search-result"' in html

                if is_captcha:
                    logger.warning("[StrategyLadder] Playwright encountered Captcha challenge! Dumping snapshot & screenshot...")
                    diagnostics.capture_failure_snapshot(
                        niche=niche, query_or_asin=query or url,
                        status="captcha_detected",
                        reason="Playwright session reached Amazon Captcha prompt",
                        html=html, page_handle=page, run_id=run_id
                    )
                    context.close()
                    return html, "captcha", "playwright_browser"

                if not has_cards:
                    logger.warning("[StrategyLadder] Playwright returned 0 search result cards. Dumping snapshot...")
                    diagnostics.capture_failure_snapshot(
                        niche=niche, query_or_asin=query or url,
                        status="zero_cards",
                        reason="Playwright page loaded successfully but zero search result cards were found",
                        html=html, page_handle=page, run_id=run_id
                    )
                    context.close()
                    return html, "zero_cards", "playwright_browser"

                context.close()
                return html, "success", "playwright_browser"
        except Exception as e:
            logger.error(f"[StrategyLadder] Playwright error for {url}: {e}")
            diagnostics.capture_failure_snapshot(
                niche=niche, query_or_asin=query or url,
                status="playwright_error",
                reason=f"Playwright navigation exception: {e}",
                html="", run_id=run_id
            )
            return "", "error", "playwright_browser"


# ---------------------------------------------------------
# Breadth Discovery Saturation Engine
# ---------------------------------------------------------

def run_breadth_discovery_saturation_loop(
    seed_keyword: str,
    target_niche: Optional[str] = None,
    max_queries: int = 20,
    max_pages_per_query: int = 3,
    saturation_threshold_yield: float = 4.0,  # Below 4% new ASINs considered diminishing yield
    resume: bool = True,
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main Breadth Discovery Pipeline:
    1. Expands seed keyword into multi-lane queries and enqueues to discovery_query_queue (Checkpoint/Resume).
    2. Sequentially executes queries using the Strategy Ladder.
    3. Traverses multiple pages per query (&page=1, 2, 3...) using check_has_next_page.
    4. Gathers cheap fields for 100% of candidates and saves them into DB as COLD tier.
    5. Computes marginal discovery yield on each step and detects Discovery Saturation.
    6. Logs all queries, denominators, duplicates into Coverage Ledger.
    """
    niche = (target_niche or seed_keyword).strip()
    session_id = str(uuid.uuid4())[:8]

    if job_id:
        db.update_job(job_id, status="breadth_discovery", progress=10, message=f"Khởi động Multi-Lane Breadth Discovery cho '{niche}'...")

    # Load existing ASINs for this niche
    existing_asins, _ = db.get_existing_asins(keyword=niche)
    cumulative_unique: Set[str] = set(existing_asins)
    initial_count = len(cumulative_unique)

    logger.info(f"[BreadthCrawler] Initial universe for '{niche}' has {initial_count} ASINs.")

    # 1. Multi-lane expansion and queue persistence (Composite UNIQUE(niche, query))
    lanes = expand_niche_lanes(seed_keyword)
    queue_entries: List[Tuple[str, str, int]] = []

    for q in lanes.get("keyword_search", []):
        queue_entries.append(("keyword_search", q, 1))
    for q in lanes.get("suggestions", []):
        queue_entries.append(("suggestions", q, 2))
    for q in lanes.get("intent_modifiers", []):
        queue_entries.append(("intent_modifiers", q, 3))

    db.enqueue_discovery_queries(niche, queue_entries)

    # 2. Reclaim any stale in_progress queries from crashes or interruptions
    reclaimed = db.reclaim_stale_in_progress_queries(niche, timeout_minutes=15)
    if reclaimed > 0:
        logger.info(f"[BreadthCrawler] Reclaimed {reclaimed} stale in-progress queries for '{niche}'.")

    discovered_brands: Set[str] = set()
    discovered_titles: List[str] = []
    consecutive_low_yield_count = 0
    queries_executed = 0
    total_new_discovered = 0
    failures_403 = 0
    failures_429 = 0
    parser_partial = 0

    fetcher = StrategyLadderFetcher()
    db.create_research_run(session_id, niche)

    # Dynamic Queue Loop: dynamically pulls newly enqueued brand & vocabulary queries in the SAME run
    while queries_executed < max_queries:
        item = db.get_next_pending_query(niche)
        if not item:
            logger.info(f"[BreadthCrawler] Queue exhausted for '{niche}' or all queries processed.")
            break

        lane = item.get("lane", "keyword_search")
        query = item.get("query", "")
        db.mark_discovery_query_status(niche, query, "in_progress")

        queries_executed += 1
        query_new_asins = 0
        query_total_asins = 0
        consecutive_zero_page_count = 0

        # True Page-Level Checkpoint / Resume
        start_page = max(1, item.get("next_page", 1))
        target_pages = item.get("target_pages", max_pages_per_query)

        # Multi-Page Pagination Loop (Page start_page to target_pages)
        for page_num in range(start_page, target_pages + 1):
            search_url = f"https://www.amazon.com/s?k={quote(query)}&page={page_num}" if page_num > 1 else f"https://www.amazon.com/s?k={quote(query)}"
            logger.info(f"[BreadthCrawler] [{queries_executed}/{max_queries}] [{lane}] Query: '{query}' (Page {page_num}/{target_pages}) -> {search_url}")

            if job_id:
                prog = 10 + int((queries_executed / max_queries) * 60)
                db.update_job(
                    job_id,
                    progress=min(prog, 70),
                    message=f"Đang cào rộng ({lane}): '{query}' [Trang {page_num}] | Đã tích lũy {len(cumulative_unique)} ASINs...",
                    cumulative_universe_count=len(cumulative_unique)
                )

            html, status, strategy_used = fetcher.fetch_page_html(search_url, query=query, niche=niche, run_id=session_id)
            if not html or status in ("zero_cards", "captcha", "error"):
                if status == "captcha":
                    failures_429 += 1
                elif status in ("error", "zero_cards"):
                    parser_partial += 1

                db.record_coverage_ledger_entry(
                    session_id=session_id,
                    niche=niche,
                    lane=lane,
                    query_or_target=query,
                    page_number=page_num,
                    asins_found_total=0,
                    asins_new_unique=0,
                    asins_duplicate=0,
                    cumulative_unique=len(cumulative_unique),
                    status=f"empty_or_{status}",
                    strategy_used=strategy_used
                )
                db.update_query_progress(niche, query, page_num, status="in_progress", error=f"empty_or_{status}")
                break

            products, observations = extract_cheap_products_from_html(
                html, query=query, lane=lane, niche=niche, page=page_num, run_id=session_id
            )
            asins_found_page = len(products)
            if asins_found_page == 0:
                parser_partial += 1
                db.update_query_progress(niche, query, page_num, status="in_progress", error="zero_products_parsed")
                break

            page_new_unique = 0
            page_duplicates = 0

            for p in products:
                asin = p["asin"]
                if p.get("title"):
                    discovered_titles.append(p["title"])

                if asin in cumulative_unique:
                    page_duplicates += 1
                else:
                    page_new_unique += 1
                    cumulative_unique.add(asin)
                    total_new_discovered += 1
                    if p.get("brand") and len(p["brand"]) > 2:
                        discovered_brands.add(p["brand"])
                        db.upsert_brand_entity(p["brand"], niche)

                # Classify relevance for data truth
                try:
                    rel_result = relevance_engine.classify_product(p, niche=niche, query_context=query)
                    p["relevance_class"] = rel_result["relevance_class"]
                    p["relevance_confidence"] = rel_result["relevance_confidence"]
                    p["relevance_evidence"] = rel_result["relevance_evidence"]
                    p["relevance_rule_version"] = rel_result["rule_version"]
                    p["sub_cluster"] = rel_result["sub_cluster"]
                except Exception as e:
                    logger.debug(f"Relevance classification error for {asin}: {e}")

                # Save candidate entity without bloating product_snapshots on every search card
                db.save_product(p, record_snapshot=False)

            # Record granular search observations for every card (Sponsored vs Organic with exact position)
            for obs in observations:
                db.record_search_observation(obs)

            query_new_asins += page_new_unique
            query_total_asins += asins_found_page

            # Update page progress in queue checkpoint
            db.update_query_progress(niche, query, page_num, status="in_progress")

            # Log entry to Coverage Ledger for this specific page
            db.record_coverage_ledger_entry(
                session_id=session_id,
                niche=niche,
                lane=lane,
                query_or_target=query,
                page_number=page_num,
                asins_found_total=asins_found_page,
                asins_new_unique=page_new_unique,
                asins_duplicate=page_duplicates,
                cumulative_unique=len(cumulative_unique),
                status="success",
                strategy_used=strategy_used
            )

            logger.info(f" -> [Page {page_num}] Found: {asins_found_page} | New: {page_new_unique} | Cumulative: {len(cumulative_unique)}")

            # Robust Saturation Check: Require 2 consecutive zero-yield pages before breaking
            if page_new_unique == 0:
                consecutive_zero_page_count += 1
                if consecutive_zero_page_count >= 2:
                    logger.info(f"[BreadthCrawler] 2 consecutive pages yielded 0 new unique ASINs. Stopping pagination for '{query}'.")
                    break
            else:
                consecutive_zero_page_count = 0

            # If no active next page button, stop paginating this query
            if not check_has_next_page(html):
                logger.info(f"[BreadthCrawler] Reached last page according to pagination controls for '{query}'.")
                break

            time.sleep(random.uniform(0.6, 1.3))

        marginal_yield = round((query_new_asins / query_total_asins * 100), 2) if query_total_asins > 0 else 0.0
        db.mark_discovery_query_status(niche, query, "completed")

        # Check Saturation condition
        if query_total_asins >= 10 and marginal_yield < saturation_threshold_yield:
            consecutive_low_yield_count += 1
            if consecutive_low_yield_count >= 3:
                logger.info(f"[BreadthCrawler] 🎯 DISCOVERY SATURATION REACHED! 3 consecutive queries yielded < {saturation_threshold_yield}%.")
                db.mark_discovery_query_status(niche, query, "saturated")
                break
        else:
            consecutive_low_yield_count = 0

        # Dynamically inject high-signal brand queries into queue
        if discovered_brands:
            brand_injections: List[Tuple[str, str, int]] = []
            for b in list(discovered_brands)[:4]:
                brand_query = f"{b} {seed_keyword}"
                brand_injections.append(("brand_expansion", brand_query, 4))
            db.enqueue_discovery_queries(niche, brand_injections)

        # Dynamically learn 2-word phrase queries from discovered titles
        if len(discovered_titles) >= 15 and queries_executed % 3 == 0:
            learned_queries = extract_dynamic_query_candidates(seed_keyword, discovered_titles, max_tokens=3)
            learned_injections = [("adaptive_vocabulary", lq, 5) for lq in learned_queries]
            db.enqueue_discovery_queries(niche, learned_injections)

        time.sleep(random.uniform(0.5, 1.2))

    # Update research run summary
    db.update_research_run(
        session_id,
        completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        queries_executed=queries_executed,
        unique_asins=len(cumulative_unique),
        brands_count=len(discovered_brands),
        new_asins_this_run=total_new_discovered,
        discovery_status="approaching saturation" if consecutive_low_yield_count >= 3 else "completed_pass",
        failures_403=failures_403,
        failures_429=failures_429,
        parser_partial=parser_partial
    )

    # Finalize batch relevance classification for the niche
    try:
        rel_summary = relevance_engine.classify_niche_products(niche)
        logger.info(f"[BreadthCrawler] Relevance classification complete for {niche}: {rel_summary}")
    except Exception as e:
        logger.warning(f"[BreadthCrawler] Batch relevance classification warning: {e}")

    summary = {
        "niche": niche,
        "session_id": session_id,
        "queries_executed": queries_executed,
        "initial_universe_size": initial_count,
        "total_new_discovered": total_new_discovered,
        "final_universe_size": len(cumulative_unique),
        "saturation_reached": consecutive_low_yield_count >= 3,
        "unique_brands_found": len(discovered_brands)
    }

    if job_id:
        db.update_job(
            job_id,
            status="breadth_completed",
            progress=75,
            message=f"Hoàn thành cào rộng! Đã thu nạp {total_new_discovered} ASINs mới (Tổng vũ trụ: {len(cumulative_unique)} ASINs).",
            new_products_count=total_new_discovered,
            cumulative_universe_count=len(cumulative_unique)
        )

    logger.info(f"[BreadthCrawler] Completed discovery pass: {json.dumps(summary, ensure_ascii=False)}")
    return summary


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    print(f"Testing Breadth Crawler for '{kw}'...")
    res = run_breadth_discovery_saturation_loop(kw, max_queries=5)
    print("Result:", json.dumps(res, indent=2))
