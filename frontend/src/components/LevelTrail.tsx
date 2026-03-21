import { useMemo } from 'react';

interface LevelTrailProps {
  allLevels: string[];
  currentLevel: string;
  completedLevels: string[];
  onSelectLevel?: (level: string) => void;
}

export default function LevelTrail({ allLevels, currentLevel, completedLevels, onSelectLevel }: LevelTrailProps) {
  const currentIdx = allLevels.indexOf(currentLevel);
  const completedSet = useMemo(() => new Set(completedLevels), [completedLevels]);

  // Show completed levels + current + 4 upcoming
  const visibleEnd = Math.min(currentIdx + 5, allLevels.length);
  const visibleStart = 0;
  const visibleLevels = allLevels.slice(visibleStart, visibleEnd);

  // SVG path generation — winding trail
  const nodeSpacingY = 80;
  const svgWidth = 320;
  const svgHeight = visibleLevels.length * nodeSpacingY + 40;

  const nodes = visibleLevels.map((level, i) => {
    // Alternate left-right for winding effect
    const x = i % 2 === 0 ? svgWidth * 0.35 : svgWidth * 0.65;
    const y = (visibleLevels.length - 1 - i) * nodeSpacingY + 40;
    const state = completedSet.has(level)
      ? 'completed'
      : level === currentLevel
      ? 'current'
      : 'locked';
    return { level, x, y, state };
  });

  // Build path between nodes
  const pathParts: string[] = [];
  for (let i = 0; i < nodes.length - 1; i++) {
    const from = nodes[i];
    const to = nodes[i + 1];
    if (i === 0) {
      pathParts.push(`M ${from.x} ${from.y}`);
    }
    const cpY = (from.y + to.y) / 2;
    pathParts.push(`Q ${from.x} ${cpY}, ${to.x} ${to.y}`);
  }

  return (
    <div className="overflow-y-auto max-h-[500px] flex justify-center" style={{ scrollbarWidth: 'thin' }}>
      <svg width={svgWidth} height={svgHeight} viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
        {/* Trail path */}
        {pathParts.length > 0 && (
          <path
            d={pathParts.join(' ')}
            fill="none"
            stroke="#d1d5db"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray="12 8"
          />
        )}

        {/* Completed trail overlay */}
        {(() => {
          const completedNodes = nodes.filter(n => n.state === 'completed');
          if (completedNodes.length < 2) return null;
          const parts: string[] = [];
          for (let i = 0; i < completedNodes.length - 1; i++) {
            const from = completedNodes[i];
            const to = completedNodes[i + 1];
            if (i === 0) parts.push(`M ${from.x} ${from.y}`);
            const cpY = (from.y + to.y) / 2;
            parts.push(`Q ${from.x} ${cpY}, ${to.x} ${to.y}`);
          }
          return (
            <path
              d={parts.join(' ')}
              fill="none"
              stroke="#fbbf24"
              strokeWidth="6"
              strokeLinecap="round"
            />
          );
        })()}

        {/* Level nodes */}
        {nodes.map((node) => {
          const isCompleted = node.state === 'completed';
          const isCurrent = node.state === 'current';
          const isLocked = node.state === 'locked';

          const radius = isCurrent ? 24 : 20;
          const fill = isCompleted
            ? 'url(#goldGrad)'
            : isCurrent
            ? 'url(#blueGrad)'
            : '#e5e7eb';
          const textFill = isLocked ? '#9ca3af' : '#ffffff';

          return (
            <g
              key={node.level}
              onClick={() => !isLocked && onSelectLevel?.(node.level)}
              className={!isLocked ? 'cursor-pointer' : ''}
            >
              {isCurrent && (
                <circle cx={node.x} cy={node.y} r={radius + 6} fill="none" stroke="#93c5fd" strokeWidth="3" opacity="0.6">
                  <animate attributeName="r" values={`${radius + 4};${radius + 8};${radius + 4}`} dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.6;0.2;0.6" dur="2s" repeatCount="indefinite" />
                </circle>
              )}
              <circle cx={node.x} cy={node.y} r={radius} fill={fill} />
              {isCompleted && (
                <text x={node.x + radius - 4} y={node.y - radius + 6} fontSize="12" fill="#fbbf24" textAnchor="middle">&#9733;</text>
              )}
              <text
                x={node.x}
                y={node.y + 1}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={isCurrent ? '16' : '14'}
                fontWeight="800"
                fill={textFill}
              >
                {node.level}
              </text>
            </g>
          );
        })}

        {/* Gradients */}
        <defs>
          <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#fcd34d" />
            <stop offset="100%" stopColor="#f59e0b" />
          </linearGradient>
          <linearGradient id="blueGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#60a5fa" />
            <stop offset="100%" stopColor="#2563eb" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}
