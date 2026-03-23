import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchRewardItems,
  createRewardItem,
  updateRewardItem,
  deleteRewardItem,
  fetchChildren,
  fetchBalance,
  fetchRedemptionHistory,
  RewardItemResponse,
  ChildResponse,
  BalanceResponse,
  RedemptionResponse,
} from '../services/api';

const EMOJI_OPTIONS = ['🎁', '🍦', '🎮', '📱', '🎬', '🧸', '⚽', '🎨', '📚', '🍕', '🎪', '🏊', '🎵', '🧁', '🌟', '🎯'];

export default function RewardManagementPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<RewardItemResponse[]>([]);
  const [children, setChildren] = useState<ChildResponse[]>([]);
  const [balances, setBalances] = useState<Record<string, BalanceResponse>>({});
  const [childHistory, setChildHistory] = useState<Record<string, RedemptionResponse[]>>({});
  const [loading, setLoading] = useState(true);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formCost, setFormCost] = useState('');
  const [formEmoji, setFormEmoji] = useState('🎁');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [expandedChild, setExpandedChild] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchRewardItems(false), fetchChildren()])
      .then(async ([itemsData, childrenData]) => {
        setItems(itemsData);
        setChildren(childrenData);
        // Fetch balances for all children
        const balanceMap: Record<string, BalanceResponse> = {};
        await Promise.all(
          childrenData.map(async (c) => {
            try {
              balanceMap[c.id] = await fetchBalance(c.id);
            } catch { /* child may have no sessions */ }
          })
        );
        setBalances(balanceMap);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const loadHistory = async (childId: string) => {
    if (childHistory[childId]) return;
    try {
      const hist = await fetchRedemptionHistory(childId);
      setChildHistory(prev => ({ ...prev, [childId]: hist }));
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  const resetForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormName('');
    setFormDescription('');
    setFormCost('');
    setFormEmoji('🎁');
    setFormError(null);
  };

  const handleEdit = (item: RewardItemResponse) => {
    setEditingId(item.id);
    setFormName(item.name);
    setFormDescription(item.description || '');
    setFormCost(String(item.cost));
    setFormEmoji(item.emoji);
    setShowForm(true);
  };

  const handleSave = async () => {
    const cost = parseInt(formCost);
    if (!formName.trim() || isNaN(cost) || cost < 1) return;
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        const updated = await updateRewardItem(editingId, formName.trim(), cost, formEmoji, formDescription.trim() || undefined);
        setItems(prev => prev.map(i => i.id === editingId ? updated : i));
      } else {
        const created = await createRewardItem(formName.trim(), cost, formEmoji, formDescription.trim() || undefined);
        setItems(prev => [...prev, created]);
      }
      resetForm();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save reward';
      setFormError(message);
      console.error('Failed to save reward:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteRewardItem(id);
      setItems(prev => prev.map(i => i.id === id ? { ...i, active: false } : i));
    } catch (err) {
      console.error('Failed to deactivate reward:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-xl text-gray-400 animate-pulse">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={() => navigate('/parent/dashboard')}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            &larr; Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-800">Reward Management</h1>
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="bg-amber-500 hover:bg-amber-600 text-white px-5 py-2 rounded-full font-medium transition"
          >
            + Add Reward
          </button>
        </div>

        {/* Reward Items */}
        <div className="mb-10">
          <h2 className="text-xl font-bold text-gray-700 mb-4">Reward Items</h2>
          {items.length === 0 ? (
            <div className="bg-white rounded-2xl p-8 text-center text-gray-400 shadow">
              No rewards created yet. Add one to get started!
            </div>
          ) : (
            <div className="space-y-3">
              {items.map(item => (
                <div
                  key={item.id}
                  className={`bg-white rounded-2xl p-4 shadow flex items-center gap-4 ${!item.active ? 'opacity-50' : ''}`}
                >
                  <span className="text-4xl">{item.emoji}</span>
                  <div className="flex-1">
                    <div className="font-bold text-gray-800">
                      {item.name}
                      {!item.active && <span className="text-xs text-red-400 ml-2">(inactive)</span>}
                    </div>
                    {item.description && (
                      <div className="text-sm text-gray-500">{item.description}</div>
                    )}
                  </div>
                  <div className="text-xl font-bold text-amber-600">{item.cost} words</div>
                  {item.active && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(item)}
                        className="text-sm text-blue-500 hover:text-blue-700 transition"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="text-sm text-red-400 hover:text-red-600 transition"
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Child Balances */}
        <div>
          <h2 className="text-xl font-bold text-gray-700 mb-4">Child Balances</h2>
          <div className="space-y-3">
            {children.map(child => {
              const bal = balances[child.id];
              const isExpanded = expandedChild === child.id;
              return (
                <div key={child.id} className="bg-white rounded-2xl shadow overflow-hidden">
                  <button
                    onClick={() => {
                      setExpandedChild(isExpanded ? null : child.id);
                      if (!isExpanded) loadHistory(child.id);
                    }}
                    className="w-full p-4 flex items-center gap-4 hover:bg-gray-50 transition text-left"
                  >
                    <span className="text-3xl">{child.avatar || '😊'}</span>
                    <div className="flex-1">
                      <div className="font-bold text-gray-800">{child.name}</div>
                      <div className="text-sm text-gray-400">
                        {child.total_words_read} words earned
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-amber-600">
                        {bal ? bal.balance : child.total_words_read}
                      </div>
                      <div className="text-xs text-gray-400">available</div>
                    </div>
                  </button>
                  {isExpanded && (
                    <div className="px-4 pb-4 border-t">
                      {bal && (
                        <div className="flex gap-6 text-sm text-gray-500 py-3">
                          <span>Earned: {bal.total_earned}</span>
                          <span>Spent: {bal.total_spent}</span>
                        </div>
                      )}
                      <h4 className="text-sm font-medium text-gray-600 mb-2">Recent Redemptions</h4>
                      {(childHistory[child.id] || []).length === 0 ? (
                        <div className="text-sm text-gray-400">No redemptions yet</div>
                      ) : (
                        <div className="space-y-2">
                          {(childHistory[child.id] || []).slice(0, 10).map(r => (
                            <div key={r.id} className="flex items-center gap-3 text-sm">
                              <span className="text-xl">{r.item_emoji}</span>
                              <span className="flex-1 text-gray-700">{r.item_name}</span>
                              <span className="text-amber-600 font-medium">-{r.cost}</span>
                              <span className="text-gray-400">
                                {r.redeemed_at ? new Date(r.redeemed_at).toLocaleDateString() : ''}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Add/Edit Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">
              {editingId ? 'Edit Reward' : 'New Reward'}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                  placeholder="e.g., Ice cream trip"
                  className="w-full p-3 border-2 border-gray-200 rounded-xl focus:border-amber-400 focus:outline-none"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Description (optional)</label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={e => setFormDescription(e.target.value)}
                  placeholder="e.g., A trip to the ice cream shop"
                  className="w-full p-3 border-2 border-gray-200 rounded-xl focus:border-amber-400 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Cost (words)</label>
                <input
                  type="number"
                  value={formCost}
                  onChange={e => setFormCost(e.target.value)}
                  placeholder="e.g., 100"
                  min="1"
                  className="w-full p-3 border-2 border-gray-200 rounded-xl focus:border-amber-400 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-2">Icon</label>
                <div className="grid grid-cols-8 gap-2">
                  {EMOJI_OPTIONS.map(e => (
                    <button
                      key={e}
                      onClick={() => setFormEmoji(e)}
                      className={`text-2xl p-2 rounded-lg transition ${
                        formEmoji === e ? 'bg-amber-100 ring-2 ring-amber-400 scale-110' : 'hover:bg-gray-100'
                      }`}
                    >
                      {e}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {formError && (
              <div className="mt-4 bg-red-100 text-red-700 rounded-xl p-3 text-sm text-center">
                {formError}
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button
                onClick={resetForm}
                className="flex-1 py-3 text-gray-500 bg-gray-100 rounded-full hover:bg-gray-200 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!formName.trim() || !formCost || parseInt(formCost) < 1 || saving}
                className="flex-1 py-3 text-white bg-amber-500 rounded-full hover:bg-amber-600 transition font-bold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
