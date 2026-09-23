import pytest
from backend.relevance_engine import classify_product


def test_acceptance_case_1_samsonite_spinner():
    """'Samsonite Freeform Carry-On Spinner' -> CORE"""
    p = {
        "title": "Samsonite Freeform Hardside Expandable with Double Spinner Wheels, Carry-On 21-Inch",
        "price": 149.99,
        "category": "Suitcases",
        "brand": "Samsonite"
    }
    res = classify_product(p, niche="luggage")
    assert res["relevance_class"] == "CORE"
    assert res["relevance_confidence"] >= 0.85
    assert any("core_phrase" in ev for ev in res["relevance_evidence"])


def test_acceptance_case_2_tsa_locks():
    """'4 Pack TSA Approved Luggage Locks' -> ACCESSORY"""
    p = {
        "title": "4 Pack TSA Approved Luggage Locks, Open Alert Indicator, 3 Digit Combination Padlock for Travel Suitcase",
        "price": 13.99,
        "category": "Travel Accessories",
        "brand": "Anvil"
    }
    res = classify_product(p, niche="luggage")
    assert res["relevance_class"] == "ACCESSORY"
    assert res["sub_cluster"] == "luggage locks"
    assert res["relevance_confidence"] >= 0.85


def test_acceptance_case_3_pvc_cover():
    """'Clear PVC Suitcase Cover' -> ACCESSORY"""
    p = {
        "title": "Clear PVC Suitcase Cover Protector for 20-30 Inch Luggage, Waterproof Transparent Baggage Sleeve",
        "price": 15.99,
        "category": "Luggage Accessories",
        "brand": "ExploreLand"
    }
    res = classify_product(p, niche="luggage")
    assert res["relevance_class"] == "ACCESSORY"
    assert res["sub_cluster"] == "luggage covers"
    assert res["relevance_confidence"] >= 0.85


def test_acceptance_case_4_replacement_wheels():
    """'Replacement Spinner Wheels for Suitcase' -> ACCESSORY"""
    p = {
        "title": "Replacement Spinner Wheels for Suitcase, 2 Pcs Universal Silent Mute Rubber Swivel Casters A52",
        "price": 14.50,
        "category": "Luggage & Travel Gear Accessories",
        "brand": "WheelPro"
    }
    res = classify_product(p, niche="luggage")
    assert res["relevance_class"] == "ACCESSORY"
    assert res["sub_cluster"] == "replacement parts"
    assert res["relevance_confidence"] >= 0.85


def test_acceptance_case_5_expandable_with_tsa_lock():
    """'Expandable Carry-On with TSA Lock' -> CORE (embedded feature must not trigger accessory)"""
    p = {
        "title": "Coolife Luggage Expandable Suitcase PC+ABS Spinner 20in Carry-On with TSA Lock",
        "price": 79.99,
        "category": "Suitcases",
        "brand": "Coolife"
    }
    res = classify_product(p, niche="luggage")
    assert res["relevance_class"] == "CORE"
    assert res["relevance_confidence"] >= 0.85
    # Must identify embedded feature guard
    assert any("embedded_feature=with tsa lock" in ev for ev in res["relevance_evidence"])


def test_acceptance_case_6_travel_duffel_bag():
    """'Travel Duffel Bag' -> ADJACENT"""
    p = {
        "title": "Canway 65L Travel Duffel Bag, Foldable Weekender Bag with Shoes Compartment for Men Women",
        "price": 29.99,
        "category": "Travel Duffels",
        "brand": "Canway"
    }
    res = classify_product(p, niche="luggage")
    assert res["relevance_class"] == "ADJACENT"
    assert res["sub_cluster"] == "duffel bags"
    assert res["relevance_confidence"] >= 0.85


def test_acceptance_case_7_unclear_product_unknown():
    """Unclear product -> UNKNOWN (never guess or invent)"""
    p = {
        "title": "Generic Multi-Tool Device Model 992-X Heavy Duty",
        "price": 32.00,
        "category": "",
        "brand": "Generic"
    }
    res = classify_product(p, niche="luggage")
    assert res["relevance_class"] == "UNKNOWN"
    assert res["relevance_confidence"] == 0.0
    assert "insufficient_evidence_or_conflict" in res["relevance_evidence"]
