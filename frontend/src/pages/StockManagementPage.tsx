import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchStocks,
  createStock,
  updateStock,
  deleteStock,
  StockInfoResponse,
} from '../services/api';

const EMOJI_OPTIONS = ['📊', '🦄', '🍌', '🦕', '🧪', '🤖', '🍕', '🌈', '🧦', '🏰', '🫧', '🚛', '🫘', '🐉', '🌋', '💨', '🧊', '🪄', '☁️', '💩', '🐱', '🎮', '🧸', '🎪', '🚀', '👽', '🎩', '🦑', '🍩', '🔮'];
const CATEGORY_OPTIONS = ['food', 'toys', 'pets', 'transport', 'space', 'fashion', 'services', 'construction', 'magical', 'weather', 'collectibles', 'awards', 'education', 'furniture', 'other'];

export default function StockManagementPage() {
  const navigate = useNavigate();
  const [stocks, setStocks] = useState<StockInfoResponse[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formSymbol, setFormSymbol] = useState('');
  const [formName, setFormName] = useState('');
  const [formEmoji, setFormEmoji] = useState('📊');
  const [formCategory, setFormCategory] = useState('other');
  const [formDescription, setFormDescription] = useState('');
  const [formPrice, setFormPrice] = useState('100');
  const [formVolatility, setFormVolatility] = useState('0.15');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  useEffect(() => {
    fetchStocks()
      .then(setStocks)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const resetForm = () => {
    setEditingId(null);
    setFormSymbol('');
    setFormName('');
    setFormEmoji('📊');
    setFormCategory('other');
    setFormDescription('');
    setFormPrice('100');
    setFormVolatility('0.15');
    setFormError(null);
  };

  const handleEdit = (stock: StockInfoResponse) => {
    setEditingId(stock.id);
    setFormSymbol(stock.symbol);
    setFormName(stock.name);
    setFormEmoji(stock.emoji);
    setFormCategory(stock.category);
    setFormDescription(stock.description || '');
    setFormPrice(String(stock.current_price));
    setFormVolatility('0.15');
    setFormError(null);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!formSymbol.trim() || !formName.trim()) {
      setFormError('Symbol and name are required');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const data = {
        symbol: formSymbol.trim().toUpperCase(),
        name: formName.trim(),
        emoji: formEmoji,
        category: formCategory,
        description: formDescription.trim() || undefined,
        base_price: parseFloat(formPrice) || 100,
        volatility: parseFloat(formVolatility) || 0.15,
      };

      if (editingId) {
        await updateStock(editingId, data);
      } else {
        await createStock(data);
      }

      const refreshed = await fetchStocks();
      setStocks(refreshed);
      setShowForm(false);
      resetForm();
    } catch (err: any) {
      setFormError(err.message || 'Failed to save stock');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (stockId: number) => {
    try {
      await deleteStock(stockId);
      setStocks(prev => prev.filter(s => s.id !== stockId));
      setDeleteConfirm(null);
    } catch (err: any) {
      alert(err.message || 'Failed to delete stock');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-xl text-gray-500 animate-pulse">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/parent/dashboard')}
            className="text-gray-500 hover:text-gray-700 px-4 py-2 rounded-full bg-white shadow transition"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-bold text-gray-800">Manage Stocks</h1>
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="px-4 py-2 bg-green-500 text-white rounded-full hover:bg-green-600 transition font-medium"
          >
            + Add Stock
          </button>
        </div>

        {/* Stock list */}
        <div className="space-y-2">
          {stocks.map((stock) => (
            <div key={stock.id} className="bg-white rounded-xl shadow p-4 flex items-center gap-3">
              <span className="text-3xl">{stock.emoji}</span>
              <div className="flex-1">
                <div className="font-bold text-gray-800">{stock.name}</div>
                <div className="text-xs text-gray-400">{stock.symbol} &middot; {stock.category} &middot; {stock.current_price.toFixed(2)} coins</div>
                {stock.description && (
                  <div className="text-xs text-gray-400 mt-0.5">{stock.description}</div>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleEdit(stock)}
                  className="px-3 py-1.5 text-sm bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition font-medium"
                >
                  Edit
                </button>
                {deleteConfirm === stock.id ? (
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleDelete(stock.id)}
                      className="px-3 py-1.5 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition font-medium"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeleteConfirm(stock.id)}
                    className="px-3 py-1.5 text-sm bg-red-50 text-red-500 rounded-lg hover:bg-red-100 transition font-medium"
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          ))}
          {stocks.length === 0 && (
            <div className="text-center py-10 text-gray-400">No stocks yet. Add one!</div>
          )}
        </div>

        {/* Form modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl">
              <h2 className="text-xl font-bold text-gray-800 mb-4">
                {editingId ? 'Edit Stock' : 'Add New Stock'}
              </h2>

              <div className="space-y-3">
                {/* Symbol */}
                <div>
                  <label className="text-sm font-medium text-gray-600">Symbol</label>
                  <input
                    type="text"
                    value={formSymbol}
                    onChange={(e) => setFormSymbol(e.target.value.toUpperCase().slice(0, 10))}
                    placeholder="e.g. UNIC"
                    className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:border-blue-400"
                    disabled={!!editingId}
                  />
                </div>

                {/* Name */}
                <div>
                  <label className="text-sm font-medium text-gray-600">Company Name</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. Unicorn Glitter Co."
                    className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:border-blue-400"
                  />
                </div>

                {/* Emoji */}
                <div>
                  <label className="text-sm font-medium text-gray-600">Emoji</label>
                  <div className="grid grid-cols-10 gap-1 mt-1">
                    {EMOJI_OPTIONS.map((e) => (
                      <button
                        key={e}
                        onClick={() => setFormEmoji(e)}
                        className={`text-xl p-1 rounded transition ${
                          formEmoji === e ? 'bg-blue-100 ring-2 ring-blue-400 scale-110' : 'hover:bg-gray-100'
                        }`}
                      >
                        {e}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Category */}
                <div>
                  <label className="text-sm font-medium text-gray-600">Category</label>
                  <select
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:border-blue-400"
                  >
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                {/* Description */}
                <div>
                  <label className="text-sm font-medium text-gray-600">Description</label>
                  <input
                    type="text"
                    value={formDescription}
                    onChange={(e) => setFormDescription(e.target.value)}
                    placeholder="What does this silly company do?"
                    className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:border-blue-400"
                  />
                </div>

                {/* Price & Volatility */}
                <div className="flex gap-3">
                  <div className="flex-1">
                    <label className="text-sm font-medium text-gray-600">Starting Price</label>
                    <input
                      type="number"
                      value={formPrice}
                      onChange={(e) => setFormPrice(e.target.value)}
                      min={1} max={10000} step={0.01}
                      className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:border-blue-400"
                      disabled={!!editingId}
                    />
                  </div>
                  <div className="flex-1">
                    <label className="text-sm font-medium text-gray-600">Volatility</label>
                    <input
                      type="number"
                      value={formVolatility}
                      onChange={(e) => setFormVolatility(e.target.value)}
                      min={0.01} max={1} step={0.01}
                      className="w-full border rounded-lg px-3 py-2 mt-1 focus:outline-none focus:border-blue-400"
                    />
                    <div className="text-xs text-gray-400 mt-0.5">Low: 0.10 | Med: 0.20 | Wild: 0.35</div>
                  </div>
                </div>

                {/* Error */}
                {formError && (
                  <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</div>
                )}

                {/* Buttons */}
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={() => { setShowForm(false); resetForm(); }}
                    className="flex-1 py-2 text-gray-500 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex-1 py-2 text-white bg-green-500 rounded-lg hover:bg-green-600 transition font-bold disabled:opacity-50"
                  >
                    {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
