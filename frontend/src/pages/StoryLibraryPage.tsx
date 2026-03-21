import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchStories, StoryResponse } from '../services/api';
import { useAuth } from '../context/AuthContext';
import StoryCard from '../components/StoryCard';

const DIFFICULTY_TABS = ['all', 'easy', 'medium', 'hard'] as const;

export default function StoryLibraryPage() {
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const [stories, setStories] = useState<StoryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('all');

  const childName = selectedChild?.name || 'Reader';
  const childAvatar = selectedChild?.avatar || '😊';

  useEffect(() => {
    fetchStories()
      .then(setStories)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = activeTab === 'all'
    ? stories
    : stories.filter(s => s.difficulty === activeTab);

  const tabColors: Record<string, string> = {
    all: 'bg-blue-500 text-white',
    easy: 'bg-green-500 text-white',
    medium: 'bg-yellow-500 text-white',
    hard: 'bg-red-500 text-white',
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-purple-100 to-pink-50 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <button
          onClick={() => navigate('/')}
          className="text-lg bg-white/80 hover:bg-white px-4 py-2 rounded-full shadow transition"
        >
          &larr; Back
        </button>
        <div className="flex items-center gap-3">
          <span className="text-3xl">{childAvatar}</span>
          <span className="text-2xl font-bold text-gray-700">{childName}</span>
        </div>
      </div>

      <h1 className="text-4xl font-extrabold text-gray-800 mb-6 text-center">
        Pick a Story!
      </h1>

      {/* Difficulty Tabs */}
      <div className="flex justify-center gap-3 mb-8">
        {DIFFICULTY_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-6 py-2 rounded-full font-bold text-lg transition-all capitalize ${
              activeTab === tab
                ? tabColors[tab]
                : 'bg-white text-gray-600 hover:bg-gray-100'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center text-2xl text-gray-500 animate-pulse py-20">
          Loading stories...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-6xl mb-4">📚</div>
          <p className="text-xl text-gray-500">No stories yet! Ask a parent to add some.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 max-w-6xl mx-auto">
          {filtered.map((story) => (
            <StoryCard
              key={story.id}
              storyId={story.id}
              title={story.title}
              difficulty={story.difficulty}
              theme={story.theme}
              onClick={() => navigate(`/read/${story.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
