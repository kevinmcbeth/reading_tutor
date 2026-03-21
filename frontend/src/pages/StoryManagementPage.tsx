import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchStories,
  fetchGenerationJobs,
  generateStory,
  generateBatch,
  generateMeta,
  generateFPStory,
  fetchFPLevels,
  deleteStory,
  StoryResponse,
  GenerationJobResponse,
  FPLevelResponse,
} from '../services/api';

const statusStyles: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  generating_text: 'bg-yellow-100 text-yellow-700',
  generating_images: 'bg-yellow-100 text-yellow-700',
  generating_audio: 'bg-yellow-100 text-yellow-700',
  ready: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

export default function StoryManagementPage() {
  const navigate = useNavigate();
  const [stories, setStories] = useState<StoryResponse[]>([]);
  const [jobs, setJobs] = useState<GenerationJobResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedStory, setExpandedStory] = useState<string | null>(null);

  // Generate Single
  const [topic, setTopic] = useState('');
  const [difficulty, setDifficulty] = useState('easy');
  const [theme, setTheme] = useState('');
  const [generating, setGenerating] = useState(false);

  // Batch Generate
  const [batchTopics, setBatchTopics] = useState('');
  const [batchDifficulty, setBatchDifficulty] = useState('easy');
  const [batchGenerating, setBatchGenerating] = useState(false);

  // Meta Generate
  const [metaDescription, setMetaDescription] = useState('');
  const [metaCount, setMetaCount] = useState(5);
  const [metaGenerating, setMetaGenerating] = useState(false);

  // Leveled Generate
  const [fpTopic, setFpTopic] = useState('');
  const [fpLevel, setFpLevel] = useState('A');
  const [fpLevels, setFpLevels] = useState<FPLevelResponse[]>([]);
  const [fpGenerating, setFpGenerating] = useState(false);

  const [activeTab, setActiveTab] = useState<'single' | 'batch' | 'meta' | 'leveled'>('single');

  const loadData = useCallback(async () => {
    try {
      const [s, j, lvls] = await Promise.all([fetchStories(), fetchGenerationJobs(), fetchFPLevels()]);
      setStories(s);
      setJobs(j);
      setFpLevels(lvls);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Refresh jobs periodically
  useEffect(() => {
    const interval = setInterval(() => {
      fetchGenerationJobs().then(setJobs).catch(console.error);
      fetchStories().then(setStories).catch(console.error);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    setGenerating(true);
    try {
      await generateStory(topic.trim(), difficulty, theme.trim() || undefined);
      setTopic('');
      setTheme('');
      await loadData();
    } catch (err) {
      console.error('Generation failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  const handleBatchGenerate = async () => {
    const topics = batchTopics.split('\n').map(t => t.trim()).filter(Boolean);
    if (topics.length === 0) return;
    setBatchGenerating(true);
    try {
      const prompts = topics.map(t => `Topic: ${t}. Difficulty: ${batchDifficulty}.`);
      await generateBatch(prompts);
      setBatchTopics('');
      await loadData();
    } catch (err) {
      console.error('Batch generation failed:', err);
    } finally {
      setBatchGenerating(false);
    }
  };

  const handleMetaGenerate = async () => {
    if (!metaDescription.trim()) return;
    setMetaGenerating(true);
    try {
      await generateMeta(metaDescription.trim(), metaCount);
      setMetaDescription('');
      await loadData();
    } catch (err) {
      console.error('Meta generation failed:', err);
    } finally {
      setMetaGenerating(false);
    }
  };

  const handleFPGenerate = async () => {
    if (!fpTopic.trim()) return;
    setFpGenerating(true);
    try {
      await generateFPStory(fpTopic.trim(), fpLevel);
      setFpTopic('');
      await loadData();
    } catch (err) {
      console.error('F&P generation failed:', err);
    } finally {
      setFpGenerating(false);
    }
  };

  const handleDeleteStory = async (id: string) => {
    if (!confirm('Delete this story?')) return;
    try {
      await deleteStory(id);
      setStories(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const getJobForStory = (storyId: string) => {
    return jobs.find(j => j.story_id === storyId);
  };

  const isProcessing = (status: string) => {
    return ['generating_text', 'generating_images', 'generating_audio', 'pending'].includes(status);
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
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={() => navigate('/parent/dashboard')}
            className="text-gray-500 hover:text-gray-700 px-4 py-2 rounded-full bg-white shadow transition"
          >
            &larr; Back
          </button>
          <h1 className="text-3xl font-bold text-gray-800">Story Management</h1>
          <div />
        </div>

        {/* Generation Section */}
        <div className="bg-white rounded-2xl shadow p-6 mb-8">
          <div className="flex gap-2 mb-6 flex-wrap">
            {(['single', 'batch', 'meta', 'leveled'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-full font-medium capitalize transition ${
                  activeTab === tab
                    ? tab === 'leveled' ? 'bg-purple-500 text-white' : 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {tab === 'single' ? 'Generate New' : tab === 'batch' ? 'Batch Generate' : tab === 'meta' ? 'Meta Generate' : 'Leveled (F&P)'}
              </button>
            ))}
          </div>

          {activeTab === 'single' && (
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Story topic (e.g., 'a brave kitten')"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="w-full p-3 border rounded-xl focus:border-blue-400 focus:outline-none"
              />
              <div className="flex gap-4">
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="p-3 border rounded-xl focus:border-blue-400 focus:outline-none"
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
                <input
                  type="text"
                  placeholder="Theme (optional)"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value)}
                  className="flex-1 p-3 border rounded-xl focus:border-blue-400 focus:outline-none"
                />
              </div>
              <button
                onClick={handleGenerate}
                disabled={!topic.trim() || generating}
                className="px-6 py-3 bg-blue-500 text-white rounded-xl font-bold hover:bg-blue-600 transition disabled:opacity-50"
              >
                {generating ? 'Generating...' : 'Generate Story'}
              </button>
            </div>
          )}

          {activeTab === 'batch' && (
            <div className="space-y-4">
              <textarea
                placeholder="One topic per line"
                value={batchTopics}
                onChange={(e) => setBatchTopics(e.target.value)}
                rows={5}
                className="w-full p-3 border rounded-xl focus:border-blue-400 focus:outline-none resize-none"
              />
              <div className="flex gap-4 items-center">
                <select
                  value={batchDifficulty}
                  onChange={(e) => setBatchDifficulty(e.target.value)}
                  className="p-3 border rounded-xl focus:border-blue-400 focus:outline-none"
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
                <button
                  onClick={handleBatchGenerate}
                  disabled={!batchTopics.trim() || batchGenerating}
                  className="px-6 py-3 bg-blue-500 text-white rounded-xl font-bold hover:bg-blue-600 transition disabled:opacity-50"
                >
                  {batchGenerating ? 'Generating...' : 'Generate All'}
                </button>
              </div>
            </div>
          )}

          {activeTab === 'meta' && (
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Describe what stories you want (e.g., 'animal adventures for beginners')"
                value={metaDescription}
                onChange={(e) => setMetaDescription(e.target.value)}
                className="w-full p-3 border rounded-xl focus:border-blue-400 focus:outline-none"
              />
              <div className="flex gap-4 items-center">
                <label className="text-gray-600">
                  Count:
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={metaCount}
                    onChange={(e) => setMetaCount(parseInt(e.target.value) || 5)}
                    className="ml-2 w-20 p-3 border rounded-xl focus:border-blue-400 focus:outline-none"
                  />
                </label>
                <button
                  onClick={handleMetaGenerate}
                  disabled={!metaDescription.trim() || metaGenerating}
                  className="px-6 py-3 bg-blue-500 text-white rounded-xl font-bold hover:bg-blue-600 transition disabled:opacity-50"
                >
                  {metaGenerating ? 'Generating...' : 'Generate'}
                </button>
              </div>
            </div>
          )}

          {activeTab === 'leveled' && (
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Story topic (e.g., 'a brave kitten')"
                value={fpTopic}
                onChange={(e) => setFpTopic(e.target.value)}
                className="w-full p-3 border rounded-xl focus:border-purple-400 focus:outline-none"
              />
              <div className="flex gap-4 items-center">
                <select
                  value={fpLevel}
                  onChange={(e) => setFpLevel(e.target.value)}
                  className="p-3 border rounded-xl focus:border-purple-400 focus:outline-none"
                >
                  {fpLevels.map(l => (
                    <option key={l.level} value={l.level}>
                      Level {l.level} — {l.grade_range} ({l.min_sentences}-{l.max_sentences} sentences)
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleFPGenerate}
                  disabled={!fpTopic.trim() || fpGenerating}
                  className="px-6 py-3 bg-purple-500 text-white rounded-xl font-bold hover:bg-purple-600 transition disabled:opacity-50"
                >
                  {fpGenerating ? 'Generating...' : 'Generate Leveled Story'}
                </button>
              </div>
              {fpLevels.find(l => l.level === fpLevel) && (
                <div className="text-sm text-gray-500 bg-purple-50 rounded-xl p-3">
                  {fpLevels.find(l => l.level === fpLevel)?.description}
                  {fpLevels.find(l => l.level === fpLevel)?.generate_images === false && (
                    <span className="ml-2 text-orange-500 font-medium">(No images at this level)</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Active Jobs */}
        {jobs.filter(j => isProcessing(j.status)).length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-4 mb-6">
            <h3 className="font-bold text-yellow-700 mb-2">Active Jobs</h3>
            <div className="space-y-2">
              {jobs.filter(j => isProcessing(j.status)).map((job) => (
                <div key={job.id} className="flex items-center gap-3 text-sm">
                  <div className="w-4 h-4 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-gray-700 truncate flex-1">{job.prompt}</span>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusStyles[job.status] || ''}`}>
                    {job.status}
                  </span>
                  <button
                    onClick={() => navigate(`/parent/logs/${job.id}`)}
                    className="text-blue-500 hover:text-blue-700 text-xs underline"
                  >
                    Logs
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Story Library */}
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Story Library ({stories.length})</h2>

          {stories.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No stories yet. Generate some above!</p>
          ) : (
            <div className="space-y-2">
              {stories.map((story) => {
                const job = getJobForStory(story.id);
                return (
                  <div key={story.id} className="border rounded-xl overflow-hidden">
                    <div className="flex items-center">
                      <button
                        onClick={() => setExpandedStory(expandedStory === story.id ? null : story.id)}
                        className="flex-1 p-4 flex items-center gap-3 hover:bg-gray-50 transition text-left"
                      >
                        <div className="flex-1">
                          <span className="font-medium text-gray-800">{story.title}</span>
                        </div>
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                          statusStyles[story.difficulty] || 'bg-gray-100 text-gray-600'
                        }`}>
                          {story.difficulty}
                        </span>
                        {story.theme && (
                          <span className="px-3 py-1 rounded-full text-xs font-medium bg-purple-50 text-purple-600">
                            {story.theme}
                          </span>
                        )}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteStory(story.id); }}
                        className="px-4 py-4 text-red-400 hover:text-red-600 hover:bg-red-50 transition text-lg"
                        title="Delete story"
                      >
                        X
                      </button>
                    </div>

                    {expandedStory === story.id && (
                      <div className="px-4 pb-4 border-t bg-gray-50">
                        <div className="pt-3 text-sm text-gray-600 space-y-2">
                          <p><strong>Topic:</strong> {story.topic || 'N/A'}</p>
                          <p><strong>Difficulty:</strong> {story.difficulty || 'N/A'}</p>
                        </div>
                        <div className="mt-3 flex gap-2">
                          {job && (
                            <button
                              onClick={() => navigate(`/parent/logs/${job.id}`)}
                              className="text-sm text-blue-500 hover:text-blue-700 underline"
                            >
                              View Logs
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteStory(story.id)}
                            className="text-sm text-red-500 hover:text-red-700 underline ml-auto"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
