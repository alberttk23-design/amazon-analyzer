import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from playwright.sync_api import sync_playwright
import backend.db as db

PROFILE_DIR = BASE_DIR / "data" / "browser_profile"
logger = logging.getLogger("amazon.ads_bestsellers")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def crawl_sponsored_ads(keyword: str, max_ads: int = 30, job_id: str = None) -> List[Dict[str, Any]]:
    """
    Crawl sponsored product ads from Amazon search for the keyword.
    Captures ad positioning, title, price, brand, and reviews count.
    """
    clean_kw = keyword.strip()
    if job_id:
        db.update_job(job_id, status="crawling_ads", progress=20, message=f"Đang quét Sponsored Ads cho '{clean_kw}'...")

    search_url = f"https://www.amazon.com/s?k={quote(clean_kw)}"
    ads_list = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollBy(0, 1500)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(1500)

            raw_ads = page.evaluate("""() => {
                const list = [];
                const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
                cards.forEach(el => {
                    const isSponsored = Boolean(
                        el.innerText.includes('Sponsored') || 
                        el.querySelector('.puis-sponsored-label-text, [data-component-type="sp-sponsored-result"]')
                    );
                    if (!isSponsored) return;

                    const asin = el.getAttribute('data-asin') || '';
                    if (!asin) return;

                    const titleEl = el.querySelector('h2 a span, h2 span');
                    const title = titleEl ? titleEl.innerText.trim() : '';

                    const priceOff = el.querySelector('.a-price .a-offscreen');
                    const priceText = priceOff ? priceOff.innerText.trim() : '';

                    const starEl = el.querySelector('.a-icon-star-small .a-icon-alt, .a-icon-alt');
                    const ratingText = starEl ? starEl.innerText.trim() : '';

                    const revEl = el.querySelector('a[href*="#customerReviews"] span, span[aria-label*="ratings"]');
                    const reviewsText = revEl ? revEl.innerText.trim() : '';

                    const imgEl = el.querySelector('img.s-image');
                    const imgUrl = imgEl ? (imgEl.getAttribute('src') || '') : '';

                    const brandEl = el.querySelector('h5 .a-size-base-plus, .a-row.a-size-base.a-color-secondary .a-size-base');
                    const brand = brandEl ? brandEl.innerText.trim() : '';

                    list.push({
                        asin,
                        title,
                        priceText,
                        ratingText,
                        reviewsText,
                        imgUrl,
                        brand
                    });
                });
                return list;
            }""")

            for item in raw_ads:
                # Parse numeric fields
                price_match = re.search(r"[\$£€]?\s*([\d,]+\.?\d*)", item.get("priceText", ""))
                price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

                rating_match = re.search(r"([\d\.]+)", item.get("ratingText", ""))
                rating = float(rating_match.group(1)) if rating_match else 0.0

                rev_match = re.search(r"([\d,]+)", item.get("reviewsText", "").replace("+", ""))
                rev_count = int(rev_match.group(1).replace(",", "")) if rev_match else 0

                ads_list.append({
                    "asin": item.get("asin"),
                    "title": item.get("title"),
                    "price": price,
                    "rating": rating,
                    "reviews_count": rev_count,
                    "brand": item.get("brand") or "Sponsored Brand",
                    "image_url": item.get("imgUrl") or ""
                })
                if len(ads_list) >= max_ads:
                    break
        except Exception as e:
            logger.error(f"Error crawling sponsored ads: {e}")
        finally:
            context.close()

    db.save_sponsored_ads(ads_list, keyword=clean_kw)
    logger.info(f"Crawled {len(ads_list)} sponsored ads for '{clean_kw}'.")
    return ads_list


def crawl_best_sellers(category_url: str = None, category_name: str = "Best Sellers", max_items: int = 50, job_id: str = None) -> List[Dict[str, Any]]:
    """
    Crawl Amazon Top Best Sellers list.
    Default URL: Amazon Best Sellers Home.
    """
    target_url = category_url or "https://www.amazon.com/Best-Sellers/zgbs"
    if job_id:
        db.update_job(job_id, status="crawling_bestsellers", progress=30, message=f"Đang cào bảng xếp hạng Best Sellers ({category_name})...")

    items_list = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollBy(0, 1500)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollBy(0, 2500)")
            page.wait_for_timeout(1500)

            raw_items = page.evaluate("""() => {
                const list = [];
                // Look for best seller cards
                const cards = document.querySelectorAll('div[id*="gridItemRoot"], .zg-grid-general-faceout, [data-asin]');
                
                cards.forEach(el => {
                    const asin = el.getAttribute('data-asin') || '';
                    const rankEl = el.querySelector('.zg-badge-text, span[class*="zg-badge"], .zg-bdg-text');
                    const rankText = rankEl ? rankEl.innerText.trim() : '';

                    const titleEl = el.querySelector('div[class*="_p13n-zg-list-grid-desktop_truncationStyles"] div, a span div, h2');
                    const title = titleEl ? titleEl.innerText.trim() : (el.innerText.split('\\n')[1] || '');

                    const priceEl = el.querySelector('.p13n-sc-price, ._cDEzb_p13n-sc-price_3mJ9Z, .a-price .a-offscreen');
                    const priceText = priceEl ? priceEl.innerText.trim() : '';

                    const starEl = el.querySelector('.a-icon-alt');
                    const ratingText = starEl ? starEl.innerText.trim() : '';

                    const revEl = el.querySelector('.a-size-small');
                    const reviewsText = revEl ? revEl.innerText.trim() : '';

                    const imgEl = el.querySelector('img');
                    const imgUrl = imgEl ? (imgEl.getAttribute('src') || '') : '';

                    if (asin || title) {
                        list.push({
                            asin,
                            rankText,
                            title,
                            priceText,
                            ratingText,
                            reviewsText,
                            imgUrl
                        });
                    }
                });
                return list;
            }""")

            for idx, item in enumerate(raw_items):
                rank_match = re.search(r"#?(\d+)", item.get("rankText", ""))
                rank = int(rank_match.group(1)) if rank_match else (idx + 1)

                price_match = re.search(r"[\$£€]?\s*([\d,]+\.?\d*)", item.get("priceText", ""))
                price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

                rating_match = re.search(r"([\d\.]+)", item.get("ratingText", ""))
                rating = float(rating_match.group(1)) if rating_match else 4.5

                rev_match = re.search(r"([\d,]+)", item.get("reviewsText", ""))
                rev_count = int(rev_match.group(1).replace(",", "")) if rev_match else 100

                asin = item.get("asin") or f"BS_{rank}"

                items_list.append({
                    "asin": asin,
                    "rank": rank,
                    "title": item.get("title") or f"Best Seller #{rank}",
                    "price": price,
                    "rating": rating,
                    "reviews_count": rev_count,
                    "image_url": item.get("imgUrl") or ""
                })

                if len(items_list) >= max_items:
                    break
        except Exception as e:
            logger.error(f"Error crawling best sellers: {e}")
        finally:
            context.close()

    db.save_best_sellers(items_list, category=category_name)
    logger.info(f"Crawled {len(items_list)} Best Sellers in category '{category_name}'.")
    return items_list


if __name__ == "__main__":
    print("Testing Sponsored Ads and Best Sellers crawler...")
    ads = crawl_sponsored_ads("portable blender", max_ads=5)
    print("Sponsored Ads:", len(ads))
