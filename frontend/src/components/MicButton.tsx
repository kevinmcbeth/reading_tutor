interface MicButtonProps {
  onPress: () => void;
  isListening: boolean;
  disabled?: boolean;
}

export default function MicButton({ onPress, isListening, disabled }: MicButtonProps) {
  return (
    <button
      onClick={onPress}
      disabled={disabled}
      className={`
        rounded-full w-20 h-20 md:w-24 md:h-24 flex items-center justify-center
        text-4xl md:text-5xl shadow-lg transition-all duration-200
        ${disabled
          ? 'bg-gray-300 cursor-not-allowed opacity-50'
          : isListening
            ? 'bg-red-500 animate-pulse shadow-red-300 scale-110'
            : 'bg-blue-500 hover:bg-blue-600 hover:scale-105 active:scale-95 shadow-blue-300'
        }
      `}
      aria-label={isListening ? 'Listening...' : 'Press to speak'}
    >
      <span className="select-none">🎤</span>
    </button>
  );
}
