import re
import json
import sqlite3
from typing import Dict, List, Any, Optional
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "amazon.db"

# ---------------------------------------------------------------------------
# 6-Pillar Amazon E-Commerce VoC Taxonomy
# ---------------------------------------------------------------------------

PILLAR_TAXONOMY = {
    "defects_durability": {
        "title": "1. Lỗi Kỹ Thuật & Độ Bền Kém (Product Defects & Durability)",
        "badge": "⚠️ Lỗi Kỹ Thuật Đối Thủ",
        "color": "rose",
        "icon": "ShieldAlert",
        "description": "Các sự cố hư hỏng trong quá trình sử dụng: linh kiện nứt vỡ, motor dừng hoạt động, pin chai/cháy, rò rỉ, vật liệu nhựa rẻ tiền, độ bền kém.",
        "keywords": [
            "broken", "defective", "broke", "stopped working", "doesn't work", "stopped", "leak", "leaking",
            "crack", "cracked", "tear", "torn", "burn", "burned", "noise", "loud", "motor", "battery",
            "died", "cheap plastic", "fragile", "fell apart", "loose", "sharp", "smell", "odor", "chemical",
            "flimsy", "weak", "poorly made", "shuts off", "overheat", "overheating",
            # Vietnamese
            "hỏng", "gãy", "vỡ", "nứt", "rỉ", "chảy", "mùi khét", "chết motor", "chai pin", "kém bền",
            "ọp ẹp", "mùi hôi", "tiếng ồn", "nóng", "chập", "nhựa đểu", "dễ vỡ"
        ],
        "psychological_driver": "Khách hàng bực bội vì bỏ tiền mua sản phẩm kém chất lượng, tạo cơ hội cho seller nào cam kết vật liệu bền bỉ hơn."
    },
    "misleading_listing": {
        "title": "2. Sai Lệch Listing & Kỳ Vọng Thất Vọng (Misleading Listing & Expectation Gap)",
        "badge": "👁️ Khác Ảnh Quảng Cáo",
        "color": "amber",
        "icon": "Eye",
        "description": "Nỗi thất vọng khi nhận hàng: Kích thước thực tế bé hơn nhiều so với hình ảnh dàn dựng, màu sắc sai lệch, thông số kỹ thuật bị phóng đại.",
        "keywords": [
            "smaller than expected", "tiny", "size", "dimension", "misleading", "false advertising",
            "not as pictured", "looks different", "filter", "color", "thin", "scam", "deceptive",
            "exaggerated", "too small", "not true to size", "cheap looking", "ugly",
            # Vietnamese
            "nhỏ hơn hình", "bé tí", "khác hình", "lừa đảo", "quảng cáo láo", "màu xấu", "mỏng manh",
            "không giống ảnh", "thổi phồng", "quá nhỏ", "kích thước sai"
        ],
        "psychological_driver": "Cảm giác bị đánh lừa bởi ảnh render 3D hoặc góc chụp phóng đại; khách hàng mong muốn thông tin kích thước và ảnh chụp thực tế rõ ràng."
    },
    "packaging_shipping": {
        "title": "3. Đóng Gói, Vận Chuyển & Lắp Đặt Hư Hỏng (Packaging & Assembly)",
        "badge": "📦 Đóng Gói & Lắp Ráp",
        "color": "sky",
        "icon": "Package",
        "description": "Sự cố giao hàng và trải nghiệm mở hộp: Hộp hàng méo rách, thiếu ốc vít/phụ kiện, hướng dẫn sử dụng tiếng Anh khó hiểu, lắp đặt phức tạp.",
        "keywords": [
            "box damaged", "crushed", "dented", "missing part", "missing piece", "missing parts", "screw",
            "screws", "manual", "instruction", "instructions", "hard to assemble", "assembly", "difficult to use",
            "directions", "unboxing", "poor packaging", "no manual", "unclear", "confusing",
            # Vietnamese
            "thiếu ốc", "thiếu phụ kiện", "sách hướng dẫn", "khó lắp", "hộp nát", "móp méo", "khó dùng",
            "đóng gói ẩu", "thiếu đồ", "không có hướng dẫn", "lắp ráp cực hình"
        ],
        "psychological_driver": "Trải nghiệm 'First Impression' bị phá hỏng ngay từ phút đầu; người mua cần bao bì chống sốc chuẩn FBA và hướng dẫn minh họa trực quan."
    },
    "value_friction": {
        "title": "4. Giá Trị Thực vs Chi Phí & Lý Do Trả Hàng (Price-to-Value & Return Regret)",
        "badge": "🏷️ Đắt vs Chất Lượng / Trả Hàng",
        "color": "violet",
        "icon": "TrendingUp",
        "description": "Cảm giác hớ giá, sản phẩm không xứng đáng với số tiền bỏ ra, dẫn đến hành động trả hàng (return/refund) hoặc tiếc nuối.",
        "keywords": [
            "returned", "return", "refund", "overpriced", "waste of money", "not worth", "regret",
            "expensive", "rip off", "garbage", "junk", "throw away", "disappointed", "poor value",
            "don't buy", "save your money",
            # Vietnamese
            "trả hàng", "hoàn tiền", "phí tiền", "vứt đi", "rác rưởi", "đắt vô lý", "không đáng một xu",
            "thất vọng", "đừng mua", "tiếc tiền", "phí của"
        ],
        "psychological_driver": "Tâm lý Buyer's Remorse (hối hận sau mua); cơ hội vàng để định vị mức giá hợp lý đi kèm chế độ bảo hành/đổi trả 1-đổi-1 tự tin."
    },
    "hero_triggers": {
        "title": "5. Yếu Tố Ăn Tiền & Động Lực Chốt Đơn 5 Sao (Hero Features & Buying Triggers)",
        "badge": "⭐ Động Lực Mua Hàng 5★",
        "color": "emerald",
        "icon": "Sparkles",
        "description": "Các điểm sáng vượt trội khiến khách hàng chấm 5 sao, giới thiệu người thân, chọn làm quà tặng hoặc cảm nhận vượt xa mong đợi.",
        "keywords": [
            "love", "best", "perfect", "amazing", "highly recommend", "gift", "easy to clean", "sturdy",
            "powerful", "game changer", "exceeded expectations", "worth every penny", "favorite",
            "great quality", "works great", "impressed", "durable", "convenient", "smooth", "quiet",
            # Vietnamese
            "tuyệt vời", "rất thích", "đáng tiền", "bền", "đẹp", "dễ dùng", "mua tặng", "giới thiệu",
            "hài lòng", "chân ái", "quá đỉnh", "xịn", "chắc chắn", "vượt mong đợi"
        ],
        "psychological_driver": "Niềm thỏa mãn khi giải quyết được trọn vẹn nhu cầu; đây là các luận điểm bán hàng (USPs) cần đưa thẳng lên 5 Bullet Points của Listing."
    },
    "sourcing_directives": {
        "title": "6. Chỉ Thị Nâng Cấp Sản Phẩm Cho Seller (Sourcing & Listing Optimization Directives)",
        "badge": "🏭 Chỉ Thị Đàm Phán Xưởng",
        "color": "pink",
        "icon": "Wrench",
        "description": "Checklist giải pháp kỹ thuật cụ thể từ dữ liệu review để đàm phán với xưởng sản xuất và thiết kế Listing Amazon áp đảo đối thủ.",
        "keywords": [
            "wish", "should have", "upgrade", "improve", "better if", "needs", "suggestion", "add",
            "feature", "design", "redesign", "supplier", "manufacturer", "bundle",
            # Vietnamese
            "giá như", "cần cải tiến", "nên có", "góp ý", "nâng cấp", "thiết kế lại", "kèm thêm",
            "bổ sung", "ước gì", "thay đổi"
        ],
        "psychological_driver": "Biến mọi lời phàn nàn của đối thủ thành lợi thế cạnh tranh độc quyền cho sản phẩm thế hệ mới của bạn."
    }
}


def clean_review_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_key_phrases(reviews: List[Dict[str, Any]], top_n: int = 15) -> List[Dict[str, Any]]:
    """Extract frequent 2-3 word phrases from review texts."""
    phrases = []
    stopwords = {
        "the", "and", "a", "an", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was",
        "it", "this", "that", "you", "i", "my", "your", "so", "but", "not", "have", "from", "be",
        "me", "we", "they", "them", "what", "how", "all", "just", "can", "get", "do", "as", "by",
        "or", "if", "out", "about", "had", "been", "there", "their", "when", "would", "very",
        # Vietnamese
        "và", "là", "của", "cho", "trong", "với", "có", "này", "đó", "thì", "mà", "nhưng",
        "rồi", "lại", "được", "các", "những", "cái", "con", "người", "tôi", "mình", "bạn"
    }

    word_pattern = re.compile(r"[a-zA-Z0-9àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệđìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]{3,}", re.IGNORECASE)

    for r in reviews:
        if isinstance(r, sqlite3.Row):
            text = r["review_text"] if "review_text" in r.keys() else ""
        elif isinstance(r, dict):
            text = r.get("review_text", "")
        else:
            text = getattr(r, "review_text", "")
        if not text:
            continue
        words = [w.lower() for w in word_pattern.findall(text)]
        if len(words) < 2:
            continue

        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            if w1 not in stopwords and w2 not in stopwords:
                phrases.append(f"{w1} {w2}")

        for i in range(len(words) - 2):
            w1, w2, w3 = words[i], words[i + 1], words[i + 2]
            if w1 not in stopwords and w3 not in stopwords:
                phrases.append(f"{w1} {w2} {w3}")

    counts = Counter(phrases)
    return [{"phrase": p, "count": cnt} for p, cnt in counts.most_common(top_n)]


def analyze_voc_deep(keyword: str, db_path: str = None) -> Dict[str, Any]:
    """
    Orchestrates the 6-Pillar Voice of Customer intelligence engine across all reviews
    stored in SQLite for a given keyword / niche folder.
    """
    target_db = db_path or str(DB_PATH)
    conn = sqlite3.connect(target_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            r.id, r.review_id, r.asin, r.reviewer_name, r.star_rating,
            r.review_title, r.review_text, r.helpful_votes, r.sentiment,
            p.title as product_title, p.price, p.rating as product_rating
        FROM reviews r
        LEFT JOIN products p ON r.asin = p.asin
        WHERE r.keyword = ? AND length(r.review_text) > 4
        ORDER BY r.helpful_votes DESC, r.id DESC
    """, (keyword,))
    raw_rows = cursor.fetchall()
    conn.close()

    total_reviews = len(raw_rows)
    if total_reviews == 0:
        return {
            "keyword": keyword,
            "total_analyzed": 0,
            "critical_count": 0,
            "positive_count": 0,
            "pillars": {},
            "sourcing_recommendations": [],
            "frequent_phrases": []
        }

    critical_count = sum(1 for r in raw_rows if (r["star_rating"] or 5) <= 3)
    positive_count = sum(1 for r in raw_rows if (r["star_rating"] or 5) == 5)

    # Buckets for each pillar
    pillar_buckets = {k: [] for k in PILLAR_TAXONOMY}

    for row in raw_rows:
        text = row["review_text"]
        title = row["review_title"] or ""
        combined = f"{title} {text}".lower()
        stars = row["star_rating"] or 5
        votes = row["helpful_votes"] or 0

        item = {
            "id": row["id"],
            "review_id": row["review_id"],
            "asin": row["asin"],
            "product_title": row["product_title"] or "",
            "reviewer_name": row["reviewer_name"] or "Amazon Customer",
            "star_rating": stars,
            "review_title": title,
            "review_text": text,
            "helpful_votes": votes
        }

        # Pillar matching
        for p_key, p_meta in PILLAR_TAXONOMY.items():
            # Hero triggers prioritize 5-star reviews
            if p_key == "hero_triggers" and stars < 4:
                continue
            # Defects & Return regrets prioritize 1-3 star reviews
            if p_key in ["defects_durability", "value_friction"] and stars > 3:
                continue

            matched = False
            for kw in p_meta["keywords"]:
                if ' ' in kw:
                    if kw in combined:
                        matched = True
                        break
                else:
                    pattern = r"\b" + re.escape(kw) + r"\b"
                    if re.search(pattern, combined):
                        matched = True
                        break

            if matched:
                pillar_buckets[p_key].append(item)

    # Calculate stats per pillar
    pillars_result = {}
    for p_key, p_meta in PILLAR_TAXONOMY.items():
        items = pillar_buckets[p_key]
        count = len(items)
        pct = round((count / total_reviews) * 100, 1) if total_reviews > 0 else 0.0

        # Sort quotes by helpful_votes to get the most resonant voice
        top_quotes = sorted(items, key=lambda x: x["helpful_votes"], reverse=True)[:8]

        pillars_result[p_key] = {
            "pillar_id": p_key,
            "title": p_meta["title"],
            "badge": p_meta["badge"],
            "color": p_meta["color"],
            "icon": p_meta["icon"],
            "description": p_meta["description"],
            "psychological_driver": p_meta["psychological_driver"],
            "count": count,
            "percentage": pct,
            "top_quotes": top_quotes
        }

    # Dynamic Sourcing Recommendations generated from top customer friction points
    sourcing_recommendations = []
    kw_title = keyword.title()

    # Sourcing Directive 1: Material & Durability
    dur_count = pillars_result["defects_durability"]["count"]
    sample_dur = pillars_result["defects_durability"]["top_quotes"][0]["review_text"] if pillars_result["defects_durability"]["top_quotes"] else ""
    sourcing_recommendations.append({
        "pillar": "defects_durability",
        "title": f"🛠️ Nâng cấp Vật liệu & Kiểm định Độ Bền ({dur_count} khiếu nại)",
        "problem": f"Khách hàng đối thủ liên tục phàn nàn về linh kiện dễ gãy/cháy/hỏng: '{sample_dur[:120]}...'" if sample_dur else "Đối thủ nhận nhiều đánh giá 1-3 sao về độ bền linh kiện.",
        "factory_directive": "Yêu cầu xưởng nâng cấp nhựa ABS chịu lực / thép không gỉ thay vì vật liệu mỏng; tăng cường kiểm tra QC 100% trước khi đóng gói xuất khẩu FBA.",
        "listing_bullet_angle": "Đưa cam kết 'Vật liệu nâng cấp siêu bền + Bảo hành 1-đổi-1 trong 12 tháng' lên ngay Bullet Point số 1."
    })

    # Sourcing Directive 2: Misleading Size / Photos
    mis_count = pillars_result["misleading_listing"]["count"]
    sample_mis = pillars_result["misleading_listing"]["top_quotes"][0]["review_text"] if pillars_result["misleading_listing"]["top_quotes"] else ""
    sourcing_recommendations.append({
        "pillar": "misleading_listing",
        "title": f"📏 Minh bạch Kích thước & Tránh Bẫy Khác Hình ({mis_count} phản hồi)",
        "problem": f"Người mua thất vọng vì kích thước thực tế quá bé hoặc màu sắc không đúng hình: '{sample_mis[:120]}...'" if sample_mis else "Kỳ vọng của khách bị lệch so với ảnh chụp listing.",
        "factory_directive": "Chụp bộ ảnh sản phẩm thực tế cầm trên tay người thật (Lifestyle photography) và biểu đồ đo đạc kích thước từng góc (Infographic dimensions).",
        "listing_bullet_angle": "Ghi rõ kích thước thực tế cả đơn vị Inches và CM ngay dòng đầu Bullet Point 2 để triệt tiêu tỷ lệ hoàn hàng vì nhầm size."
    })

    # Sourcing Directive 3: Packaging & Manual
    pack_count = pillars_result["packaging_shipping"]["count"]
    sample_pack = pillars_result["packaging_shipping"]["top_quotes"][0]["review_text"] if pillars_result["packaging_shipping"]["top_quotes"] else ""
    sourcing_recommendations.append({
        "pillar": "packaging_shipping",
        "title": f"📦 Tối ưu Bao bì Chống Va Đập & Hướng dẫn Sử dụng ({pack_count} phản hồi)",
        "problem": f"Khách hàng nhận hộp móp méo hoặc lúng túng khi lắp ráp: '{sample_pack[:120]}...'" if sample_pack else "Đóng gói vận chuyển FBA dễ làm hỏng linh kiện bên trong.",
        "factory_directive": "Nâng cấp hộp carton 5 lớp có mút định hình EPE chống sốc rơi vỡ; in kèm sách hướng dẫn tiếng Anh chuẩn 100% có mã QR quét video tutorial.",
        "listing_bullet_angle": "Nhấn mạnh 'Ready to Gift & Easy Setup' trong 3 bước đơn giản, phù hợp làm quà tặng không lo móp méo."
    })

    # Sourcing Directive 4: Hero Feature Bundle
    hero_count = pillars_result["hero_triggers"]["count"]
    sample_hero = pillars_result["hero_triggers"]["top_quotes"][0]["review_text"] if pillars_result["hero_triggers"]["top_quotes"] else ""
    sourcing_recommendations.append({
        "pillar": "hero_triggers",
        "title": f"⭐ Combo Tặng Kèm Phụ Kiện Độc Quyền ({hero_count} lời khen 5★)",
        "problem": f"Khách hàng đánh giá 5 sao cho tính năng: '{sample_hero[:120]}...'" if sample_hero else "Những tính năng được khách hàng 5 sao đánh giá cao nhất.",
        "factory_directive": "Tạo gói Bundle kèm thêm phụ kiện thiết yếu (túi đựng, cọ vệ sinh, adapter) với chi phí xưởng rẻ (<$0.50) nhưng tăng giá trị cảm nhận lên gấp đôi.",
        "listing_bullet_angle": "Làm nổi bật Combo All-in-One trên Title và ảnh Main Image để đạt CTR vượt trội so với listing đơn lẻ của đối thủ."
    })

    frequent_phrases = extract_key_phrases(raw_rows, top_n=15)

    result = {
        "keyword": keyword,
        "total_analyzed": total_reviews,
        "critical_count": critical_count,
        "positive_count": positive_count,
        "pillars": pillars_result,
        "sourcing_recommendations": sourcing_recommendations,
        "frequent_phrases": frequent_phrases
    }

    # Cache into SQLite
    try:
        import backend.db as db_module
        db_module.save_voc_insights(keyword, result)
    except Exception as e:
        print(f"[VoC Engine Notice] Cache save: {e}")

    return result


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "portable blender"
    print(f"Testing VoC engine for '{kw}'...")
    res = analyze_voc_deep(kw)
    print(f"Total reviews: {res['total_analyzed']} (Critical: {res['critical_count']}, Positive: {res['positive_count']})")
    for p_id, p_data in res["pillars"].items():
        print(f" - {p_data['title']}: {p_data['count']} reviews ({p_data['percentage']}%)")
