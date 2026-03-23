import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  fetchStockDetail,
  fetchStockPortfolio,
  buyStock,
  sellStock,
  StockDetailResponse,
  StockPortfolioResponse,
} from '../services/api';

function MiniChart({ history }: { history: { price: number; market_day: string }[] }) {
  if (history.length < 2) return null;

  const prices = history.map((h) => h.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const w = 300;
  const h = 100;
  const padding = 8;

  const points = prices.map((p, i) => {
    const x = padding + (i / (prices.length - 1)) * (w - padding * 2);
    const y = h - padding - ((p - min) / range) * (h - padding * 2);
    return `${x},${y}`;
  }).join(' ');

  const lastPrice = prices[prices.length - 1];
  const firstPrice = prices[0];
  const color = lastPrice >= firstPrice ? '#10b981' : '#ef4444';

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-24">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function StockDetailPage() {
  const navigate = useNavigate();
  const { stockId } = useParams<{ stockId: string }>();
  const { selectedChild } = useAuth();
  const childId = selectedChild?.id || '';

  const [detail, setDetail] = useState<StockDetailResponse | null>(null);
  const [portfolio, setPortfolio] = useState<StockPortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [shares, setShares] = useState(1);
  const [trading, setTrading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const loadData = useCallback(async () => {
    if (!childId || !stockId) return;
    try {
      const [d, p] = await Promise.all([
        fetchStockDetail(parseInt(stockId), childId),
        fetchStockPortfolio(childId),
      ]);
      setDetail(d);
      setPortfolio(p);
    } catch (err) {
      console.error('Failed to load stock detail:', err);
    } finally {
      setLoading(false);
    }
  }, [childId, stockId]);

  useEffect(() => {
    if (!childId) { navigate('/'); return; }
    loadData();
  }, [childId, navigate, loadData]);

  const myShares = portfolio?.holdings.find((h: any) => h.stock_id === parseInt(stockId || '0'))?.shares || 0;

  const handleBuy = async () => {
    if (!stockId || !childId) return;
    setTrading(true);
    setMessage(null);
    try {
      const result = await buyStock(parseInt(stockId), shares, childId);
      setMessage({ text: `Bought ${result.shares} shares of ${result.symbol} for ${result.total.toFixed(0)} coins!`, type: 'success' });
      await loadData();
    } catch (err: any) {
      setMessage({ text: err.message || 'Trade failed', type: 'error' });
    } finally {
      setTrading(false);
    }
  };

  const handleSell = async () => {
    if (!stockId || !childId) return;
    setTrading(true);
    setMessage(null);
    try {
      const result = await sellStock(parseInt(stockId), shares, childId);
      setMessage({ text: `Sold ${result.shares} shares of ${result.symbol} for ${result.total.toFixed(0)} coins!`, type: 'success' });
      await loadData();
    } catch (err: any) {
      setMessage({ text: err.message || 'Trade failed', type: 'error' });
    } finally {
      setTrading(false);
    }
  };

  if (loading || !detail) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-green-400 via-emerald-300 to-teal-200 flex items-center justify-center">
        <div className="text-2xl text-white animate-pulse">Loading...</div>
      </div>
    );
  }

  const { stock, history, story } = detail;
  const isUp = stock.change_pct >= 0;
  const totalCost = stock.current_price * shares;

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-400 via-emerald-300 to-teal-200 flex flex-col items-center p-4">
      {/* Back */}
      <div className="absolute top-4 left-4">
        <button
          onClick={() => navigate('/stockmarket')}
          className="text-white/80 hover:text-white bg-white/20 hover:bg-white/30 px-4 py-2 rounded-full transition"
        >
          &larr; Back
        </button>
      </div>

      {/* Stock header */}
      <div className="mt-12 mb-4 text-center">
        <div className="text-6xl mb-2">{stock.emoji}</div>
        <h1 className="text-3xl font-extrabold text-white drop-shadow-lg">{stock.name}</h1>
        <div className="text-white/70 text-sm">
          {stock.symbol} &middot; {stock.category}
          {stock.type === 'bond' && (
            <span className="ml-1.5 bg-blue-200/80 text-blue-800 px-2 py-0.5 rounded-full text-xs font-bold">BOND</span>
          )}
        </div>
      </div>

      {/* Price */}
      <div className="bg-white/90 rounded-2xl shadow-xl p-5 w-full max-w-md mb-4">
        <div className="flex items-baseline justify-between">
          <div className="text-4xl font-extrabold text-gray-800">
            {stock.current_price.toFixed(2)}
          </div>
          <div className={`text-xl font-bold ${isUp ? 'text-green-600' : 'text-red-500'}`}>
            {isUp ? '\u25B2' : '\u25BC'} {Math.abs(stock.change_pct).toFixed(1)}%
          </div>
        </div>
        <div className="text-xs text-gray-400 mt-1">coins per share</div>

        {/* Chart */}
        {history.length > 1 && (
          <div className="mt-3 -mx-2">
            <MiniChart history={history} />
          </div>
        )}
      </div>

      {/* Yield info */}
      {stock.dividend_yield > 0 && (
        <div className="bg-green-50 border-2 border-green-200 rounded-2xl p-4 w-full max-w-md mb-4">
          <div className="text-xs uppercase tracking-wide text-green-600 font-bold mb-1">
            {stock.type === 'bond' ? 'Coupon Rate' : 'Dividend Yield'}
          </div>
          <div className="text-2xl font-extrabold text-green-700">
            {(stock.dividend_yield * 100).toFixed(1)}% per year
          </div>
          <div className="text-sm text-gray-500 mt-1">
            Earns coins daily while you hold {stock.type === 'bond' ? 'bonds' : 'shares'}
          </div>
        </div>
      )}

      {/* News story */}
      {story && (
        <div className="bg-yellow-50 border-2 border-yellow-200 rounded-2xl p-4 w-full max-w-md mb-4">
          <div className="text-xs uppercase tracking-wide text-yellow-600 font-bold mb-1">
            Today's News
          </div>
          <div className="font-bold text-gray-800 text-lg leading-tight mb-2">
            {story.headline}
          </div>
          <p className="text-gray-600 leading-relaxed whitespace-pre-line">{story.body}</p>
        </div>
      )}

      {/* Trade panel */}
      <div className="bg-white/90 rounded-2xl shadow-xl p-5 w-full max-w-md mb-4">
        <div className="flex justify-between text-sm text-gray-500 mb-3">
          <span>You own: <strong className="text-gray-800">{myShares} shares</strong></span>
          <span>Coins: <strong className="text-yellow-600">{portfolio?.coins.toFixed(0)}</strong></span>
        </div>

        {/* Shares selector */}
        <div className="flex items-center justify-center gap-3 mb-3">
          <button
            onClick={() => setShares(Math.max(1, shares - 1))}
            className="w-10 h-10 rounded-full bg-gray-100 hover:bg-gray-200 font-bold text-xl transition"
          >
            -
          </button>
          <div className="text-center">
            <div className="text-3xl font-extrabold text-gray-800">{shares}</div>
            <div className="text-xs text-gray-400">shares</div>
          </div>
          <button
            onClick={() => setShares(Math.min(100, shares + 1))}
            className="w-10 h-10 rounded-full bg-gray-100 hover:bg-gray-200 font-bold text-xl transition"
          >
            +
          </button>
        </div>

        <div className="text-center text-sm text-gray-500 mb-4">
          Cost: <strong>{totalCost.toFixed(2)}</strong> coins
        </div>

        {/* Buy/Sell buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleBuy}
            disabled={trading || (portfolio?.coins || 0) < totalCost}
            className="flex-1 py-3 bg-green-500 hover:bg-green-600 text-white font-bold rounded-xl transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {trading ? '...' : 'Buy'}
          </button>
          <button
            onClick={handleSell}
            disabled={trading || myShares < shares}
            className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white font-bold rounded-xl transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {trading ? '...' : 'Sell'}
          </button>
        </div>

        {/* Feedback message */}
        {message && (
          <div className={`mt-3 text-center text-sm font-medium rounded-xl px-4 py-2 ${
            message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}>
            {message.text}
          </div>
        )}
      </div>

      {/* Description */}
      {stock.description && (
        <div className="bg-white/60 rounded-2xl p-4 w-full max-w-md text-center text-gray-600 text-sm">
          {stock.description}
        </div>
      )}
    </div>
  );
}
