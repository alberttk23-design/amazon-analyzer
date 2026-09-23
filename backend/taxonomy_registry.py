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
        }
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
        }
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
