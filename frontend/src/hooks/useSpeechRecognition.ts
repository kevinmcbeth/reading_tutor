import { useState, useCallback, useRef } from 'react';
import { getAccessToken } from '../services/auth';

interface UseSpeechRecognitionReturn {
  isListening: boolean;
  transcript: string;
  alternatives: string[];
  confidence: number;
  startListening: (targetWord?: string) => void;
  stopListening: () => void;
  isSupported: boolean;
  isProcessing: boolean;
  error: string | null;
}

export function useSpeechRecognition(): UseSpeechRecognitionReturn {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [alternatives, setAlternatives] = useState<string[]>([]);
  const [confidence, setConfidence] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const targetWordRef = useRef<string | undefined>(undefined);

  const isSupported = typeof navigator !== 'undefined' &&
    navigator.mediaDevices !== undefined &&
    typeof MediaRecorder !== 'undefined';

  const sendAudioToBackend = useCallback(async (audioBlob: Blob, targetWord?: string) => {
    setIsProcessing(true);
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      if (targetWord) {
        formData.append('target_word', targetWord);
      }

      const token = getAccessToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const response = await fetch('/api/speech/recognize', {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Speech recognition failed: ${response.statusText}`);
      }

      const data = await response.json();
      setTranscript(data.transcript || '');
      setAlternatives(data.alternatives || []);
      setConfidence(data.confidence || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Speech recognition failed');
      setTranscript('');
      setAlternatives([]);
      setConfidence(0);
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const startListening = useCallback((targetWord?: string) => {
    if (!isSupported) {
      setError('Audio recording is not supported in this browser.');
      return;
    }

    setError(null);
    setTranscript('');
    setAlternatives([]);
    setConfidence(0);
    chunksRef.current = [];
    targetWordRef.current = targetWord;

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        // Try to use a format Whisper handles well
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/webm')
            ? 'audio/webm'
            : 'audio/mp4';

        const mediaRecorder = new MediaRecorder(stream, { mimeType });
        mediaRecorderRef.current = mediaRecorder;

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            chunksRef.current.push(event.data);
          }
        };

        mediaRecorder.onstop = () => {
          // Stop all tracks to release the mic
          stream.getTracks().forEach(track => track.stop());

          const audioBlob = new Blob(chunksRef.current, { type: mimeType });
          if (audioBlob.size > 0) {
            sendAudioToBackend(audioBlob, targetWordRef.current);
          }
        };

        mediaRecorder.start();
        setIsListening(true);
      })
      .catch((err) => {
        setError(`Microphone access denied: ${err.message}`);
      });
  }, [isSupported, sendAudioToBackend]);

  const stopListening = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    }
    setIsListening(false);
  }, []);

  return {
    isListening,
    transcript,
    alternatives,
    confidence,
    startListening,
    stopListening,
    isSupported,
    isProcessing,
    error
  };
}
