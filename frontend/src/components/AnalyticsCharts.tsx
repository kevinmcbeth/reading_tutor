import { AnalyticsResponse, SessionResponse } from '../services/api';

interface AnalyticsChartsProps {
  analytics: AnalyticsResponse | null;
  sessions: SessionResponse[];
}

export default function AnalyticsCharts({ analytics, sessions }: AnalyticsChartsProps) {
  return (
    <div className="space-y-6">
      {analytics && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-blue-50 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">{analytics.total_sessions}</div>
            <div className="text-sm text-blue-500">Sessions</div>
          </div>
          <div className="bg-purple-50 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold text-purple-600">
              {Math.round(analytics.average_score)}%
            </div>
            <div className="text-sm text-purple-500">Avg Score</div>
          </div>
        </div>
      )}

      {analytics && analytics.commonly_missed_words.length > 0 && (
        <div className="bg-white rounded-xl p-4 shadow">
          <h4 className="font-bold text-gray-700 mb-3">Commonly Missed Words</h4>
          <div className="flex flex-wrap gap-2">
            {analytics.commonly_missed_words.slice(0, 20).map((mw: { word: string; count: number }) => (
              <span
                key={mw.word}
                className="bg-red-50 text-red-600 px-3 py-1 rounded-full text-sm font-medium border border-red-200"
              >
                {mw.word} ({mw.count})
              </span>
            ))}
          </div>
        </div>
      )}

      {sessions.length > 0 && (
        <div className="bg-white rounded-xl p-4 shadow">
          <h4 className="font-bold text-gray-700 mb-3">Recent Sessions</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2">Date</th>
                <th className="pb-2">Attempt</th>
                <th className="pb-2">Score</th>
              </tr>
            </thead>
            <tbody>
              {sessions.slice(0, 20).map((s) => (
                <tr key={s.id} className="border-b border-gray-100">
                  <td className="py-2 text-gray-600">
                    {s.completed_at ? new Date(s.completed_at).toLocaleDateString() : 'In progress'}
                  </td>
                  <td className="py-2 text-gray-700">#{s.attempt_number}</td>
                  <td className="py-2">
                    {s.completed_at ? (
                      <span className={`font-bold ${
                        s.score === s.total_words ? 'text-green-600' : 'text-gray-700'
                      }`}>
                        {s.score}/{s.total_words}
                      </span>
                    ) : (
                      <span className="text-gray-400">In progress</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
