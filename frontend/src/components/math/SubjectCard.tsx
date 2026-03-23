import type { MathSubjectInfo, MathProgressEntry } from '../../services/api';

const GRADE_NAMES: Record<number, string> = { 0: 'K', 1: '1st', 2: '2nd', 3: '3rd', 4: '4th' };

const SUBJECT_COLORS: Record<string, string> = {
  addition: 'from-green-400 to-emerald-500',
  subtraction: 'from-blue-400 to-indigo-500',
  multiplication: 'from-purple-400 to-violet-500',
  division: 'from-orange-400 to-red-500',
  word_problems: 'from-pink-400 to-rose-500',
  counting: 'from-cyan-400 to-teal-500',
  comparison: 'from-amber-400 to-yellow-500',
  patterns: 'from-lime-400 to-green-500',
  place_value: 'from-sky-400 to-blue-500',
  time: 'from-indigo-400 to-purple-500',
  money: 'from-emerald-400 to-teal-500',
  measurement: 'from-rose-400 to-pink-500',
  fractions: 'from-violet-400 to-purple-500',
  geometry: 'from-teal-400 to-cyan-500',
};

function getStars(accuracy: number): string {
  if (accuracy >= 90) return '\u2b50\u2b50\u2b50';
  if (accuracy >= 75) return '\u2b50\u2b50';
  if (accuracy >= 60) return '\u2b50';
  return '';
}

interface SubjectCardProps {
  subject: MathSubjectInfo;
  progress?: MathProgressEntry;
  onSelect: (subject: string) => void;
}

export default function SubjectCard({ subject, progress, onSelect }: SubjectCardProps) {
  const gradient = SUBJECT_COLORS[subject.subject] || 'from-gray-400 to-gray-500';
  const gradeLevel = progress?.grade_level ?? subject.grades[0];
  const accuracy = progress?.accuracy ?? 0;
  const stars = progress ? getStars(accuracy) : '';
  const attempted = progress?.problems_attempted ?? 0;

  return (
    <button
      onClick={() => !subject.coming_soon && onSelect(subject.subject)}
      disabled={subject.coming_soon}
      className={`
        relative bg-gradient-to-br ${gradient} rounded-2xl p-5 text-white text-center
        shadow-lg transition-all duration-200
        ${subject.coming_soon
          ? 'opacity-50 cursor-not-allowed'
          : 'hover:shadow-xl hover:scale-105 active:scale-95'
        }
      `}
    >
      {subject.coming_soon && (
        <span className="absolute top-2 right-2 text-xs bg-white/30 px-2 py-0.5 rounded-full">
          Coming Soon
        </span>
      )}
      <div className="text-4xl mb-2 font-bold">{subject.emoji}</div>
      <div className="text-lg font-bold mb-1">{subject.display_name}</div>
      <div className="text-sm text-white/80 mb-2">{subject.description}</div>

      {!subject.coming_soon && (
        <div className="mt-2 space-y-1">
          <div className="text-sm font-semibold bg-white/20 rounded-full px-3 py-0.5 inline-block">
            Grade {GRADE_NAMES[gradeLevel] || gradeLevel}
          </div>
          {attempted > 0 && (
            <>
              <div className="text-sm">{accuracy}% accuracy</div>
              {stars && <div className="text-lg">{stars}</div>}
            </>
          )}
        </div>
      )}
    </button>
  );
}
