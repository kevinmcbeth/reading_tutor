import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchChildren,
  fetchChildSessions,
  fetchAnalytics,
  ChildResponse,
  SessionResponse,
  AnalyticsResponse,
} from '../services/api';
import AnalyticsCharts from '../components/AnalyticsCharts';

export default function ParentDashboard() {
  const navigate = useNavigate();
  const [children, setChildren] = useState<ChildResponse[]>([]);
  const [expandedChild, setExpandedChild] = useState<string | null>(null);
  const [childSessions, setChildSessions] = useState<Record<string, SessionResponse[]>>({});
  const [childAnalytics, setChildAnalytics] = useState<Record<string, AnalyticsResponse>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchChildren()
      .then(setChildren)
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
                    <div className="pt-4">
                      <AnalyticsCharts
                        analytics={childAnalytics[child.id] || null}
                        sessions={childSessions[child.id] || []}
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
