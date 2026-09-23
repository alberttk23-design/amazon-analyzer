import pytest
from backend.breadth_crawler import parse_price, parse_rating, parse_count, parse_bought_past_month
from backend.depth_crawler import parse_detail_price
from backend.review_crawler import parse_star_rating, parse_helpful_votes, parse_visible_review_count


def test_parse_rating_zero_on_missing_or_corrupt():
    """Missing or corrupted rating strings must evaluate to 0.0, never 4.2 or 4.5."""
    assert parse_rating("") == 0.0
    assert parse_rating(None) == 0.0
    assert parse_rating("No ratings yet") == 0.0
    assert parse_rating("Currently unavailable") == 0.0
    assert parse_rating("4.8 out of 5 stars") == 4.8
    assert parse_rating("3.5 out of 5") == 3.5


def test_parse_price_zero_on_missing():
    """Missing prices must remain 0.0 and never invent dummy prices."""
    assert parse_price("") == 0.0
    assert parse_price(None) == 0.0
    assert parse_price("$29.99") == 29.99
    assert parse_price("$1,249.00") == 1249.00
    assert parse_detail_price("") == 0.0
    assert parse_detail_price("$19.95") == 19.95


def test_parse_count():
    assert parse_count("") == 0
    assert parse_count(None) == 0
    assert parse_count("1,452") == 1452
    assert parse_count("12K") == 12000
    assert parse_count("2.5K") == 2500


def test_parse_bought_past_month():
    assert parse_bought_past_month("") == 0
    assert parse_bought_past_month("1K+ bought in past month") == 1000
    assert parse_bought_past_month("50+ bought in past month") == 50
    assert parse_bought_past_month("10K+ bought in past month") == 10000


def test_parse_star_rating():
    assert parse_star_rating("1.0 out of 5 stars") == 1
    assert parse_star_rating("5.0 out of 5 stars") == 5
    assert parse_star_rating("2 out of 5") == 2


def test_parse_helpful_votes():
    assert parse_helpful_votes("") == 0
    assert parse_helpful_votes("One person found this helpful") == 1
    assert parse_helpful_votes("34 people found this helpful") == 34
    assert parse_helpful_votes("1,200 people found this helpful") == 1200


def test_parse_visible_review_count():
    assert parse_visible_review_count("") == 0
    assert parse_visible_review_count("Showing 1-10 of 1,245 reviews") == 1245
    assert parse_visible_review_count("Showing 1-10 of 42 reviews (filtered by 5 star)") == 42
    assert parse_visible_review_count("Showing 1-10 of 3,890 global reviews") == 3890
    assert parse_visible_review_count("520 total ratings, 88 with reviews") == 88
    assert parse_visible_review_count("1,500 total ratings") == 1500


def test_extract_cheap_products_no_fake_brand_or_price_invention():
    from backend.breadth_crawler import extract_cheap_products_from_html
    
    # HTML card with no brand element, unobserved strike price, and real data-csa-c-product-type="SUITCASE"
    html = """
    <div data-component-type="s-search-result" data-asin="B00EXAMPLE">
        <h2><span>Expandable Carry On Luggage 20 Inch</span></h2>
        <a href="/dp/B00EXAMPLE">Link</a>
        <div class="a-price"><span class="a-offscreen">$99.99</span></div>
        <div data-csa-c-product-type="SUITCASE"></div>
    </div>
    """
    prods, obs = extract_cheap_products_from_html(html, query="luggage", lane="keyword_search", niche="luggage", page=1)
    assert len(prods) == 1
    p = prods[0]
    assert p["asin"] == "B00EXAMPLE"
    assert p["price"] == 99.99
    # Crucial Data Truth assertions:
    assert p["original_price"] == 0.0, "Missing strike price must remain 0.0, never invent 99.99!"
    assert p["brand"] == "", "Must NEVER invent brand 'Expandable' from first word of title!"
    assert p["bsr_category"] == "Suitcase", "Must extract real Amazon product-type, never fake bsr_category = niche!"

