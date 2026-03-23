import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  fetchRewardItems,
  fetchBalance,
  redeemItem,
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

  const canAfford = (cost: number) => balance ? balance.balance >= cost : false;

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-amber-400 via-orange-300 to-yellow-200 flex items-center justify-center">
        <div className="text-3xl text-white animate-pulse">Loading shop...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-amber-400 via-orange-300 to-yellow-200 p-6">
      {/* Header */}
      <div className="max-w-4xl mx-auto">
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

        {/* Balance Card */}
        <div className="bg-white/90 rounded-3xl p-6 shadow-xl mb-8 text-center">
          <div className="text-lg text-gray-500 mb-1">
            {selectedChild?.name}'s Word Balance
          </div>
          <div className="text-6xl font-extrabold text-amber-600 mb-2">
            {balance?.balance ?? 0}
          </div>
          <div className="text-sm text-gray-400">
            {balance?.total_earned ?? 0} earned &middot; {balance?.total_spent ?? 0} spent
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

        {showHistory ? (
          /* Redemption History */
          <div>
            <h2 className="text-2xl font-bold text-white mb-4 drop-shadow">Redemption History</h2>
            {history.length === 0 ? (
              <div className="bg-white/80 rounded-3xl p-8 text-center text-gray-500 text-lg">
                No redemptions yet. Start reading to earn words!
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
                    <div className="text-lg font-bold text-amber-600">-{r.cost} words</div>
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
                        {item.cost} words
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
