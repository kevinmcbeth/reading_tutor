import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchGenerationJobs, fetchJobLogs, GenerationJobResponse, GenerationLogResponse } from '../services/api';

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: 'Waiting', color: 'text-gray-600', bg: 'bg-gray-100' },
  generating_text: { label: 'Writing Story', color: 'text-blue-700', bg: 'bg-blue-100' },
  generating_images: { label: 'Creating Images', color: 'text-purple-700', bg: 'bg-purple-100' },
  generating_audio: { label: 'Recording Audio', color: 'text-orange-700', bg: 'bg-orange-100' },
  completed: { label: 'Done', color: 'text-green-700', bg: 'bg-green-100' },
  failed: { label: 'Failed', color: 'text-red-700', bg: 'bg-red-100' },
  cancelled: { label: 'Cancelled', color: 'text-gray-500', bg: 'bg-gray-100' },
};

const STEPS = ['pending', 'generating_text', 'generating_images', 'generating_audio', 'completed'];

function StepIndicator({ status }: { status: string }) {
  const currentStep = STEPS.indexOf(status);
  const isFailed = status === 'failed' || status === 'cancelled';

  return (
    <div className="flex items-center gap-1 mt-2">
      {STEPS.map((step, i) => {
        let color = 'bg-gray-200';
        if (isFailed && i <= currentStep) color = 'bg-red-300';
        else if (i < currentStep) color = 'bg-green-400';
        else if (i === currentStep) color = 'bg-blue-500 animate-pulse';

        return (
          <div key={step} className="flex items-center">
            <div className={`w-3 h-3 rounded-full ${color}`} title={step} />
            {i < STEPS.length - 1 && (
              <div className={`w-6 h-0.5 ${i < currentStep ? 'bg-green-400' : 'bg-gray-200'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function QueueMonitorPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<GenerationJobResponse[]>([]);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [jobLogs, setJobLogs] = useState<Record<string, GenerationLogResponse[]>>({});
  const [loading, setLoading] = useState(true);

  const loadJobs = async () => {
    try {
      const data = await fetchGenerationJobs();
      setJobs(data);
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleExpand = async (jobId: string) => {
    if (expandedJob === jobId) {
      setExpandedJob(null);
      return;
    }
    setExpandedJob(jobId);
    try {
      const logs = await fetchJobLogs(jobId);
      setJobLogs(prev => ({ ...prev, [jobId]: logs }));
    } catch (err) {
      console.error('Failed to load logs:', err);
    }
  };

  // Refresh logs for expanded job
  useEffect(() => {
    if (!expandedJob) return;
    const interval = setInterval(async () => {
      try {
        const logs = await fetchJobLogs(expandedJob);
        setJobLogs(prev => ({ ...prev, [expandedJob]: logs }));
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(interval);
  }, [expandedJob]);

  const active = jobs.filter(j => ['pending', 'generating_text', 'generating_images', 'generating_audio'].includes(j.status));
  const completed = jobs.filter(j => j.status === 'completed');
  const failed = jobs.filter(j => j.status === 'failed' || j.status === 'cancelled');

  const activeJob = active.find(j => j.status !== 'pending');
  const queued = active.filter(j => j.status === 'pending');

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-xl text-gray-500 animate-pulse">Loading queue...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/parent/dashboard')}
            className="text-gray-500 hover:text-gray-700 px-4 py-2 rounded-full bg-white shadow transition"
          >
            &larr; Back
          </button>
          <h1 className="text-3xl font-bold text-gray-800">Queue Monitor</h1>
          <div />
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-xl shadow p-4 text-center">
            <div className="text-3xl font-black text-blue-500">{active.length}</div>
            <div className="text-sm text-gray-500">Active</div>
          </div>
          <div className="bg-white rounded-xl shadow p-4 text-center">
            <div className="text-3xl font-black text-gray-400">{queued.length}</div>
            <div className="text-sm text-gray-500">Queued</div>
          </div>
          <div className="bg-white rounded-xl shadow p-4 text-center">
            <div className="text-3xl font-black text-green-500">{completed.length}</div>
            <div className="text-sm text-gray-500">Done</div>
          </div>
          <div className="bg-white rounded-xl shadow p-4 text-center">
            <div className="text-3xl font-black text-red-400">{failed.length}</div>
            <div className="text-sm text-gray-500">Failed</div>
          </div>
        </div>

        {/* Currently Processing */}
        {activeJob && (
          <div className="bg-blue-50 border-2 border-blue-200 rounded-2xl p-6 mb-6">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <h2 className="text-lg font-bold text-blue-800">Now Processing</h2>
            </div>
            <div className="text-xl font-medium text-gray-800">
              Job #{activeJob.id} &mdash; {activeJob.prompt || `Story #${activeJob.story_id}`}
            </div>
            <div className="flex items-center gap-4 mt-3">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusConfig[activeJob.status]?.bg || ''} ${statusConfig[activeJob.status]?.color || ''}`}>
                {statusConfig[activeJob.status]?.label || activeJob.status}
              </span>
              <StepIndicator status={activeJob.status} />
            </div>
            {/* Progress bar */}
            <div className="mt-3 bg-blue-100 rounded-full h-3 overflow-hidden">
              <div
                className="bg-blue-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${activeJob.progress_pct || 0}%` }}
              />
            </div>
            <div className="text-xs text-blue-600 mt-1">{Math.round(activeJob.progress_pct || 0)}%</div>
          </div>
        )}

        {/* Queue */}
        {queued.length > 0 && (
          <div className="bg-white rounded-2xl shadow mb-6">
            <div className="p-4 border-b">
              <h2 className="text-lg font-bold text-gray-700">Waiting ({queued.length})</h2>
            </div>
            <div className="divide-y max-h-60 overflow-y-auto">
              {queued.map((job, i) => (
                <div key={job.id} className="px-4 py-3 flex items-center gap-3">
                  <span className="text-gray-400 text-sm w-8">#{i + 1}</span>
                  <span className="text-gray-600 flex-1 truncate">
                    Job #{job.id} &mdash; Story #{job.story_id}
                  </span>
                  <span className="text-xs text-gray-400">pending</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Completed & Failed */}
        <div className="bg-white rounded-2xl shadow">
          <div className="p-4 border-b">
            <h2 className="text-lg font-bold text-gray-700">History</h2>
          </div>
          <div className="divide-y max-h-96 overflow-y-auto">
            {jobs.filter(j => j.status !== 'pending').map((job) => {
              const cfg = statusConfig[job.status] || statusConfig.pending;
              const logs = jobLogs[job.id] || [];
              const isExpanded = expandedJob === job.id;

              return (
                <div key={job.id}>
                  <button
                    onClick={() => handleExpand(job.id)}
                    className="w-full px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition text-left"
                  >
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color}`}>
                      {cfg.label}
                    </span>
                    <span className="text-gray-700 flex-1 truncate">
                      Job #{job.id} &mdash; Story #{job.story_id}
                    </span>
                    <StepIndicator status={job.status} />
                    <span className="text-xs text-gray-400 ml-2">
                      {job.completed_at ? new Date(job.completed_at).toLocaleTimeString() : ''}
                    </span>
                  </button>

                  {isExpanded && (
                    <div className="px-4 pb-4 bg-gray-50 border-t">
                      <div className="mt-3 max-h-48 overflow-y-auto text-xs font-mono space-y-1">
                        {logs.length === 0 ? (
                          <p className="text-gray-400 italic">No logs yet...</p>
                        ) : (
                          logs.map((log) => (
                            <div
                              key={log.id}
                              className={`flex gap-2 ${
                                log.level === 'error' ? 'text-red-600' :
                                log.level === 'warning' ? 'text-yellow-600' :
                                'text-gray-600'
                              }`}
                            >
                              <span className="text-gray-400 shrink-0">
                                {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                              </span>
                              <span className="uppercase w-12 shrink-0 font-bold">{log.level}</span>
                              <span>{log.message}</span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
