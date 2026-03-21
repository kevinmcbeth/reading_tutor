import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchChildSessions, fetchFPProgress, fetchStory, SessionResponse, FPProgressResponse } from '../services/api';
import { useAuth } from '../context/AuthContext';
import ReactConfetti from 'react-confetti';

export default function SessionResultPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fpProgress, setFpProgress] = useState<FPProgressResponse | null>(null);
  const [storyFpLevel, setStoryFpLevel] = useState<string | null>(null);

  const childId = selectedChild?.id || '';

  useEffect(() => {
    if (!childId) {
      navigate('/');
      return;
    }
    fetchChildSessions(childId)
      .then(async (sessions) => {
        const found = sessions.find(s => s.id === sessionId);
        setSession(found || null);

        // Check if this was an F&P story
        if (found) {
          try {
            const story = await fetchStory(found.story_id);
            if (story.fp_level) {
              setStoryFpLevel(story.fp_level);
              const prog = await fetchFPProgress(childId).catch(() => null);
              setFpProgress(prog);
            }
          } catch {
            // Not critical, ignore
          }
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [childId, sessionId, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-green-50 flex items-center justify-center">
        <div className="text-2xl text-gray-500 animate-pulse">Loading results...</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="min-h-screen bg-green-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-2xl text-gray-600">Session not found</p>
          <button
            onClick={() => navigate('/library')}
            className="mt-4 px-6 py-2 bg-blue-500 text-white rounded-full"
          >
            Back to Library
          </button>
        </div>
      </div>
    );
  }

  const totalWords = session.total_words || 0;
  const correctWords = session.score || 0;
  const isPerfect = correctWords === totalWords && totalWords > 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-100 to-blue-50 flex flex-col items-center justify-center p-6">
      {isPerfect && (
        <ReactConfetti
          width={window.innerWidth}
          height={window.innerHeight}
          recycle={false}
          numberOfPieces={400}
        />
      )}

      <div className="bg-white rounded-3xl shadow-2xl p-10 max-w-lg w-full text-center">
        <div className="text-6xl mb-4">{isPerfect ? '🎉' : '⭐'}</div>
        <h1 className="text-4xl font-extrabold text-gray-800 mb-2">
          {isPerfect ? 'Amazing!' : 'Great Job!'}
        </h1>

        {/* Score Display */}
        <div className="my-8">
          <div className="text-7xl font-black text-green-500">
            {correctWords}
          </div>
          <div className="text-2xl text-gray-500">
            out of {totalWords} words
          </div>
        </div>

        {/* F&P Level Progress */}
        {storyFpLevel && fpProgress && (
          <div className="my-6 bg-purple-50 rounded-2xl p-4">
            <div className="text-sm text-purple-600 font-medium mb-1">
              Level {fpProgress.fp_level} Progress
            </div>
            <div className="flex items-center gap-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className={`flex-1 h-3 rounded-full ${
                    i < fpProgress.stories_passed
                      ? 'bg-purple-500'
                      : 'bg-purple-200'
                  }`}
                />
              ))}
            </div>
            <div className="text-xs text-purple-400 mt-1">
              {fpProgress.stories_passed} of 3 stories passed
            </div>
            {fpProgress.suggest_advance && (
              <div className="mt-2 text-sm font-bold text-green-600">
                Level up! You're advancing to the next level!
              </div>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={() => navigate(`/read/${session.story_id}`)}
            className="w-full py-4 bg-blue-500 hover:bg-blue-600 text-white rounded-full text-xl font-bold transition"
          >
            Try Again
          </button>
          {storyFpLevel ? (
            <button
              onClick={() => navigate('/leveled')}
              className="w-full py-4 bg-purple-100 hover:bg-purple-200 text-purple-600 rounded-full text-xl font-bold transition"
            >
              Back to Level Map
            </button>
          ) : (
            <button
              onClick={() => navigate('/library')}
              className="w-full py-4 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full text-xl font-bold transition"
            >
              Back to Library
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
