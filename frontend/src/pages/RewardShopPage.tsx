import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  fetchRewardItems,
  fetchBalance,
  redeemItem,
  convertWordsToCoins,
  fetchRedemptionHistory,
  RewardItemResponse,
  BalanceResponse,
  RedemptionResponse,
} from '../services/api';

export default function RewardShopPage() {
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const [items, setItems] = useState<RewardItemResponse[]>([]);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [history, setHistory] = useState<RedemptionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [redeeming, setRedeeming] = useState<number | null>(null);
  const [showSuccess, setShowSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [showConvert, setShowConvert] = useState(false);
  const [convertAmount, setConvertAmount] = useState('');
  const [converting, setConverting] = useState(false);

  const childId = selectedChild?.id;

  const loadData = useCallback(async () => {
    if (!childId) return;
    try {
      const [itemsData, balanceData, historyData] = await Promise.all([
        fetchRewardItems(),
        fetchBalance(childId),
        fetchRedemptionHistory(childId),
      ]);
      setItems(itemsData);
      setBalance(balanceData);
      setHistory(historyData);
    } catch (err) {
      console.error('Failed to load reward shop:', err);
    } finally {
      setLoading(false);
    }
  }, [childId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRedeem = async (item: RewardItemResponse) => {
    if (!childId || redeeming) return;
    setError(null);
    setRedeeming(item.id);
    try {
      const result = await redeemItem(item.id, childId);
      setShowSuccess(`${item.emoji} ${result.item_name}`);
      setTimeout(() => setShowSuccess(null), 3000);
      await loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Redemption failed';
      setError(message);
      setTimeout(() => setError(null), 4000);
    } finally {
      setRedeeming(null);
    }
  };

  const handleConvert = async () => {
    if (!childId || converting) return;
    const coins = parseInt(convertAmount);
    if (isNaN(coins) || coins < 1) return;
    setConverting(true);
    setError(null);
    try {
      await convertWordsToCoins(childId, coins);
      setShowConvert(false);
      setConvertAmount('');
      await loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Conversion failed';
      setError(message);
      setTimeout(() => setError(null), 4000);
    } finally {
      setConverting(false);
    }
  };

  const canAfford = (cost: number) => balance ? balance.coins_balance >= cost : false;
  const maxCoinsConvertible = balance ? Math.floor(balance.words_available / balance.words_per_coin) : 0;

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-amber-400 via-orange-300 to-yellow-200 flex items-center justify-center">
        <div className="text-3xl text-white animate-pulse">Loading shop...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-amber-400 via-orange-300 to-yellow-200 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/')}
            className="text-white/80 hover:text-white text-lg transition"
          >
            &larr; Back
          </button>
          <h1 className="text-4xl font-extrabold text-white drop-shadow-lg">
            Reward Shop
          </h1>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="text-sm bg-white/30 hover:bg-white/50 text-white px-4 py-2 rounded-full transition"
          >
            {showHistory ? 'Shop' : 'History'}
          </button>
        </div>

        {/* Balance Cards */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          {/* Words Balance */}
          <div className="bg-white/90 rounded-3xl p-5 shadow-xl text-center">
            <div className="text-sm text-gray-500 mb-1">Words to Convert</div>
            <div className="text-4xl font-extrabold text-green-600 mb-1">
              {balance?.words_available ?? 0}
            </div>
            <div className="text-xs text-gray-400">
              {selectedChild?.total_words_read ?? 0} total read
            </div>
            <button
              onClick={() => setShowConvert(true)}
              disabled={maxCoinsConvertible < 1}
              className={`text-sm px-4 py-1.5 rounded-full font-medium transition mt-1 ${
                maxCoinsConvertible >= 1
                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              Convert to coins
            </button>
          </div>

          {/* Coins Balance */}
          <div className="bg-white/90 rounded-3xl p-5 shadow-xl text-center">
            <div className="text-sm text-gray-500 mb-1">Coins</div>
            <div className="text-4xl font-extrabold text-amber-600 mb-1">
              <span className="text-3xl">🪙</span> {balance?.coins_balance ?? 0}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              {balance?.words_per_coin ?? 10} words = 1 coin
            </div>
          </div>
        </div>

        {/* Error / Success Messages */}
        {error && (
          <div className="bg-red-100 text-red-700 rounded-2xl p-4 mb-6 text-center font-medium">
            {error}
          </div>
        )}

        {showSuccess && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-3xl p-10 shadow-2xl text-center animate-bounce">
              <div className="text-8xl mb-4">{showSuccess.split(' ')[0]}</div>
              <div className="text-3xl font-bold text-gray-800 mb-2">Redeemed!</div>
              <div className="text-xl text-gray-500">{showSuccess.slice(showSuccess.indexOf(' ') + 1)}</div>
            </div>
          </div>
        )}

        {/* Convert Modal */}
        {showConvert && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-3xl p-8 max-w-sm w-full shadow-2xl text-center">
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Convert Words to Coins</h2>
              <p className="text-gray-500 mb-1">
                {balance?.words_per_coin} words = 1 🪙
              </p>
              <p className="text-sm text-gray-400 mb-6">
                You have {balance?.words_available} words (up to {maxCoinsConvertible} coins)
              </p>

              <input
                type="number"
                value={convertAmount}
                onChange={e => setConvertAmount(e.target.value)}
                placeholder="How many coins?"
                min="1"
                max={maxCoinsConvertible}
                className="w-full text-2xl p-4 border-2 border-gray-200 rounded-2xl mb-2 text-center focus:border-amber-400 focus:outline-none"
                autoFocus
              />
              {convertAmount && parseInt(convertAmount) > 0 && (
                <p className="text-sm text-gray-500 mb-4">
                  Costs {parseInt(convertAmount) * (balance?.words_per_coin ?? 10)} words
                </p>
              )}

              <div className="flex gap-3 mt-4">
                <button
                  onClick={() => { setShowConvert(false); setConvertAmount(''); }}
                  className="flex-1 py-3 text-gray-500 bg-gray-100 rounded-full hover:bg-gray-200 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={() => { setConvertAmount(String(maxCoinsConvertible)); }}
                  className="py-3 px-4 text-green-700 bg-green-100 rounded-full hover:bg-green-200 transition font-medium"
                >
                  Max
                </button>
                <button
                  onClick={handleConvert}
                  disabled={!convertAmount || parseInt(convertAmount) < 1 || parseInt(convertAmount) > maxCoinsConvertible || converting}
                  className="flex-1 py-3 text-white bg-amber-500 rounded-full hover:bg-amber-600 transition font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {converting ? 'Converting...' : 'Convert!'}
                </button>
              </div>
            </div>
          </div>
        )}

        {showHistory ? (
          /* Redemption History */
          <div>
            <h2 className="text-2xl font-bold text-white mb-4 drop-shadow">Redemption History</h2>
            {history.length === 0 ? (
              <div className="bg-white/80 rounded-3xl p-8 text-center text-gray-500 text-lg">
                No redemptions yet. Start reading to earn coins!
              </div>
            ) : (
              <div className="space-y-3">
                {history.map((r) => (
                  <div key={r.id} className="bg-white/90 rounded-2xl p-4 shadow flex items-center gap-4">
                    <span className="text-4xl">{r.item_emoji}</span>
                    <div className="flex-1">
                      <div className="font-bold text-gray-800">{r.item_name}</div>
                      <div className="text-sm text-gray-400">
                        {r.redeemed_at ? new Date(r.redeemed_at).toLocaleDateString() : ''}
                      </div>
                    </div>
                    <div className="text-lg font-bold text-amber-600">-{r.cost} 🪙</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Shop Items Grid */
          <div>
            {items.length === 0 ? (
              <div className="bg-white/80 rounded-3xl p-8 text-center text-gray-500 text-lg">
                No rewards available yet. Ask a parent to add some!
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {items.map((item) => {
                  const affordable = canAfford(item.cost);
                  const isRedeeming = redeeming === item.id;
                  return (
                    <div
                      key={item.id}
                      className={`bg-white/90 rounded-3xl p-6 shadow-xl flex flex-col items-center text-center transition-all ${
                        affordable ? 'hover:shadow-2xl hover:scale-105' : 'opacity-60'
                      }`}
                    >
                      <span className="text-6xl mb-3">{item.emoji}</span>
                      <h3 className="text-xl font-bold text-gray-800 mb-1">{item.name}</h3>
                      {item.description && (
                        <p className="text-sm text-gray-500 mb-3">{item.description}</p>
                      )}
                      <div className="text-2xl font-extrabold text-amber-600 mb-4">
                        {item.cost} 🪙
                      </div>
                      <button
                        onClick={() => handleRedeem(item)}
                        disabled={!affordable || isRedeeming}
                        className={`w-full py-3 rounded-full font-bold text-lg transition ${
                          affordable
                            ? 'bg-gradient-to-r from-amber-400 to-orange-400 text-white hover:from-amber-500 hover:to-orange-500 active:scale-95'
                            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                        }`}
                      >
                        {isRedeeming ? 'Redeeming...' : affordable ? 'Redeem!' : 'Not enough'}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
