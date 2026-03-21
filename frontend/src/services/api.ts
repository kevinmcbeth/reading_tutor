import { getAccessToken, refreshAccessToken, clearTokens } from './auth';

// TypeScript interfaces matching backend models

export interface StoryResponse {
  id: string;
  title: string;
  topic: string;
  difficulty: string;
  theme: string;
  style: string;
  fp_level: string | null;
  status: string;
  sentences: unknown[];
  created_at: string;
}

export interface ChildResponse {
  id: string;
  name: string;
  avatar: string | null;
  fp_level: string | null;
  created_at: string;
  total_words_read: number;
  total_sessions: number;
}

export interface SessionResponse {
  id: string;
  child_id: string;
  story_id: string;
  attempt_number: number;
  score: number;
  total_words: number;
  completed_at: string | null;
}

export interface WordResult {
  word_id: number;
  attempts: number;
  correct: boolean;
}

export interface GenerationJobResponse {
  id: string;
  status: string;
  prompt: string;
  story_id: string | null;
  progress_pct: number;
  created_at: string;
  completed_at: string | null;
  error: string | null;
}

export interface GenerationLogResponse {
  id: string;
  job_id: string;
  level: string;
  message: string;
  timestamp: string;
}

export interface AnalyticsResponse {
  child_id: number;
  total_sessions: number;
  average_score: number;
  commonly_missed_words: { word: string; count: number }[];
}

export interface SpeechRecognitionResponse {
  transcript: string;
  alternatives: string[];
  confidence: number;
}

// API client functions

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });

  // Auto-refresh on 401
  if (response.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers,
      });
    } else {
      clearTokens();
      throw new Error('Session expired - please log in again');
    }
  }

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    console.error(`API error ${response.status} ${url}:`, body);
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function fetchStories(difficulty?: string, theme?: string): Promise<StoryResponse[]> {
  const params = new URLSearchParams();
  if (difficulty) params.set('difficulty', difficulty);
  if (theme) params.set('theme', theme);
  const query = params.toString();
  return fetchJson<StoryResponse[]>(`/stories${query ? `?${query}` : ''}`);
}

export async function fetchStory(id: string): Promise<StoryResponse> {
  return fetchJson<StoryResponse>(`/stories/${id}`);
}

export async function generateStory(topic: string, difficulty: string = 'easy', theme?: string): Promise<unknown> {
  return fetchJson('/stories/generate', {
    method: 'POST',
    body: JSON.stringify({ topic, difficulty, theme: theme || null }),
  });
}

export async function generateBatch(prompts: string[]): Promise<{ job_ids: string[] }> {
  return fetchJson<{ job_ids: string[] }>('/stories/generate/batch', {
    method: 'POST',
    body: JSON.stringify({ prompts }),
  });
}

export async function generateMeta(description: string, count?: number): Promise<{ job_ids: string[] }> {
  return fetchJson<{ job_ids: string[] }>('/stories/generate/meta', {
    method: 'POST',
    body: JSON.stringify({ description, count }),
  });
}

export async function fetchChildren(): Promise<ChildResponse[]> {
  return fetchJson<ChildResponse[]>('/children');
}

export async function createChild(name: string, avatar?: string): Promise<ChildResponse> {
  return fetchJson<ChildResponse>('/children', {
    method: 'POST',
    body: JSON.stringify({ name, avatar }),
  });
}

export interface LeaderboardEntry {
  name: string;
  avatar: string | null;
  total_words: number;
  total_sessions: number;
}

export async function fetchLeaderboard(): Promise<LeaderboardEntry[]> {
  return fetchJson<LeaderboardEntry[]>('/children/leaderboard');
}

export async function fetchChild(id: string): Promise<ChildResponse> {
  return fetchJson<ChildResponse>(`/children/${id}`);
}

export async function createSession(childId: string, storyId: string): Promise<SessionResponse> {
  return fetchJson<SessionResponse>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ child_id: childId, story_id: storyId }),
  });
}

export async function completeSession(sessionId: string, results: WordResult[]): Promise<SessionResponse> {
  return fetchJson<SessionResponse>(`/sessions/${sessionId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ results }),
  });
}

export async function fetchChildSessions(childId: string): Promise<SessionResponse[]> {
  return fetchJson<SessionResponse[]>(`/sessions/child/${childId}`);
}

export async function fetchGenerationJobs(): Promise<GenerationJobResponse[]> {
  return fetchJson<GenerationJobResponse[]>('/generation/jobs');
}

export async function fetchJobLogs(jobId: string): Promise<GenerationLogResponse[]> {
  return fetchJson<GenerationLogResponse[]>(`/generation/jobs/${jobId}/logs`);
}

export async function fetchAnalytics(childId?: string): Promise<AnalyticsResponse> {
  const url = childId ? `/parent/analytics/${childId}` : '/parent/analytics';
  return fetchJson<AnalyticsResponse>(url);
}

export async function deleteStory(id: string): Promise<void> {
  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  await fetch(`${API_BASE}/stories/${id}`, { method: 'DELETE', headers });
}

export async function recognizeSpeech(audio: Blob, targetWord?: string): Promise<SpeechRecognitionResponse> {
  const token = getAccessToken();
  const formData = new FormData();
  formData.append('audio', audio, 'recording.webm');
  if (targetWord) formData.append('target_word', targetWord);
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/speech/recognize`, { method: 'POST', body: formData, headers });
  if (!res.ok) throw new Error('Speech recognition failed');
  return res.json();
}

// --- F&P Guided Reading Levels ---

export interface FPLevelResponse {
  id: number;
  level: string;
  sort_order: number;
  grade_range: string | null;
  min_sentences: number;
  max_sentences: number;
  generate_images: boolean;
  image_support: string | null;
  description: string | null;
}

export interface FPProgressResponse {
  child_id: number;
  fp_level: string;
  stories_at_level: number;
  stories_passed: number;
  average_accuracy: number;
  suggest_advance: boolean;
  suggest_drop: boolean;
}

export async function fetchFPLevels(): Promise<FPLevelResponse[]> {
  return fetchJson<FPLevelResponse[]>('/fp/levels');
}

export async function fetchFPStories(level: string): Promise<StoryResponse[]> {
  return fetchJson<StoryResponse[]>(`/fp/stories?level=${encodeURIComponent(level)}`);
}

export async function fetchFPProgress(childId: string): Promise<FPProgressResponse> {
  return fetchJson<FPProgressResponse>(`/fp/child/${childId}/progress`);
}

export async function setFPLevel(childId: string, level: string): Promise<unknown> {
  return fetchJson(`/fp/child/${childId}/level`, {
    method: 'POST',
    body: JSON.stringify({ level }),
  });
}

export async function startFPMode(childId: string, startingLevel: string): Promise<unknown> {
  return fetchJson(`/fp/child/${childId}/start`, {
    method: 'POST',
    body: JSON.stringify({ starting_level: startingLevel }),
  });
}

export async function generateFPStory(topic: string, level: string, theme?: string): Promise<unknown> {
  return fetchJson('/fp/generate', {
    method: 'POST',
    body: JSON.stringify({ topic, level, theme: theme || null }),
  });
}
