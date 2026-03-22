import { getAccessToken } from '../services/auth';

interface StoryCardProps {
  storyId: string;
  title: string;
  difficulty: string;
  theme: string;
  onClick: () => void;
}

const difficultyColors: Record<string, string> = {
  easy: 'bg-green-100 text-green-700 border-green-300',
  medium: 'bg-yellow-100 text-yellow-700 border-yellow-300',
  hard: 'bg-red-100 text-red-700 border-red-300',
};

export default function StoryCard({ storyId, title, difficulty, theme, onClick }: StoryCardProps) {
  const colorClass = difficultyColors[difficulty] || 'bg-gray-100 text-gray-700 border-gray-300';
  const token = getAccessToken();
  const qs = token ? `?token=${encodeURIComponent(token)}` : '';

  return (
    <div
      onClick={onClick}
      className="bg-white border-2 border-gray-100 rounded-2xl overflow-hidden shadow-md hover:shadow-xl cursor-pointer transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
    >
      {/* Thumbnail */}
      <div className="h-36 bg-gradient-to-br from-purple-200 via-pink-100 to-yellow-100 flex items-center justify-center">
        <img
          src={`/api/assets/image/${storyId}/0${qs}`}
          alt={title}
          className="max-h-full max-w-full object-contain"
          onError={(e) => {
            const img = e.target as HTMLImageElement;
            img.style.display = 'none';
          }}
        />
      </div>
      <div className="p-4">
        <h3 className="text-xl font-bold text-gray-800 mb-2 truncate">{title}</h3>
        <div className="flex gap-2 flex-wrap">
          <span className={`text-sm px-3 py-1 rounded-full border font-medium ${colorClass}`}>
            {difficulty}
          </span>
          {theme && (
            <span className="text-sm px-3 py-1 rounded-full border border-purple-200 bg-purple-50 text-purple-600 font-medium">
              {theme}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
