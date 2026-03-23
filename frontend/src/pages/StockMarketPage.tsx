import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  fetchStocks,
  fetchStockPortfolio,
  fetchStockNews,
  fetchPortfolioHistory,
  StockInfoResponse,
  StockPortfolioResponse,
  StockNewsItemResponse,
} from '../services/api';

function PriceChange({ pct }: { pct: number }) {
  const color = pct >= 0 ? 'text-green-600' : 'text-red-500';
  const arrow = pct >= 0 ? '\u25B2' : '\u25BC';
  return (
    <span className={`${color} font-bold text-sm`}>
      {arrow} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function PortfolioChart({ points: data }: { points: { timestamp: string; total_value: number }[] }) {
  if (data.length < 2) return null;
  const values = data.map(d => d.total_value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 300, h = 120, padX = 6, padTop = 20, padBot = 22;
  const chartH = h - padTop - padBot;

  const pts = values.map((v, i) => {
    const x = padX + (i / (values.length - 1)) * (w - padX * 2);
    const y = padTop + chartH - ((v - min) / range) * chartH;
    return { x, y };
  });
  const line = pts.map(p => `${p.x},${p.y}`).join(' ');
  const last = values[values.length - 1];
  const first = values[0];
  const color = last >= first ? '#10b981' : '#ef4444';

  // Time labels — show first, middle, last
  const fmtTime = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  };
  const labelIdxs = [0, Math.floor(data.length / 2), data.length - 1];

  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>{min.toFixed(0)}</span>
        <span className={`font-bold ${last >= first ? 'text-green-600' : 'text-red-500'}`}>
          Current: {last.toFixed(0)}
        </span>
        <span>{max.toFixed(0)}</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 100 }}>
        {/* Grid lines */}
        <line x1={padX} y1={padTop} x2={w - padX} y2={padTop} stroke="#e5e7eb" strokeWidth="0.5" />
        <line x1={padX} y1={padTop + chartH / 2} x2={w - padX} y2={padTop + chartH / 2} stroke="#e5e7eb" strokeWidth="0.5" />
        <line x1={padX} y1={padTop + chartH} x2={w - padX} y2={padTop + chartH} stroke="#e5e7eb" strokeWidth="0.5" />
        {/* Line */}
        <polyline points={line} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        {/* End dot */}
        <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="3" fill={color} />
        {/* Time labels */}
        {labelIdxs.map((idx, i) => (
          <text
            key={i}
            x={pts[idx].x}
            y={h - 4}
            textAnchor={i === 0 ? 'start' : i === labelIdxs.length - 1 ? 'end' : 'middle'}
            fontSize="9"
            fill="#9ca3af"
          >
            {fmtTime(data[idx].timestamp)}
          </text>
        ))}
      </svg>
    </div>
  );
}

export default function StockMarketPage() {
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const childId = selectedChild?.id || '';

  const [stocks, setStocks] = useState<StockInfoResponse[]>([]);
  const [portfolio, setPortfolio] = useState<StockPortfolioResponse | null>(null);
  const [news, setNews] = useState<StockNewsItemResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'market' | 'news' | 'portfolio'>('market');
  const [expandedNews, setExpandedNews] = useState<number | null>(null);
  const [balanceHistory, setBalanceHistory] = useState<{ timestamp: string; total_value: number }[]>([]);

  const loadData = useCallback(async () => {
    if (!childId) return;
    try {
      const [s, p, n, bh] = await Promise.all([
        fetchStocks(),
        fetchStockPortfolio(childId),
        fetchStockNews(childId),
        fetchPortfolioHistory(childId).catch(() => []),
      ]);
      setStocks(s);
      setPortfolio(p);
      setNews(n);
      setBalanceHistory(bh);
    } catch (err) {
      console.error('Failed to load stock data:', err);
    } finally {
      setLoading(false);
    }
  }, [childId]);

  useEffect(() => {
    if (!childId) { navigate('/'); return; }
    loadData();
  }, [childId, navigate, loadData]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-green-400 via-emerald-300 to-teal-200 flex items-center justify-center">
        <div className="text-2xl text-white animate-pulse">Loading Market...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-400 via-emerald-300 to-teal-200 flex flex-col items-center p-4">
      {/* Back button */}
      <div className="absolute top-4 left-4">
        <button
          onClick={() => navigate('/')}
          className="text-white/80 hover:text-white bg-white/20 hover:bg-white/30 px-4 py-2 rounded-full transition"
        >
          &larr; Back
        </button>
      </div>

      {/* Header */}
      <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-1 drop-shadow-lg mt-8">
        Kid Stock Market
      </h1>
      <p className="text-lg text-white/90 mb-4 drop-shadow">
        {selectedChild?.name}'s Trading Floor
      </p>

      {/* Balance bar */}
      {portfolio && (
        <div className="bg-white/90 rounded-2xl shadow-xl px-6 py-3 mb-4 flex gap-4 text-center flex-wrap justify-center">
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Coins</div>
            <div className="text-xl font-extrabold text-yellow-600">{portfolio.coins.toFixed(0)}</div>
          </div>
          <div className="border-l border-gray-200" />
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Holdings</div>
            <div className="text-xl font-extrabold text-emerald-600">
              {(portfolio.total_value - portfolio.coins).toFixed(0)}
            </div>
          </div>
          <div className="border-l border-gray-200" />
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Total</div>
            <div className="text-xl font-extrabold text-blue-600">{portfolio.total_value.toFixed(0)}</div>
          </div>
          <div className="border-l border-gray-200" />
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Gains</div>
            <div className={`text-xl font-extrabold ${portfolio.total_gains >= 0 ? 'text-green-600' : 'text-red-500'}`}>
              {portfolio.total_gains >= 0 ? '+' : ''}{portfolio.total_gains.toFixed(0)}
            </div>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-2 mb-4">
        {(['market', 'news', 'portfolio'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2 rounded-full font-bold text-sm transition-all ${
              tab === t
                ? 'bg-white text-emerald-700 shadow-lg scale-105'
                : 'bg-white/30 text-white hover:bg-white/50'
            }`}
          >
            {t === 'market' ? 'Market' : t === 'news' ? 'News' : 'My Stuff'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="w-full max-w-lg">
        {tab === 'market' && (() => {
          const holdingsMap = new Map<number, { shares: number; value: number }>();
          portfolio?.holdings.forEach((h: any) => holdingsMap.set(h.stock_id, { shares: h.shares, value: h.value }));
          const sorted = [...stocks].sort((a, b) => b.current_price - a.current_price);
          const myStocks = sorted.filter(s => holdingsMap.has(s.id));

          return (
            <div className="space-y-3">
              {/* Track My Stocks */}
              {myStocks.length > 0 && (
                <div className="bg-white/90 rounded-2xl shadow-lg p-4">
                  <div className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-2">My Stocks</div>
                  {balanceHistory.length >= 2 && (
                    <div className="mb-3">
                      <PortfolioChart points={balanceHistory} />
                    </div>
                  )}
                  {portfolio && (
                    <div className="flex gap-4 text-center text-sm mb-3">
                      <div className="flex-1 bg-gray-50 rounded-xl py-2">
                        <div className="text-xs text-gray-400">Invested</div>
                        <div className="font-bold text-gray-700">{(portfolio.total_value - portfolio.coins).toFixed(0)}</div>
                      </div>
                      <div className="flex-1 bg-gray-50 rounded-xl py-2">
                        <div className="text-xs text-gray-400">Gains</div>
                        <div className={`font-bold ${portfolio.total_gains >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                          {portfolio.total_gains >= 0 ? '+' : ''}{portfolio.total_gains.toFixed(0)}
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="space-y-1">
                    {myStocks.map(s => {
                      const h = holdingsMap.get(s.id)!;
                      return (
                        <button
                          key={s.id}
                          onClick={() => navigate(`/stockmarket/${s.id}`)}
                          className="w-full flex items-center gap-2 p-2 rounded-xl hover:bg-gray-50 transition"
                        >
                          <span className="text-xl">{s.emoji}</span>
                          <span className="text-sm font-bold text-gray-700 flex-1 text-left">{s.symbol}</span>
                          <PriceChange pct={s.change_pct} />
                          <div className="text-right ml-2">
                            <div className="text-sm font-bold text-gray-800">{h.value.toFixed(0)}</div>
                            <div className="text-[10px] text-gray-400">{h.shares} shares</div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Stock list sorted by price */}
              {sorted.map((stock) => {
                const holding = holdingsMap.get(stock.id);
                return (
                  <button
                    key={stock.id}
                    onClick={() => navigate(`/stockmarket/${stock.id}`)}
                    className="w-full bg-white/90 rounded-2xl shadow-lg p-4 flex items-center gap-3 hover:scale-[1.02] transition-all active:scale-[0.98]"
                  >
                    <span className="text-3xl">{stock.emoji}</span>
                    <div className="flex-1 text-left">
                      <div className="font-bold text-gray-800">
                        {stock.name}
                        {stock.type === 'bond' && (
                          <span className="ml-1.5 text-[10px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full font-bold">BOND</span>
                        )}
                      </div>
                      <div className="text-xs text-gray-400">
                        {stock.symbol}
                        {stock.dividend_yield > 0 && (
                          <span className="ml-1 text-green-600 font-medium">
                            {(stock.dividend_yield * 100).toFixed(1)}% yield
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-extrabold text-gray-800">{stock.current_price.toFixed(2)}</div>
                      <PriceChange pct={stock.change_pct} />
                    </div>
                    {holding && (
                      <div className="text-right border-l border-gray-200 pl-3 ml-1">
                        <div className="text-sm font-bold text-purple-600">{holding.shares}</div>
                        <div className="text-[10px] text-gray-400">owned</div>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          );
        })()}

        {tab === 'news' && (
          <div className="space-y-3">
            {news.length === 0 && (
              <div className="bg-white/90 rounded-2xl p-6 text-center text-gray-500">
                No news yet! Check back tomorrow.
              </div>
            )}
            {news.map((item, i) => (
              <div
                key={i}
                className="bg-white/90 rounded-2xl shadow-lg p-4 cursor-pointer hover:shadow-xl transition"
                onClick={() => setExpandedNews(expandedNews === i ? null : i)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xl">{item.stock_emoji}</span>
                  <PriceChange pct={item.change_pct} />
                  <span className="text-xs text-gray-400">{item.stock_symbol}</span>
                </div>
                <div className="font-bold text-gray-800 text-lg leading-tight">
                  {item.headline}
                </div>
                {expandedNews === i && (
                  <p className="mt-3 text-gray-600 leading-relaxed whitespace-pre-line">
                    {item.body}
                  </p>
                )}
                {expandedNews !== i && (
                  <p className="mt-1 text-xs text-gray-400">Tap to read more...</p>
                )}
              </div>
            ))}
          </div>
        )}

        {tab === 'portfolio' && portfolio && (
          <div className="space-y-3">
            {/* Holdings */}
            {portfolio.holdings.length === 0 ? (
              <div className="bg-white/90 rounded-2xl p-6 text-center">
                <div className="text-4xl mb-2">📊</div>
                <div className="text-gray-500">No stocks yet! Go buy some!</div>
              </div>
            ) : (
              portfolio.holdings.map((h: any) => (
                <button
                  key={h.stock_id}
                  onClick={() => navigate(`/stockmarket/${h.stock_id}`)}
                  className="w-full bg-white/90 rounded-2xl shadow-lg p-4 flex items-center gap-3 hover:scale-[1.02] transition-all active:scale-[0.98]"
                >
                  <span className="text-3xl">{h.emoji}</span>
                  <div className="flex-1 text-left">
                    <div className="font-bold text-gray-800">
                      {h.name}
                      {h.type === 'bond' && (
                        <span className="ml-1.5 text-[10px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full font-bold">BOND</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400">
                      {h.shares} shares
                      {h.dividend_yield > 0 && (
                        <span className="ml-1 text-green-600 font-medium">
                          {(h.dividend_yield * 100).toFixed(1)}% yield
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-extrabold text-emerald-600">{h.value.toFixed(0)}</div>
                    <div className="text-xs text-gray-400">@ {h.current_price.toFixed(2)} ea</div>
                  </div>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
