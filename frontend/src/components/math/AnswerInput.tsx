import MicButton from '../MicButton';

interface AnswerInputProps {
  transcript: string;
  isListening: boolean;
  isProcessing: boolean;
  onMicPress: () => void;
  lastResult: { correct: boolean; correct_answer: string; child_answer: string } | null;
  disabled?: boolean;
}

export default function AnswerInput({
  transcript,
  isListening,
  isProcessing,
  onMicPress,
  lastResult,
  disabled,
}: AnswerInputProps) {
  return (
    <div className="flex flex-col items-center gap-4">
      {/* Transcript display */}
      <div className="min-h-[3rem] flex items-center justify-center">
        {isProcessing ? (
          <div className="text-xl text-gray-400 animate-pulse">Thinking...</div>
        ) : transcript ? (
          <div className="text-3xl font-bold text-gray-700">{transcript}</div>
        ) : lastResult ? (
          <div className={`text-3xl font-bold ${lastResult.correct ? 'text-green-500' : 'text-red-500'}`}>
            {lastResult.correct ? lastResult.child_answer : lastResult.correct_answer}
          </div>
        ) : (
          <div className="text-xl text-gray-300">Tap the mic and say your answer</div>
        )}
      </div>

      {/* Result feedback */}
      {lastResult && !isListening && !isProcessing && (
        <div className={`text-2xl font-bold ${lastResult.correct ? 'text-green-500' : 'text-red-500'}`}>
          {lastResult.correct ? 'Correct!' : `The answer was ${lastResult.correct_answer}`}
        </div>
      )}

      {/* Mic button */}
      <MicButton
        onPress={onMicPress}
        isListening={isListening}
        disabled={disabled || isProcessing}
      />

      {isListening && (
        <div className="text-lg text-red-500 animate-pulse font-medium">
          Listening... tap to stop
        </div>
      )}
    </div>
  );
}
