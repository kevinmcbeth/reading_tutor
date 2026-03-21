import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchChildren, createChild, fetchLeaderboard, ChildResponse, LeaderboardEntry } from '../services/api';
import { useAuth } from '../context/AuthContext';

const PRESET_AVATARS = ['🐱', '🐶', '🐰', '🦊', '🐻', '🦁', '🐸', '🐵', '🦄', '🐼'];

export default function ChildLoginPage() {
  const navigate = useNavigate();
  const { selectChild, logout, familyName } = useAuth();
  const [children, setChildren] = useState<ChildResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [selectedAvatar, setSelectedAvatar] = useState(PRESET_AVATARS[0]);
  const [creating, setCreating] = useState(false);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    Promise.all([fetchChildren(), fetchLeaderboard()])
      .then(([c, lb]) => { setChildren(c); setLeaderboard(lb); })
      .catch((err) => {
        console.error(err);
        if (err.message?.includes('Session expired') || err.message?.includes('log in')) {
          logout();
          navigate('/parent');
        }
      })
      .finally(() => setLoading(false));
  }, [logout, navigate]);

  const handleSelectChild = (child: ChildResponse) => {
    selectChild({ id: child.id, name: child.name, avatar: child.avatar || '' });
    navigate('/library');
  };

  const handleCreateChild = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const child = await createChild(newName.trim(), selectedAvatar);
      setChildren(prev => [...prev, child]);
      setShowModal(false);
      setNewName('');
      handleSelectChild(child);
    } catch (err) {
      console.error('Failed to create child:', err);
    } finally {
      setCreating(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/parent');
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-400 via-blue-300 to-cyan-200 flex flex-col items-center p-8">
      {/* Top bar */}
      <div className="absolute top-4 right-4 flex items-center gap-3">
        {familyName && (
          <span className="text-sm text-white/80">{familyName}</span>
        )}
        <button
          onClick={() => navigate('/parent/dashboard')}
          className="text-sm bg-white/30 hover:bg-white/50 text-white px-4 py-2 rounded-full transition"
        >
          Dashboard
        </button>
        <button
          onClick={handleLogout}
          className="text-sm bg-white/20 hover:bg-white/40 text-white px-3 py-2 rounded-full transition"
        >
          Logout
        </button>
      </div>

      <h1 className="text-5xl md:text-6xl font-extrabold text-white mb-2 drop-shadow-lg mt-8">
        Reading Tutor
      </h1>
      <p className="text-2xl text-white/90 mb-10 drop-shadow">Who is reading today?</p>

      {loading ? (
        <div className="text-2xl text-white animate-pulse">Loading...</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 max-w-4xl w-full mb-8">
          {children.map((child) => (
            <button
              key={child.id}
              onClick={() => handleSelectChild(child)}
              className="bg-white rounded-3xl p-6 shadow-xl hover:shadow-2xl hover:scale-105 active:scale-95 transition-all duration-200 flex flex-col items-center gap-3"
            >
              <span className="text-6xl">{child.avatar || '😊'}</span>
              <span className="text-2xl font-bold text-gray-700">{child.name}</span>
              {child.total_words_read > 0 && (
                <span className="text-sm text-green-600 font-medium bg-green-50 px-3 py-1 rounded-full">
                  {child.total_words_read} words read
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      <button
        onClick={() => setShowModal(true)}
        className="bg-white/90 hover:bg-white text-blue-600 font-bold text-xl px-8 py-4 rounded-full shadow-lg hover:shadow-xl transition-all hover:scale-105 active:scale-95 mb-8"
      >
        + Add New Reader
      </button>

      {/* Leaderboard */}
      {leaderboard.length > 0 && (
        <div className="bg-white/90 rounded-3xl p-6 shadow-xl max-w-md w-full">
          <h2 className="text-2xl font-extrabold text-gray-800 text-center mb-4">
            🏆 Leaderboard
          </h2>
          <div className="space-y-2">
            {leaderboard.map((entry, i) => {
              const medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i + 1}.`;
              return (
                <div
                  key={`${entry.name}-${i}`}
                  className={`flex items-center gap-3 p-3 rounded-xl ${
                    i === 0 ? 'bg-yellow-50' : i === 1 ? 'bg-gray-50' : i === 2 ? 'bg-orange-50' : ''
                  }`}
                >
                  <span className="text-2xl w-10 text-center">{medal}</span>
                  <span className="text-2xl">{entry.avatar || '😊'}</span>
                  <span className="text-lg font-bold text-gray-700 flex-1">{entry.name}</span>
                  <div className="text-right">
                    <div className="text-lg font-bold text-green-600">{entry.total_words}</div>
                    <div className="text-xs text-gray-400">words</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl">
            <h2 className="text-3xl font-bold text-gray-800 mb-6 text-center">New Reader</h2>

            <input
              type="text"
              placeholder="What's your name?"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full text-2xl p-4 border-2 border-gray-200 rounded-2xl mb-6 text-center focus:border-blue-400 focus:outline-none"
              autoFocus
            />

            <p className="text-lg text-gray-600 mb-3 text-center">Pick your avatar:</p>
            <div className="grid grid-cols-5 gap-3 mb-6">
              {PRESET_AVATARS.map((avatar) => (
                <button
                  key={avatar}
                  onClick={() => setSelectedAvatar(avatar)}
                  className={`text-4xl p-2 rounded-xl transition-all ${
                    selectedAvatar === avatar
                      ? 'bg-blue-100 ring-4 ring-blue-400 scale-110'
                      : 'hover:bg-gray-100'
                  }`}
                >
                  {avatar}
                </button>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => { setShowModal(false); setNewName(''); }}
                className="flex-1 py-3 text-lg text-gray-500 bg-gray-100 rounded-full hover:bg-gray-200 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateChild}
                disabled={!newName.trim() || creating}
                className="flex-1 py-3 text-lg text-white bg-blue-500 rounded-full hover:bg-blue-600 transition disabled:opacity-50 disabled:cursor-not-allowed font-bold"
              >
                {creating ? 'Creating...' : "Let's Go!"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
