"""
Relevance Classification & Sub-Niche Clustering Engine.
Deterministic, multi-signal, context-aware classification:
CORE | ADJACENT | ACCESSORY | IRRELEVANT | UNKNOWN.
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

import backend.db as db
import backend.taxonomy_registry as taxonomy_registry

logger = logging.getLogger("amazon.relevance")
RULE_VERSION = "v1.0"


def clean_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    # Normalize common symbols
    t = t.replace("&amp;", "&").replace("’", "'").replace("“", '"').replace("”", '"')
    return t


def classify_product(
    product: Dict[str, Any],
    niche: str,
    query_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Classifies a product into CORE, ADJACENT, ACCESSORY, IRRELEVANT, or UNKNOWN.
    Returns:
    {
        "relevance_class": "CORE" | "ADJACENT" | "ACCESSORY" | "IRRELEVANT" | "UNKNOWN",
        "relevance_confidence": float (0.0 - 1.0),
        "relevance_evidence": List[str],
        "sub_cluster": str,
        "rule_version": str
    }
    """
    title = product.get("title") or ""
    category = product.get("bsr_category") or product.get("category") or ""
    price = float(product.get("price") or 0.0)
    query = query_context or product.get("discovered_via_query") or ""

    clean_t = clean_text(title)
    clean_cat = clean_text(category)
    clean_q = clean_text(query)

    config = taxonomy_registry.get_taxonomy_config_for_niche(niche)
    if not config:
        # Fallback generic logic when no specific taxonomy exists
        if niche.lower() in clean_t:
            return {
                "relevance_class": "CORE",
                "relevance_confidence": 0.70,
                "relevance_evidence": [f"generic_keyword_match={niche.lower()}"],
                "sub_cluster": "",
                "rule_version": RULE_VERSION
            }
        return {
            "relevance_class": "UNKNOWN",
            "relevance_confidence": 0.0,
            "relevance_evidence": ["no_taxonomy_config_and_no_keyword_match"],
            "sub_cluster": "",
            "rule_version": RULE_VERSION
        }

    evidence: List[str] = []
    embedded_features: List[str] = []

    # 1. Neutralize embedded features (e.g. "carry-on with TSA lock" -> lock is a feature of suitcase)
    neutralized_title = clean_t
    for feat in config.get("embedded_feature_guards", []):
        if any(tok in feat for tok in [r"(?:", r"\s", r"|", r"[", r"]"]):
            m = re.search(feat, neutralized_title, flags=re.IGNORECASE)
            if m:
                matched_text = m.group(0).strip().lower()
                embedded_features.append(matched_text)
                evidence.append(f"embedded_feature={matched_text}")
                neutralized_title = re.sub(feat, " [feat] ", neutralized_title, flags=re.IGNORECASE)
        elif feat in neutralized_title:
            embedded_features.append(feat)
            evidence.append(f"embedded_feature={feat}")
            neutralized_title = neutralized_title.replace(feat, f" [feat_{feat.replace(' ', '_')}] ")

    # Contextual Feature Neutralization: When title represents a primary suitcase or set,
    # trailing or embedded feature mentions (e.g. "TSA lock", "spinner wheels") belong to the suitcase.
    has_suitcase_marker = any(w in neutralized_title for w in ["suitcase", "luggage set", "piece set", "piece luggage", "piece suitcase", "carry-on spinner", "carry on spinner"])
    has_relational = any(rg in clean_t for rg in ["for suitcase", "for luggage", "replacement for", "fits 20-28"])
    if has_suitcase_marker and not has_relational:
        tsa_m = re.search(r'\b(?:(?:with|w/|lightweight|integrated|built-in)\s+)?tsa(?:\s+approved)?\s+lock\b', neutralized_title, flags=re.IGNORECASE)
        if tsa_m:
            matched_tsa = tsa_m.group(0).strip().lower()
            embedded_features.append(matched_tsa)
            evidence.append(f"embedded_feature={matched_tsa}")
            neutralized_title = re.sub(r'\b(?:(?:with|w/|lightweight|integrated|built-in)\s+)?tsa(?:\s+approved)?\s+lock\b', " [feat] ", neutralized_title, flags=re.IGNORECASE)

    # 2. Check ACCESSORY Patterns
    matched_accessory_cluster = None
    matched_accessory_phrase = None
    for cluster_name, phrases in config.get("accessory_categories", {}).items():
        for phrase in phrases:
            # Word-boundary or exact phrase match in neutralized title
            pattern = r'(?:\b|^)' + re.escape(phrase) + r'(?:\b|$)'
            if re.search(pattern, neutralized_title):
                matched_accessory_cluster = cluster_name
                matched_accessory_phrase = phrase
                evidence.append(f"title_phrase={phrase}")
                evidence.append(f"sub_cluster={cluster_name}")
                break
        if matched_accessory_cluster:
            break

    # Also check relational accessory guards (e.g. "for suitcase", "replacement for")
    is_relational_accessory = False
    has_adjacent_bag = any(w in clean_t for w in ["duffel", "duffle", "backpack", "garment bag", "tote bag", "weekender"])
    for rel_guard in config.get("relational_accessory_guards", []):
        is_match = False
        if any(tok in rel_guard for tok in [r"(?:", r"\s", r"|", r"[", r"]"]):
            if re.search(rel_guard, clean_t, flags=re.IGNORECASE):
                is_match = True
        elif rel_guard.lower() in clean_t:
            is_match = True

        if is_match and not (has_adjacent_bag and rel_guard in ["for luggage", "for suitcase", "for carry-on"]):
            is_relational_accessory = True
            evidence.append(f"relational_accessory_guard={rel_guard}")
            if not matched_accessory_cluster:
                if "lock" in rel_guard:
                    matched_accessory_cluster = "luggage locks"
                elif "tag" in rel_guard:
                    matched_accessory_cluster = "luggage tags"
                elif "wheel" in rel_guard or "replacement" in rel_guard:
                    matched_accessory_cluster = "replacement parts"
                elif "scale" in rel_guard:
                    matched_accessory_cluster = "scales"
                elif "strap" in rel_guard:
                    matched_accessory_cluster = "straps"
                else:
                    matched_accessory_cluster = "accessories"
            break

    if matched_accessory_cluster:
        conf = 0.88
        # Category signal boost
        for cat_sig in config.get("category_signals", {}).get("accessory", []):
            if cat_sig in clean_cat:
                conf += 0.08
                evidence.append(f"category_signal={cat_sig}")
                break

        # Price signal boost (accessories are typically cheaper)
        max_p = config.get("price_thresholds", {}).get("accessory_typical_max", 35.0)
        if 0 < price <= max_p:
            conf += 0.04
            evidence.append(f"price=${price:.2f}<=typical_max(${max_p})")

        return {
            "relevance_class": "ACCESSORY",
            "relevance_confidence": min(0.99, round(conf, 2)),
            "relevance_evidence": evidence,
            "sub_cluster": matched_accessory_cluster,
            "rule_version": RULE_VERSION
        }

    # Check for Strong Core Suitcase / Set signals (e.g. "3 Piece Luggage Set with Duffel Bag" is CORE, not ADJACENT)
    strong_core_tokens = [
        "luggage set", "suitcase set", "piece luggage set", "piece suitcase set", "piece set",
        "carry-on suitcase", "carry on suitcase", "checked suitcase", "spinner suitcase",
        "hardside luggage", "hardside suitcase", "rolling suitcase", "carry-on spinner", "carry on spinner"
    ]
    for sct in strong_core_tokens:
        if re.search(r'(?:\b|^)' + re.escape(sct) + r'(?:\b|$)', clean_t):
            evidence.append(f"strong_core_phrase={sct}")
            conf = 0.95
            if embedded_features:
                conf += 0.03
                evidence.append("embedded_features_reinforce_core")
            return {
                "relevance_class": "CORE",
                "relevance_confidence": min(0.99, round(conf, 2)),
                "relevance_evidence": evidence,
                "sub_cluster": "",
                "rule_version": RULE_VERSION
            }

    # Check for Out-of-Scope / IRRELEVANT markers before generic single-word core match
    matched_irrelevant = None
    for irr_phrase in config.get("irrelevant_phrases", []):
        if re.search(r'(?:\b|^)' + re.escape(irr_phrase) + r'(?:\b|$)', clean_t):
            matched_irrelevant = irr_phrase
            evidence.append(f"irrelevant_phrase={irr_phrase}")
            break

    if matched_irrelevant and not has_suitcase_marker:
        return {
            "relevance_class": "IRRELEVANT",
            "relevance_confidence": 0.95,
            "relevance_evidence": evidence,
            "sub_cluster": "irrelevant",
            "rule_version": RULE_VERSION
        }

    # 3. Check ADJACENT Patterns (e.g. duffel bag, travel backpack, garment bag)
    matched_adjacent_cluster = None
    for cluster_name, phrases in config.get("adjacent_categories", {}).items():
        for phrase in phrases:
            pattern = r'(?:\b|^)' + re.escape(phrase) + r'(?:\b|$)'
            if re.search(pattern, clean_t):
                matched_adjacent_cluster = cluster_name
                evidence.append(f"adjacent_phrase={phrase}")
                evidence.append(f"sub_cluster={cluster_name}")
                break
        if matched_adjacent_cluster:
            break

    if matched_adjacent_cluster:
        conf = 0.90
        for cat_sig in config.get("category_signals", {}).get("adjacent", []):
            if cat_sig in clean_cat:
                conf += 0.07
                evidence.append(f"category_signal={cat_sig}")
                break

        return {
            "relevance_class": "ADJACENT",
            "relevance_confidence": min(0.99, round(conf, 2)),
            "relevance_evidence": evidence,
            "sub_cluster": matched_adjacent_cluster,
            "rule_version": RULE_VERSION
        }

    # 4. Check CORE Patterns
    matched_core_phrase = None
    for phrase in config.get("core_product_phrases", []):
        pattern = r'(?:\b|^)' + re.escape(phrase) + r'(?:\b|$)'
        if re.search(pattern, clean_t):
            matched_core_phrase = phrase
            evidence.append(f"core_phrase={phrase}")
            break

    if matched_core_phrase:
        conf = 0.88
        if embedded_features:
            conf += 0.05
            evidence.append("embedded_features_reinforce_core")

        for cat_sig in config.get("category_signals", {}).get("core", []):
            if cat_sig in clean_cat:
                conf += 0.06
                evidence.append(f"category_signal={cat_sig}")
                break

        min_p = config.get("price_thresholds", {}).get("core_typical_min", 30.0)
        if price >= min_p:
            conf += 0.03
            evidence.append(f"price=${price:.2f}>=typical_min(${min_p})")

        return {
            "relevance_class": "CORE",
            "relevance_confidence": min(0.99, round(conf, 2)),
            "relevance_evidence": evidence,
            "sub_cluster": "",
            "rule_version": RULE_VERSION
        }

    # 5. Check IRRELEVANT Patterns (explicit out-of-scope products)
    matched_irrelevant = None
    for irr_phrase in config.get("irrelevant_phrases", []):
        if re.search(r'(?:\b|^)' + re.escape(irr_phrase) + r'(?:\b|$)', clean_t):
            matched_irrelevant = irr_phrase
            evidence.append(f"irrelevant_phrase={irr_phrase}")
            break

    if matched_irrelevant:
        return {
            "relevance_class": "IRRELEVANT",
            "relevance_confidence": 0.92,
            "relevance_evidence": evidence,
            "sub_cluster": "irrelevant",
            "rule_version": RULE_VERSION
        }

    # 6. Fallback UNKNOWN (Insufficient evidence or conflict)
    return {
        "relevance_class": "UNKNOWN",
        "relevance_confidence": 0.0,
        "relevance_evidence": ["insufficient_evidence_or_conflict"],
        "sub_cluster": "",
        "rule_version": RULE_VERSION
    }


def classify_niche_products(niche: str) -> Dict[str, Any]:
    """
    Batch classifies all products in niche_products for a given niche.
    Persists results directly into SQLite.
    """
    products = db.get_products(keyword=niche, limit=10000)
    logger.info(f"[RelevanceEngine] Batch classifying {len(products)} products for niche '{niche}'...")

    class_counts = {"CORE": 0, "ADJACENT": 0, "ACCESSORY": 0, "IRRELEVANT": 0, "UNKNOWN": 0}
    classified_total = 0

    for prod in products:
        asin = prod.get("asin")
        if not asin:
            continue
        res = classify_product(prod, niche=niche)
        r_class = res["relevance_class"]
        class_counts[r_class] = class_counts.get(r_class, 0) + 1

        db.update_product_relevance(
            asin=asin,
            niche=niche,
            relevance_class=r_class,
            confidence=res["relevance_confidence"],
            evidence=res["relevance_evidence"],
            rule_version=res["rule_version"],
            sub_cluster=res["sub_cluster"]
        )
        classified_total += 1

    return {
        "niche": niche,
        "total_classified": classified_total,
        "class_breakdown": class_counts,
        "rule_version": RULE_VERSION
    }


def get_sub_niche_clusters(niche: str) -> List[Dict[str, Any]]:
    """Returns aggregated sub-niche clusters for accessories and adjacent products."""
    return db.get_sub_niche_cluster_aggregates(niche)
