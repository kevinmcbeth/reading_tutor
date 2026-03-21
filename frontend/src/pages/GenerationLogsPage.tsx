import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchJobLogs, fetchGenerationJobs, GenerationLogResponse, GenerationJobResponse } from '../services/api';
import LogViewer from '../components/LogViewer';

const statusStyles: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  generating_text: 'bg-yellow-100 text-yellow-700',
  generating_images: 'bg-yellow-100 text-yellow-700',
  generating_audio: 'bg-yellow-100 text-yellow-700',
  ready: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

export default function GenerationLogsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [logs, setLogs] = useState<GenerationLogResponse[]>([]);
  const [job, setJob] = useState<GenerationJobResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) return;

    const loadData = async () => {
      try {
        const [logsData, jobsData] = await Promise.all([
          fetchJobLogs(jobId),
          fetchGenerationJobs(),
        ]);
        setLogs(logsData);
        const found = jobsData.find(j => j.id === jobId);
        setJob(found || null);
      } catch (err) {
        console.error('Failed to load logs:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();

    // Auto-refresh if job is still processing
    const interval = setInterval(async () => {
      try {
        const [logsData, jobsData] = await Promise.all([
          fetchJobLogs(jobId),
          fetchGenerationJobs(),
        ]);
        setLogs(logsData);
        const found = jobsData.find(j => j.id === jobId);
        setJob(found || null);

        // Stop refreshing if job is done
        if (found && (found.status === 'ready' || found.status === 'failed')) {
          clearInterval(interval);
        }
      } catch {
        // Ignore refresh errors
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-xl text-gray-500 animate-pulse">Loading logs...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate('/parent/stories')}
            className="text-gray-500 hover:text-gray-700 px-4 py-2 rounded-full bg-white shadow transition"
          >
            ← Back
          </button>
          <h1 className="text-2xl font-bold text-gray-800">Generation Logs</h1>
          <div />
        </div>

        {job && (
          <div className="bg-white rounded-xl shadow p-4 mb-6">
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusStyles[job.status] || 'bg-gray-100'}`}>
                {job.status}
              </span>
              <span className="text-gray-600 text-sm truncate flex-1">{job.prompt}</span>
              {job.error && (
                <span className="text-red-500 text-sm">{job.error}</span>
              )}
            </div>
            <div className="text-xs text-gray-400 mt-2">
              Started: {new Date(job.created_at).toLocaleString()}
              {job.completed_at && ` | Completed: ${new Date(job.completed_at).toLocaleString()}`}
            </div>
          </div>
        )}

        <LogViewer logs={logs} />
      </div>
    </div>
  );
}
