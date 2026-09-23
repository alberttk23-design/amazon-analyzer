import uuid
import pytest
import backend.db as db


def test_multi_niche_membership_and_tier_isolation():
    db.init_db()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    test_asin = f"B0TST{unique_suffix}"
    niche_a = f"Test_Niche_A_{unique_suffix}"
    niche_b = f"Test_Niche_B_{unique_suffix}"

    # Save product in Niche A as COLD
    db.save_product({
        "asin": test_asin,
        "title": "Versatile Travel Backpack Test",
        "brand": "TravelPro",
        "price": 89.99,
        "keyword": niche_a,
        "tier": "COLD",
        "tier_reason": "breadth_discovery",
        "product_depth": "SHALLOW"
    })

    # Save product in Niche B as WARM
    db.save_product({
        "asin": test_asin,
        "title": "Versatile Travel Backpack Test",
        "brand": "TravelPro",
        "price": 89.99,
        "keyword": niche_b,
        "tier": "WARM",
        "tier_reason": "promoted_by_bsr",
        "product_depth": "SHALLOW"
    })

    # Verify both memberships exist
    prods_a = db.get_products(keyword=niche_a, limit=100)
    item_a = next((p for p in prods_a if p["asin"] == test_asin), None)
    assert item_a is not None
    assert item_a["tier"] == "COLD"
    assert item_a["niche"] == niche_a

    prods_b = db.get_products(keyword=niche_b, limit=100)
    item_b = next((p for p in prods_b if p["asin"] == test_asin), None)
    assert item_b is not None
    assert item_b["tier"] == "WARM"
    assert item_b["niche"] == niche_b

    # Promote only in Niche A
    db.update_product_tier(test_asin, new_tier="HOT", reason="manual_boost", niche=niche_a)

    item_a_after = next((p for p in db.get_products(keyword=niche_a) if p["asin"] == test_asin), None)
    item_b_after = next((p for p in db.get_products(keyword=niche_b) if p["asin"] == test_asin), None)

    assert item_a_after["tier"] == "HOT"
    assert item_b_after["tier"] == "WARM"  # Untouched in Niche B!


def test_product_variations_persistence():
    db.init_db()
    parent_asin = f"B0PAR_{uuid.uuid4().hex[:6].upper()}"
    child_asin = f"B0CHD_{uuid.uuid4().hex[:6].upper()}"

    dims = {"Color": "Midnight Black", "Size": "Medium 24-inch"}
    success = db.save_product_variation(
        parent_asin=parent_asin,
        child_asin=child_asin,
        dimensions=dims,
        price=129.99,
        availability="In Stock"
    )
    assert success is True

    vars_list = db.get_product_variations(parent_asin)
    assert len(vars_list) >= 1
    v = next((item for item in vars_list if item["child_asin"] == child_asin), None)
    assert v is not None
    assert v["dimensions"]["Color"] == "Midnight Black"
    assert v["dimensions"]["Size"] == "Medium 24-inch"
    assert v["price"] == 129.99
    assert v["availability"] == "In Stock"
