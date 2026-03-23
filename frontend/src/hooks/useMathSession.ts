import { useState, useCallback, useRef } from 'react';
import {
  startMathSession,
  fetchMathProblem,
  submitMathAnswer,
  completeMathSession,
  MathSessionResponse,
  MathProblemResponse,
  MathAnswerResponse,
  MathSessionCompleteResponse,
} from '../services/api';

interface UseMathSessionReturn {
  session: MathSessionResponse | null;
  currentProblem: MathProblemResponse | null;
  problemNumber: number;
  totalProblems: number;
  correctCount: number;
  streak: number;
  lastResult: MathAnswerResponse | null;
  results: MathSessionCompleteResponse | null;
  isLoading: boolean;
  error: string | null;
  start: (childId: string, subject: string) => Promise<void>;
  nextProblem: () => Promise<void>;
  submitAnswer: (answer: string, transcript?: string, alternatives?: string[]) => Promise<MathAnswerResponse>;
  complete: () => Promise<MathSessionCompleteResponse>;
}

const TOTAL_PROBLEMS = 10;

export function useMathSession(): UseMathSessionReturn {
  const [session, setSession] = useState<MathSessionResponse | null>(null);
  const [currentProblem, setCurrentProblem] = useState<MathProblemResponse | null>(null);
  const [problemNumber, setProblemNumber] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [streak, setStreak] = useState(0);
  const [lastResult, setLastResult] = useState<MathAnswerResponse | null>(null);
  const [results, setResults] = useState<MathSessionCompleteResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef<number | null>(null);

  const start = useCallback(async (childId: string, subject: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const sess = await startMathSession(childId, subject);
      setSession(sess);
      sessionIdRef.current = sess.id;
      setProblemNumber(0);
      setCorrectCount(0);
      setStreak(0);
      setLastResult(null);
      setResults(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const nextProblem = useCallback(async () => {
    if (!sessionIdRef.current) return;
    setIsLoading(true);
    setError(null);
    setLastResult(null);
    try {
      const problem = await fetchMathProblem(sessionIdRef.current);
      setCurrentProblem(problem);
      setProblemNumber(prev => prev + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get problem');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const submitAnswerFn = useCallback(async (
    answer: string,
    transcript?: string,
    alternatives?: string[],
  ): Promise<MathAnswerResponse> => {
    if (!sessionIdRef.current) throw new Error('No active session');
    setIsLoading(true);
    setError(null);
    try {
      const result = await submitMathAnswer(sessionIdRef.current, answer, transcript, alternatives);
      setLastResult(result);
      if (result.correct) {
        setCorrectCount(prev => prev + 1);
        setStreak(prev => prev + 1);
      } else {
        setStreak(0);
      }
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit answer');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const completeFn = useCallback(async (): Promise<MathSessionCompleteResponse> => {
    if (!sessionIdRef.current) throw new Error('No active session');
    setIsLoading(true);
    setError(null);
    try {
      const res = await completeMathSession(sessionIdRef.current);
      setResults(res);
      return res;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete session');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    session,
    currentProblem,
    problemNumber,
    totalProblems: TOTAL_PROBLEMS,
    correctCount,
    streak,
    lastResult,
    results,
    isLoading,
    error,
    start,
    nextProblem,
    submitAnswer: submitAnswerFn,
    complete: completeFn,
  };
}
