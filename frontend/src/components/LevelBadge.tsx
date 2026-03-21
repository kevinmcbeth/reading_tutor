interface LevelBadgeProps {
  level: string;
  state?: 'completed' | 'current' | 'locked';
  size?: 'sm' | 'md' | 'lg';
  onClick?: () => void;
}

const sizeClasses = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-12 h-12 text-base',
  lg: 'w-16 h-16 text-xl',
};

export default function LevelBadge({ level, state = 'locked', size = 'md', onClick }: LevelBadgeProps) {
  const sizeClass = sizeClasses[size];

  let colorClass = '';
  let extra = '';

  if (state === 'completed') {
    colorClass = 'bg-gradient-to-br from-yellow-300 to-yellow-500 text-white shadow-lg ring-2 ring-yellow-400';
  } else if (state === 'current') {
    colorClass = 'bg-gradient-to-br from-blue-400 to-blue-600 text-white shadow-xl ring-4 ring-blue-300';
    extra = 'animate-pulse';
  } else {
    colorClass = 'bg-gray-200 text-gray-400';
  }

  const Component = onClick ? 'button' : 'div';

  return (
    <Component
      onClick={onClick}
      className={`${sizeClass} ${colorClass} ${extra} rounded-full flex items-center justify-center font-extrabold transition-all ${
        onClick ? 'cursor-pointer hover:scale-110 active:scale-95' : ''
      }`}
    >
      {level}
      {state === 'completed' && (
        <span className="absolute -top-1 -right-1 text-xs">
          &#9733;
        </span>
      )}
    </Component>
  );
}
