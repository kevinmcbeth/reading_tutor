import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchChildSessions, SessionResponse } from '../services/api';
import { useAuth } from '../context/AuthContext';
import ReactConfetti from 'react-confetti';

export default function SessionResultPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const childId = selectedChild?.id || '';

  useEffect(() => {
    if (!childId) {
      navigate('/');
      return;
    }
    fetchChildSessions(childId)
      .then((sessions) => {
        const found = sessions.find(s => s.id === sessionId);
        setSession(found || null);
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

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={() => navigate(`/read/${session.story_id}`)}
            className="w-full py-4 bg-blue-500 hover:bg-blue-600 text-white rounded-full text-xl font-bold transition"
          >
            Try Again
          </button>
          <button
            onClick={() => navigate('/library')}
            className="w-full py-4 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full text-xl font-bold transition"
          >
            Back to Library
          </button>
        </div>
      </div>
    </div>
  );
}
