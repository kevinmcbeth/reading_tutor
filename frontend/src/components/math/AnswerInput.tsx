import { useState, useCallback, useEffect } from 'react';
import MicButton from '../MicButton';

interface AnswerInputProps {
  onSubmit: (answer: string) => void;
  lastResult: { correct: boolean; correct_answer: string; child_answer: string } | null;
  disabled?: boolean;
  // Speech recognition props (optional — mic hidden if not provided)
  transcript?: string;
  isListening?: boolean;
  isProcessing?: boolean;
  onMicPress?: () => void;
}

const BUTTON_BASE = 'text-3xl font-bold rounded-2xl shadow transition-all duration-150 active:scale-95 select-none';

/** Extract the first number from a speech transcript. */
function extractNumber(text: string): string | null {
  // Try raw digits first
  const digitMatch = text.match(/\d+/);
  if (digitMatch) return digitMatch[0];
  return null;
}

export default function AnswerInput({
  onSubmit, lastResult, disabled,
  transcript, isListening, isProcessing, onMicPress,
}: AnswerInputProps) {
  const [value, setValue] = useState('');
  const hasMic = !!onMicPress;

  // When a transcript arrives from speech, fill the numpad value
  useEffect(() => {
    if (!transcript) return;
    const num = extractNumber(transcript);
    if (num) {
      setValue(num);
    }
  }, [transcript]);

  const handleDigit = useCallback((digit: string) => {
    if (disabled) return;
    setValue(prev => {
      if (prev.length >= 5) return prev;
      return prev + digit;
    });
  }, [disabled]);

  const handleBackspace = useCallback(() => {
    if (disabled) return;
    setValue(prev => prev.slice(0, -1));
  }, [disabled]);

  const handleSubmit = useCallback(() => {
    if (disabled || !value) return;
    onSubmit(value);
    setValue('');
  }, [disabled, value, onSubmit]);

  return (
    <div className="flex flex-col items-center gap-3 w-full max-w-xs mx-auto">
      {/* Answer display */}
      <div className="w-full bg-white rounded-2xl shadow-lg px-4 py-3 min-h-[3.5rem] flex items-center justify-center">
        {isProcessing ? (
          <span className="text-xl text-gray-400 animate-pulse">Listening...</span>
        ) : value ? (
          <span className="text-4xl font-bold text-gray-800 tracking-widest">{value}</span>
        ) : lastResult ? (
          <span className={`text-2xl font-bold ${lastResult.correct ? 'text-green-500' : 'text-red-500'}`}>
            {lastResult.correct ? 'Correct!' : `Answer: ${lastResult.correct_answer}`}
          </span>
        ) : (
          <span className="text-xl text-gray-300">Type your answer</span>
        )}
      </div>

      {/* Numpad */}
      <div className="grid grid-cols-3 gap-2 w-full">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(d => (
          <button
            key={d}
            onClick={() => handleDigit(d)}
            disabled={disabled}
            className={`${BUTTON_BASE} h-16 bg-white hover:bg-gray-50 text-gray-800 disabled:opacity-40`}
          >
            {d}
          </button>
        ))}
        <button
          onClick={handleBackspace}
          disabled={disabled || !value}
          className={`${BUTTON_BASE} h-16 bg-gray-100 hover:bg-gray-200 text-gray-500 text-2xl disabled:opacity-40`}
          aria-label="Backspace"
        >
          ←
        </button>
        <button
          onClick={() => handleDigit('0')}
          disabled={disabled}
          className={`${BUTTON_BASE} h-16 bg-white hover:bg-gray-50 text-gray-800 disabled:opacity-40`}
        >
          0
        </button>
        <button
          onClick={handleSubmit}
          disabled={disabled || !value}
          className={`${BUTTON_BASE} h-16 bg-green-500 hover:bg-green-600 text-white disabled:opacity-40`}
          aria-label="Submit answer"
        >
          ✓
        </button>
      </div>

      {/* Mic button — speak to fill the numpad */}
      {hasMic && (
        <div className="mt-2 flex flex-col items-center gap-1">
          <MicButton
            onPress={onMicPress!}
            isListening={!!isListening}
            disabled={disabled || isProcessing}
          />
          <span className="text-xs text-white/60">or say your answer</span>
        </div>
      )}
    </div>
  );
}
