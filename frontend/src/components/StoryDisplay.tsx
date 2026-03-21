import { ReactNode } from 'react';

interface StoryDisplayProps {
  imagePath?: string;
  children: ReactNode;
}

export default function StoryDisplay({ imagePath, children }: StoryDisplayProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Image area: 60% */}
      <div className="h-[60%] bg-gradient-to-b from-sky-100 to-sky-50 flex items-center justify-center overflow-hidden rounded-t-2xl">
        {imagePath ? (
          <img
            src={imagePath}
            alt="Story illustration"
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <div className="text-8xl opacity-30">📖</div>
        )}
      </div>
      {/* Text area: 40% */}
      <div className="h-[40%] flex flex-col items-center justify-center p-6 bg-white rounded-b-2xl">
        {children}
      </div>
    </div>
  );
}
