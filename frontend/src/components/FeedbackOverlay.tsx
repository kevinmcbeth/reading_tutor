import ReactConfetti from 'react-confetti';

interface FeedbackOverlayProps {
  type: 'perfect' | 'good';
  visible: boolean;
  onDone?: () => void;
  completing?: boolean;
  completionError?: boolean;
  onRetry?: () => void;
  onSkip?: () => void;
}

export default function FeedbackOverlay({
  type,
  visible,
  onDone,
  completing,
  completionError,
  onRetry,
  onSkip,
}: FeedbackOverlayProps) {
  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center bg-black/40 z-50"
      onClick={completing ? undefined : onDone}
    >
      {type === 'perfect' && !completionError && (
        <ReactConfetti
          width={window.innerWidth}
          height={window.innerHeight}
          recycle={false}
          numberOfPieces={300}
        />
      )}
      <div className="bg-white rounded-3xl p-12 text-center shadow-2xl max-w-md mx-4">
        {completionError ? (
          <>
            <div className="text-6xl mb-4">😟</div>
            <h2 className="text-3xl font-bold mb-4">Couldn't save results</h2>
            <p className="text-lg text-gray-600 mb-6">
              Something went wrong saving your reading session. You can try again or exit.
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={onRetry}
                className="px-8 py-3 bg-blue-500 text-white rounded-full text-xl font-bold hover:bg-blue-600 transition"
              >
                Try Again
              </button>
              <button
                onClick={onSkip}
                className="px-8 py-3 bg-gray-300 text-gray-700 rounded-full text-xl font-bold hover:bg-gray-400 transition"
              >
                Exit
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="text-6xl mb-4">
              {type === 'perfect' ? '🎉' : '👏'}
            </div>
            <h2 className="text-4xl font-bold mb-4">
              {type === 'perfect' ? 'Amazing!' : 'Great Job!'}
            </h2>
            <p className="text-xl text-gray-600">
              {type === 'perfect'
                ? 'You got every word right!'
                : 'Keep up the good work!'}
            </p>
            <button
              onClick={onDone}
              disabled={completing}
              className={`mt-6 px-8 py-3 rounded-full text-xl font-bold transition ${
                completing
                  ? 'bg-gray-300 text-gray-500 cursor-wait'
                  : 'bg-green-500 text-white hover:bg-green-600'
              }`}
            >
              {completing ? 'Saving...' : 'Continue'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
