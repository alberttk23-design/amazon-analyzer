import React, { useState, useEffect } from 'react';
import {
  ShoppingBag,
  Search,
  Sparkles,
  BarChart3,
  ShieldAlert,
  Eye,
  Package,
  TrendingUp,
  Star,
  ExternalLink,
  RefreshCw,
  FolderPlus,
  GitMerge,
  Download,
  AlertCircle,
  CheckCircle2,
  Sliders,
  DollarSign,
  Layers,
  Wrench,
  Globe,
  Settings,
  ChevronRight,
  Filter,
  Flame,
  Check,
  X,
  Database,
  Compass,
  ArrowUpRight,
  TrendingDown,
  Target,
  Zap,
  Activity,
  ClipboardCheck
} from 'lucide-react';
import { AmazonCharts } from './components/AmazonCharts.tsx';

interface Product {
  id: number;
  asin: string;
  url: string;
  keyword: string;
  title: string;
  brand: string;
  seller: string;
  price: number;
  original_price: number;
  currency: string;
  rating: number;
  reviews_count: number;
  bought_past_month: number;
  bsr_rank: number;
  is_sponsored: number;
  is_best_seller: number;
  is_amazons_choice: number;
  image_url: string;
  score: number;
  tier: 'COLD' | 'WARM' | 'HOT';
  tier_reason: string;
  discovery_lane: string;
  discovered_via_query: string;
  review_velocity: number;
  promotion_score: number;
  product_depth: string;
  review_depth: string;
  parent_asin?: string;
  is_parent?: number;
  variant_count?: number;
  completeness_status?: string;
  visible_total_reviews?: number;
  reviews_collected?: number;
  collection_method?: string;
  review_coverage?: string;
  filters_applied?: string;
  variation_dimensions_json?: string;
  child_asins_json?: string;
  relevance_class?: 'CORE' | 'ADJACENT' | 'ACCESSORY' | 'IRRELEVANT' | 'UNKNOWN';
  relevance_confidence?: number;
  relevance_evidence_json?: string;
  sub_cluster?: string;
}

interface DiagnosticEntry {
  id: number;
  run_id: string;
  niche: string;
  query_or_asin: string;
  status: string;
  reason: string;
  html_path: string;
  screenshot_path: string;
  created_at: string;
}

interface QueueStatus {
  niche: string;
  total_queries: number;
  completed_queries: number;
  pending_queries: number;
  failed_queries: number;
  saturated_queries: number;
  progress_percent: number;
}

interface CoverageLedgerEntry {
  id: number;
  session_id: string;
  niche: string;
  lane: string;
  query_or_target: string;
  page_number: number;
  asins_found_total: number;
  asins_new_unique: number;
  asins_duplicate: number;
  marginal_yield: number;
  cumulative_unique: number;
  status: string;
  strategy_used: string;
  created_at: string;
}

interface UniverseSummary {
  keyword: string;
  total_candidates: number;
  cold_count: number;
  warm_count: number;
  hot_count: number;
  core_count?: number;
  adjacent_count?: number;
  accessory_count?: number;
  irrelevant_count?: number;
  unknown_count?: number;
  avg_price: number;
  core_avg_price?: number;
  avg_rating: number;
  total_monthly_sales: number;
  lanes: Record<string, number>;
}

interface RelevanceCluster {
  sub_cluster: string;
  relevance_class: string;
  product_count: number;
  avg_price: number;
  min_price: number;
  max_price: number;
  avg_reviews: number;
  total_monthly_sales: number;
  sample_asins: string[];
  top_brands: string[];
}

interface VoCData {
  keyword: string;
  total_analyzed: number;
  critical_count: number;
  positive_count: number;
  pillars: Record<string, any>;
  sourcing_recommendations: Array<any>;
  frequent_phrases: Array<{ phrase: string; count: number }>;
}

interface MasterAnalysis {
  keyword: string;
  engine: string;
  summary: string;
  product_flaws: Array<{ flaw: string; competitor_quote: string; solution: string; impact: string }>;
  buying_triggers: Array<{ trigger: string; quote: string; psychology: string }>;
  sourcing_directives: Array<{ category: string; specification: string; negotiation_tip: string }>;
  listing_blueprint: string;
}

interface Folder {
  name: string;
  product_count: number;
  total_sales: number;
  avg_price: number;
  avg_rating: number;
}

const API_BASE = 'http://127.0.0.1:8001';

export default function App() {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'acquisition_report' | 'universe' | 'priority_queue' | 'products' | 'voc' | 'blueprint' | 'ads_bs' | 'session' | 'folders'>('acquisition_report');
  const [activeFolder, setActiveFolder] = useState<string>(() => localStorage.getItem('amazon_analyzer_active_folder') || 'Luggage');
  const [folders, setFolders] = useState<Folder[]>([]);

  // Search & Acquisition Controls
  const [keywordInput, setKeywordInput] = useState<string>(() => localStorage.getItem('amazon_analyzer_active_folder') || 'Luggage');
  const [maxQueries, setMaxQueries] = useState<number>(20);
  const [autoDepthAfterBreadth, setAutoDepthAfterBreadth] = useState<boolean>(true);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<{ status: string; progress: number; message: string; cumulative_universe_count?: number } | null>(null);

  // Data Store
  const [candidates, setCandidates] = useState<Product[]>([]);
  const [universeSummary, setUniverseSummary] = useState<UniverseSummary | null>(null);
  const [coverageLedger, setCoverageLedger] = useState<CoverageLedgerEntry[]>([]);
  const [saturationCurve, setSaturationCurve] = useState<any[]>([]);
  const [priorityQueueFeed, setPriorityQueueFeed] = useState<Record<string, Product[]>>({});
  const [selectedQueueCategory, setSelectedQueueCategory] = useState<string>('emerging_winners');
  const [selectedAsinsForDepth, setSelectedAsinsForDepth] = useState<string[]>([]);
  const [acquisitionMetrics, setAcquisitionMetrics] = useState<any>(null);
  const [selectedMatrixAsin, setSelectedMatrixAsin] = useState<string | null>(null);
  const [asinMatrixData, setAsinMatrixData] = useState<any>(null);
  const [isMatrixLoading, setIsMatrixLoading] = useState<boolean>(false);

  // Checkpoint Queue, Diagnostics & Variations
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [diagnosticsLogs, setDiagnosticsLogs] = useState<DiagnosticEntry[]>([]);
  const [selectedVariationAsin, setSelectedVariationAsin] = useState<string | null>(null);
  const [variationData, setVariationData] = useState<any>(null);
  const [isVariationLoading, setIsVariationLoading] = useState<boolean>(false);

  // VoC & AI
  const [vocData, setVocData] = useState<VoCData | null>(null);
  const [masterAnalysis, setMasterAnalysis] = useState<MasterAnalysis | null>(null);
  const [sponsoredAds, setSponsoredAds] = useState<any[]>([]);
  const [bestSellers, setBestSellers] = useState<any[]>([]);
  const [sessionStatus, setSessionStatus] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Filters
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [laneFilter, setLaneFilter] = useState<string>('all');
  const [relevanceFilter, setRelevanceFilter] = useState<string>('ALL');
  const [relevanceClusters, setRelevanceClusters] = useState<RelevanceCluster[]>([]);
  const [isReclassifying, setIsReclassifying] = useState<boolean>(false);
  const [sortBy, setSortBy] = useState<string>('score DESC');
  const [vocSentimentFilter, setVocSentimentFilter] = useState<'all' | 'critical' | 'positive'>('all');

  // Modals
  const [showCreateFolderModal, setShowCreateFolderModal] = useState<boolean>(false);
  const [newFolderName, setNewFolderName] = useState<string>('');
  const [showMergeModal, setShowMergeModal] = useState<boolean>(false);
  const [mergeTargetFolder, setMergeTargetFolder] = useState<string>('');

  useEffect(() => {
    loadFolders();
    checkSessionStatus();
  }, []);

  useEffect(() => {
    if (activeFolder) {
      loadNicheData(activeFolder);
    }
  }, [activeFolder, sortBy, tierFilter, laneFilter, relevanceFilter]);

  // Polling Job
  useEffect(() => {
    if (!activeJobId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${activeJobId}`);
        if (!res.ok) return;
        const data = await res.json();
        setJobProgress(data);

        if (data.status === 'completed' || data.status === 'failed') {
          setActiveJobId(null);
          loadFolders(activeFolder);
          if (activeFolder) loadNicheData(activeFolder);
        }
      } catch (err) {
        console.error('Job poll error:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeJobId, activeFolder]);

  const loadFolders = async (preferFolder?: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/folders`);
      const data = await res.json();
      setFolders(data);
      const target = preferFolder || activeFolder || localStorage.getItem('amazon_analyzer_active_folder');
      if (target && data.length > 0) {
        const matched = data.find((f: Folder) => f.name.toLowerCase() === target.toLowerCase());
        if (matched) {
          if (activeFolder !== matched.name) {
            setActiveFolder(matched.name);
            setKeywordInput(matched.name);
          }
          localStorage.setItem('amazon_analyzer_active_folder', matched.name);
          return;
        }
      }
      if (data.length > 0 && !activeFolder) {
        setActiveFolder(data[0].name);
        setKeywordInput(data[0].name);
        localStorage.setItem('amazon_analyzer_active_folder', data[0].name);
      }
    } catch (err) {
      console.error('Error loading folders:', err);
    }
  };

  const checkSessionStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/browser-session/status`);
      const data = await res.json();
      setSessionStatus(data);
    } catch (err) {
      console.error('Error checking session:', err);
    }
  };

  const openAsinMatrixModal = async (asin: string) => {
    setSelectedMatrixAsin(asin);
    setIsMatrixLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/observations/${encodeURIComponent(asin)}`);
      if (res.ok) {
        const data = await res.json();
        setAsinMatrixData(data);
      }
    } catch (e) {
      console.error('Error fetching observations matrix:', e);
    } finally {
      setIsMatrixLoading(false);
    }
  };

  const openVariationModal = async (asin: string) => {
    setSelectedVariationAsin(asin);
    setIsVariationLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/products/${encodeURIComponent(asin)}/variations`);
      if (res.ok) {
        const data = await res.json();
        setVariationData(data);
      }
    } catch (e) {
      console.error('Error fetching variations:', e);
    } finally {
      setIsVariationLoading(false);
    }
  };

  const handleResumeCrawl = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/crawl/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: activeFolder, max_queries: 20, max_pages_per_query: 3 })
      });
      if (res.ok) {
        const data = await res.json();
        setActiveJobId(data.job_id);
      }
    } catch (e) {
      console.error('Error resuming crawl:', e);
    }
  };

  const loadNicheData = async (kw: string) => {
    setIsLoading(true);
    try {
      // 0. Acquisition Dashboard Summary (Step 12)
      const acqRes = await fetch(`${API_BASE}/api/acquisition/dashboard?keyword=${encodeURIComponent(kw)}`);
      if (acqRes.ok) {
        const acqData = await acqRes.json();
        setAcquisitionMetrics(acqData);
      }

      // 0.1 Checkpoint Queue Status
      const qRes = await fetch(`${API_BASE}/api/queue?keyword=${encodeURIComponent(kw)}`);
      if (qRes.ok) {
        const qData = await qRes.json();
        setQueueStatus(qData);
      }

      // 0.2 Diagnostics Logs (amkarpe pattern)
      const dRes = await fetch(`${API_BASE}/api/diagnostics?keyword=${encodeURIComponent(kw)}`);
      if (dRes.ok) {
        const dData = await dRes.json();
        setDiagnosticsLogs(dData.diagnostics || []);
      }

      // 1. Coverage & Saturation
      const covRes = await fetch(`${API_BASE}/api/breadth/coverage?keyword=${encodeURIComponent(kw)}`);
      if (covRes.ok) {
        const covData = await covRes.json();
        setCoverageLedger(covData.ledger || []);
        setSaturationCurve(covData.saturation_curve || []);
        setUniverseSummary(covData.universe_summary || null);
      }

      // 2. Candidate Universe
      let candUrl = `${API_BASE}/api/candidates?keyword=${encodeURIComponent(kw)}&sort_by=${encodeURIComponent(sortBy)}&limit=300`;
      if (tierFilter !== 'all') candUrl += `&tier=${encodeURIComponent(tierFilter)}`;
      if (laneFilter !== 'all') candUrl += `&discovery_lane=${encodeURIComponent(laneFilter)}`;
      if (relevanceFilter !== 'ALL') candUrl += `&relevance_filter=${encodeURIComponent(relevanceFilter)}`;
      const cRes = await fetch(candUrl);
      if (cRes.ok) {
        const cData = await cRes.json();
        setCandidates(cData.candidates || []);
      }

      // 2.1 Sub-Niche Clusters (Accessories / Adjacent Segmentation)
      const rcRes = await fetch(`${API_BASE}/api/relevance/clusters?keyword=${encodeURIComponent(kw)}`);
      if (rcRes.ok) {
        const rcData = await rcRes.json();
        setRelevanceClusters(rcData.clusters || []);
      }

      // 3. Priority Queue Feed
      const pqRes = await fetch(`${API_BASE}/api/priority-queue?keyword=${encodeURIComponent(kw)}`);
      if (pqRes.ok) {
        const pqData = await pqRes.json();
        setPriorityQueueFeed(pqData);
      }

      // 4. VoC Deep
      const vRes = await fetch(`${API_BASE}/api/voc-deep?keyword=${encodeURIComponent(kw)}`);
      if (vRes.ok) {
        const vData = await vRes.json();
        setVocData(vData);
      }

      // 5. Master AI Blueprint
      const mRes = await fetch(`${API_BASE}/api/master-analysis?keyword=${encodeURIComponent(kw)}`);
      if (mRes.ok) {
        const mData = await mRes.json();
        setMasterAnalysis(mData);
      }

      // 6. Sponsored Ads
      const adRes = await fetch(`${API_BASE}/api/ads/list?keyword=${encodeURIComponent(kw)}`);
      if (adRes.ok) {
        const adData = await adRes.json();
        setSponsoredAds(adData.ads || []);
      }

      // 7. Best Sellers
      const bsRes = await fetch(`${API_BASE}/api/bestsellers`);
      if (bsRes.ok) {
        const bsData = await bsRes.json();
        setBestSellers(bsData.items || []);
      }
    } catch (err) {
      console.error('Error loading niche data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReclassifyNiche = async () => {
    if (!activeFolder) return;
    setIsReclassifying(true);
    try {
      const res = await fetch(`${API_BASE}/api/relevance/reclassify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: activeFolder })
      });
      if (res.ok) {
        await loadNicheData(activeFolder);
      }
    } catch (e) {
      console.error('Error reclassifying niche:', e);
    } finally {
      setIsReclassifying(false);
    }
  };

  const handleStartAcquisition = async () => {
    const kw = keywordInput.trim();
    if (!kw) return;

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyword: kw,
          limit: maxQueries * 2,
          target_folder: kw,
          crawl_reviews: autoDepthAfterBreadth,
          max_depth_candidates: 15
        })
      });
      const data = await res.json();
      if (data.job_id) {
        const folderName = data.folder || kw;
        setActiveJobId(data.job_id);
        setActiveFolder(folderName);
        setKeywordInput(folderName);
        localStorage.setItem('amazon_analyzer_active_folder', folderName);
        setJobProgress({ status: 'started', progress: 5, message: 'Khởi động Multi-Lane Breadth Discovery...' });
        loadFolders(folderName);
      }
    } catch (err) {
      console.error('Error starting acquisition:', err);
    }
  };

  const handleTriggerDepthCrawl = async (asins?: string[]) => {
    try {
      const targetAsins = asins || selectedAsinsForDepth;
      const res = await fetch(`${API_BASE}/api/depth/crawl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyword: activeFolder,
          selected_asins: targetAsins.length > 0 ? targetAsins : null,
          max_candidates: 15,
          max_reviews_per_product: 30
        })
      });
      const data = await res.json();
      if (data.job_id) {
        setActiveJobId(data.job_id);
        setSelectedAsinsForDepth([]);
        setJobProgress({ status: 'depth_crawling', progress: 80, message: 'Đang bắt đầu cào sâu các ứng viên được chọn...' });
      }
    } catch (err) {
      alert('Lỗi kích hoạt Depth Crawl');
    }
  };

  const handlePromoteSelected = async (targetTier: 'HOT' | 'WARM') => {
    if (selectedAsinsForDepth.length === 0) return;
    try {
      await fetch(`${API_BASE}/api/candidates/promote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asins: selectedAsinsForDepth,
          target_tier: targetTier,
          reason: 'manual_user_promote'
        })
      });
      setSelectedAsinsForDepth([]);
      loadNicheData(activeFolder);
    } catch (err) {
      alert('Lỗi cập nhật tier');
    }
  };

  const handleOpenBrowser = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/browser-session/open`, { method: 'POST' });
      const data = await res.json();
      alert(data.message || 'Đã mở trình duyệt.');
      setTimeout(checkSessionStatus, 3000);
    } catch (err) {
      alert('Lỗi mở trình duyệt');
    }
  };

  const handleClearSession = async () => {
    if (!confirm('Bạn có chắc chắn muốn xóa toàn bộ cookies và phiên lưu trữ của Amazon không?')) return;
    try {
      const res = await fetch(`${API_BASE}/api/browser-session/clear`, { method: 'POST' });
      const data = await res.json();
      alert(data.message);
      checkSessionStatus();
    } catch (err) {
      alert('Lỗi xóa phiên');
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newFolderName.trim() })
      });
      if (res.ok) {
        setActiveFolder(newFolderName.trim());
        setNewFolderName('');
        setShowCreateFolderModal(false);
        loadFolders();
      }
    } catch (err) {
      alert('Lỗi tạo thư mục');
    }
  };

  const handleMergeFolder = async () => {
    if (!mergeTargetFolder || mergeTargetFolder === activeFolder) return;
    try {
      const res = await fetch(`${API_BASE}/api/folders/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_folder: activeFolder, target_folder: mergeTargetFolder })
      });
      if (res.ok) {
        setShowMergeModal(false);
        setActiveFolder(mergeTargetFolder);
        loadFolders();
      }
    } catch (err) {
      alert('Lỗi gộp thư mục');
    }
  };

  const toggleSelectAsin = (asin: string) => {
    setSelectedAsinsForDepth((prev) =>
      prev.includes(asin) ? prev.filter((a) => a !== asin) : [...prev, asin]
    );
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="sticky top-0 z-40 bg-zinc-950/85 backdrop-blur-md border-b border-zinc-800/80 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center shadow-lg shadow-amber-500/20 text-zinc-950 font-black">
            <ShoppingBag size={22} className="stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-zinc-100 flex items-center gap-1.5">
                Amazon Analyzer <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30">Acquisition First v2.0</span>
              </h1>
            </div>
            <p className="text-[11px] text-zinc-400">Candidate Universe • Breadth Saturation • Dynamic Promotion</p>
          </div>
        </div>

        {/* Niche Selector & Global Actions */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-1.5 text-xs">
            <span className="text-zinc-400 font-medium">Niche:</span>
            <select
              value={activeFolder}
              onChange={(e) => {
                const val = e.target.value;
                setActiveFolder(val);
                setKeywordInput(val);
                localStorage.setItem('amazon_analyzer_active_folder', val);
              }}
              className="bg-transparent font-bold text-amber-300 focus:outline-none cursor-pointer"
            >
              {folders.map((f) => (
                <option key={f.name} value={f.name} className="bg-zinc-900 text-zinc-100">
                  {f.name} ({f.product_count} candidates)
                </option>
              ))}
            </select>
            <button
              onClick={() => setShowCreateFolderModal(true)}
              title="Tạo niche mới"
              className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-amber-300 transition"
            >
              <FolderPlus size={15} />
            </button>
            <button
              onClick={() => setShowMergeModal(true)}
              title="Gộp niche"
              className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-amber-300 transition"
            >
              <GitMerge size={15} />
            </button>
          </div>

          {/* Zip Code Status */}
          <div
            onClick={() => setActiveTab('session')}
            className="cursor-pointer flex items-center gap-2 bg-zinc-900/90 border border-emerald-500/30 hover:border-emerald-500/60 px-3 py-1.5 rounded-xl transition"
            title="Đang định vị giao hàng New York 10001"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-xs font-semibold text-zinc-200">🇺🇸 Zip: 10001 (NY)</span>
          </div>

          {/* Export */}
          <a
            href={`${API_BASE}/api/export/csv?keyword=${encodeURIComponent(activeFolder)}`}
            download
            className="flex items-center gap-1.5 text-xs bg-zinc-900 hover:bg-zinc-800 text-zinc-200 px-3 py-1.5 rounded-xl border border-zinc-800 transition font-medium"
          >
            <Download size={14} />
            <span>Excel CSV</span>
          </a>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 space-y-6">
        {/* Acquisition Control Bar */}
        <section className="bg-gradient-to-br from-zinc-900 via-zinc-900 to-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl pointer-events-none"></div>

          <div className="flex flex-col lg:flex-row items-center gap-4">
            <div className="relative flex-1 w-full">
              <Compass size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleStartAcquisition()}
                placeholder="Nhập Seed Keyword để mở rộng đa làn (VD: portable blender, faux olive tree)..."
                className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500/60 focus:ring-1 focus:ring-amber-500/40 transition"
              />
            </div>

            <div className="flex items-center gap-3 w-full lg:w-auto">
              <div className="flex items-center gap-2 bg-zinc-950/60 border border-zinc-800 px-3 py-2 rounded-xl text-xs text-zinc-300">
                <span>Số truy vấn tối đa:</span>
                <span className="font-bold text-amber-400">{maxQueries}</span>
                <input
                  type="range"
                  min="5"
                  max="35"
                  step="5"
                  value={maxQueries}
                  onChange={(e) => setMaxQueries(Number(e.target.value))}
                  className="w-20 accent-amber-500 cursor-pointer"
                />
              </div>

              <label className="flex items-center gap-2 text-xs text-zinc-300 bg-zinc-950/60 border border-zinc-800 px-3 py-2.5 rounded-xl cursor-pointer hover:border-zinc-700 transition">
                <input
                  type="checkbox"
                  checked={autoDepthAfterBreadth}
                  onChange={(e) => setAutoDepthAfterBreadth(e.target.checked)}
                  className="accent-amber-500 rounded"
                />
                <span>Tự động Depth Crawl sau Bão hòa</span>
              </label>

              <button
                onClick={handleStartAcquisition}
                disabled={Boolean(activeJobId)}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm transition shadow-lg ${
                  activeJobId
                    ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                    : 'bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-zinc-950 shadow-amber-500/20 active:scale-[0.98]'
                }`}
              >
                {activeJobId ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" />
                    <span>Đang thu nạp Universe...</span>
                  </>
                ) : (
                  <>
                    <Zap size={16} />
                    <span>Khám Phá Đa Làn (Breadth Discovery)</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Job Progress Live Bar */}
          {jobProgress && activeJobId && (
            <div className="mt-4 pt-4 border-t border-zinc-800/80 animate-fadeIn">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-amber-400 font-medium flex items-center gap-1.5">
                  <RefreshCw size={12} className="animate-spin" />
                  {jobProgress.message}
                </span>
                <span className="text-zinc-400 font-bold">{jobProgress.progress}%</span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-amber-500 to-emerald-400 h-full transition-all duration-500 rounded-full"
                  style={{ width: `${jobProgress.progress}%` }}
                ></div>
              </div>
            </div>
          )}
        </section>

        {/* Evidence Universe Tiers Overview Bar */}
        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
          <div className="bg-zinc-900/80 border border-zinc-800/80 p-4 rounded-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs text-zinc-400">Candidate Universe</p>
              <Database size={14} className="text-zinc-500" />
            </div>
            <p className="text-2xl font-black text-zinc-100 mt-1">{universeSummary?.total_candidates || candidates.length}</p>
            <p className="text-[10px] text-emerald-400 mt-1">Đã lưu trữ vĩnh viễn</p>
          </div>

          <div className="bg-zinc-900/80 border border-blue-500/20 p-4 rounded-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs text-blue-300">COLD (Long-Tail)</p>
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
            </div>
            <p className="text-2xl font-black text-blue-400 mt-1">{universeSummary?.cold_count || 0}</p>
            <p className="text-[10px] text-zinc-500 mt-1">Metadata cơ sở giá & sales</p>
          </div>

          <div className="bg-zinc-900/80 border border-amber-500/20 p-4 rounded-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs text-amber-300">WARM (Active Signals)</p>
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            </div>
            <p className="text-2xl font-black text-amber-400 mt-1">{universeSummary?.warm_count || 0}</p>
            <p className="text-[10px] text-zinc-500 mt-1">Review velocity & ad signals</p>
          </div>

          <div className="bg-zinc-900/80 border border-rose-500/20 p-4 rounded-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs text-rose-300">HOT (Deep Crawled)</p>
              <span className="w-2 h-2 rounded-full bg-rose-400"></span>
            </div>
            <p className="text-2xl font-black text-rose-400 mt-1">{universeSummary?.hot_count || 0}</p>
            <p className="text-[10px] text-zinc-500 mt-1">Full specs + 1-3★ & 5★ reviews</p>
          </div>

          <div className="bg-zinc-900/80 border border-zinc-800/80 p-4 rounded-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs text-zinc-400">Doanh Số Tháng Ước Tính</p>
              <TrendingUp size={14} className="text-emerald-400" />
            </div>
            <p className="text-2xl font-black text-emerald-400 mt-1">
              {(universeSummary?.total_monthly_sales || 0).toLocaleString()}
            </p>
            <p className="text-[10px] text-zinc-500 mt-1">Lượt mua/tháng toàn ngách</p>
          </div>

          <div className="bg-zinc-900/80 border border-zinc-800/80 p-4 rounded-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs text-zinc-400">Độ Bão Hòa (Ledger)</p>
              <Activity size={14} className="text-sky-400" />
            </div>
            <p className="text-2xl font-black text-sky-400 mt-1">{coverageLedger.length} queries</p>
            <p className="text-[10px] text-zinc-500 mt-1">
              {coverageLedger[0]?.marginal_yield != null ? `Yield gần nhất: ${coverageLedger[0].marginal_yield}%` : 'Sẵn sàng'}
            </p>
          </div>
        </section>

        {/* Relevance Truth & Domain Guardrails Summary Bar */}
        <section className="bg-zinc-900/70 border border-zinc-800/80 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-md">
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-xl">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              <span className="text-zinc-400 font-medium">CORE Market:</span>
              <span className="font-bold text-emerald-300">{universeSummary?.core_count || 0} sản phẩm</span>
              <span className="text-[11px] text-zinc-500 ml-1 font-mono">
                (Avg: ${(universeSummary?.core_avg_price || 0).toFixed(2)})
              </span>
            </div>

            <div className="flex items-center gap-1.5 bg-sky-500/10 border border-sky-500/20 px-3 py-1.5 rounded-xl">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-400"></span>
              <span className="text-zinc-400 font-medium">ADJACENT:</span>
              <span className="font-bold text-sky-300">{universeSummary?.adjacent_count || 0}</span>
            </div>

            <div className="flex items-center gap-1.5 bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-xl">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
              <span className="text-zinc-400 font-medium">ACCESSORIES:</span>
              <span className="font-bold text-amber-300">{universeSummary?.accessory_count || 0} phụ kiện</span>
            </div>

            <div className="flex items-center gap-1.5 bg-zinc-800/60 border border-zinc-700/40 px-3 py-1.5 rounded-xl">
              <span className="w-2.5 h-2.5 rounded-full bg-zinc-500"></span>
              <span className="text-zinc-400 font-medium">UNKNOWN:</span>
              <span className="font-bold text-zinc-300">{universeSummary?.unknown_count || 0}</span>
            </div>
          </div>

          <button
            onClick={handleReclassifyNiche}
            disabled={isReclassifying}
            className="flex items-center gap-2 text-xs font-semibold px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 disabled:opacity-50 transition shadow-sm"
            title="Chạy lại Taxonomy Engine trên toàn bộ ứng viên trong ngách"
          >
            <RefreshCw size={13} className={isReclassifying ? "animate-spin text-amber-400" : "text-amber-400"} />
            <span>{isReclassifying ? "Đang phân loại..." : "Áp Dụng Phân Loại Relevance"}</span>
          </button>
        </section>

        {/* Visual Charts Component (Saturation Curve, Price vs Rating, Sales, VoC) */}
        <AmazonCharts
          products={candidates}
          vocPillars={vocData?.pillars}
          saturationCurve={saturationCurve}
          universeSummary={universeSummary || undefined}
        />

        {/* Navigation Tabs Header */}
        <div className="border-b border-zinc-800 flex items-center gap-1 text-sm font-medium overflow-x-auto pb-px">
          <button
            onClick={() => setActiveTab('acquisition_report')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'acquisition_report'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <ClipboardCheck size={16} className="text-emerald-400" />
            <span>Acquisition Report (Bước 12)</span>
          </button>

          <button
            onClick={() => setActiveTab('universe')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'universe'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Database size={16} />
            <span>Vũ Trụ Ứng Viên & Saturation ({candidates.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('priority_queue')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'priority_queue'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Target size={16} className="text-rose-400" />
            <span>Hàng Đợi Đào Sâu (Priority Queue)</span>
          </button>

          <button
            onClick={() => setActiveTab('products')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'products'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Layers size={16} />
            <span>Ma Trận Sản Phẩm (Cards)</span>
          </button>

          <button
            onClick={() => setActiveTab('voc')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'voc'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <ShieldAlert size={16} className="text-rose-400" />
            <span>VoC 6 Trụ Cột ({vocData?.total_analyzed || 0})</span>
          </button>

          <button
            onClick={() => setActiveTab('blueprint')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'blueprint'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Sparkles size={16} className="text-amber-400" />
            <span>Master AI Blueprint</span>
          </button>

          <button
            onClick={() => setActiveTab('ads_bs')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'ads_bs'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Flame size={16} className="text-amber-500" />
            <span>Sponsored & Best Sellers</span>
          </button>

          <button
            onClick={() => setActiveTab('session')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'session'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Globe size={16} />
            <span>Trình Duyệt & Zip Code</span>
          </button>

          <button
            onClick={() => setActiveTab('folders')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition whitespace-nowrap ${
              activeTab === 'folders'
                ? 'border-amber-400 text-amber-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <FolderPlus size={16} />
            <span>Niche Folders ({folders.length})</span>
          </button>
        </div>

        {/* TAB 0: ACQUISITION BEFORE ANALYSIS REPORT (BƯỚC 12) */}
        {activeTab === 'acquisition_report' && (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-zinc-900 via-zinc-900 to-amber-950/30 border border-zinc-800 rounded-3xl p-6 shadow-2xl">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
                <div>
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-400">
                    <Activity size={14} className="animate-pulse" />
                    <span>Amazon Candidate Universe Acquisition Report (Bước 12)</span>
                  </div>
                  <h2 className="text-2xl font-black text-white mt-1">
                    Báo Cáo Thu Thập Trước Phân Tích: <span className="text-amber-400">{activeFolder}</span>
                  </h2>
                  <p className="text-xs text-zinc-400 mt-1">
                    Trạng thái thu nạp vũ trụ thực thể thị trường trước khi chuyển sang Brain phân tích. 100% ASIN được bảo tồn tại tầng COLD.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-full text-xs font-bold flex items-center gap-1.5">
                    <CheckCircle2 size={13} />
                    Discovery: {acquisitionMetrics?.coverage?.discovery || 'active discovery'}
                  </span>
                  <span className="px-3 py-1.5 bg-zinc-800 text-zinc-300 rounded-full text-xs font-mono">
                    Market Coverage: <strong className="text-amber-400">UNKNOWN</strong>
                  </span>
                </div>
              </div>

              {/* 5-Block Grid: Bước 12 Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
                {/* Block 1: Discovery */}
                <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-2xl p-4">
                  <div className="text-xs font-bold text-zinc-400 uppercase tracking-wide flex items-center gap-1.5">
                    <Compass size={14} className="text-amber-400" /> Khám Phá Thị Trường
                  </div>
                  <div className="mt-3 space-y-2 text-xs">
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Queries Executed:</span>
                      <span className="font-mono font-bold text-white text-sm">{acquisitionMetrics?.discovery?.queries_executed || coverageLedger.length}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Unique ASINs:</span>
                      <span className="font-mono font-bold text-amber-400 text-sm">{acquisitionMetrics?.discovery?.unique_asin || candidates.length}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Brands:</span>
                      <span className="font-mono font-bold text-zinc-200">{acquisitionMetrics?.discovery?.brands || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Sellers / Merchants:</span>
                      <span className="font-mono font-bold text-zinc-200">{acquisitionMetrics?.discovery?.sellers || 0}</span>
                    </div>
                  </div>
                </div>

                {/* Block 2: Search Observations (Decoupled Ads vs Organic) */}
                <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-2xl p-4">
                  <div className="text-xs font-bold text-zinc-400 uppercase tracking-wide flex items-center gap-1.5">
                    <Eye size={14} className="text-blue-400" /> Search Observations
                  </div>
                  <div className="mt-3 space-y-2 text-xs">
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Total Observations:</span>
                      <span className="font-mono font-bold text-white text-sm">{acquisitionMetrics?.search_observations?.total || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400"></span> Sponsored Ads:</span>
                      <span className="font-mono font-bold text-amber-400">{acquisitionMetrics?.search_observations?.sponsored || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400"></span> Organic Rank:</span>
                      <span className="font-mono font-bold text-emerald-400">{acquisitionMetrics?.search_observations?.organic || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-zinc-500"></span> Unknown:</span>
                      <span className="font-mono font-bold text-zinc-400">{acquisitionMetrics?.search_observations?.unknown || 0}</span>
                    </div>
                  </div>
                </div>

                {/* Block 3: Enrichment & Reviews */}
                <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-2xl p-4">
                  <div className="text-xs font-bold text-zinc-400 uppercase tracking-wide flex items-center gap-1.5">
                    <Layers size={14} className="text-purple-400" /> Products Enriched
                  </div>
                  <div className="mt-3 space-y-2 text-xs">
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Total Enriched:</span>
                      <span className="font-mono font-bold text-white text-sm">{acquisitionMetrics?.products_enriched?.total || candidates.length}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Full Detail Specs:</span>
                      <span className="font-mono font-bold text-purple-400">{acquisitionMetrics?.products_enriched?.full_detail || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Review Crawled:</span>
                      <span className="font-mono font-bold text-purple-300">{acquisitionMetrics?.products_enriched?.review_crawled || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Reviews Collected:</span>
                      <span className="font-mono font-bold text-purple-200">{acquisitionMetrics?.products_enriched?.reviews_collected || 0}</span>
                    </div>
                  </div>
                </div>

                {/* Block 4: Failures & Diagnostics */}
                <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-2xl p-4">
                  <div className="text-xs font-bold text-zinc-400 uppercase tracking-wide flex items-center gap-1.5">
                    <AlertCircle size={14} className="text-rose-400" /> Failures & Diagnostics
                  </div>
                  <div className="mt-3 space-y-2 text-xs">
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>403 Forbidden:</span>
                      <span className="font-mono font-bold text-zinc-300">{acquisitionMetrics?.failures?.status_403 || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>429 Rate Limit:</span>
                      <span className="font-mono font-bold text-zinc-300">{acquisitionMetrics?.failures?.status_429 || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>Parser Partial:</span>
                      <span className="font-mono font-bold text-zinc-300">{acquisitionMetrics?.failures?.parser_partial || 0}</span>
                    </div>
                    <div className="flex justify-between items-center text-zinc-300">
                      <span>New ASINs This Run:</span>
                      <span className="font-mono font-bold text-emerald-400">+{acquisitionMetrics?.run_deltas?.new_asin_this_run || 0}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Checkpoint / Resume Queue Status */}
            <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-3xl">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-400">
                    <Zap size={14} />
                    <span>Discovery Query Checkpoint & Resume Queue</span>
                  </div>
                  <h3 className="text-lg font-bold text-white mt-1">
                    Tiến Độ Hàng Đợi Truy Vấn: {queueStatus?.completed_queries || 0} / {queueStatus?.total_queries || 0} Queries
                  </h3>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    Hàng đợi SQLite lưu vết từng query và trang đã cào. Khi bị gián đoạn hoặc gặp bot challenge, hệ thống tự động tiếp tục từ query đang chờ thay vì cào lại.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <span className="text-xs text-zinc-400">Đang chờ: </span>
                    <span className="text-sm font-bold font-mono text-amber-400">{queueStatus?.pending_queries || 0} queries</span>
                  </div>
                  <button
                    onClick={handleResumeCrawl}
                    disabled={!queueStatus || queueStatus.pending_queries === 0}
                    className="px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-950 font-black rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-amber-500/10 transition"
                  >
                    <RefreshCw size={13} />
                    Tiếp Tục Cào (Resume)
                  </button>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-zinc-800/80 rounded-full h-2.5 mt-4 overflow-hidden">
                <div
                  className="bg-amber-400 h-2.5 rounded-full transition-all duration-500"
                  style={{ width: `${queueStatus?.progress_percent || 0}%` }}
                ></div>
              </div>
            </div>

            {/* Diagnostics & Failure Dumps (amkarpe pattern) */}
            <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-3xl">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-rose-400">
                  <ShieldAlert size={14} />
                  <span>Diagnostics & Failure Dumps (HTML Snapshots & Captchas)</span>
                </div>
                <span className="text-xs text-zinc-400 font-mono">
                  {diagnosticsLogs.length} sự kiện ghi nhận
                </span>
              </div>

              {diagnosticsLogs.length === 0 ? (
                <div className="text-center py-6 text-xs text-zinc-500">
                  <CheckCircle2 size={24} className="mx-auto text-emerald-500/50 mb-1" />
                  Không có sự cố bot-wall hoặc zero-cards nào được ghi nhận. Phiên làm việc hoàn toàn thông suốt!
                </div>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-400">
                        <th className="pb-2">Thời Gian</th>
                        <th className="pb-2">Truy Vấn / ASIN</th>
                        <th className="pb-2">Trạng Thái</th>
                        <th className="pb-2">Nguyên Nhân</th>
                        <th className="pb-2 text-right">Debug Dump</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {diagnosticsLogs.map((diag) => (
                        <tr key={diag.id} className="hover:bg-zinc-800/20">
                          <td className="py-2.5 text-zinc-400 font-mono text-[11px]">{diag.created_at}</td>
                          <td className="py-2.5 font-semibold text-zinc-200">{diag.query_or_asin}</td>
                          <td className="py-2.5">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              diag.status === 'captcha_detected'
                                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                : diag.status === 'zero_cards'
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                : 'bg-zinc-800 text-zinc-300'
                            }`}>
                              {diag.status}
                            </span>
                          </td>
                          <td className="py-2.5 text-zinc-400 text-[11px] max-w-xs truncate" title={diag.reason}>
                            {diag.reason}
                          </td>
                          <td className="py-2.5 text-right font-mono">
                            {diag.html_path ? (
                              <a
                                href={`${API_BASE}/api/debug-file?path=${encodeURIComponent(diag.html_path)}`}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300 hover:underline"
                              >
                                <ExternalLink size={12} />
                                Xem HTML Dump
                              </a>
                            ) : (
                              <span className="text-zinc-600 text-[11px]">N/A</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between bg-zinc-900/60 p-4 rounded-2xl border border-zinc-800">
              <div className="text-xs text-zinc-400">
                Toàn bộ dữ liệu thu thập đang nằm sẵn sàng trong cơ sở dữ liệu. Bấm nút bên dưới để chuyển tiếp:
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab('universe')}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded-xl text-xs flex items-center gap-1.5 transition"
                >
                  <Database size={14} />
                  Xem Vũ Trụ Ứng Viên ({candidates.length})
                </button>
                <button
                  onClick={() => setActiveTab('priority_queue')}
                  className="px-4 py-2 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 font-bold rounded-xl text-xs flex items-center gap-1.5 transition border border-rose-500/30"
                >
                  <Target size={14} />
                  Hàng Đợi Ưu Tiên (HOT/WARM/COLD)
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 1: CANDIDATE UNIVERSE & COVERAGE LEDGER */}
        {activeTab === 'universe' && (
          <div className="space-y-6">
            {/* Relevance Class Filter Tabs */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-zinc-900/80 p-3 rounded-2xl border border-zinc-800">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-zinc-400 font-semibold mr-1 flex items-center gap-1">
                  <Target size={14} className="text-amber-400" /> Lọc Phân Loại Relevance:
                </span>
                {[
                  { id: 'ALL', label: 'Tất Cả Ứng Viên', count: universeSummary?.total_candidates || candidates.length, color: 'text-zinc-300' },
                  { id: 'CORE', label: '🎯 CORE Market Only', count: universeSummary?.core_count || 0, color: 'text-emerald-400' },
                  { id: 'CORE_ADJACENT', label: '🎯+🧭 Core & Adjacent', count: (universeSummary?.core_count || 0) + (universeSummary?.adjacent_count || 0), color: 'text-emerald-300' },
                  { id: 'ACCESSORY', label: '🧩 Phụ Kiện (Accessories)', count: universeSummary?.accessory_count || 0, color: 'text-amber-400' },
                  { id: 'ADJACENT', label: '🧭 Sản Phẩm Lân Cận (Adjacent)', count: universeSummary?.adjacent_count || 0, color: 'text-sky-400' },
                  { id: 'UNKNOWN', label: '❓ Chưa Rõ (Unknown)', count: universeSummary?.unknown_count || 0, color: 'text-zinc-400' }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setRelevanceFilter(tab.id)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition border ${
                      relevanceFilter === tab.id
                        ? 'bg-zinc-800 border-amber-400 text-white shadow'
                        : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                    }`}
                  >
                    <span>{tab.label}</span>
                    <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-zinc-950 ${tab.color}`}>
                      {tab.count}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Multi-Lane & Tier Filters */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-zinc-900/60 p-3.5 rounded-2xl border border-zinc-800 text-xs">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-zinc-400 font-medium flex items-center gap-1">
                  <Filter size={14} /> Phân Tầng Vòng Đời:
                </span>
                <select
                  value={tierFilter}
                  onChange={(e) => setTierFilter(e.target.value)}
                  className="bg-zinc-800 border border-zinc-700 text-zinc-200 rounded-lg px-2.5 py-1 focus:outline-none"
                >
                  <option value="all">Tất cả Tiers (COLD + WARM + HOT)</option>
                  <option value="COLD">🧊 COLD (Long Tail Metadata Only)</option>
                  <option value="WARM">⚡ WARM (Signals Active)</option>
                  <option value="HOT">🔥 HOT (Full Specs & Reviews Crawled)</option>
                </select>

                <select
                  value={laneFilter}
                  onChange={(e) => setLaneFilter(e.target.value)}
                  className="bg-zinc-800 border border-zinc-700 text-zinc-200 rounded-lg px-2.5 py-1 focus:outline-none"
                >
                  <option value="all">Tất cả Làn Khám Phá (Lanes)</option>
                  <option value="keyword_search">Keyword Search</option>
                  <option value="suggestions">Live Amazon Suggestions</option>
                  <option value="brand_expansion">Brand Expansion</option>
                  <option value="intent_modifiers">Intent Modifiers</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-zinc-400 font-medium">Sắp xếp:</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="bg-zinc-800 border border-zinc-700 text-amber-300 font-semibold rounded-lg px-2.5 py-1 focus:outline-none"
                >
                  <option value="score DESC">Điểm Tiềm Năng (Score)</option>
                  <option value="bought_past_month DESC">Doanh Số Bán Tháng (Sales)</option>
                  <option value="promotion_score DESC">Điểm Ưu Tiên (Promotion Score)</option>
                  <option value="review_velocity DESC">Tốc Độ Tăng Review (Velocity)</option>
                  <option value="reviews_count DESC">Số Lượng Reviews</option>
                  <option value="price ASC">Giá Thấp Tới Cao</option>
                </select>
              </div>
            </div>

            {/* Sub-Niche Clusters Section */}
            {relevanceClusters.length > 0 && (
              <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 shadow-xl space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                      <Package size={16} className="text-sky-400" />
                      Phân Khúc Phụ Kiện & Cụm Sản Phẩm Liên Quan (Sub-Niche Clusters)
                    </h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Tự động gom cụm các sản phẩm phụ trợ (locks, tags, covers, wheels...) để khám phá cơ hội bundle và phụ kiện
                    </p>
                  </div>
                  <span className="text-xs font-mono text-zinc-400 bg-zinc-800 px-2 py-1 rounded-lg">
                    {relevanceClusters.length} cụm phân khúc
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {relevanceClusters.map((cluster) => (
                    <div
                      key={cluster.sub_cluster}
                      className="bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3.5 space-y-2.5 hover:border-zinc-700 transition"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-amber-300 uppercase tracking-wide flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                          {cluster.sub_cluster}
                        </span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300">
                          {cluster.product_count} items
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-zinc-800/60">
                        <div>
                          <span className="text-zinc-500 block text-[10px]">Giá Trung Bình</span>
                          <span className="font-bold text-emerald-400">${cluster.avg_price}</span>
                          <span className="text-[9px] text-zinc-500 ml-1">(${cluster.min_price} - ${cluster.max_price})</span>
                        </div>
                        <div>
                          <span className="text-zinc-500 block text-[10px]">Doanh Số Tháng</span>
                          <span className="font-bold text-zinc-200">{cluster.total_monthly_sales.toLocaleString()}</span>
                        </div>
                      </div>

                      {cluster.top_brands && cluster.top_brands.length > 0 && (
                        <div className="text-[10px] text-zinc-400 flex items-center gap-1 truncate">
                          <span className="text-zinc-500 font-medium">Top brands:</span>
                          <span className="text-zinc-300 truncate">{cluster.top_brands.join(', ')}</span>
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[10px] text-zinc-500 font-mono">
                          Avg Reviews: {cluster.avg_reviews.toLocaleString()}
                        </span>
                        <button
                          onClick={() => {
                            setRelevanceFilter('ACCESSORY');
                          }}
                          className="text-[10px] text-amber-400 hover:text-amber-300 font-semibold"
                        >
                          Xem items ➔
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Candidate Universe Table */}
            <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="px-5 py-4 border-b border-zinc-800 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                    <Database size={16} className="text-amber-400" />
                    Bảng Toàn Cảnh Vũ Trụ Ứng Viên (Candidate Universe Evidence Store)
                  </h3>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    Hiển thị {candidates.length} ứng viên được lưu trữ vĩnh viễn (Không bao giờ xóa bỏ Long-tail)
                  </p>
                </div>

                {selectedAsinsForDepth.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-amber-300 font-bold">Đã chọn {selectedAsinsForDepth.length} ASINs</span>
                    <button
                      onClick={() => handlePromoteSelected('HOT')}
                      className="bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold px-3 py-1 rounded-lg text-xs"
                    >
                      Promote to HOT & Depth Crawl
                    </button>
                  </div>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-zinc-300">
                  <thead className="bg-zinc-950 text-zinc-400 uppercase text-[10px] tracking-wider border-b border-zinc-800">
                    <tr>
                      <th className="p-3 w-8 text-center">
                        <input
                          type="checkbox"
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedAsinsForDepth(candidates.map((c) => c.asin));
                            } else {
                              setSelectedAsinsForDepth([]);
                            }
                          }}
                          className="accent-amber-500 rounded"
                        />
                      </th>
                      <th className="p-3">ASIN / Tier</th>
                      <th className="p-3">Sản Phẩm</th>
                      <th className="p-3">Làn Khám Phá</th>
                      <th className="p-3 text-right">Giá ($)</th>
                      <th className="p-3 text-center">Rating</th>
                      <th className="p-3 text-right">Review Velocity</th>
                      <th className="p-3 text-right">Doanh Số Tháng</th>
                      <th className="p-3 text-right">Score</th>
                      <th className="p-3 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {candidates.map((p) => {
                      const isSelected = selectedAsinsForDepth.includes(p.asin);
                      return (
                        <tr
                          key={p.asin}
                          className={`hover:bg-zinc-800/40 transition ${isSelected ? 'bg-amber-500/5' : ''}`}
                        >
                          <td className="p-3 text-center">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelectAsin(p.asin)}
                              className="accent-amber-500 rounded cursor-pointer"
                            />
                          </td>
                          <td className="p-3">
                            <div className="font-mono text-zinc-200 font-bold">{p.asin}</div>
                            <div className="flex flex-wrap items-center gap-1 mt-0.5">
                              <span
                                className={`text-[9px] font-bold px-1.5 py-0.5 rounded inline-block ${
                                  p.tier === 'HOT'
                                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                    : p.tier === 'WARM'
                                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                    : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                                }`}
                              >
                                {p.tier}
                              </span>
                              {p.relevance_class && (
                                <span
                                  className={`text-[9px] font-bold px-1.5 py-0.5 rounded inline-block ${
                                    p.relevance_class === 'CORE'
                                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                      : p.relevance_class === 'ACCESSORY'
                                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                      : p.relevance_class === 'ADJACENT'
                                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                                      : p.relevance_class === 'IRRELEVANT'
                                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                      : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                                  }`}
                                  title={p.sub_cluster ? `Phân khúc: ${p.sub_cluster}` : p.relevance_class}
                                >
                                  {p.relevance_class === 'CORE' ? '🎯 CORE' :
                                   p.relevance_class === 'ACCESSORY' ? `🧩 ACC${p.sub_cluster ? `:${p.sub_cluster}` : ''}` :
                                   p.relevance_class === 'ADJACENT' ? '🧭 ADJ' :
                                   p.relevance_class}
                                </span>
                              )}
                              {(p.is_parent === 1 || (p.variant_count && p.variant_count > 1)) && (
                                <button
                                  onClick={() => openVariationModal(p.asin)}
                                  className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 flex items-center gap-1 transition"
                                  title="Xem Cây Biến Thể Parent / Child (Group nhưng không Flatten)"
                                >
                                  <Package size={10} /> {p.variant_count || 1} Biến Thể
                                </button>
                              )}
                              {p.parent_asin && p.is_parent === 0 && (
                                <button
                                  onClick={() => openVariationModal(p.parent_asin || p.asin)}
                                  className="text-[9px] font-mono px-1 py-0.5 rounded bg-zinc-800 text-zinc-400 hover:text-zinc-200"
                                  title={`Bản ghi thực thể con liên kết tới Parent ASIN: ${p.parent_asin}`}
                                >
                                  Child ➔ {p.parent_asin.slice(0, 6)}...
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="p-3 max-w-xs">
                            <p className="font-semibold text-zinc-200 line-clamp-2 leading-relaxed" title={p.title}>
                              {p.title}
                            </p>
                            <p className="text-[10px] text-zinc-500 mt-0.5">Brand: {p.brand || 'N/A'}</p>
                          </td>
                          <td className="p-3">
                            <span className="bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded text-[10px]">
                              {p.discovery_lane || 'keyword_search'}
                            </span>
                            {p.discovered_via_query && (
                              <p className="text-[10px] text-zinc-500 truncate max-w-[140px] mt-0.5" title={p.discovered_via_query}>
                                Q: {p.discovered_via_query}
                              </p>
                            )}
                          </td>
                          <td className="p-3 text-right font-bold text-amber-400">${p.price}</td>
                          <td className="p-3 text-center">
                            <span className="font-bold text-amber-300">{p.rating}★</span>
                            <p className="text-[10px] text-zinc-500">({p.reviews_count?.toLocaleString()})</p>
                            {p.reviews_collected ? (
                              <div className="mt-0.5">
                                <span
                                  className="text-[9px] px-1.5 py-0.5 rounded bg-purple-950/70 text-purple-300 border border-purple-800/40 inline-block font-mono"
                                  title={`Review Coverage: ${p.review_coverage || ''} | Phương thức: ${p.collection_method || 'sample'}`}
                                >
                                  VoC: {p.reviews_collected} revs
                                </span>
                              </div>
                            ) : null}
                          </td>
                          <td className="p-3 text-right">
                            <span className="text-sky-400 font-bold font-mono">+{p.review_velocity || 0}</span>
                            <span className="text-[10px] text-zinc-500">/wk</span>
                          </td>
                          <td className="p-3 text-right font-semibold text-emerald-400">
                            {p.bought_past_month > 0 ? `${p.bought_past_month.toLocaleString()}+` : '0'}
                          </td>
                          <td className="p-3 text-right font-bold text-zinc-200">{p.score}</td>
                          <td className="p-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <button
                                onClick={() => openAsinMatrixModal(p.asin)}
                                className="p-1 hover:bg-zinc-800 rounded text-amber-400 hover:text-amber-300 transition"
                                title="Xem Ma Trận Vị Trí & Tình Trạng Ads/Organic (Search Observations)"
                              >
                                <Eye size={14} />
                              </button>
                              <button
                                onClick={() => openVariationModal(p.parent_asin || p.asin)}
                                className="p-1 hover:bg-zinc-800 rounded text-purple-400 hover:text-purple-300 transition"
                                title="Xem Biến Thể Parent / Child (Group nhưng không Flatten)"
                              >
                                <Package size={14} />
                              </button>
                              <a
                                href={p.url}
                                target="_blank"
                                rel="noreferrer"
                                className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-zinc-200"
                                title="Xem trên Amazon"
                              >
                                <ExternalLink size={14} />
                              </a>
                              {p.tier !== 'HOT' && (
                                <button
                                  onClick={() => handleTriggerDepthCrawl([p.asin])}
                                  className="text-[10px] bg-rose-500/20 hover:bg-rose-500/40 text-rose-300 px-2 py-0.5 rounded font-bold transition"
                                  title="Cào sâu reviews"
                                >
                                  Deep Crawl
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Coverage Ledger (Denominators & Saturation Logging) */}
            <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="px-5 py-4 border-b border-zinc-800">
                <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                  <Activity size={16} className="text-emerald-400" />
                  Sổ Cái Độ Bao Phủ & Tỷ Lệ Yield (Coverage Ledger & Denominators)
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Minh bạch 100% mẫu số khám phá: các câu lệnh đã chạy, số ASIN mới xuất hiện vs ASIN trùng lặp
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-zinc-300">
                  <thead className="bg-zinc-950 text-zinc-400 uppercase text-[10px] tracking-wider border-b border-zinc-800">
                    <tr>
                      <th className="p-3">Truy Vấn (Query)</th>
                      <th className="p-3">Làn (Lane)</th>
                      <th className="p-3 text-center">Trang</th>
                      <th className="p-3 text-right">Tìm Thấy</th>
                      <th className="p-3 text-right">Mới (+Unique)</th>
                      <th className="p-3 text-right">Trùng Lặp</th>
                      <th className="p-3 text-right">Marginal Yield</th>
                      <th className="p-3 text-right">Tích Lũy</th>
                      <th className="p-3 text-center">Chiến Lược</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {coverageLedger.map((row) => (
                      <tr key={row.id} className="hover:bg-zinc-800/40 transition">
                        <td className="p-3 font-semibold text-zinc-200">{row.query_or_target}</td>
                        <td className="p-3">
                          <span className="bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded text-[10px]">
                            {row.lane}
                          </span>
                        </td>
                        <td className="p-3 text-center">{row.page_number}</td>
                        <td className="p-3 text-right">{row.asins_found_total}</td>
                        <td className="p-3 text-right font-bold text-sky-400">+{row.asins_new_unique}</td>
                        <td className="p-3 text-right text-zinc-500">{row.asins_duplicate}</td>
                        <td className="p-3 text-right">
                          <span className={`font-bold font-mono ${
                            row.marginal_yield > 40 ? 'text-emerald-400' :
                            row.marginal_yield > 15 ? 'text-amber-400' : 'text-zinc-500'
                          }`}>
                            {row.marginal_yield}%
                          </span>
                        </td>
                        <td className="p-3 text-right font-black text-emerald-400">{row.cumulative_unique}</td>
                        <td className="p-3 text-center">
                          <span className="text-[10px] bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800 text-zinc-400 font-mono">
                            {row.strategy_used}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {coverageLedger.length === 0 && (
                      <tr>
                        <td colSpan={9} className="p-6 text-center text-zinc-500 text-xs">
                          Chưa có nhật ký cào rộng cho ngách này. Bấm "Khám Phá Đa Làn" ở trên để bắt đầu!
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: PRIORITY QUEUE & SELECTION TAXONOMY */}
        {activeTab === 'priority_queue' && (
          <div className="space-y-6">
            {/* Taxonomy Tabs */}
            <div className="flex flex-wrap items-center gap-2 bg-zinc-900/60 p-3 rounded-2xl border border-zinc-800">
              {[
                { id: 'emerging_winners', label: '🚀 Emerging Winners (Mới Nổi)', count: priorityQueueFeed.emerging_winners?.length || 0 },
                { id: 'top_performers', label: '👑 Top Performers (Dẫn Đầu)', count: priorityQueueFeed.top_performers?.length || 0 },
                { id: 'review_velocity_outliers', label: '📈 Review Velocity Outliers', count: priorityQueueFeed.review_velocity_outliers?.length || 0 },
                { id: 'high_complaints', label: '⚠️ High Complaints (Mỏ Lỗi Đối Thủ)', count: priorityQueueFeed.high_complaints?.length || 0 },
                { id: 'price_outliers', label: '🏷️ Price Outliers (Góc Giá)', count: priorityQueueFeed.price_outliers?.length || 0 },
                { id: 'ad_active', label: '🔥 Ad-Active (Chạy Ads)', count: priorityQueueFeed.ad_active?.length || 0 },
                { id: 'long_tail', label: '🌱 Long-Tail Samples', count: priorityQueueFeed.long_tail?.length || 0 }
              ].map((tax) => (
                <button
                  key={tax.id}
                  onClick={() => setSelectedQueueCategory(tax.id)}
                  className={`text-xs px-3 py-2 rounded-xl transition font-semibold flex items-center gap-1.5 ${
                    selectedQueueCategory === tax.id
                      ? 'bg-amber-500 text-zinc-950 shadow-md'
                      : 'bg-zinc-800/80 text-zinc-300 hover:bg-zinc-700'
                  }`}
                >
                  <span>{tax.label}</span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                    selectedQueueCategory === tax.id ? 'bg-zinc-950 text-amber-300' : 'bg-zinc-900 text-zinc-400'
                  }`}>
                    {tax.count}
                  </span>
                </button>
              ))}
            </div>

            {/* Selected Category Content */}
            <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div>
                  <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                    <Target size={18} className="text-rose-400" />
                    Hàng Đợi Lựa Chọn: {selectedQueueCategory.replace('_', ' ').toUpperCase()}
                  </h3>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    Hệ thống tự động đề xuất các ứng viên đặc thù cần đào sâu reviews và specs
                  </p>
                </div>

                <button
                  onClick={() => {
                    const currentItems = priorityQueueFeed[selectedQueueCategory] || [];
                    handleTriggerDepthCrawl(currentItems.map((c) => c.asin));
                  }}
                  className="bg-rose-500 hover:bg-rose-400 text-white font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 transition shadow-lg shadow-rose-500/20"
                >
                  <Zap size={14} />
                  <span>Cào Sâu Toàn Bộ Mục Này ({priorityQueueFeed[selectedQueueCategory]?.length || 0} ASINs)</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {(priorityQueueFeed[selectedQueueCategory] || []).map((p) => (
                  <div
                    key={p.asin}
                    className="bg-zinc-950/80 border border-zinc-800 p-4 rounded-xl flex flex-col justify-between space-y-3"
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
                        <span className="font-mono text-zinc-500">{p.asin}</span>
                        <span className="text-emerald-400 font-bold">${p.price}</span>
                      </div>
                      <h4 className="text-xs font-semibold text-zinc-200 line-clamp-2">{p.title}</h4>
                      <p className="text-[10px] text-zinc-500 mt-1">Brand: {p.brand}</p>
                    </div>

                    <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between text-xs">
                      <div>
                        <span className="text-amber-300 font-bold">{p.rating}★</span>
                        <span className="text-zinc-500 text-[10px] ml-1">({p.reviews_count?.toLocaleString()})</span>
                      </div>
                      <span className="text-sky-400 font-bold text-[11px]">
                        {p.bought_past_month ? `${p.bought_past_month.toLocaleString()}+ sales/mo` : ''}
                      </span>
                    </div>

                    <button
                      onClick={() => handleTriggerDepthCrawl([p.asin])}
                      className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 py-1.5 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1"
                    >
                      <span>Depth Crawl Reviews</span>
                      <ArrowUpRight size={13} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: PRODUCTS MATRIX */}
        {activeTab === 'products' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {candidates.map((p) => (
                <div
                  key={p.asin}
                  className="bg-zinc-900/90 border border-zinc-800/80 rounded-2xl overflow-hidden shadow-lg flex flex-col hover:border-amber-500/40 transition group"
                >
                  <div className="relative h-48 bg-zinc-950 flex items-center justify-center p-3 border-b border-zinc-800/60 overflow-hidden">
                    {p.image_url ? (
                      <img
                        src={p.image_url}
                        alt={p.title}
                        className="max-h-full max-w-full object-contain group-hover:scale-105 transition duration-300"
                        loading="lazy"
                      />
                    ) : (
                      <div className="text-zinc-600 flex flex-col items-center">
                        <ShoppingBag size={32} />
                        <span className="text-[10px] mt-1">Không có ảnh</span>
                      </div>
                    )}

                    <div className="absolute top-2.5 left-2.5 flex flex-col gap-1 items-start">
                      <span className={`text-[9px] font-black px-2 py-0.5 rounded shadow ${
                        p.tier === 'HOT' ? 'bg-rose-500 text-white' :
                        p.tier === 'WARM' ? 'bg-amber-500 text-zinc-950' : 'bg-zinc-800 text-blue-300'
                      }`}>
                        {p.tier}
                      </span>
                      {p.relevance_class && (
                        <span className={`text-[9px] font-black px-1.5 py-0.5 rounded shadow ${
                          p.relevance_class === 'CORE' ? 'bg-emerald-600 text-white' :
                          p.relevance_class === 'ACCESSORY' ? 'bg-amber-600 text-white' :
                          p.relevance_class === 'ADJACENT' ? 'bg-sky-600 text-white' :
                          p.relevance_class === 'IRRELEVANT' ? 'bg-rose-700 text-white' :
                          'bg-zinc-700 text-zinc-300'
                        }`}>
                          {p.relevance_class === 'CORE' ? '🎯 CORE' :
                           p.relevance_class === 'ACCESSORY' ? `🧩 ACC${p.sub_cluster ? `:${p.sub_cluster}` : ''}` :
                           p.relevance_class === 'ADJACENT' ? '🧭 ADJ' :
                           p.relevance_class}
                        </span>
                      )}
                      {Boolean(p.is_best_seller) && (
                        <span className="bg-amber-500 text-zinc-950 text-[9px] font-black px-1.5 py-0.5 rounded">
                          #1 BEST SELLER
                        </span>
                      )}
                      {Boolean(p.is_sponsored) && (
                        <span className="bg-indigo-600/80 text-white text-[9px] font-semibold px-1.5 py-0.5 rounded">
                          Sponsored
                        </span>
                      )}
                    </div>

                    <div className="absolute top-2.5 right-2.5 bg-zinc-900/90 backdrop-blur border border-zinc-700 text-amber-300 font-bold text-xs px-2 py-1 rounded-lg">
                      {p.score} <span className="text-[9px] text-zinc-400">pts</span>
                    </div>
                  </div>

                  <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                    <div>
                      <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
                        <span className="font-mono text-zinc-500">{p.asin}</span>
                        {p.brand && <span className="font-semibold text-zinc-300 truncate max-w-[120px]">{p.brand}</span>}
                      </div>
                      <h4 className="text-xs font-semibold text-zinc-200 line-clamp-2 leading-relaxed" title={p.title}>
                        {p.title}
                      </h4>
                    </div>

                    <div className="pt-2 border-t border-zinc-800/60 space-y-1.5">
                      <div className="flex items-baseline justify-between">
                        <span className="text-lg font-black text-amber-400">${p.price}</span>
                        <div className="flex items-center gap-1 text-xs text-amber-300 font-bold">
                          <Star size={13} className="fill-amber-400 text-amber-400" />
                          <span>{p.rating}</span>
                          <span className="text-zinc-500 font-normal">({p.reviews_count?.toLocaleString()})</span>
                        </div>
                      </div>

                      {p.bought_past_month > 0 && (
                        <div className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                          <TrendingUp size={12} />
                          <span>{p.bought_past_month.toLocaleString()}+ đã mua tháng qua</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 pt-2">
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs py-1.5 rounded-lg flex items-center justify-center gap-1 transition"
                      >
                        <span>Xem Amazon</span>
                        <ExternalLink size={12} />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: VoC 6-PILLAR INTELLIGENCE */}
        {activeTab === 'voc' && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 bg-zinc-900/60 p-4 rounded-2xl border border-zinc-800">
              <div>
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <ShieldAlert size={20} className="text-amber-400" />
                  Bóc Tách Voice of Customer 6 Trụ Cột (VoC Intelligence)
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Đã phân tích {vocData?.total_analyzed || 0} reviews từ Amazon US ({vocData?.critical_count || 0} review 1-3★ tiêu cực & {vocData?.positive_count || 0} review 5★)
                </p>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <button
                  onClick={() => setVocSentimentFilter('all')}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    vocSentimentFilter === 'all'
                      ? 'bg-amber-500 text-zinc-950 font-bold'
                      : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                  }`}
                >
                  Tất cả ({vocData?.total_analyzed || 0})
                </button>
                <button
                  onClick={() => setVocSentimentFilter('critical')}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    vocSentimentFilter === 'critical'
                      ? 'bg-rose-500 text-white font-bold'
                      : 'bg-zinc-800 text-rose-300 hover:bg-zinc-700'
                  }`}
                >
                  ⚠️ Lỗi Đối Thủ 1-3★ ({vocData?.critical_count || 0})
                </button>
                <button
                  onClick={() => setVocSentimentFilter('positive')}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    vocSentimentFilter === 'positive'
                      ? 'bg-emerald-500 text-zinc-950 font-bold'
                      : 'bg-zinc-800 text-emerald-300 hover:bg-zinc-700'
                  }`}
                >
                  ⭐ Động Lực Mua 5★ ({vocData?.positive_count || 0})
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {vocData?.pillars &&
                Object.entries(vocData.pillars).map(([pKey, pVal]: [string, any]) => (
                  <div
                    key={pKey}
                    className="bg-zinc-900/90 border border-zinc-800/90 rounded-2xl p-5 shadow-xl flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-zinc-800 text-amber-300 border border-zinc-700">
                          {pVal.badge}
                        </span>
                        <span className="text-xs font-bold text-zinc-400">
                          {pVal.count} reviews ({pVal.percentage}%)
                        </span>
                      </div>

                      <h4 className="text-sm font-bold text-zinc-100 mb-2">{pVal.title}</h4>
                      <p className="text-xs text-zinc-400 mb-3 leading-relaxed">{pVal.description}</p>
                      
                      <div className="bg-zinc-950/80 p-2.5 rounded-xl border border-zinc-800/80 text-[11px] text-zinc-300 mb-4">
                        <span className="font-semibold text-amber-400">Tâm lý cốt lõi: </span>
                        {pVal.psychological_driver}
                      </div>

                      <div className="space-y-2">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Trích dẫn thực tế từ khách:</p>
                        {pVal.top_quotes?.slice(0, 3).map((q: any, qIdx: number) => (
                          <div
                            key={qIdx}
                            className="bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800/60 text-xs text-zinc-300 italic"
                          >
                            <div className="flex items-center justify-between not-italic text-[10px] text-zinc-400 mb-1">
                              <span className="text-amber-400 font-bold">{q.star_rating}★</span>
                              <span>{q.reviewer_name}</span>
                            </div>
                            "{q.review_text?.slice(0, 140)}..."
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
            </div>

            {/* Sourcing Recommendations */}
            {vocData?.sourcing_recommendations && vocData.sourcing_recommendations.length > 0 && (
              <div className="bg-zinc-900/90 border border-zinc-800/90 rounded-2xl p-6 shadow-xl space-y-4">
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Wrench size={20} className="text-emerald-400" />
                  Chỉ Thị Sourcing & Đàm Phán Xưởng (Factory Actionable Directives)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {vocData.sourcing_recommendations.map((rec: any, rIdx: number) => (
                    <div key={rIdx} className="bg-zinc-950/80 border border-zinc-800 p-4 rounded-xl space-y-2">
                      <h4 className="text-sm font-bold text-amber-400">{rec.title}</h4>
                      <p className="text-xs text-zinc-300">
                        <strong className="text-rose-400">Vấn đề: </strong>
                        {rec.problem}
                      </p>
                      <p className="text-xs text-zinc-300">
                        <strong className="text-emerald-400">Yêu cầu nhà xưởng: </strong>
                        {rec.factory_directive}
                      </p>
                      <p className="text-xs text-zinc-300">
                        <strong className="text-sky-400">Góc viết Listing: </strong>
                        {rec.listing_bullet_angle}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: MASTER AI BLUEPRINT */}
        {activeTab === 'blueprint' && (
          <div className="space-y-6">
            <div className="bg-zinc-900/80 border border-zinc-800 p-6 rounded-2xl shadow-xl space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                <div>
                  <h3 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                    <Sparkles size={22} className="text-amber-400" />
                    Master Amazon Strategy Blueprint
                  </h3>
                  <p className="text-xs text-zinc-400 mt-1">
                    Động cơ AI phân tích thị trường kết hợp định hướng xưởng và tối ưu Listing Amazon chuẩn SEO
                  </p>
                </div>
                <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-bold px-3 py-1 rounded-full">
                  Engine: {masterAnalysis?.engine || 'Local Synthesis'}
                </span>
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-bold text-amber-400 uppercase tracking-wider">Tóm Tắt Thị Trường & Cơ Hội Cạnh Tranh</h4>
                <p className="text-sm text-zinc-200 leading-relaxed bg-zinc-950/80 p-4 rounded-xl border border-zinc-800/80">
                  {masterAnalysis?.summary}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-zinc-950/80 border border-zinc-800 p-4 rounded-xl space-y-3">
                  <h4 className="text-sm font-bold text-rose-400 flex items-center gap-2">
                    <ShieldAlert size={16} /> Lỗi Chết Người Của Đối Thủ Cần Tránh
                  </h4>
                  {masterAnalysis?.product_flaws?.map((f, i) => (
                    <div key={i} className="text-xs border-b border-zinc-800/60 pb-2.5 last:border-0 last:pb-0 space-y-1">
                      <p className="font-semibold text-zinc-200">• {f.flaw}</p>
                      <p className="text-zinc-400 italic">"{f.competitor_quote}"</p>
                      <p className="text-emerald-400">💡 Giải pháp: {f.solution}</p>
                    </div>
                  ))}
                </div>

                <div className="bg-zinc-950/80 border border-zinc-800 p-4 rounded-xl space-y-3">
                  <h4 className="text-sm font-bold text-emerald-400 flex items-center gap-2">
                    <Star size={16} className="fill-emerald-400" /> Động Lực Chốt Đơn 5★ Cần Phát Huy
                  </h4>
                  {masterAnalysis?.buying_triggers?.map((t, i) => (
                    <div key={i} className="text-xs border-b border-zinc-800/60 pb-2.5 last:border-0 last:pb-0 space-y-1">
                      <p className="font-semibold text-zinc-200">• {t.trigger}</p>
                      <p className="text-zinc-400 italic">"{t.quote}"</p>
                      <p className="text-amber-400">🧠 Tâm lý: {t.psychology}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-sm font-bold text-amber-400 uppercase tracking-wider">
                  Mẫu Listing Amazon Tối Ưu Toàn Diện (Title, 5 Bullets, Backend Keywords, A+)
                </h4>
                <div className="bg-zinc-950 p-5 rounded-xl border border-zinc-800 font-mono text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap selection:bg-amber-500/40">
                  {masterAnalysis?.listing_blueprint}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 6: SPONSORED ADS & BEST SELLERS */}
        {activeTab === 'ads_bs' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-zinc-900/90 border border-zinc-800 p-5 rounded-2xl shadow-xl space-y-4">
                <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                  <Flame size={18} className="text-rose-500" />
                  Amazon Sponsored Products ({sponsoredAds.length})
                </h3>
                <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
                  {sponsoredAds.map((ad, i) => (
                    <div key={i} className="bg-zinc-950/80 p-3 rounded-xl border border-zinc-800 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-3">
                        <span className="w-6 h-6 rounded bg-zinc-800 font-mono text-zinc-400 flex items-center justify-center text-[10px]">
                          #{ad.position || i + 1}
                        </span>
                        <div>
                          <p className="font-semibold text-zinc-200 line-clamp-1 max-w-xs">{ad.title}</p>
                          <p className="text-[10px] text-zinc-400">Brand: {ad.brand} | ASIN: {ad.asin}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-emerald-400">${ad.price}</p>
                        <p className="text-[10px] text-amber-300">{ad.rating}★ ({ad.reviews_count})</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-zinc-900/90 border border-zinc-800 p-5 rounded-2xl shadow-xl space-y-4">
                <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                  <Star size={18} className="fill-amber-400 text-amber-400" />
                  Top Best Sellers Leaderboard ({bestSellers.length})
                </h3>
                <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
                  {bestSellers.map((bs, i) => (
                    <div key={i} className="bg-zinc-950/80 p-3 rounded-xl border border-zinc-800 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-3">
                        <span className="w-6 h-6 rounded bg-amber-500/20 text-amber-300 font-mono font-bold flex items-center justify-center text-xs">
                          #{bs.rank || i + 1}
                        </span>
                        <div>
                          <p className="font-semibold text-zinc-200 line-clamp-1 max-w-xs">{bs.title}</p>
                          <p className="text-[10px] text-zinc-400">ASIN: {bs.asin}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-emerald-400">${bs.price}</p>
                        <p className="text-[10px] text-amber-300">{bs.rating}★ ({bs.reviews_count})</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 7: BROWSER SESSION & ZIP 10001 */}
        {activeTab === 'session' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="bg-zinc-900/90 border border-zinc-800 p-6 rounded-2xl shadow-xl space-y-5">
              <div>
                <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Globe size={20} className="text-amber-400" />
                  Quản Lý Trình Duyệt & Địa Chỉ Giao Hàng US (Zip 10001)
                </h3>
                <p className="text-xs text-zinc-400 mt-1">
                  Amazon Analyzer sử dụng Persistent Chromium Profile để tự động lưu giữ cookies đăng nhập, giải captcha và duy trì địa chỉ giao hàng New York 10001.
                </p>
              </div>

              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Trạng thái phiên:</span>
                  <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
                    <CheckCircle2 size={14} />
                    {sessionStatus?.message || 'Đang sẵn sàng'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Mã bưu điện (Zip Code):</span>
                  <span className="font-mono font-bold text-amber-300">10001 (New York, US)</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Cookies đã lưu:</span>
                  <span className="font-mono text-zinc-200">{sessionStatus?.cookie_count || 0} mục</span>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <button
                  onClick={handleOpenBrowser}
                  className="w-full bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-zinc-950 font-bold py-2.5 px-4 rounded-xl text-sm transition flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20"
                >
                  <Globe size={18} />
                  <span>Mở Trình Duyệt Kiểm Tra / Đăng Nhập Amazon</span>
                </button>

                <button
                  onClick={handleClearSession}
                  className="w-full bg-zinc-800 hover:bg-rose-900/40 text-rose-300 border border-zinc-700 hover:border-rose-700/50 font-semibold py-2.5 px-4 rounded-xl text-xs transition flex items-center justify-center gap-2"
                >
                  <X size={16} />
                  <span>Xóa Sạch Cookies / Đặt Lại Phiên Trình Duyệt</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 8: FOLDERS & DB */}
        {activeTab === 'folders' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-zinc-100">Quản Lý Thư Mục Niche ({folders.length})</h3>
                <p className="text-xs text-zinc-400">Tổ chức và lưu trữ cơ sở dữ liệu sản phẩm theo từng ngách</p>
              </div>
              <button
                onClick={() => setShowCreateFolderModal(true)}
                className="bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition"
              >
                <FolderPlus size={14} />
                <span>Thêm Niche Mới</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {folders.map((f) => (
                <div
                  key={f.name}
                  onClick={() => {
                    setActiveFolder(f.name);
                    setKeywordInput(f.name);
                    localStorage.setItem('amazon_analyzer_active_folder', f.name);
                  }}
                  className={`p-4 rounded-2xl border cursor-pointer transition ${
                    activeFolder === f.name
                      ? 'bg-amber-500/10 border-amber-500/50 shadow-lg'
                      : 'bg-zinc-900/80 border-zinc-800 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-bold text-zinc-100">{f.name}</h4>
                    <span className="text-xs bg-zinc-800 text-amber-300 font-bold px-2 py-0.5 rounded">
                      {f.product_count} candidates
                    </span>
                  </div>
                  <div className="space-y-1 text-xs text-zinc-400">
                    <p>Doanh số ước tính: <span className="text-emerald-400 font-semibold">{f.total_sales?.toLocaleString() || 0}</span></p>
                    <p>Giá trung bình: <span className="text-zinc-200 font-semibold">${f.avg_price || 0}</span></p>
                    <p>Rating: <span className="text-amber-300 font-semibold">{f.avg_rating || 0}★</span></p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Modal: Create Folder */}
      {showCreateFolderModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-sm w-full space-y-4">
            <h3 className="text-base font-bold text-zinc-100">Tạo Thư Mục Niche Mới</h3>
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="VD: cordless vacuum, matcha whisk..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-amber-400"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowCreateFolderModal(false)}
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
              >
                Hủy
              </button>
              <button
                onClick={handleCreateFolder}
                className="bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold px-4 py-1.5 rounded-xl text-xs"
              >
                Tạo Niche
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Merge Folder */}
      {showMergeModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 max-w-sm w-full space-y-4">
            <h3 className="text-base font-bold text-zinc-100">Gộp Dữ Liệu Niche</h3>
            <p className="text-xs text-zinc-400">
              Gộp toàn bộ sản phẩm và reviews từ <strong className="text-amber-300">{activeFolder}</strong> vào:
            </p>
            <select
              value={mergeTargetFolder}
              onChange={(e) => setMergeTargetFolder(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-amber-400"
            >
              <option value="">-- Chọn thư mục đích --</option>
              {folders.filter((f) => f.name !== activeFolder).map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name}
                </option>
              ))}
            </select>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowMergeModal(false)}
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
              >
                Hủy
              </button>
              <button
                onClick={handleMergeFolder}
                disabled={!mergeTargetFolder}
                className="bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold px-4 py-1.5 rounded-xl text-xs disabled:opacity-50"
              >
                Xác Nhận Gộp
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ASIN SEARCH OBSERVATION MATRIX MODAL */}
      {selectedMatrixAsin && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-3xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs font-bold text-amber-400 uppercase tracking-wide">
                  <Compass size={14} />
                  <span>Search Observation Matrix (Vị Trí & Ngữ Cảnh Tìm Kiếm)</span>
                </div>
                <h3 className="text-lg font-black text-white mt-1">
                  ASIN: <span className="font-mono text-amber-400">{selectedMatrixAsin}</span> - {asinMatrixData?.product?.title?.slice(0, 60)}...
                </h3>
              </div>
              <button
                onClick={() => setSelectedMatrixAsin(null)}
                className="p-2 hover:bg-zinc-800 rounded-full text-zinc-400 hover:text-white transition"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4">
              {isMatrixLoading ? (
                <div className="py-12 text-center text-zinc-500 text-sm">Đang tải ma trận vị trí...</div>
              ) : (
                <>
                  {/* Summary Counters */}
                  <div className="grid grid-cols-4 gap-3 text-center">
                    <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
                      <div className="text-[10px] text-zinc-500 font-bold uppercase">Tổng Lần Quan Sát</div>
                      <div className="text-lg font-mono font-bold text-white mt-0.5">{asinMatrixData?.total_observations || 0}</div>
                    </div>
                    <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
                      <div className="text-[10px] text-amber-400 font-bold uppercase">Sponsored (Chạy Ads)</div>
                      <div className="text-lg font-mono font-bold text-amber-400 mt-0.5">{asinMatrixData?.sponsored_observations || 0}</div>
                    </div>
                    <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
                      <div className="text-[10px] text-emerald-400 font-bold uppercase">Organic (Tự Nhiên)</div>
                      <div className="text-lg font-mono font-bold text-emerald-400 mt-0.5">{asinMatrixData?.organic_observations || 0}</div>
                    </div>
                    <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
                      <div className="text-[10px] text-zinc-400 font-bold uppercase">Số Từ Khóa Xuất Hiện</div>
                      <div className="text-lg font-mono font-bold text-zinc-200 mt-0.5">{asinMatrixData?.queries_count || 0}</div>
                    </div>
                  </div>

                  {/* Observations Table */}
                  <div className="border border-zinc-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-950 text-zinc-400 font-bold border-b border-zinc-800">
                        <tr>
                          <th className="py-2.5 px-4">Từ Khóa Tìm Kiếm (Query)</th>
                          <th className="py-2.5 px-3">Trang</th>
                          <th className="py-2.5 px-3">Vị Trí</th>
                          <th className="py-2.5 px-3">Phân Loại (Placement)</th>
                          <th className="py-2.5 px-3">Bằng Chứng (Evidence)</th>
                          <th className="py-2.5 px-3">Khuyến Mãi / Giao Hàng</th>
                          <th className="py-2.5 px-4 text-right">Thời Điểm</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800/60 font-medium">
                        {(asinMatrixData?.observations || []).map((o: any) => (
                          <tr key={o.id} className="hover:bg-zinc-800/30 transition">
                            <td className="py-2.5 px-4 font-bold text-zinc-200">
                              "{o.query}"
                            </td>
                            <td className="py-2.5 px-3 text-zinc-400">Trang {o.page}</td>
                            <td className="py-2.5 px-3">
                              <span className="font-mono font-bold text-amber-400">#{o.position}</span>
                            </td>
                            <td className="py-2.5 px-3">
                              {o.placement_type === 'SPONSORED' ? (
                                <span className="px-2 py-0.5 bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded font-bold text-[10px]">
                                  🏷️ SPONSORED
                                </span>
                              ) : o.placement_type === 'ORGANIC' ? (
                                <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded font-bold text-[10px]">
                                  🌿 ORGANIC
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 bg-zinc-700 text-zinc-300 rounded text-[10px]">
                                  ❓ UNKNOWN
                                </span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">
                              {o.sponsored_evidence}
                            </td>
                            <td className="py-2.5 px-3 text-zinc-400">
                              {o.coupon && <span className="text-emerald-400 mr-2">[{o.coupon}]</span>}
                              {o.delivery_signal && <span>{o.delivery_signal}</span>}
                              {!o.coupon && !o.delivery_signal && <span className="text-zinc-600">-</span>}
                            </td>
                            <td className="py-2.5 px-4 text-right font-mono text-zinc-500 text-[11px]">
                              {o.observed_at ? o.observed_at.split(' ')[0] : 'N/A'}
                            </td>
                          </tr>
                        ))}
                        {(!asinMatrixData?.observations || asinMatrixData.observations.length === 0) && (
                          <tr>
                            <td colSpan={7} className="py-8 text-center text-zinc-500">
                              Chưa có observation nào được ghi nhận cho ASIN này trong đợt quét vừa qua.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PARENT / CHILD VARIATION ARCHITECTURE MODAL */}
      {selectedVariationAsin && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-3xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs font-bold text-purple-400 uppercase tracking-wide">
                  <Package size={14} />
                  <span>Parent / Child Variation Entity Architecture (Group Nhưng Không Flatten)</span>
                </div>
                <h3 className="text-lg font-black text-white mt-1">
                  Parent ASIN: <span className="font-mono text-purple-400">{variationData?.parent_asin || selectedVariationAsin}</span> ({variationData?.siblings_count || 0} Biến Thể Liên Kết)
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Từng Child ASIN được bảo tồn độc lập với giá, tình trạng tồn kho và vị trí tìm kiếm riêng biệt.
                </p>
              </div>
              <button
                onClick={() => setSelectedVariationAsin(null)}
                className="p-2 hover:bg-zinc-800 rounded-full text-zinc-400 hover:text-white transition"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-5">
              {isVariationLoading ? (
                <div className="py-12 text-center text-zinc-500 text-sm">Đang tải cấu trúc biến thể...</div>
              ) : (
                <>
                  {/* Variation Dimensions Badges */}
                  {variationData?.variation_dimensions && Object.keys(variationData.variation_dimensions).length > 0 && (
                    <div className="bg-zinc-950 p-4 rounded-2xl border border-zinc-800">
                      <div className="text-xs font-bold text-zinc-400 uppercase tracking-wide mb-2">
                        Kích Thước Biến Thể Đã Bóc Tách (Twister Dimensions):
                      </div>
                      <div className="flex flex-wrap gap-3">
                        {Object.entries(variationData.variation_dimensions).map(([dimName, vals]: [string, any]) => (
                          <div key={dimName} className="bg-zinc-900 border border-zinc-700/60 rounded-xl px-3 py-1.5 text-xs">
                            <span className="text-purple-300 font-bold">{dimName}: </span>
                            <span className="text-zinc-300">
                              {Array.isArray(vals) ? vals.join(', ') : String(vals)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Sibling Entities Table */}
                  <div className="border border-zinc-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-950 text-zinc-400 font-bold border-b border-zinc-800">
                        <tr>
                          <th className="py-2.5 px-4">ASIN / Vai Trò</th>
                          <th className="py-2.5 px-3">Tên Biến Thể</th>
                          <th className="py-2.5 px-3 text-right">Giá Hiện Tại</th>
                          <th className="py-2.5 px-3">Tồn Kho</th>
                          <th className="py-2.5 px-3">Trạng Thái</th>
                          <th className="py-2.5 px-3">Tier</th>
                          <th className="py-2.5 px-4 text-center">Amazon</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800/60 font-medium">
                        {(variationData?.related_entities || []).map((v: any) => (
                          <tr key={v.asin} className={`hover:bg-zinc-800/30 transition ${v.asin === selectedVariationAsin ? 'bg-purple-500/10' : ''}`}>
                            <td className="py-2.5 px-4 font-mono font-bold text-zinc-200">
                              <div>{v.asin}</div>
                              <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded mt-0.5 inline-block ${
                                v.is_parent === 1
                                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                                  : 'bg-zinc-800 text-zinc-400'
                              }`}>
                                {v.is_parent === 1 ? '👑 PARENT' : '🔗 CHILD VARIANT'}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-semibold text-zinc-300 max-w-xs truncate" title={v.title}>
                              {v.title}
                            </td>
                            <td className="py-2.5 px-3 text-right font-bold text-amber-400 font-mono">
                              ${v.price || '0.00'}
                            </td>
                            <td className="py-2.5 px-3 text-zinc-300">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                (v.availability || '').toLowerCase().includes('in stock')
                                  ? 'text-emerald-400 bg-emerald-500/10'
                                  : 'text-amber-400 bg-amber-500/10'
                              }`}>
                                {v.availability || 'In Stock'}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px]">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                v.completeness_status === 'complete'
                                  ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                                  : 'text-zinc-400 bg-zinc-800'
                              }`}>
                                {v.completeness_status || 'partial'}
                              </span>
                            </td>
                            <td className="py-2.5 px-3">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                v.tier === 'HOT'
                                  ? 'bg-rose-500/20 text-rose-300'
                                  : v.tier === 'WARM'
                                  ? 'bg-amber-500/20 text-amber-300'
                                  : 'bg-blue-500/20 text-blue-300'
                              }`}>
                                {v.tier || 'COLD'}
                              </span>
                            </td>
                            <td className="py-2.5 px-4 text-center">
                              <a
                                href={`https://www.amazon.com/dp/${v.asin}`}
                                target="_blank"
                                rel="noreferrer"
                                className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white inline-block"
                                title="Xem trên Amazon"
                              >
                                <ExternalLink size={13} />
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
