import csv
import io
import json
import uuid
import asyncio
from typing import Optional, List
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Query, Response, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import backend.db as db
import backend.amazon_crawler as amazon_crawler
import backend.review_crawler as review_crawler
import backend.voc_engine as voc_engine
import backend.ai_engine as ai_engine
import backend.ads_bestsellers as ads_bestsellers
import backend.session_manager as session_manager
import backend.breadth_crawler as breadth_crawler
import backend.depth_crawler as depth_crawler
import backend.promotion_engine as promotion_engine
import backend.relevance_engine as relevance_engine

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORTS_DIR = BASE_DIR / "exports"

app = FastAPI(
    title="Amazon Analyzer API",
    version="2.0",
    description="Acquisition-First E-Commerce Market Intelligence Suite"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Request Models
# ---------------------------------------------------------

class AnalyzeRequest(BaseModel):
    keyword: str
    limit: int = 40
    target_folder: Optional[str] = None
    crawl_reviews: bool = True
    max_depth_candidates: int = 12
    enable_price_partition: bool = False


class BreadthDiscoverRequest(BaseModel):
    seed_keyword: str
    target_niche: Optional[str] = None
    max_queries: int = 20
    saturation_threshold: float = 4.0
    enable_price_partition: bool = False


class DepthCrawlRequest(BaseModel):
    keyword: str
    selected_asins: Optional[List[str]] = None
    max_candidates: int = 15
    max_reviews_per_product: int = 30


class PromoteCandidateRequest(BaseModel):
    asins: List[str]
    target_tier: str = "HOT"
    reason: str = "manual_user_promotion"


class MasterAnalysisRequest(BaseModel):
    keyword: str
    engine: str = "gemini"
    api_key: Optional[str] = None


class CrawlReviewsRequest(BaseModel):
    keyword: str
    top_n: int = 5
    max_reviews_per_product: int = 40


class AdsCrawlRequest(BaseModel):
    keyword: str
    limit: int = 30


class BestSellersRequest(BaseModel):
    category_name: str = "Best Sellers"
    limit: int = 50


class CreateFolderRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class RenameFolderRequest(BaseModel):
    new_name: str


class ReclassifyRequest(BaseModel):
    niche: str


class MergeFolderRequest(BaseModel):
    source_folder: str
    target_folder: str


class ResumeCrawlRequest(BaseModel):
    niche: str
    max_queries: int = 20
    max_pages_per_query: int = 3
    query: Optional[str] = None
    partition_id: Optional[str] = None


# ---------------------------------------------------------
# Acquisition-First Background Pipeline Execution
# ---------------------------------------------------------

def execute_amazon_pipeline(
    job_id: str,
    keyword: str,
    limit: int = 40,
    target_folder: Optional[str] = None,
    crawl_reviews: bool = True,
    max_depth_candidates: int = 12,
    enable_price_partition: bool = False
):
    """
    Acquisition-First 2-Tier Pipeline:
    1. BREADTH CRAWL: Discovers candidate universe across multi-lanes until saturation
    2. DYNAMIC PROMOTION: Scores and prioritizes candidates across taxonomy
    3. DEPTH CRAWL: Selects balanced portfolio (Top, Emerging, Review Outliers, Complaints, Long-tail) and gathers reviews
    4. ANALYSIS: VoC 6-Pillars & Master Listing Blueprint
    """
    pool_folder = (target_folder or keyword).strip()
    try:
        print(f"[Pipeline] Starting 2-Tier Acquisition Job {job_id} for '{keyword}' -> Folder '{pool_folder}'...")

        # Tier 1: Breadth Crawl until Discovery Saturation
        breadth_crawler.run_breadth_discovery_saturation_loop(
            seed_keyword=keyword,
            target_niche=pool_folder,
            max_queries=max(10, limit // 3),
            job_id=job_id,
            enable_price_partition=enable_price_partition
        )

        # Signal Evaluation & Promotion Engine
        promotion_engine.compute_and_update_niche_promotions(pool_folder)

        # Tier 2: Depth Crawl on Balanced Portfolio
        if crawl_reviews:
            depth_crawler.run_depth_crawl_pipeline(
                keyword=pool_folder,
                max_candidates=max_depth_candidates,
                max_reviews_per_product=30,
                job_id=job_id
            )
        else:
            db.update_job(job_id, status="completed", progress=100, message=f"Đã hoàn thành thu thập Candidate Universe cho '{pool_folder}'!")

        print(f"[Pipeline] Job {job_id} finished successfully.")
    except Exception as e:
        print(f"[Pipeline Error] Job {job_id} failed: {e}")
        db.update_job(job_id, status="failed", message=f"Lỗi pipeline: {str(e)}")


# ---------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "app": "Amazon Analyzer",
        "philosophy": "Acquisition Before Analysis",
        "status": "ready",
        "version": "2.0",
        "target_marketplace": "Amazon US (Zip 10001)"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "amazon-analyzer",
        "version": "2.0"
    }


@app.post("/api/analyze")
def start_analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    kw = req.keyword.strip()
    if not kw:
        raise HTTPException(status_code=400, detail="Keyword cannot be empty")

    pool_name = (req.target_folder or kw).strip()
    job_id = str(uuid.uuid4())[:8]
    db.create_niche_folder(pool_name)
    db.create_job(job_id, pool_name)

    background_tasks.add_task(
        execute_amazon_pipeline,
        job_id=job_id,
        keyword=kw,
        limit=req.limit,
        target_folder=pool_name,
        crawl_reviews=req.crawl_reviews,
        max_depth_candidates=req.max_depth_candidates,
        enable_price_partition=req.enable_price_partition
    )

    return {
        "job_id": job_id,
        "status": "started",
        "keyword": kw,
        "folder": pool_name,
        "message": f"Đã khởi động tiến trình cào rộng đa làn và bóc tách chuyên sâu cho '{pool_name}'."
    }


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------
# Candidate Universe & Breadth Discovery Routes
# ---------------------------------------------------------

@app.post("/api/breadth/discover")
def run_breadth_discovery(req: BreadthDiscoverRequest, background_tasks: BackgroundTasks):
    kw = req.seed_keyword.strip()
    pool_name = (req.target_niche or kw).strip()
    job_id = str(uuid.uuid4())[:8]
    db.create_job(job_id, pool_name)

    def task():
        try:
            breadth_crawler.run_breadth_discovery_saturation_loop(
                seed_keyword=kw,
                target_niche=pool_name,
                max_queries=req.max_queries,
                saturation_threshold_yield=req.saturation_threshold,
                job_id=job_id,
                enable_price_partition=req.enable_price_partition
            )
            promotion_engine.compute_and_update_niche_promotions(pool_name)
            db.update_job(job_id, status="completed", progress=100, message="Cào rộng đa làn hoàn tất!")
        except Exception as e:
            db.update_job(job_id, status="failed", message=f"Lỗi breadth crawl: {e}")

    background_tasks.add_task(task)
    return {"job_id": job_id, "status": "started", "niche": pool_name}


@app.get("/api/breadth/coverage")
def get_breadth_coverage(keyword: Optional[str] = None, niche: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    ledger = db.get_coverage_ledger(kw, limit=100)
    saturation = db.get_saturation_curve(kw)
    summary = db.get_candidate_universe_summary(kw)
    return {
        "keyword": kw,
        "ledger": ledger,
        "saturation_curve": saturation,
        "universe_summary": summary
    }


@app.get("/api/acquisition/dashboard")
def get_acquisition_dashboard(keyword: Optional[str] = None, niche: Optional[str] = None, run_id: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    return db.get_acquisition_dashboard_metrics(kw, run_id=run_id)


@app.get("/api/observations/{asin}")
def get_asin_observations(asin: str):
    return db.get_asin_search_matrix(asin.strip())


@app.get("/api/brands")
def get_brands(keyword: Optional[str] = None, niche: Optional[str] = None, limit: int = 100):
    kw = (keyword or niche or "").strip() or None
    brands = db.get_brand_entities(niche=kw, limit=limit)
    return {"total": len(brands), "brands": brands}


@app.get("/api/runs")
def get_research_runs(keyword: Optional[str] = None, niche: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    run = db.get_latest_research_run(kw)
    return {"latest_run": run}


@app.get("/api/diagnostics")
def get_diagnostics(keyword: Optional[str] = None, niche: Optional[str] = None, limit: int = 50):
    kw = (keyword or niche or "").strip() or None
    return {"diagnostics": db.get_recent_diagnostics(niche=kw, limit=limit)}


@app.get("/api/queue")
def get_queue_status(keyword: Optional[str] = None, niche: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    return db.get_query_queue_checkpoint(kw)


@app.post("/api/crawl/resume")
def resume_crawl(req: ResumeCrawlRequest, bg_tasks: BackgroundTasks):
    # Explicitly transition paused_captcha or interrupted queries back to pending
    resumed = db.resume_partition_after_user_action(
        niche=req.niche,
        query=req.query,
        partition_id=req.partition_id
    )
    session_info = session_manager.verify_session_usable()

    job_id = f"job_resume_{uuid.uuid4().hex[:8]}"
    db.create_crawl_job(job_id, req.niche, f"Tiếp tục cào từ Checkpoint hàng đợi cho '{req.niche}' ({resumed} queries resumed)...")
    bg_tasks.add_task(
        breadth_crawler.run_breadth_discovery_saturation_loop,
        seed_keyword=req.niche,
        target_niche=req.niche,
        max_queries=req.max_queries,
        max_pages_per_query=req.max_pages_per_query,
        resume=True,
        job_id=job_id
    )
    return {
        "job_id": job_id,
        "status": "resuming",
        "niche": req.niche,
        "resumed_queries": resumed,
        "session": session_info
    }


@app.get("/api/products/{asin}/variations")
def get_product_variations(asin: str):
    clean_asin = asin.strip()
    prod = db.get_product_by_asin(clean_asin)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    parent_asin = prod.get("parent_asin") or clean_asin
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT asin, title, price, original_price, rating, reviews_count, availability,
           parent_asin, is_parent, completeness_status, tier
    FROM products
    WHERE parent_asin = ? OR asin = ?
    ORDER BY is_parent DESC, asin ASC
    """, (parent_asin, parent_asin))
    rows = cursor.fetchall()
    conn.close()
    siblings = [dict(r) for r in rows]

    try:
        dims = json.loads(prod.get("variation_dimensions_json") or "{}")
    except Exception:
        dims = {}

    try:
        children = json.loads(prod.get("child_asins_json") or "[]")
    except Exception:
        children = []

    return {
        "asin": clean_asin,
        "parent_asin": parent_asin,
        "is_parent": prod.get("is_parent", 0),
        "variation_dimensions": dims,
        "child_asins": children,
        "siblings_count": len(siblings),
        "related_entities": siblings
    }


@app.get("/api/debug-file")
def get_debug_file(path: str):
    p = (BASE_DIR / path).resolve()
    debug_base = (BASE_DIR / "data" / "debug").resolve()
    if not p.exists() or not str(p).startswith(str(debug_base)):
        raise HTTPException(status_code=404, detail="Debug file not found")
    media_type = "image/png" if path.endswith(".png") else "text/html"
    return FileResponse(p, media_type=media_type)


@app.get("/api/candidates/summary")
def get_universe_summary(keyword: Optional[str] = None, niche: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    return db.get_candidate_universe_summary(kw)


@app.get("/api/candidates")
def list_candidates(
    keyword: Optional[str] = None,
    niche: Optional[str] = None,
    tier: Optional[str] = None,
    discovery_lane: Optional[str] = None,
    relevance_filter: Optional[str] = None,
    sort_by: str = "score DESC",
    min_rating: Optional[float] = None,
    is_sponsored: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
):
    kw = (keyword or niche or "").strip() or None
    items = db.get_products(
        keyword=kw,
        tier=tier,
        discovery_lane=discovery_lane,
        relevance_filter=relevance_filter,
        sort_by=sort_by,
        min_rating=min_rating,
        is_sponsored=is_sponsored,
        limit=limit,
        offset=offset
    )
    return {
        "keyword": keyword,
        "tier": tier,
        "relevance_filter": relevance_filter,
        "total": len(items),
        "candidates": items
    }


@app.get("/api/relevance/clusters")
def get_relevance_clusters(keyword: Optional[str] = None, niche: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    if not kw:
        return {"niche": "", "total_clusters": 0, "clusters": []}
    clusters = relevance_engine.get_sub_niche_clusters(kw)
    return {
        "niche": kw,
        "total_clusters": len(clusters),
        "clusters": clusters
    }


@app.post("/api/relevance/reclassify")
def reclassify_niche(req: ReclassifyRequest):
    kw = req.niche.strip()
    if not kw:
        raise HTTPException(status_code=400, detail="niche is required")
    summary = relevance_engine.classify_niche_products(kw)
    return {
        "niche": kw,
        "summary": summary
    }


# ---------------------------------------------------------
# Dynamic Promotion & Depth Crawl Routes
# ---------------------------------------------------------

@app.get("/api/priority-queue")
def get_priority_queue(keyword: Optional[str] = None, niche: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    return promotion_engine.get_taxonomy_feed(kw)


@app.post("/api/candidates/promote")
def promote_candidates(req: PromoteCandidateRequest):
    updated = 0
    for asin in req.asins:
        if db.update_product_tier(asin, new_tier=req.target_tier, reason=req.reason):
            updated += 1
    return {"promoted_count": updated, "target_tier": req.target_tier}


@app.post("/api/depth/crawl")
def trigger_depth_crawl(req: DepthCrawlRequest, background_tasks: BackgroundTasks):
    kw = req.keyword.strip()
    job_id = str(uuid.uuid4())[:8]
    db.create_job(job_id, kw)

    def task():
        try:
            depth_crawler.run_depth_crawl_pipeline(
                keyword=kw,
                selected_asins=req.selected_asins,
                max_candidates=req.max_candidates,
                max_reviews_per_product=req.max_reviews_per_product,
                job_id=job_id
            )
        except Exception as e:
            db.update_job(job_id, status="failed", message=f"Lỗi depth crawl: {e}")

    background_tasks.add_task(task)
    return {"job_id": job_id, "status": "started", "keyword": kw}


@app.get("/api/snapshots/{asin}")
def get_asin_snapshots(asin: str):
    snaps = db.get_product_snapshots(asin)
    return {"asin": asin, "total_snapshots": len(snaps), "snapshots": snaps}


# ---------------------------------------------------------
# Legacy Product, Reviews & VoC Routes
# ---------------------------------------------------------

@app.get("/api/products")
def list_products(
    keyword: Optional[str] = None,
    niche: Optional[str] = None,
    tier: Optional[str] = None,
    sort_by: str = "score DESC",
    min_rating: Optional[float] = None,
    is_sponsored: Optional[int] = None,
    limit: int = 100
):
    kw = (keyword or niche or "").strip() or None
    items = db.get_products(
        keyword=kw,
        tier=tier,
        sort_by=sort_by,
        min_rating=min_rating,
        is_sponsored=is_sponsored,
        limit=limit
    )
    return {
        "keyword": kw,
        "total": len(items),
        "products": items
    }


@app.get("/api/reviews")
def list_reviews(
    keyword: Optional[str] = None,
    niche: Optional[str] = None,
    asin: Optional[str] = None,
    sentiment: Optional[str] = None,
    min_stars: Optional[int] = None,
    max_stars: Optional[int] = None,
    limit: int = 200
):
    kw = (keyword or niche or "").strip() or None
    items = db.get_reviews(
        keyword=kw,
        asin=asin,
        sentiment=sentiment,
        min_stars=min_stars,
        max_stars=max_stars,
        limit=limit
    )
    return {
        "keyword": kw,
        "asin": asin,
        "total": len(items),
        "reviews": items
    }


@app.get("/api/voc-deep")
def get_voc_deep(keyword: Optional[str] = None, niche: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    cached = db.get_voc_insights(kw)
    if cached and cached.get("total_analyzed", 0) > 0:
        return cached
    data = voc_engine.analyze_voc_deep(kw)
    return data


@app.post("/api/analyze-master")
def run_master_analysis(req: MasterAnalysisRequest):
    kw = req.keyword.strip()
    result = ai_engine.generate_master_amazon_blueprint(
        keyword=kw,
        engine=req.engine,
        api_key=req.api_key
    )
    return result


@app.get("/api/master-analysis")
def get_master_analysis(keyword: Optional[str] = None, niche: Optional[str] = None, engine: Optional[str] = None):
    kw = (keyword or niche or "").strip()
    res = db.get_master_analysis(kw, engine=engine)
    if not res:
        res = ai_engine.generate_master_amazon_blueprint(keyword=kw)
    return res


@app.get("/api/analysis/latest")
def get_analysis_latest(keyword: Optional[str] = None, niche: Optional[str] = None, engine: Optional[str] = None):
    return get_master_analysis(keyword=keyword, niche=niche, engine=engine)


# ---------------------------------------------------------
# Sponsored Ads & Best Sellers Routes
# ---------------------------------------------------------

@app.post("/api/ads/crawl")
def crawl_ads(req: AdsCrawlRequest, background_tasks: BackgroundTasks):
    kw = req.keyword.strip()
    job_id = str(uuid.uuid4())[:8]
    db.create_job(job_id, kw)

    def run_ads():
        try:
            ads_bestsellers.crawl_sponsored_ads(kw, max_ads=req.limit, job_id=job_id)
            db.update_job(job_id, status="completed", progress=100, message="Cào Sponsored Ads hoàn tất!")
        except Exception as e:
            db.update_job(job_id, status="failed", message=f"Lỗi: {e}")

    background_tasks.add_task(run_ads)
    return {"job_id": job_id, "status": "started", "keyword": kw}


@app.get("/api/ads/list")
def list_ads(keyword: Optional[str] = None, limit: int = 100):
    ads = db.get_sponsored_ads(keyword=keyword, limit=limit)
    return {"total": len(ads), "ads": ads}


@app.post("/api/ads/clear")
def clear_ads(keyword: Optional[str] = None):
    db.clear_sponsored_ads(keyword=keyword)
    return {"status": "cleared", "keyword": keyword}


@app.post("/api/bestsellers/crawl")
def crawl_bestsellers(req: BestSellersRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    db.create_job(job_id, req.category_name)

    def run_bs():
        try:
            ads_bestsellers.crawl_best_sellers(category_name=req.category_name, max_items=req.limit, job_id=job_id)
            db.update_job(job_id, status="completed", progress=100, message="Cào Top Best Sellers hoàn tất!")
        except Exception as e:
            db.update_job(job_id, status="failed", message=f"Lỗi: {e}")

    background_tasks.add_task(run_bs)
    return {"job_id": job_id, "status": "started", "category": req.category_name}


@app.get("/api/bestsellers")
def list_bestsellers(category: Optional[str] = None, limit: int = 100):
    items = db.get_best_sellers(category=category, limit=limit)
    return {"total": len(items), "category": category or "All", "items": items}


# ---------------------------------------------------------
# Niche Folders Routes
# ---------------------------------------------------------

@app.get("/api/folders")
def get_folders():
    return db.get_niche_folders()


@app.post("/api/folders")
def create_folder(req: CreateFolderRequest):
    ok = db.create_niche_folder(req.name, req.description)
    if not ok:
        raise HTTPException(status_code=400, detail="Folder already exists or invalid name")
    return {"status": "created", "name": req.name}


@app.delete("/api/folders/{name}")
def delete_folder(name: str, delete_data: bool = True):
    ok = db.delete_niche_folder(name, delete_data=delete_data)
    return {"status": "deleted" if ok else "failed", "name": name}


@app.post("/api/folders/{name}/rename")
def rename_folder(name: str, req: RenameFolderRequest):
    ok = db.rename_niche_folder(name, req.new_name)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot rename folder")
    return {"status": "renamed", "old_name": name, "new_name": req.new_name}


@app.post("/api/folders/merge")
def merge_folders(req: MergeFolderRequest):
    ok = db.merge_niche_folders(req.source_folder, req.target_folder)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot merge folders")
    return {"status": "merged", "source": req.source_folder, "target": req.target_folder}


# ---------------------------------------------------------
# Browser Session & Zip Code Routes
# ---------------------------------------------------------

@app.get("/api/browser-session/status")
def session_status():
    return session_manager.get_session_status()


@app.post("/api/browser-session/open")
def session_open(target_url: str = "https://www.amazon.com"):
    return session_manager.launch_gui_browser_for_login(target_url=target_url)


@app.post("/api/browser-session/clear")
def session_clear():
    return session_manager.clear_session()


# ---------------------------------------------------------
# Exports (Excel CSV UTF-8 BOM & JSON)
# ---------------------------------------------------------

@app.get("/api/export/csv")
def export_csv(keyword: Optional[str] = None):
    products = db.get_products(keyword=keyword, limit=5000)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"amazon_universe_{keyword or 'all'}.csv"
    output = io.StringIO()
    output.write('\ufeff')

    writer = csv.writer(output)
    writer.writerow([
        "ASIN", "Tier", "Discovery Lane", "Query", "Title", "Brand", "Seller",
        "Price (USD)", "Original Price", "Rating", "Reviews Count", "Review Velocity",
        "Bought Past Month", "BSR Rank", "Is Sponsored", "Is Best Seller",
        "Is Amazon Choice", "Viability Score", "Amazon URL"
    ])

    for p in products:
        writer.writerow([
            p.get("asin"),
            p.get("tier"),
            p.get("discovery_lane"),
            p.get("discovered_via_query"),
            p.get("title"),
            p.get("brand"),
            p.get("seller"),
            p.get("price"),
            p.get("original_price"),
            p.get("rating"),
            p.get("reviews_count"),
            p.get("review_velocity"),
            p.get("bought_past_month"),
            p.get("bsr_rank"),
            "Yes" if p.get("is_sponsored") else "No",
            "Yes" if p.get("is_best_seller") else "No",
            "Yes" if p.get("is_amazons_choice") else "No",
            p.get("score"),
            p.get("url")
        ])

    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/export/json")
def export_json(keyword: Optional[str] = None):
    products = db.get_products(keyword=keyword, limit=5000)
    coverage = db.get_coverage_ledger(keyword) if keyword else []
    voc_data = db.get_voc_insights(keyword) if keyword else None
    master = db.get_master_analysis(keyword) if keyword else None

    payload = {
        "keyword": keyword or "all",
        "candidate_universe_size": len(products),
        "coverage_ledger_entries": len(coverage),
        "products": products,
        "coverage_ledger": coverage,
        "voc_insights": voc_data,
        "master_blueprint": master
    }
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=amazon_evidence_universe_{keyword or 'all'}.json"}
    )
