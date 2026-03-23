interface ProblemDisplayProps {
  display: string;
  problemNumber: number;
  totalProblems: number;
}

export default function ProblemDisplay({ display, problemNumber, totalProblems }: ProblemDisplayProps) {
  return (
    <div className="text-center">
      <div className="text-sm text-gray-400 mb-4">
        Problem {problemNumber} of {totalProblems}
      </div>
      <div className="text-5xl md:text-7xl font-bold text-gray-800 tracking-wider">
        {display}
      </div>
    </div>
  );
}
