interface ProgressBarProps {
  current: number;
  total: number;
}

export default function ProgressBar({ current, total }: ProgressBarProps) {
  const percent = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className="w-full">
      <div className="flex justify-between text-sm text-gray-500 mb-1">
        <span>Sentence {Math.min(current + 1, total)} of {total}</span>
        <span>{percent}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
        <div
          className="bg-gradient-to-r from-green-400 to-green-500 h-4 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
