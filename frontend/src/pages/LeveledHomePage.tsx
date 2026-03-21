import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  fetchFPLevels,
  fetchFPProgress,
  startFPMode,
  FPLevelResponse,
  FPProgressResponse,
} from '../services/api';
import LevelTrail from '../components/LevelTrail';
import LevelBadge from '../components/LevelBadge';

const ALL_LEVEL_ORDER = [
  'A','B','C','D','E','F','G','H','I','J','K','L','M','N',
  'O','P','Q','R','S','T','U','V','W','X','Y','Z','Z1','Z2',
];

export default function LeveledHomePage() {
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const [levels, setLevels] = useState<FPLevelResponse[]>([]);
  const [progress, setProgress] = useState<FPProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasLevel, setHasLevel] = useState(false);
  const [selectedStartLevel, setSelectedStartLevel] = useState('A');
  const [starting, setStarting] = useState(false);

  const childId = selectedChild?.id || '';

  useEffect(() => {
    if (!childId) { navigate('/'); return; }

    Promise.all([
      fetchFPLevels(),
      fetchFPProgress(childId).catch(() => null),
    ]).then(([lvls, prog]) => {
      setLevels(lvls);
      if (prog) {
        setProgress(prog);
        setHasLevel(true);
      }
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, [childId, navigate]);

  const handleStartLeveled = async () => {
    if (!childId) return;
    setStarting(true);
    try {
      await startFPMode(childId, selectedStartLevel);
      // Refresh progress
      const prog = await fetchFPProgress(childId).catch(() => null);
      if (prog) {
        setProgress(prog);
        setHasLevel(true);
      } else {
        setHasLevel(true);
        setProgress({
          child_id: parseInt(childId),
          fp_level: selectedStartLevel,
          stories_at_level: 0,
          stories_passed: 0,
          average_accuracy: 0,
          suggest_advance: false,
          suggest_drop: false,
        });
      }
    } catch (err) {
      console.error('Failed to start leveled reading:', err);
    } finally {
      setStarting(false);
    }
  };

  // Determine completed levels from progress
  const completedLevels: string[] = [];
  if (progress) {
    const currentIdx = ALL_LEVEL_ORDER.indexOf(progress.fp_level);
    for (let i = 0; i < currentIdx; i++) {
      completedLevels.push(ALL_LEVEL_ORDER[i]);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-purple-400 via-purple-300 to-blue-200 flex items-center justify-center">
        <div className="text-2xl text-white animate-pulse">Loading...</div>
      </div>
    );
  }

  const currentLevel = progress?.fp_level || selectedStartLevel;

  return (
    <div className="min-h-screen bg-gradient-to-b from-purple-400 via-purple-300 to-blue-200 flex flex-col items-center p-6">
      {/* Back button */}
      <div className="absolute top-4 left-4">
        <button
          onClick={() => navigate('/')}
          className="text-white/80 hover:text-white bg-white/20 hover:bg-white/30 px-4 py-2 rounded-full transition"
        >
          &larr; Back
        </button>
      </div>

      <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-2 drop-shadow-lg mt-8">
        Leveled Reading
      </h1>
      <p className="text-xl text-white/90 mb-6 drop-shadow">
        {selectedChild?.name}'s Reading Journey
      </p>

      {!hasLevel ? (
        /* Onboarding — choose starting level */
        <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full">
          <h2 className="text-2xl font-bold text-gray-800 mb-4 text-center">
            Choose Your Starting Level
          </h2>
          <p className="text-gray-500 text-center mb-6">
            Pick a level to begin. You can always change it later.
          </p>

          <div className="grid grid-cols-7 gap-2 mb-6">
            {ALL_LEVEL_ORDER.map((lvl) => (
              <button
                key={lvl}
                onClick={() => setSelectedStartLevel(lvl)}
                className={`w-10 h-10 rounded-full text-xs font-bold transition-all ${
                  selectedStartLevel === lvl
                    ? 'bg-blue-500 text-white ring-4 ring-blue-300 scale-110'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          {levels.find(l => l.level === selectedStartLevel) && (
            <div className="bg-gray-50 rounded-xl p-3 mb-6 text-sm text-gray-600">
              <strong>Level {selectedStartLevel}</strong>: {levels.find(l => l.level === selectedStartLevel)?.description}
              <br />
              <span className="text-gray-400">
                Grade: {levels.find(l => l.level === selectedStartLevel)?.grade_range}
              </span>
            </div>
          )}

          <button
            onClick={handleStartLeveled}
            disabled={starting}
            className="w-full py-4 bg-purple-500 hover:bg-purple-600 text-white rounded-full text-xl font-bold transition disabled:opacity-50"
          >
            {starting ? 'Starting...' : "Let's Begin!"}
          </button>
        </div>
      ) : (
        /* Active leveled reading view */
        <>
          {/* Current level badge */}
          <div className="mb-6 flex flex-col items-center">
            <div className="relative">
              <LevelBadge level={currentLevel} state="current" size="lg" />
            </div>
            <p className="text-white/80 mt-2 text-lg font-medium">
              Level {currentLevel}
            </p>
          </div>

          {/* Progress indicator */}
          {progress && (
            <div className="bg-white/90 rounded-2xl shadow-xl p-5 max-w-sm w-full mb-6">
              <div className="text-center">
                <div className="text-3xl font-extrabold text-purple-600">
                  {progress.stories_passed} / 3
                </div>
                <div className="text-gray-500">
                  stories passed at Level {progress.fp_level}
                </div>
                {progress.stories_at_level > 0 && (
                  <div className="mt-2 text-sm text-gray-400">
                    Average accuracy: {Math.round(progress.average_accuracy * 100)}%
                  </div>
                )}
                {progress.suggest_advance && (
                  <div className="mt-3 bg-green-50 text-green-700 rounded-xl px-4 py-2 text-sm font-medium">
                    Ready to advance! Keep reading at this level to level up automatically.
                  </div>
                )}
                {progress.suggest_drop && (
                  <div className="mt-3 bg-orange-50 text-orange-700 rounded-xl px-4 py-2 text-sm font-medium">
                    This level might be too challenging. Ask a parent about adjusting.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Level trail */}
          <div className="bg-white/90 rounded-3xl shadow-xl p-4 max-w-sm w-full mb-6">
            <LevelTrail
              allLevels={ALL_LEVEL_ORDER}
              currentLevel={currentLevel}
              completedLevels={completedLevels}
            />
          </div>

          {/* Start reading button */}
          <button
            onClick={() => navigate(`/leveled/${currentLevel}`)}
            className="bg-white hover:bg-white/90 text-purple-600 font-extrabold text-2xl px-10 py-5 rounded-full shadow-xl hover:shadow-2xl transition-all hover:scale-105 active:scale-95"
          >
            Start Reading
          </button>
        </>
      )}
    </div>
  );
}
