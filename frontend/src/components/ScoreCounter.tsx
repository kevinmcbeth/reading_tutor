import { useEffect, useState } from 'react';

interface ScoreCounterProps {
  score: number;
}

export default function ScoreCounter({ score }: ScoreCounterProps) {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    if (score > 0) {
      setAnimate(true);
      const timer = setTimeout(() => setAnimate(false), 300);
      return () => clearTimeout(timer);
    }
  }, [score]);

  return (
    <div
      className={`
        inline-flex items-center gap-2 bg-yellow-100 text-yellow-700
        px-4 py-2 rounded-full font-bold text-xl shadow
        transition-transform duration-300
        ${animate ? 'scale-125' : 'scale-100'}
      `}
    >
      ⭐ {score}
    </div>
  );
}
