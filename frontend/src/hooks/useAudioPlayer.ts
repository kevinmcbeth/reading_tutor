import { useState, useCallback, useRef } from 'react'

interface UseAudioPlayerReturn {
  play: (url: string) => Promise<void>;
  stop: () => void;
  isPlaying: boolean;
}

export function useAudioPlayer(): UseAudioPlayerReturn {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  const play = useCallback(async (url: string) => {
    // Stop any current playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    const audio = new Audio(url);
    audioRef.current = audio;
    setIsPlaying(true);

    return new Promise<void>((resolve, reject) => {
      audio.onended = () => {
        setIsPlaying(false);
        audioRef.current = null;
        resolve();
      };
      audio.onerror = () => {
        setIsPlaying(false);
        audioRef.current = null;
        reject(new Error('Audio playback failed'));
      };
      audio.play().catch((err) => {
        setIsPlaying(false);
        audioRef.current = null;
        reject(err);
      });
    });
  }, []);

  return { play, stop, isPlaying };
}
