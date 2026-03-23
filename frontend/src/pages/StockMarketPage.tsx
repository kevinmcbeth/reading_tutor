import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  fetchStocks,
  fetchStockPortfolio,
  fetchStockNews,
  fetchBalance,
  depositStockCoins,
  StockInfoResponse,
  StockPortfolioResponse,
  StockNewsItemResponse,
  BalanceResponse,
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

export default function StockMarketPage() {
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const childId = selectedChild?.id || '';

  const [stocks, setStocks] = useState<StockInfoResponse[]>([]);
  const [portfolio, setPortfolio] = useState<StockPortfolioResponse | null>(null);
  const [news, setNews] = useState<StockNewsItemResponse[]>([]);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'market' | 'news' | 'portfolio'>('market');
  const [expandedNews, setExpandedNews] = useState<number | null>(null);
  const [depositAmount, setDepositAmount] = useState(10);
  const [depositing, setDepositing] = useState(false);
  const [depositMsg, setDepositMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const loadData = useCallback(async () => {
    if (!childId) return;
    try {
      const [s, p, n, b] = await Promise.all([
        fetchStocks(),
        fetchStockPortfolio(childId),
        fetchStockNews(childId),
        fetchBalance(childId).catch(() => null),
      ]);
      setStocks(s);
      setPortfolio(p);
      setNews(n);
      setBalance(b);
    } catch (err) {
      console.error('Failed to load stock data:', err);
    } finally {
      setLoading(false);
    }
  }, [childId]);

  const handleDeposit = async () => {
    if (!childId || depositAmount < 1) return;
    setDepositing(true);
    setDepositMsg(null);
    try {
      const result = await depositStockCoins(childId, depositAmount);
      setDepositMsg({
        text: `Deposited ${result.coins_deposited} coins! (${result.words_spent} words used)`,
        type: 'success',
      });
      await loadData();
    } catch (err: any) {
      setDepositMsg({ text: err.message || 'Deposit failed', type: 'error' });
    } finally {
      setDepositing(false);
    }
  };

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
        <div className="bg-white/90 rounded-2xl shadow-xl px-6 py-3 mb-4 flex gap-6 text-center">
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
        {tab === 'market' && (
          <div className="space-y-2">
            {stocks.map((stock) => (
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
              </button>
            ))}
          </div>
        )}

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
            {/* Deposit words → coins */}
            <div className="bg-yellow-50 border-2 border-yellow-200 rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">📖</span>
                <div className="font-bold text-gray-800">Add Coins from Reading</div>
              </div>
              {balance && (
                <div className="text-sm text-gray-500 mb-3">
                  You have <strong className="text-gray-800">{balance.words_available}</strong> words available
                  {balance.words_per_coin > 0 && (
                    <> ({balance.words_per_coin} words = 1 coin)</>
                  )}
                </div>
              )}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setDepositAmount(Math.max(1, depositAmount - 5))}
                  className="w-9 h-9 rounded-full bg-yellow-100 hover:bg-yellow-200 font-bold text-lg transition"
                >
                  -
                </button>
                <input
                  type="number"
                  min={1}
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-20 text-center text-xl font-extrabold border-2 border-yellow-200 rounded-xl py-1 focus:outline-none focus:border-yellow-400"
                />
                <button
                  onClick={() => setDepositAmount(depositAmount + 5)}
                  className="w-9 h-9 rounded-full bg-yellow-100 hover:bg-yellow-200 font-bold text-lg transition"
                >
                  +
                </button>
                <span className="text-sm text-gray-500">coins</span>
                <button
                  onClick={handleDeposit}
                  disabled={depositing}
                  className="ml-auto px-5 py-2 bg-yellow-500 hover:bg-yellow-600 text-white font-bold rounded-xl transition disabled:opacity-40"
                >
                  {depositing ? '...' : 'Deposit'}
                </button>
              </div>
              {depositMsg && (
                <div className={`mt-2 text-sm font-medium rounded-xl px-3 py-1.5 ${
                  depositMsg.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                }`}>
                  {depositMsg.text}
                </div>
              )}
            </div>

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
