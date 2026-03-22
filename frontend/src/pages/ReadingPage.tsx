import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchStory, createSession, completeSession, StoryResponse, WordResult } from '../services/api';
import { getAccessToken } from '../services/auth';
import { useAuth } from '../context/AuthContext';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { compareWords } from '../utils/wordMatch';
import StoryDisplay from '../components/StoryDisplay';
import MicButton from '../components/MicButton';
import ProgressBar from '../components/ProgressBar';
import FeedbackOverlay from '../components/FeedbackOverlay';

interface BackendWord {
  id: number;
  idx: number;
  text: string;
  has_audio: boolean;
  is_challenge_word: boolean;
}

interface BackendSentence {
  id: number;
  idx: number;
  text: string;
  words: BackendWord[];
}

type WordState = 'pending' | 'correct' | 'partial' | 'missed';

interface WordScore {
  state: WordState;
  attempts: number;
}

function matchTranscriptToWords(transcript: string, words: BackendWord[]): Map<number, WordState> {
  const spokenWords = transcript.toLowerCase().split(/\s+/).filter(w => w.trim());
  const results = new Map<number, WordState>();

  // Try to match each target word against spoken words
  // Use a greedy left-to-right alignment
  let spokenIdx = 0;
  for (const word of words) {
    let matched = false;
    // Look ahead up to 3 positions for a match (allows skipped/extra words)
    for (let look = 0; look < 3 && spokenIdx + look < spokenWords.length; look++) {
      if (compareWords(spokenWords[spokenIdx + look], word.text)) {
        results.set(word.id, 'correct');
        spokenIdx = spokenIdx + look + 1;
        matched = true;
        break;
      }
    }
    if (!matched) {
      results.set(word.id, 'missed');
    }
  }

  return results;
}

export default function ReadingPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const { selectedChild } = useAuth();

  const [story, setStory] = useState<StoryResponse | null>(null);
  const [sentences, setSentences] = useState<BackendSentence[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Word scoring across all sentences
  const [wordScores, setWordScores] = useState<Map<number, WordScore>>(new Map());
  const [completedSentences, setCompletedSentences] = useState<Set<number>>(new Set());
  const [totalWords, setTotalWords] = useState(0);

  // Completion overlay
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackType, setFeedbackType] = useState<'perfect' | 'good'>('good');
  const [completing, setCompleting] = useState(false);
  const [completionError, setCompletionError] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(false);

  const speech = useSpeechRecognition();
  const childId = selectedChild?.id;

  // Load story
  useEffect(() => {
    if (!storyId) return;
    setLoading(true);
    fetchStory(storyId)
      .then((s) => {
        setStory(s);
        const sents = (s.sentences || []) as BackendSentence[];
        setSentences(sents);
        const total = sents.reduce((sum, sent) => sum + sent.words.length, 0);
        setTotalWords(total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [storyId]);

  // Create session
  useEffect(() => {
    if (childId && storyId && !sessionId && sentences.length > 0) {
      createSession(childId, storyId)
        .then((s) => setSessionId(s.id))
        .catch(console.error);
    }
  }, [storyId, sentences, sessionId, childId]);

  const currentSentence = sentences[currentIdx];
  const isLastSlide = currentIdx >= sentences.length - 1;
  const isFirstSlide = currentIdx === 0;
  const sentenceComplete = completedSentences.has(currentIdx);

  // Compute score
  const correctWords = Array.from(wordScores.values()).filter(s => s.state === 'correct').length;
  const partialWords = Array.from(wordScores.values()).filter(s => s.state === 'partial').length;
  const displayScore = correctWords + Math.floor(partialWords * 0.5);

  const playSentenceAudio = () => {
    if (!storyId || !currentSentence) return;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    const token = getAccessToken();
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    const audio = new Audio(`/api/assets/audio/sentence/${storyId}/${currentSentence.idx}${qs}`);
    audioRef.current = audio;
    setIsPlaying(true);
    audio.onended = () => setIsPlaying(false);
    audio.onerror = () => setIsPlaying(false);
    audio.play().catch(() => setIsPlaying(false));
  };

  const playWordHint = (wordId: number) => {
    if (!storyId) return;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    const token = getAccessToken();
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    const audio = new Audio(`/api/assets/audio/word/${storyId}/${wordId}${qs}`);
    audioRef.current = audio;
    setIsPlaying(true);
    audio.onended = () => setIsPlaying(false);
    audio.onerror = () => setIsPlaying(false);
    audio.play().catch(() => setIsPlaying(false));
  };

  // Handle speech result — match entire sentence
  useEffect(() => {
    if (!speech.transcript || speech.isListening || speech.isProcessing) return;
    if (!currentSentence || sentenceComplete) return;

    const transcript = speech.alternatives.length > 0
      ? speech.alternatives.join(' ')
      : speech.transcript;

    const matches = matchTranscriptToWords(transcript, currentSentence.words);
    const newScores = new Map(wordScores);

    matches.forEach((state, wordId) => {
      const prev = newScores.get(wordId);
      const attempts = (prev?.attempts || 0) + 1;

      if (state === 'correct') {
        // Always upgrade to correct
        newScores.set(wordId, { state: 'correct', attempts });
      } else if (prev?.state === 'correct') {
        // Don't downgrade a correct word
      } else if (attempts >= 2) {
        // After 2 attempts, give partial credit for missed words
        newScores.set(wordId, { state: 'partial', attempts });
      } else {
        newScores.set(wordId, { state: 'missed', attempts });
      }
    });

    setWordScores(newScores);

    // Check if all words are resolved (correct or partial)
    const allResolved = currentSentence.words.every(w => {
      const s = newScores.get(w.id);
      return s && (s.state === 'correct' || s.state === 'partial');
    });

    if (allResolved) {
      setCompletedSentences(prev => new Set(prev).add(currentIdx));
    }
  }, [speech.transcript, speech.isListening, speech.isProcessing]);

  const handleMicPress = useCallback(() => {
    if (speech.isListening) {
      speech.stopListening();
    } else {
      speech.startListening();
    }
  }, [speech]);

  const submitCompletion = useCallback((sid: string, results: WordResult[]) => {
    setCompleting(true);
    setCompletionError(false);
    completeSession(sid, results)
      .then(() => {
        setSessionComplete(true);
        setCompleting(false);
      })
      .catch(err => {
        console.error('Session complete failed:', err);
        setCompletionError(true);
        setCompleting(false);
      });
  }, []);

  const pendingResultsRef = useRef<WordResult[] | null>(null);

  const handleNext = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
    }
    if (isLastSlide) {
      if (sessionId) {
        const results: WordResult[] = [];
        wordScores.forEach((ws, wordId) => {
          results.push({
            word_id: wordId,
            attempts: ws.attempts,
            correct: ws.state === 'correct',
          });
        });
        pendingResultsRef.current = results;
        const isPerfect = correctWords === totalWords && totalWords > 0;
        setFeedbackType(isPerfect ? 'perfect' : 'good');
        setShowFeedback(true);
        submitCompletion(sessionId, results);
      } else {
        navigate('/library');
      }
    } else {
      setCurrentIdx(prev => prev + 1);
    }
  };

  const handlePrev = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
    }
    if (!isFirstSlide) {
      setCurrentIdx(prev => prev - 1);
    }
  };

  const handleRetry = () => {
    if (sessionId && pendingResultsRef.current) {
      submitCompletion(sessionId, pendingResultsRef.current);
    }
  };

  const handleFeedbackDone = () => {
    // Don't navigate while completion is in-flight
    if (completing) return;

    // If completion failed, don't dismiss — user can retry or skip
    if (completionError) return;

    setShowFeedback(false);
    if (sessionId && sessionComplete && story?.fp_level) {
      // Levelled reader: go to results page for level-up screen
      navigate(`/results/${sessionId}`);
    } else if (story?.fp_level) {
      // Session still completing for levelled reader — go to level map
      navigate('/leveled');
    } else {
      // Free reading: go straight to library
      navigate('/library');
    }
  };

  const handleSkipAndExit = () => {
    // Allow user to leave even if save failed (session stays orphaned but
    // can be cleaned up via the delete-incomplete endpoint)
    setShowFeedback(false);
    navigate('/library');
  };

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-yellow-50 flex items-center justify-center">
        <div className="text-3xl text-gray-500 animate-pulse">Loading story...</div>
      </div>
    );
  }

  if (!story || sentences.length === 0) {
    return (
      <div className="min-h-screen bg-yellow-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">😕</div>
          <p className="text-2xl text-gray-600">Story not found</p>
          <button
            onClick={() => navigate('/library')}
            className="mt-4 px-6 py-2 bg-blue-500 text-white rounded-full text-lg"
          >
            Back to Library
          </button>
        </div>
      </div>
    );
  }

  const imgToken = getAccessToken();
  const imgQs = imgToken ? `?token=${encodeURIComponent(imgToken)}` : '';
  const imagePath = `/api/assets/image/${storyId}/${currentIdx}${imgQs}`;

  return (
    <div className="h-screen flex flex-col bg-yellow-50 overflow-hidden">
      {/* Header + Progress Bar */}
      <div className="p-3 bg-white shadow-sm">
        <h1 className="text-xl font-bold text-gray-800 text-center mb-2">{story.title}</h1>
        <ProgressBar current={currentIdx} total={sentences.length} />
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        <StoryDisplay imagePath={imagePath}>
          {/* Sentence text with word highlighting */}
          <div className="flex flex-wrap justify-center gap-2 mb-6 px-4">
            {currentSentence?.words.map((word) => {
              const ws = wordScores.get(word.id);

              let className = 'text-3xl md:text-4xl font-bold transition-all ';
              if (ws?.state === 'correct') {
                className += 'text-green-500';
              } else if (ws?.state === 'partial') {
                className += 'text-yellow-500';
              } else if (ws?.state === 'missed') {
                className += 'text-red-400';
              } else {
                className += 'text-gray-800';
              }

              return (
                <span
                  key={word.id}
                  className={className}
                  onClick={() => ws?.state === 'missed' && playWordHint(word.id)}
                  style={{ cursor: ws?.state === 'missed' ? 'pointer' : 'default' }}
                >
                  {word.text}
                </span>
              );
            })}
          </div>

          {/* Controls */}
          <div className="flex items-center justify-center gap-6">
            {/* Play sentence button */}
            <button
              onClick={playSentenceAudio}
              disabled={isPlaying}
              className={`w-16 h-16 rounded-full flex items-center justify-center text-2xl shadow-lg transition-all active:scale-95 ${
                isPlaying
                  ? 'bg-gray-300 text-gray-500'
                  : 'bg-green-500 hover:bg-green-600 text-white'
              }`}
              title="Listen to sentence"
            >
              {isPlaying ? '...' : '▶'}
            </button>

            {/* Mic button — read the whole sentence */}
            {!sentenceComplete && (
              <MicButton
                onPress={handleMicPress}
                isListening={speech.isListening}
                disabled={speech.isProcessing}
              />
            )}

            {/* Sentence complete indicator */}
            {sentenceComplete && (
              <div className="text-4xl">✅</div>
            )}
          </div>

          {/* Speech feedback */}
          {speech.isProcessing && (
            <p className="text-center text-gray-400 mt-3 animate-pulse">Listening...</p>
          )}
          {speech.transcript && !speech.isListening && !speech.isProcessing && !sentenceComplete && (
            <p className="text-center text-gray-500 mt-3 text-sm">
              Heard: "{speech.transcript}"
              {currentSentence && (() => {
                const missed = currentSentence.words.filter(w => {
                  const s = wordScores.get(w.id);
                  return s?.state === 'missed';
                });
                if (missed.length > 0) {
                  return <span className="text-red-400 ml-2">— tap red words to hear them</span>;
                }
                return null;
              })()}
            </p>
          )}
        </StoryDisplay>
      </div>

      {/* Bottom bar */}
      <div className="p-4 bg-white shadow-inner flex justify-between items-center">
        <button
          onClick={() => navigate(story?.fp_level ? '/leveled' : '/library')}
          className="text-gray-400 hover:text-gray-600 px-4 py-2 rounded-full transition"
        >
          &larr; Quit
        </button>

        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">
            {currentIdx + 1} / {sentences.length}
          </span>
          {totalWords > 0 && (
            <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm font-bold">
              {displayScore} / {totalWords}
            </span>
          )}
        </div>

        <div className="flex gap-2">
          {!isFirstSlide && (
            <button
              onClick={handlePrev}
              className="px-6 py-3 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-full font-bold text-lg transition active:scale-95"
            >
              &larr; Back
            </button>
          )}
          <button
            onClick={handleNext}
            className="px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-full font-bold text-lg transition active:scale-95"
          >
            {isLastSlide ? 'Done' : 'Next →'}
          </button>
        </div>
      </div>

      {/* Feedback overlay */}
      <FeedbackOverlay
        type={feedbackType}
        visible={showFeedback}
        onDone={handleFeedbackDone}
        completing={completing}
        completionError={completionError}
        onRetry={handleRetry}
        onSkip={handleSkipAndExit}
      />

      {/* Speech error notice */}
      {speech.error && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 bg-red-100 text-red-700 px-4 py-2 rounded-full text-sm">
          {speech.error}
        </div>
      )}
    </div>
  );
}
