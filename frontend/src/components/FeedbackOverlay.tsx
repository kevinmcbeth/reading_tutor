import ReactConfetti from 'react-confetti';

interface FeedbackOverlayProps {
  type: 'perfect' | 'good';
  visible: boolean;
  onDone?: () => void;
}

export default function FeedbackOverlay({ type, visible, onDone }: FeedbackOverlayProps) {
  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center bg-black/40 z-50"
      onClick={onDone}
    >
      {type === 'perfect' && (
        <ReactConfetti
          width={window.innerWidth}
          height={window.innerHeight}
          recycle={false}
          numberOfPieces={300}
        />
      )}
      <div className="bg-white rounded-3xl p-12 text-center shadow-2xl max-w-md mx-4">
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
          className="mt-6 px-8 py-3 bg-green-500 text-white rounded-full text-xl font-bold hover:bg-green-600 transition"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
