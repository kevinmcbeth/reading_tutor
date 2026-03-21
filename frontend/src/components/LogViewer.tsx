import { useEffect, useRef } from 'react';

interface LogEntry {
  level: string;
  message: string;
  timestamp: string;
}

interface LogViewerProps {
  logs: LogEntry[];
}

const levelColors: Record<string, string> = {
  INFO: 'text-blue-400',
  WARN: 'text-yellow-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  DEBUG: 'text-gray-500',
};

const levelBg: Record<string, string> = {
  INFO: 'bg-blue-900/30',
  WARN: 'bg-yellow-900/30',
  WARNING: 'bg-yellow-900/30',
  ERROR: 'bg-red-900/30',
  DEBUG: 'bg-gray-900/30',
};

export default function LogViewer({ logs }: LogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div
      ref={scrollRef}
      className="bg-gray-900 text-gray-100 rounded-lg p-4 font-mono text-sm max-h-[500px] overflow-y-auto"
    >
      {logs.length === 0 ? (
        <p className="text-gray-500">No logs available.</p>
      ) : (
        logs.map((log, i) => {
          const level = log.level.toUpperCase();
          return (
            <div key={i} className={`py-1 px-2 rounded ${levelBg[level] || ''}`}>
              <span className="text-gray-500">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>{' '}
              <span className={`font-bold ${levelColors[level] || 'text-gray-400'}`}>
                [{level}]
              </span>{' '}
              <span>{log.message}</span>
            </div>
          );
        })
      )}
    </div>
  );
}
