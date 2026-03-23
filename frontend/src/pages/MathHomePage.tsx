import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchMathSubjects, fetchMathProgress, fetchMathBalance, convertMathToCoins, MathSubjectInfo, MathProgressEntry, MathBalanceResponse } from '../services/api';
import SubjectCard from '../components/math/SubjectCard';

export default function MathHomePage() {
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const [subjects, setSubjects] = useState<MathSubjectInfo[]>([]);
  const [progress, setProgress] = useState<MathProgressEntry[]>([]);
  const [balance, setBalance] = useState<MathBalanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [converting, setConverting] = useState(false);

  useEffect(() => {
    if (!selectedChild) return;
    Promise.all([
      fetchMathSubjects(),
      fetchMathProgress(String(selectedChild.id)),
      fetchMathBalance(String(selectedChild.id)),
    ])
      .then(([subs, prog, bal]) => {
        setSubjects(subs);
        setProgress(prog);
        setBalance(bal);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedChild]);

  const handleSelectSubject = (subject: string) => {
    navigate(`/math/${subject}`);
  };

  const handleConvert = async () => {
    if (!selectedChild || !balance || balance.coins_convertible < 1) return;
    setConverting(true);
    try {
      await convertMathToCoins(String(selectedChild.id), balance.coins_convertible);
      const bal = await fetchMathBalance(String(selectedChild.id));
      setBalance(bal);
    } catch (err) {
      console.error('Convert failed:', err);
    } finally {
      setConverting(false);
    }
  };

  const progressMap = new Map(progress.map(p => [p.subject, p]));

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-indigo-400 via-purple-300 to-pink-200 flex items-center justify-center">
        <div className="text-2xl text-white animate-pulse">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-400 via-purple-300 to-pink-200 p-6">
      {/* Header */}
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/')}
            className="text-white/80 hover:text-white text-lg transition"
          >
            &larr; Back
          </button>
          {selectedChild && (
            <div className="flex items-center gap-2 text-white">
              <span className="text-2xl">{selectedChild.avatar || '\uD83D\uDE0A'}</span>
              <span className="font-bold text-lg">{selectedChild.name}</span>
            </div>
          )}
        </div>

        <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-2 text-center drop-shadow-lg">
          Math Practice
        </h1>
        <p className="text-xl text-white/80 text-center mb-8">Choose a subject to practice!</p>

        {/* Math balance card */}
        {balance && balance.problems_available > 0 && (
          <div className="bg-white/90 rounded-2xl p-4 mb-8 flex items-center justify-between max-w-md mx-auto shadow-lg">
            <div>
              <div className="text-sm text-gray-500">Math problems solved</div>
              <div className="text-2xl font-bold text-purple-600">{balance.problems_available}</div>
              <div className="text-xs text-gray-400">{balance.math_problems_per_coin} problems = 1 coin</div>
            </div>
            {balance.coins_convertible > 0 && (
              <button
                onClick={handleConvert}
                disabled={converting}
                className="bg-gradient-to-r from-amber-400 to-orange-400 text-white font-bold px-4 py-2 rounded-full hover:shadow-lg transition disabled:opacity-50"
              >
                {converting ? '...' : `Get ${balance.coins_convertible} coin${balance.coins_convertible !== 1 ? 's' : ''}`}
              </button>
            )}
          </div>
        )}

        {/* Subject grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {subjects.map(subject => (
            <SubjectCard
              key={subject.subject}
              subject={subject}
              progress={progressMap.get(subject.subject)}
              onSelect={handleSelectSubject}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
