import React from 'react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  BarChart,
  Bar,
  Cell,
  CartesianGrid,
  LineChart,
  Line,
  Legend,
  AreaChart,
  Area
} from 'recharts';

interface Product {
  asin: string;
  title: string;
  price: number;
  rating: number;
  reviews_count: number;
  bought_past_month: number;
  is_sponsored: number;
  is_best_seller: number;
  tier?: string;
  discovery_lane?: string;
}

interface SaturationPoint {
  id: number;
  lane: string;
  query_or_target: string;
  page_number: number;
  asins_new_unique: number;
  cumulative_unique: number;
  marginal_yield: number;
  strategy_used: string;
}

interface AmazonChartsProps {
  products: Product[];
  vocPillars?: Record<string, { title: string; count: number; percentage: number; color: string }>;
  saturationCurve?: SaturationPoint[];
  universeSummary?: {
    total_candidates: number;
    cold_count: number;
    warm_count: number;
    hot_count: number;
    lanes?: Record<string, number>;
  };
}

export const AmazonCharts: React.FC<AmazonChartsProps> = ({
  products,
  vocPillars,
  saturationCurve,
  universeSummary
}) => {
  if (!products || products.length === 0) {
    return null;
  }

  // Scatter data: Price vs Rating
  const scatterData = products.map((p) => ({
    name: p.title.slice(0, 30) + '...',
    price: p.price,
    rating: p.rating,
    sales: p.bought_past_month || 10,
    asin: p.asin,
    tier: p.tier || 'COLD',
    isSponsored: Boolean(p.is_sponsored),
    isBestSeller: Boolean(p.is_best_seller)
  }));

  // Top Products by Monthly Sales
  const topSalesData = [...products]
    .sort((a, b) => (b.bought_past_month || 0) - (a.bought_past_month || 0))
    .slice(0, 8)
    .map((p) => ({
      name: (p.asin || p.title).slice(0, 15),
      fullTitle: p.title,
      sales: p.bought_past_month || 0,
      price: p.price,
      rating: p.rating
    }));

  // VoC Pillar Data
  const pillarChartData = vocPillars
    ? Object.entries(vocPillars).map(([key, val]) => ({
        name: val.title.split('(')[0].trim().replace(/^\d+\.\s*/, ''),
        count: val.count,
        percentage: val.percentage,
        color: val.color === 'rose' ? '#f43f5e' :
               val.color === 'amber' ? '#f59e0b' :
               val.color === 'sky' ? '#0ea5e9' :
               val.color === 'violet' ? '#8b5cf6' :
               val.color === 'emerald' ? '#10b981' : '#ec4899'
      }))
    : [];

  // Saturation Curve Data
  const saturationData = saturationCurve && saturationCurve.length > 0
    ? saturationCurve.map((pt, idx) => ({
        step: `Q${idx + 1}`,
        query: pt.query_or_target,
        cumulative: pt.cumulative_unique,
        marginalYield: pt.marginal_yield,
        newAsins: pt.asins_new_unique,
        lane: pt.lane
      }))
    : [];

  // Lane Breakdown Data
  const laneData = universeSummary?.lanes
    ? Object.entries(universeSummary.lanes).map(([lane, count]) => ({
        laneName: lane === 'keyword_search' ? 'Keyword Search' :
                  lane === 'suggestions' ? 'Live Suggestions' :
                  lane === 'brand_expansion' ? 'Brand Expansion' :
                  lane === 'intent_modifiers' ? 'Intent Modifiers' : lane,
        count
      }))
    : [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 my-6">
      {/* 1. Discovery Saturation Curve (If Available) */}
      {saturationData.length > 0 && (
        <div className="lg:col-span-2 bg-gradient-to-br from-zinc-900 via-zinc-900 to-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
                <h3 className="text-base font-bold text-zinc-100">
                  Đường Cong Bão Hòa Khám Phá (Discovery Saturation Curve)
                </h3>
                <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full">
                  Acquisition Principle
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                Theo dõi số ASIN tích lũy (Cột xanh) vs Tỷ lệ sinh ASIN mới (Marginal Yield % - Đường vàng). Khi đường vàng tiệm cận 0, ngách đã tiếp cận điểm bão hòa.
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-zinc-500">Tổng ứng viên tích lũy:</span>
              <p className="text-xl font-black text-emerald-400">
                {saturationData[saturationData.length - 1]?.cumulative} ASINs
              </p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={saturationData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorCumul" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="step" stroke="#71717a" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
                <YAxis yAxisId="left" stroke="#10b981" tick={{ fill: '#10b981', fontSize: 11 }} unit=" ASIN" />
                <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" tick={{ fill: '#f59e0b', fontSize: 11 }} unit="%" domain={[0, 100]} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const d = payload[0].payload;
                      return (
                        <div className="bg-zinc-950 border border-zinc-700 p-3 rounded-xl shadow-2xl text-xs text-zinc-200">
                          <p className="font-bold text-amber-400 mb-1">{d.query}</p>
                          <p className="text-[10px] text-zinc-400 mb-2">Làn: {d.lane}</p>
                          <p>ASINs tích lũy: <strong className="text-emerald-400">{d.cumulative}</strong></p>
                          <p>ASINs mới thêm: <strong className="text-sky-400">+{d.newAsins}</strong></p>
                          <p>Marginal Yield: <strong className="text-amber-300">{d.marginalYield}%</strong></p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area yAxisId="left" type="monotone" dataKey="cumulative" stroke="#10b981" strokeWidth={2.5} fillOpacity={1} fill="url(#colorCumul)" name="ASINs Tích Lũy" />
                <Line yAxisId="right" type="monotone" dataKey="marginalYield" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4, fill: '#f59e0b' }} name="Marginal Yield %" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 2. Price vs Star Rating Scatter Plot */}
      <div className="bg-zinc-900/90 border border-zinc-800/80 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse"></span>
              Ma trận Giá Bán vs Đánh Giá Sao (Price vs Rating)
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Kích thước bong bóng = Doanh số bán ước tính tháng qua (Sales Velocity)
            </p>
          </div>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                type="number"
                dataKey="price"
                name="Giá bán"
                unit="$"
                stroke="#71717a"
                tick={{ fill: '#a1a1aa', fontSize: 11 }}
              />
              <YAxis
                type="number"
                dataKey="rating"
                name="Đánh giá"
                domain={[3.0, 5.0]}
                unit="★"
                stroke="#71717a"
                tick={{ fill: '#a1a1aa', fontSize: 11 }}
              />
              <ZAxis type="number" dataKey="sales" range={[60, 450]} />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-zinc-950 border border-zinc-700 p-3 rounded-lg shadow-2xl text-xs text-zinc-200">
                        <p className="font-semibold text-amber-400 mb-1">{data.name}</p>
                        <p>ASIN: <span className="text-zinc-100 font-mono">{data.asin}</span></p>
                        <p>Tier: <span className="text-sky-300 font-bold">{data.tier}</span></p>
                        <p>Giá: <span className="text-emerald-400 font-bold">${data.price}</span></p>
                        <p>Rating: <span className="text-amber-300 font-bold">{data.rating}★</span></p>
                        <p>Doanh số tháng: <span className="text-sky-400 font-bold">{data.sales?.toLocaleString()} sales/mo</span></p>
                        {data.isBestSeller && <span className="mt-1 inline-block bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded text-[10px]">#1 Best Seller</span>}
                        {data.isSponsored && <span className="mt-1 ml-1 inline-block bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded text-[10px]">Sponsored Ad</span>}
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Scatter name="Sản phẩm" data={scatterData} fill="#f59e0b" fillOpacity={0.7} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3. Top Products by Monthly Sales */}
      <div className="bg-zinc-900/90 border border-zinc-800/80 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              Top Sản Phẩm Doanh Số Ước Tính Cao Nhất (Monthly Velocity)
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Lượt mua thực tế trong tháng gần nhất trên Amazon US
            </p>
          </div>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={topSalesData} margin={{ top: 10, right: 10, bottom: 25, left: -5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="#71717a"
                tick={{ fill: '#a1a1aa', fontSize: 11 }}
                angle={-15}
                textAnchor="end"
              />
              <YAxis stroke="#71717a" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-zinc-950 border border-zinc-700 p-3 rounded-lg shadow-2xl text-xs text-zinc-200">
                        <p className="font-semibold text-emerald-400 mb-1">{data.fullTitle}</p>
                        <p>Ước tính tháng: <span className="font-bold text-zinc-100">{data.sales?.toLocaleString()} units</span></p>
                        <p>Giá niêm yết: <span className="font-bold text-amber-300">${data.price}</span></p>
                        <p>Đánh giá: <span className="font-bold text-sky-400">{data.rating}★</span></p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar dataKey="sales" radius={[6, 6, 0, 0]}>
                {topSalesData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={index === 0 ? '#10b981' : index === 1 ? '#059669' : '#047857'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 4. VoC 6-Pillars Distribution (Full width if available) */}
      {pillarChartData.length > 0 && (
        <div className="lg:col-span-2 bg-zinc-900/90 border border-zinc-800/80 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping"></span>
                Tỷ Trọng Tiếng Nói Khách Hàng 6 Trụ Cột (VoC Intelligence Breakdown)
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Bóc tách từ tập đánh giá tiêu cực (1-3★) và đánh giá tích cực (5★) từ người mua hàng
              </p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={pillarChartData} layout="vertical" margin={{ top: 5, right: 30, left: 140, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
                <XAxis type="number" stroke="#71717a" tick={{ fill: '#a1a1aa', fontSize: 11 }} unit="%" />
                <YAxis
                  dataKey="name"
                  type="category"
                  stroke="#71717a"
                  tick={{ fill: '#e4e4e7', fontSize: 12, fontWeight: 500 }}
                  width={130}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-zinc-950 border border-zinc-700 p-3 rounded-lg shadow-2xl text-xs text-zinc-200">
                          <p className="font-semibold text-zinc-100 mb-1">{data.name}</p>
                          <p>Số lượng phản hồi: <span className="font-bold text-amber-400">{data.count} reviews</span></p>
                          <p>Tỷ trọng phân tích: <span className="font-bold text-emerald-400">{data.percentage}%</span></p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="percentage" radius={[0, 6, 6, 0]}>
                  {pillarChartData.map((entry, index) => (
                    <Cell key={`pillar-cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};
