import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchChildren,
  fetchChildSessions,
  fetchAnalytics,
  fetchFPLevels,
  fetchFPProgress,
  setFPLevel,
  ChildResponse,
  SessionResponse,
  AnalyticsResponse,
  FPLevelResponse,
  FPProgressResponse,
} from '../services/api';
import AnalyticsCharts from '../components/AnalyticsCharts';

export default function ParentDashboard() {
  const navigate = useNavigate();
  const [children, setChildren] = useState<ChildResponse[]>([]);
  const [expandedChild, setExpandedChild] = useState<string | null>(null);
  const [childSessions, setChildSessions] = useState<Record<string, SessionResponse[]>>({});
  const [childAnalytics, setChildAnalytics] = useState<Record<string, AnalyticsResponse>>({});
  const [fpLevels, setFpLevels] = useState<FPLevelResponse[]>([]);
  const [childFPProgress, setChildFPProgress] = useState<Record<string, FPProgressResponse | null>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchChildren(), fetchFPLevels()])
      .then(([c, lvls]) => { setChildren(c); setFpLevels(lvls); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleExpandChild = async (childId: string) => {
    if (expandedChild === childId) {
      setExpandedChild(null);
      return;
    }
    setExpandedChild(childId);

    if (!childSessions[childId]) {
      try {
        const [sessions, analytics] = await Promise.all([
          fetchChildSessions(childId),
          fetchAnalytics(childId),
        ]);
        setChildSessions(prev => ({ ...prev, [childId]: sessions }));
        setChildAnalytics(prev => ({ ...prev, [childId]: analytics }));

        // Load F&P progress
        const child = children.find(c => c.id === childId);
        if (child?.fp_level) {
          const prog = await fetchFPProgress(childId).catch(() => null);
          setChildFPProgress(prev => ({ ...prev, [childId]: prog }));
        }
      } catch (err) {
        console.error('Failed to load child data:', err);
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-xl text-gray-500 animate-pulse">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={() => navigate('/')}
            className="text-gray-500 hover:text-gray-700 px-4 py-2 rounded-full bg-white shadow transition"
          >
            &larr; Back
          </button>
          <h1 className="text-3xl font-bold text-gray-800">Parent Dashboard</h1>
          <div className="flex gap-2">
            <button
              onClick={() => navigate('/parent/queue')}
              className="px-4 py-2 bg-purple-500 text-white rounded-full hover:bg-purple-600 transition font-medium"
            >
              Queue Monitor
            </button>
            <button
              onClick={() => navigate('/parent/stories')}
              className="px-4 py-2 bg-blue-500 text-white rounded-full hover:bg-blue-600 transition font-medium"
            >
              Manage Stories
            </button>
          </div>
        </div>

        {/* Children List */}
        {children.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-xl text-gray-500">No children registered yet.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {children.map((child) => (
              <div key={child.id} className="bg-white rounded-2xl shadow overflow-hidden">
                <button
                  onClick={() => handleExpandChild(child.id)}
                  className="w-full p-6 flex items-center gap-4 hover:bg-gray-50 transition text-left"
                >
                  <span className="text-4xl">{child.avatar || '😊'}</span>
                  <div className="flex-1">
                    <h2 className="text-xl font-bold text-gray-800">{child.name}</h2>
                    <p className="text-sm text-gray-500">
                      Joined {new Date(child.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className="text-gray-400 text-2xl">
                    {expandedChild === child.id ? '▲' : '▼'}
                  </span>
                </button>

                {expandedChild === child.id && (
                  <div className="px-6 pb-6 border-t">
                    {/* F&P Level Section */}
                    <div className="pt-4 mb-4">
                      <h3 className="text-lg font-bold text-gray-700 mb-3">Leveled Reading (F&P)</h3>
                      <div className="bg-purple-50 rounded-xl p-4">
                        {child.fp_level ? (
                          <div>
                            <div className="flex items-center gap-3 mb-3">
                              <div className="w-10 h-10 bg-purple-500 text-white rounded-full flex items-center justify-center font-bold text-lg">
                                {child.fp_level}
                              </div>
                              <div>
                                <div className="font-medium text-gray-700">Current Level: {child.fp_level}</div>
                                {childFPProgress[child.id] && (
                                  <div className="text-sm text-gray-500">
                                    {childFPProgress[child.id]!.stories_passed}/3 passed | Avg accuracy: {Math.round((childFPProgress[child.id]!.average_accuracy || 0) * 100)}%
                                  </div>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <label className="text-sm text-gray-600">Override level:</label>
                              <select
                                value={child.fp_level}
                                onChange={async (e) => {
                                  try {
                                    await setFPLevel(child.id, e.target.value);
                                    setChildren(prev => prev.map(c =>
                                      c.id === child.id ? { ...c, fp_level: e.target.value } : c
                                    ));
                                    const prog = await fetchFPProgress(child.id).catch(() => null);
                                    setChildFPProgress(prev => ({ ...prev, [child.id]: prog }));
                                  } catch (err) {
                                    console.error('Failed to set level:', err);
                                  }
                                }}
                                className="border rounded-lg px-2 py-1 text-sm"
                              >
                                {fpLevels.map(l => (
                                  <option key={l.level} value={l.level}>
                                    {l.level} — {l.grade_range} ({l.description?.split('—')[0]?.trim()})
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-2">
                            <p className="text-gray-500 text-sm mb-2">Not started yet</p>
                            <p className="text-xs text-gray-400">
                              The child can start leveled reading from the reading mode selection screen.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="pt-2">
                      <AnalyticsCharts
                        analytics={childAnalytics[child.id] || null}
                        sessions={childSessions[child.id] || []}
                        childId={child.id}
                        onSessionsChanged={async () => {
                          const [sessions, analytics] = await Promise.all([
                            fetchChildSessions(child.id),
                            fetchAnalytics(child.id),
                          ]);
                          setChildSessions(prev => ({ ...prev, [child.id]: sessions }));
                          setChildAnalytics(prev => ({ ...prev, [child.id]: analytics }));
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
