import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { useMathSession } from '../hooks/useMathSession';
import ProblemDisplay from '../components/math/ProblemDisplay';
import AnswerInput from '../components/math/AnswerInput';
import StreakCounter from '../components/math/StreakCounter';
import FeedbackOverlay from '../components/FeedbackOverlay';

const SUBJECT_NAMES: Record<string, string> = {
  addition: 'Addition',
  subtraction: 'Subtraction',
  multiplication: 'Multiplication',
  division: 'Division',
};

export default function MathPracticePage() {
  const { subject } = useParams<{ subject: string }>();
  const navigate = useNavigate();
  const { selectedChild } = useAuth();
  const speech = useSpeechRecognition();
  const math = useMathSession();

  const [phase, setPhase] = useState<'loading' | 'problem' | 'complete'>('loading');
  const [waitingForNext, setWaitingForNext] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [completionError, setCompletionError] = useState(false);
  const submittingRef = useRef(false);

  // Start session on mount
  useEffect(() => {
    if (!selectedChild || !subject) return;
    math.start(String(selectedChild.id), subject)
      .then(() => setPhase('problem'))
      .catch(() => setPhase('loading'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChild, subject]);

  // Fetch first problem once session is ready
  useEffect(() => {
    if (math.session && phase === 'problem' && !math.currentProblem && !math.isLoading) {
      math.nextProblem();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [math.session, phase]);

  const handleSubmitAnswer = useCallback((answer: string) => {
    if (submittingRef.current || waitingForNext) return;
    submittingRef.current = true;

    math.submitAnswer(answer).then(result => {
      setWaitingForNext(true);
      setTimeout(() => {
        setWaitingForNext(false);
        submittingRef.current = false;
        if (math.problemNumber >= math.totalProblems) {
          setPhase('complete');
        } else {
          math.nextProblem();
        }
      }, result.correct ? 800 : 2000);
    }).catch(() => {
      submittingRef.current = false;
    });
  }, [math, waitingForNext]);

  const handleMicPress = useCallback(() => {
    if (speech.isListening) {
      speech.stopListening();
    } else if (!waitingForNext) {
      speech.startListening();
    }
  }, [speech, waitingForNext]);

  const handleComplete = useCallback(async () => {
    setCompleting(true);
    setCompletionError(false);
    try {
      const results = await math.complete();
      navigate(`/math/results/${results.session_id}`, {
        state: results,
      });
    } catch {
      setCompletionError(true);
      setCompleting(false);
    }
  }, [math, navigate]);

  if (!selectedChild || !subject) {
    navigate('/math');
    return null;
  }

  if (phase === 'loading' && math.error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-indigo-400 via-purple-300 to-pink-200 flex items-center justify-center">
        <div className="bg-white rounded-3xl p-8 text-center shadow-2xl max-w-md">
          <div className="text-4xl mb-4">{'\uD83D\uDE1F'}</div>
          <h2 className="text-2xl font-bold mb-2">Couldn't start session</h2>
          <p className="text-gray-500 mb-4">{math.error}</p>
          <button
            onClick={() => navigate('/math')}
            className="bg-purple-500 text-white px-6 py-2 rounded-full font-bold hover:bg-purple-600 transition"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-400 via-purple-300 to-pink-200 flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between p-4">
        <button
          onClick={() => navigate('/math')}
          className="text-white/80 hover:text-white text-lg transition"
        >
          &larr; Quit
        </button>
        <div className="text-white font-bold text-lg">
          {SUBJECT_NAMES[subject] || subject}
        </div>
        <div className="text-white/80 text-sm">
          Grade {math.session?.grade_level === 0 ? 'K' : math.session?.grade_level}
        </div>
      </div>

      {/* Progress bar */}
      <div className="px-4 mb-4">
        <div className="bg-white/30 rounded-full h-3 overflow-hidden">
          <div
            className="bg-white h-full rounded-full transition-all duration-500"
            style={{ width: `${(math.problemNumber / math.totalProblems) * 100}%` }}
          />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 gap-6">
        {math.currentProblem && phase === 'problem' && (
          <>
            <StreakCounter
              streak={math.streak}
              correctCount={math.correctCount}
              totalAnswered={math.problemNumber - (math.lastResult ? 0 : 1)}
            />

            <div className="bg-white rounded-3xl p-8 md:p-12 shadow-2xl w-full max-w-lg">
              <ProblemDisplay
                display={math.currentProblem.display}
                problemNumber={math.problemNumber}
                totalProblems={math.totalProblems}
              />
            </div>

            <AnswerInput
              onSubmit={handleSubmitAnswer}
              lastResult={math.lastResult}
              disabled={waitingForNext}
              transcript={speech.transcript}
              isListening={speech.isListening}
              isProcessing={speech.isProcessing}
              onMicPress={handleMicPress}
            />
          </>
        )}

        {phase === 'loading' && !math.error && (
          <div className="text-2xl text-white animate-pulse">Loading...</div>
        )}
      </div>

      {/* Session complete overlay */}
      {phase === 'complete' && (
        <FeedbackOverlay
          type={math.correctCount === math.totalProblems ? 'perfect' : 'good'}
          visible={true}
          onDone={handleComplete}
          completing={completing}
          completionError={completionError}
          onRetry={handleComplete}
          onSkip={() => navigate('/math')}
        />
      )}
    </div>
  );
}
