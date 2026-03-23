interface StreakCounterProps {
  streak: number;
  correctCount: number;
  totalAnswered: number;
}

export default function StreakCounter({ streak, correctCount, totalAnswered }: StreakCounterProps) {
  return (
    <div className="flex items-center gap-6 text-lg">
      {streak > 1 && (
        <div className="bg-orange-100 text-orange-600 px-4 py-2 rounded-full font-bold flex items-center gap-1">
          <span className="text-xl">{'\uD83D\uDD25'}</span> {streak} streak
        </div>
      )}
      <div className="bg-green-100 text-green-600 px-4 py-2 rounded-full font-bold">
        {correctCount}/{totalAnswered} correct
      </div>
    </div>
  );
}
