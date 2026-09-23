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
    for rel_guard in config.get("relational_accessory_guards", []):
        if rel_guard in clean_t:
            is_relational_accessory = True
            evidence.append(f"relational_accessory_guard={rel_guard}")
            if not matched_accessory_cluster:
                matched_accessory_cluster = "replacement parts" if "replacement" in rel_guard else "accessories"
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

    # 5. Fallback UNKNOWN (Insufficient evidence or conflict)
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
