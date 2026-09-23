"""
Taxonomy Registry for Multi-Niche Relevance Classification.
Defines core product phrases, accessory sub-clusters, adjacent categories,
and context disambiguation rules per niche.
"""
from typing import Dict, Any, List, Optional


TAXONOMY_CONFIGS: Dict[str, Dict[str, Any]] = {
    "luggage": {
        "niche_name": "luggage",
        "core_product_phrases": [
            "carry-on suitcase", "carry on suitcase", "carry-on luggage", "carry on luggage",
            "checked luggage", "checked suitcase", "spinner suitcase", "luggage set",
            "suitcase set", "piece luggage set", "piece suitcase set", "piece set",
            "hardside luggage", "hard shell luggage", "expandable suitcase", "rolling suitcase",
            "spinner luggage", "upright suitcase", "travel suitcase", "polycarbonate suitcase",
            "hardshell suitcase", "rolling luggage", "underseat luggage", "wheeled luggage",
            "carry-on spinner", "carry on spinner", "carry-on", "carry on", "hardside",
            "hardshell", "suitcase", "luggage"
        ],
        "adjacent_categories": {
            "duffel bags": [
                "duffel bag", "duffle bag", "weekender bag", "travel duffel", "gym duffel", "rolling duffel",
                "foldable travel duffel", "overnight weekender"
            ],
            "travel backpacks": [
                "travel backpack", "carry on backpack", "flight approved backpack", "luggage backpack",
                "travel laptop backpack", "laptop backpack", "travel business backpack"
            ],
            "garment bags": [
                "garment bag", "suit carrier", "dress bag", "suit bag", "hanging garment bag"
            ],
            "tote bags": [
                "travel tote", "flight bag", "underseat tote", "weekender tote"
            ]
        },
        "accessory_categories": {
            "luggage locks": [
                "luggage lock", "suitcase lock", "tsa approved lock", "tsa lock",
                "travel padlock", "combination lock for luggage", "luggage locks",
                "padlock", "padlocks", "dial padlock", "combination padlock"
            ],
            "luggage tags": [
                "luggage tag", "suitcase tag", "bag tag", "baggage tag",
                "travel tag", "luggage label", "luggage tags", "id tag"
            ],
            "luggage covers": [
                "luggage cover", "suitcase cover", "pvc luggage cover", "protector cover",
                "luggage protector", "suitcase protector", "clear pvc cover"
            ],
            "replacement parts": [
                "replacement spinner wheels", "replacement wheel", "replacement wheels", "replacement handle",
                "luggage wheel", "suitcase wheel", "spare wheel", "luggage replacement wheels",
                "swivel casters", "handle replacement", "spare parts", "repair kit"
            ],
            "straps": [
                "luggage strap", "luggage straps", "suitcase strap", "suitcase straps", "cross strap",
                "bag strap", "luggage belts", "travel belt", "travel belts", "suitcase belts"
            ],
            "scales": [
                "luggage scale", "travel scale", "hanging baggage scale", "weight scale for luggage",
                "baggage scale", "baggage scales", "travel baggage scale", "postal weight scale"
            ],
            "packing cubes": [
                "packing cube", "packing cubes", "compression packing cube", "travel organizer bags"
            ],
            "cup holders": [
                "luggage cup holder", "suitcase cup holder", "travel cup holder", "drink caddy"
            ]
        },
        "embedded_feature_guards": [
            r'(?:with|w/|including|includes|built-in|integrated|features|[|,\-–—])\s*(?:a\s+)?tsa(?:\s+approved)?\s+lock',
            r'(?:with|w/|including|includes|built-in|integrated|features|[|,\-–—])\s*lock',
            r'(?:with|w/|including|includes|features|[|,\-–—])\s*(?:dual\s+)?(?:double\s+)?(?:360°\s+)?(?:multi-directional\s+)?spinner\s+wheels',
            r'(?:with|w/|including|includes|features|[|,\-–—])\s*(?:dual\s+)?(?:multi-directional\s+)?wheels',
            r'(?:with|w/|including|includes|features|[|,\-–—])\s*telescoping\s+handle',
            r'(?:with|w/|including|includes|features|[|,\-–—])\s*usb(?:\s+charging)?\s+port',
            r'(?:with|w/|including|includes|features|[|,\-–—])\s*cup\s+holder',
            r'(?:with|w/|including|includes|features|[|,\-–—])\s*(?:shoulder\s+)?strap',
            "with tsa lock", "with lock", "built-in tsa lock", "integrated lock", "includes lock",
            "with double spinner wheels", "with spinner wheels", "with wheels",
            "with strap", "shoulder strap included", "with luggage strap",
            "with cup holder", "with usb port", "with luggage tag"
        ],
        "relational_accessory_guards": [
            "for suitcase", "for luggage", "for carry-on", "fits 20-28", "replacement for",
            "compatible with samsonite",
            r'(?:pack of|\d+\s*pack)\s+(?:luggage\s+)?(?:locks?|tags?|straps?|wheels?|scales?)'
        ],
        "category_signals": {
            "core": ["suitcases", "luggage sets", "carry-ons"],
            "adjacent": ["travel duffels", "backpacks", "garment bags"],
            "accessory": ["travel accessories", "luggage tags", "luggage locks", "suitcases & travel gear accessories"]
        },
        "price_thresholds": {
            "accessory_typical_max": 35.0,
            "core_typical_min": 35.0
        },
        "irrelevant_phrases": [
            "foot rest", "footrest", "airplane foot", "drone", "car rooftop", "rooftop cargo",
            "travel adapter", "power adapter", "plug adapter", "passport holder", "passport cover",
            "passport wallet", "neck pillow", "travel pillow", "sleep mask", "laptop sleeve",
            "shoe bag", "shoe bags", "cable organizer", "electronics organizer", "door lock for hotel",
            "hotel door lock", "door lock", "roof luggage"
        ],
        "default_price_buckets": [
            {"partition_id": "PRICE_0_25", "min_price": 0.0, "max_price": 25.0, "label": "Budget & Accessories"},
            {"partition_id": "PRICE_25_60", "min_price": 25.0, "max_price": 60.0, "label": "Mid-Range / Carry-On"},
            {"partition_id": "PRICE_60_150", "min_price": 60.0, "max_price": 150.0, "label": "Premium Suitcases"},
            {"partition_id": "PRICE_150_PLUS", "min_price": 150.0, "max_price": 0.0, "label": "Luxury & Sets"}
        ]
    },

    "migraine relief cap": {
        "niche_name": "migraine relief cap",
        "core_product_phrases": [
            "migraine relief cap", "headache hat", "ice cap for migraines", "migraine hat",
            "headache relief cap", "cold therapy cap", "cooling cap", "gel ice cap"
        ],
        "adjacent_categories": {
            "eye masks": ["migraine eye mask", "weighted eye mask", "sleep mask cooling"],
            "neck wraps": ["cooling neck wrap", "cold therapy neck wrap"]
        },
        "accessory_categories": {
            "ice pack refills": ["replacement gel pack", "ice pack refill", "extra gel pack"],
            "pouches": ["storage pouch", "freezer storage bag"]
        },
        "embedded_feature_guards": [
            "with gel pack", "with ice pack", "with cooling gel"
        ],
        "relational_accessory_guards": [
            "for migraine cap", "for headache hat", "replacement for"
        ],
        "category_signals": {
            "core": ["cold packs", "hot & cold therapies"],
            "adjacent": ["eye masks", "sleep aids"],
            "accessory": ["first aid accessories"]
        },
        "price_thresholds": {
            "accessory_typical_max": 15.0,
            "core_typical_min": 18.0
        },
        "default_price_buckets": [
            {"partition_id": "PRICE_0_15", "min_price": 0.0, "max_price": 15.0, "label": "Budget Caps"},
            {"partition_id": "PRICE_15_25", "min_price": 15.0, "max_price": 25.0, "label": "Mainstream Relief Caps"},
            {"partition_id": "PRICE_25_40", "min_price": 25.0, "max_price": 40.0, "label": "Premium Gel Caps"},
            {"partition_id": "PRICE_40_PLUS", "min_price": 40.0, "max_price": 0.0, "label": "Therapy Kits & Sets"}
        ]
    },

    "portable blender": {
        "niche_name": "portable blender",
        "core_product_phrases": [
            "portable blender", "personal blender", "smoothie blender cordless",
            "mini blender", "travel blender", "usb rechargeable blender"
        ],
        "adjacent_categories": {
            "shaker bottles": ["protein shaker bottle", "electric shaker bottle"],
            "countertop blenders": ["countertop blender", "immersion blender"]
        },
        "accessory_categories": {
            "replacement parts": ["replacement blades", "blender cup replacement", "sealing ring", "gasket"],
            "cables": ["usb magnetic charging cable", "blender charger"]
        },
        "embedded_feature_guards": [
            "with extra cup", "with charging cable", "with 6 blades"
        ],
        "relational_accessory_guards": [
            "for portable blender", "for ninja blast", "replacement for"
        ],
        "category_signals": {
            "core": ["personal blenders", "countertop blenders"],
            "adjacent": ["shaker cups", "juicers"],
            "accessory": ["blender replacement parts"]
        },
        "price_thresholds": {
            "accessory_typical_max": 18.0,
            "core_typical_min": 25.0
        },
        "default_price_buckets": [
            {"partition_id": "PRICE_0_20", "min_price": 0.0, "max_price": 20.0, "label": "Budget & Parts"},
            {"partition_id": "PRICE_20_40", "min_price": 20.0, "max_price": 40.0, "label": "Mainstream Blenders"},
            {"partition_id": "PRICE_40_70", "min_price": 40.0, "max_price": 70.0, "label": "High-Power Cordless"},
            {"partition_id": "PRICE_70_PLUS", "min_price": 70.0, "max_price": 0.0, "label": "Premium Brand Blenders"}
        ]
    }
}


def get_taxonomy_config_for_niche(niche: str) -> Optional[Dict[str, Any]]:
    """Resolve taxonomy configuration for a given niche keyword (smart lookup)."""
    if not niche:
        return None
    normalized = niche.strip().lower()
    # 1. Exact match
    if normalized in TAXONOMY_CONFIGS:
        return TAXONOMY_CONFIGS[normalized]
    # 2. Substring match
    for key, cfg in TAXONOMY_CONFIGS.items():
        if key in normalized or normalized in key:
            return cfg
    return None


def build_amazon_price_slice_param(min_price: float, max_price: float) -> str:
    """
    Builds the Amazon URL parameter &rh=p_36%3A... for price filtering.
    Prices on Amazon p_36 facet are specified in cents.
    Examples:
      0 to 25 -> &rh=p_36%3A-2500
      25 to 60 -> &rh=p_36%3A2500-6000
      150 to 0 (or max_price <= 0) -> &rh=p_36%3A15000-
    """
    min_cents = int(round(min_price * 100)) if min_price > 0 else 0
    max_cents = int(round(max_price * 100)) if max_price > 0 else 0

    if min_cents <= 0 and max_cents > 0:
        return f"&rh=p_36%3A-{max_cents}"
    elif min_cents > 0 and max_cents > 0:
        return f"&rh=p_36%3A{min_cents}-{max_cents}"
    elif min_cents > 0 and max_cents <= 0:
        return f"&rh=p_36%3A{min_cents}-"
    return ""


def get_semantic_price_buckets(
    niche: str,
    query: str = "",
    observed_prices: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Returns semantic price buckets for a niche.
    1. If observed_prices has >= 12 positive values, computes dynamic percentile buckets (25%, 50%, 75%).
    2. Otherwise, returns taxonomy configured default_price_buckets if present.
    3. Fallback: standard 4-tier e-commerce buckets ($0-$25, $25-$50, $50-$100, $100+).
    """
    cfg = get_taxonomy_config_for_niche(niche) or (get_taxonomy_config_for_niche(query) if query else None)

    # 1. Dynamic percentiles if enough sample prices observed
    valid_prices = [p for p in (observed_prices or []) if p > 0.0]
    if len(valid_prices) >= 12:
        valid_prices.sort()
        n = len(valid_prices)
        p25 = round(valid_prices[int(n * 0.25)], 2)
        p50 = round(valid_prices[int(n * 0.50)], 2)
        p75 = round(valid_prices[int(n * 0.75)], 2)

        # Ensure strict monotonicity and reasonable minimum
        if p25 < p50 < p75 and p25 >= 5.0:
            return [
                {"partition_id": f"PRICE_0_{int(p25)}", "min_price": 0.0, "max_price": p25, "label": f"Budget (<${p25})"},
                {"partition_id": f"PRICE_{int(p25)}_{int(p50)}", "min_price": p25, "max_price": p50, "label": f"Entry (${p25}-${p50})"},
                {"partition_id": f"PRICE_{int(p50)}_{int(p75)}", "min_price": p50, "max_price": p75, "label": f"Mid-Range (${p50}-${p75})"},
                {"partition_id": f"PRICE_{int(p75)}_PLUS", "min_price": p75, "max_price": 0.0, "label": f"Premium (>${p75})"}
            ]

    # 2. Configured defaults
    if cfg and "default_price_buckets" in cfg:
        return [dict(b) for b in cfg["default_price_buckets"]]

    # 3. Sensible generic fallback
    return [
        {"partition_id": "PRICE_0_25", "min_price": 0.0, "max_price": 25.0, "label": "Budget ($0-$25)"},
        {"partition_id": "PRICE_25_50", "min_price": 25.0, "max_price": 50.0, "label": "Mid ($25-$50)"},
        {"partition_id": "PRICE_50_100", "min_price": 50.0, "max_price": 100.0, "label": "Premium ($50-$100)"},
        {"partition_id": "PRICE_100_PLUS", "min_price": 100.0, "max_price": 0.0, "label": "Luxury ($100+)"}
    ]
