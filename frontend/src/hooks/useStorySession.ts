import { useState, useCallback, useMemo } from 'react'

export interface StoryWord {
  id: string;
  text: string;
  sentenceIdx: number;
  wordIdx: number;
  isChallenge: boolean;
}

export interface WordAttempt {
  wordId: string;
  attempts: number;
  correct: boolean;
  spoken: string;
}

export interface RetryConfig {
  mode: 'all' | 'missed';
  missedWordIds?: string[];
}

interface UseStorySessionReturn {
  currentSentenceIdx: number;
  currentWordIdx: number;
  score: number;
  wordResults: Map<string, WordAttempt>;
  isComplete: boolean;
  handleWordCorrect: (wordId: string, spoken: string) => void;
  handleWordFail: (wordId: string, spoken: string) => void;
  nextWord: () => void;
  getCurrentWord: () => StoryWord | null;
  isChallengeWord: (wordId: string) => boolean;
  totalChallengeWords: number;
  sentences: StoryWord[][];
}

export function useStorySession(
  words: StoryWord[],
  retryConfig?: RetryConfig
): UseStorySessionReturn {
  const [currentSentenceIdx, setCurrentSentenceIdx] = useState(0);
  const [currentWordIdx, setCurrentWordIdx] = useState(0);
  const [score, setScore] = useState(0);
  const [wordResults, setWordResults] = useState<Map<string, WordAttempt>>(new Map());
  const [isComplete, setIsComplete] = useState(false);

  // Group words into sentences
  const sentences = useMemo(() => {
    const grouped: StoryWord[][] = [];
    for (const word of words) {
      while (grouped.length <= word.sentenceIdx) {
        grouped.push([]);
      }
      // If retry mode is 'missed', only include missed words as challenges
      if (retryConfig?.mode === 'missed' && retryConfig.missedWordIds) {
        const isMissed = retryConfig.missedWordIds.includes(word.id);
        grouped[word.sentenceIdx].push({
          ...word,
          isChallenge: isMissed,
        });
      } else {
        grouped[word.sentenceIdx].push(word);
      }
    }
    return grouped;
  }, [words, retryConfig]);

  const totalChallengeWords = useMemo(() => {
    return words.filter(w => {
      if (retryConfig?.mode === 'missed' && retryConfig.missedWordIds) {
        return retryConfig.missedWordIds.includes(w.id);
      }
      return w.isChallenge;
    }).length;
  }, [words, retryConfig]);

  const getCurrentWord = useCallback((): StoryWord | null => {
    if (isComplete) return null;
    const sentence = sentences[currentSentenceIdx];
    if (!sentence || currentWordIdx >= sentence.length) return null;
    return sentence[currentWordIdx];
  }, [sentences, currentSentenceIdx, currentWordIdx, isComplete]);

  const isChallengeWord = useCallback((wordId: string): boolean => {
    const word = words.find(w => w.id === wordId);
    if (!word) return false;
    if (retryConfig?.mode === 'missed' && retryConfig.missedWordIds) {
      return retryConfig.missedWordIds.includes(wordId);
    }
    return word.isChallenge;
  }, [words, retryConfig]);

  const advanceToNext = useCallback(() => {
    const sentence = sentences[currentSentenceIdx];
    if (!sentence) {
      setIsComplete(true);
      return;
    }

    const nextIdx = currentWordIdx + 1;
    if (nextIdx >= sentence.length) {
      // Move to next sentence
      const nextSentence = currentSentenceIdx + 1;
      if (nextSentence >= sentences.length) {
        setIsComplete(true);
      } else {
        setCurrentSentenceIdx(nextSentence);
        setCurrentWordIdx(0);
      }
    } else {
      setCurrentWordIdx(nextIdx);
    }
  }, [sentences, currentSentenceIdx, currentWordIdx]);

  const handleWordCorrect = useCallback((wordId: string, spoken: string) => {
    setWordResults(prev => {
      const next = new Map(prev);
      const existing = next.get(wordId);
      next.set(wordId, {
        wordId,
        attempts: (existing?.attempts ?? 0) + 1,
        correct: true,
        spoken,
      });
      return next;
    });
    setScore(prev => prev + 1);
    advanceToNext();
  }, [advanceToNext]);

  const handleWordFail = useCallback((wordId: string, spoken: string) => {
    setWordResults(prev => {
      const next = new Map(prev);
      const existing = next.get(wordId);
      const attempts = (existing?.attempts ?? 0) + 1;
      if (attempts >= 3) {
        // 3 strikes - mark as failed and advance
        next.set(wordId, { wordId, attempts, correct: false, spoken });
        // Use setTimeout to avoid state update during render
        setTimeout(() => advanceToNext(), 0);
      } else {
        next.set(wordId, { wordId, attempts, correct: false, spoken });
      }
      return next;
    });
  }, [advanceToNext]);

  const nextWord = useCallback(() => {
    advanceToNext();
  }, [advanceToNext]);

  return {
    currentSentenceIdx,
    currentWordIdx,
    score,
    wordResults,
    isComplete,
    handleWordCorrect,
    handleWordFail,
    nextWord,
    getCurrentWord,
    isChallengeWord,
    totalChallengeWords,
    sentences,
  };
}
