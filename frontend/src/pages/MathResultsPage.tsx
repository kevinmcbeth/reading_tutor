import { useLocation, useNavigate } from 'react-router-dom';
import ReactConfetti from 'react-confetti';
import type { MathSessionCompleteResponse } from '../services/api';

const GRADE_NAMES: Record<number, string> = { 0: 'K', 1: '1st', 2: '2nd', 3: '3rd', 4: '4th' };

export default function MathResultsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const results = location.state as MathSessionCompleteResponse | undefined;

  if (!results) {
    navigate('/math');
    return null;
  }

  const { problems_attempted, problems_correct, accuracy, streak, best_streak, grade_level, advanced, perfect } = results;

  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-400 via-purple-300 to-pink-200 flex items-center justify-center p-4">
      {(perfect || advanced) && (
        <ReactConfetti
          width={window.innerWidth}
          height={window.innerHeight}
          recycle={false}
          numberOfPieces={300}
        />
      )}

      <div className="bg-white rounded-3xl p-8 md:p-12 shadow-2xl max-w-md w-full text-center">
        <div className="text-6xl mb-4">
          {perfect ? '\uD83C\uDF89' : accuracy >= 80 ? '\uD83C\uDF1F' : '\uD83D\uDCAA'}
        </div>

        <h1 className="text-3xl font-bold mb-2">
          {perfect ? 'Perfect Score!' : accuracy >= 80 ? 'Great Job!' : 'Keep Practicing!'}
        </h1>

        {advanced && (
          <div className="bg-gradient-to-r from-yellow-400 to-orange-400 text-white rounded-full px-4 py-2 inline-block mb-4 font-bold text-lg animate-bounce">
            Level Up! Now Grade {GRADE_NAMES[grade_level] || grade_level}
          </div>
        )}

        <div className="space-y-4 my-8">
          <div className="flex justify-between items-center bg-gray-50 rounded-xl p-4">
            <span className="text-gray-600">Score</span>
            <span className="text-2xl font-bold text-purple-600">
              {problems_correct}/{problems_attempted}
            </span>
          </div>

          <div className="flex justify-between items-center bg-gray-50 rounded-xl p-4">
            <span className="text-gray-600">Accuracy</span>
            <span className={`text-2xl font-bold ${accuracy >= 80 ? 'text-green-500' : accuracy >= 50 ? 'text-yellow-500' : 'text-red-500'}`}>
              {accuracy}%
            </span>
          </div>

          {best_streak > 1 && (
            <div className="flex justify-between items-center bg-gray-50 rounded-xl p-4">
              <span className="text-gray-600">Best Streak</span>
              <span className="text-2xl font-bold text-orange-500">
                {'\uD83D\uDD25'} {best_streak}
              </span>
            </div>
          )}

          <div className="flex justify-between items-center bg-gray-50 rounded-xl p-4">
            <span className="text-gray-600">Grade Level</span>
            <span className="text-2xl font-bold text-indigo-500">
              {GRADE_NAMES[grade_level] || grade_level}
            </span>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => navigate('/math')}
            className="flex-1 py-3 text-lg bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition font-bold"
          >
            Done
          </button>
          <button
            onClick={() => navigate(`/math/${results.subject}`, { replace: true })}
            className="flex-1 py-3 text-lg bg-purple-500 text-white rounded-full hover:bg-purple-600 transition font-bold"
          >
            Play Again
          </button>
        </div>
      </div>
    </div>
  );
}
