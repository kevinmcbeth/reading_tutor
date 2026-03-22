import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchFPStories, StoryResponse } from '../services/api';
import { getAccessToken } from '../services/auth';
import LevelBadge from '../components/LevelBadge';

export default function LeveledStoryListPage() {
  const { level } = useParams<{ level: string }>();
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const [stories, setStories] = useState<StoryResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!level) return;
    fetchFPStories(level)
      .then(setStories)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [level]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-purple-100 to-blue-50 flex items-center justify-center">
        <div className="text-2xl text-gray-500 animate-pulse">Loading stories...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-purple-100 to-blue-50 p-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button
            onClick={() => navigate('/leveled')}
            className="text-gray-500 hover:text-gray-700 bg-white px-4 py-2 rounded-full shadow transition"
          >
            &larr; Back
          </button>
          <div className="flex items-center gap-3 flex-1">
            <LevelBadge level={level || ''} state="current" size="md" />
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Level {level} Stories</h1>
              <p className="text-sm text-gray-500">{selectedChild?.name}'s reading list</p>
            </div>
          </div>
        </div>

        {/* Story list */}
        {stories.length === 0 ? (
          <div className="bg-white rounded-3xl shadow-xl p-10 text-center">
            <div className="text-5xl mb-4">📚</div>
            <h2 className="text-2xl font-bold text-gray-700 mb-2">No Stories Yet</h2>
            <p className="text-gray-500 mb-6">
              There are no Level {level} stories available yet. Ask a parent to generate some!
            </p>
            <button
              onClick={() => navigate('/leveled')}
              className="px-6 py-3 bg-purple-500 text-white rounded-full font-bold hover:bg-purple-600 transition"
            >
              Back to Level Map
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
            {stories.map((story) => {
              const token = getAccessToken();
              const qs = token ? `?token=${encodeURIComponent(token)}` : '';
              const coverUrl = `/api/assets/image/${story.id}/0${qs}`;
              return (
                <button
                  key={story.id}
                  onClick={() => navigate(`/read/${story.id}`)}
                  className="bg-white rounded-2xl shadow-lg overflow-hidden hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] transition-all text-left flex flex-col"
                >
                  <div className="relative w-full aspect-[4/3] bg-gradient-to-b from-sky-100 to-sky-50">
                    <img
                      src={coverUrl}
                      alt={story.title || 'Story cover'}
                      className="w-full h-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                    <div className="absolute top-2 right-2">
                      <LevelBadge level={level || ''} state="current" size="sm" />
                    </div>
                  </div>
                  <div className="p-3">
                    <h3 className="text-base font-bold text-gray-800 leading-tight">{story.title}</h3>
                    <p className="text-xs text-purple-500 font-semibold mt-1">Level {level}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
