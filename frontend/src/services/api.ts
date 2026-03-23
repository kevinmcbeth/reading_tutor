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

export interface TranscriptionHypothesis {
  text: string;
  probability: number;
}

export interface SpeechRecognitionResponse {
  transcript: string;
  alternatives: TranscriptionHypothesis[];
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

export async function fetchStories(
  difficulty?: string,
  theme?: string,
  limit: number = 50,
  offset: number = 0,
): Promise<StoryResponse[]> {
  const params = new URLSearchParams();
  if (difficulty) params.set('difficulty', difficulty);
  if (theme) params.set('theme', theme);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return fetchJson<StoryResponse[]>(`/stories?${params.toString()}`);
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

export interface LevelLeaderboardEntry {
  name: string;
  avatar: string | null;
  fp_level: string;
  sort_order: number;
}

export async function fetchLevelLeaderboard(): Promise<LevelLeaderboardEntry[]> {
  return fetchJson<LevelLeaderboardEntry[]>('/children/leaderboard/levels');
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

export async function deleteIncompleteSessions(childId: string): Promise<{ deleted: number }> {
  return fetchJson<{ deleted: number }>(`/sessions/child/${childId}/incomplete`, {
    method: 'DELETE',
  });
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

// --- Rewards / Ticket Redeem ---

export interface RewardItemResponse {
  id: number;
  name: string;
  description: string | null;
  emoji: string;
  cost: number;
  active: boolean;
  created_at: string | null;
}

export interface RedemptionResponse {
  id: number;
  child_id: number;
  item_id: number;
  item_name: string;
  item_emoji: string;
  cost: number;
  redeemed_at: string | null;
}

export interface BalanceResponse {
  child_id: number;
  words_available: number;
  words_per_coin: number;
  coins_balance: number;
  total_coins_earned: number;
  total_coins_spent: number;
}

export interface RedeemResult {
  detail: string;
  redemption_id: number;
  item_name: string;
  cost: number;
  new_balance: number;
}

export async function fetchRewardItems(activeOnly: boolean = true): Promise<RewardItemResponse[]> {
  return fetchJson<RewardItemResponse[]>(`/rewards/items?active_only=${activeOnly}`);
}

export async function createRewardItem(name: string, cost: number, emoji?: string, description?: string): Promise<RewardItemResponse> {
  return fetchJson<RewardItemResponse>('/rewards/items', {
    method: 'POST',
    body: JSON.stringify({ name, cost, emoji: emoji || '\u{1f381}', description: description || null }),
  });
}

export async function updateRewardItem(id: number, name: string, cost: number, emoji?: string, description?: string): Promise<RewardItemResponse> {
  return fetchJson<RewardItemResponse>(`/rewards/items/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ name, cost, emoji: emoji || '\u{1f381}', description: description || null }),
  });
}

export async function deleteRewardItem(id: number): Promise<void> {
  await fetchJson(`/rewards/items/${id}`, { method: 'DELETE' });
}

export async function fetchBalance(childId: string): Promise<BalanceResponse> {
  return fetchJson<BalanceResponse>(`/rewards/balance/${childId}`);
}

export async function redeemItem(itemId: number, childId: string): Promise<RedeemResult> {
  return fetchJson<RedeemResult>(`/rewards/${itemId}/redeem?child_id=${childId}`, {
    method: 'POST',
  });
}

export async function fetchRedemptionHistory(childId: string): Promise<RedemptionResponse[]> {
  return fetchJson<RedemptionResponse[]>(`/rewards/history/${childId}`);
}

export interface WalletItem {
  item_id: number;
  item_name: string;
  item_emoji: string;
  item_description: string | null;
  quantity: number;
  last_redeemed: string | null;
}

export async function fetchWallet(childId: string): Promise<WalletItem[]> {
  return fetchJson<WalletItem[]>(`/rewards/wallet/${childId}`);
}

export interface ConvertResult {
  detail: string;
  words_spent: number;
  coins_earned: number;
  words_remaining: number;
}

export async function convertWordsToCoins(childId: string, coins: number): Promise<ConvertResult> {
  return fetchJson<ConvertResult>(`/rewards/convert/${childId}?coins=${coins}`, {
    method: 'POST',
  });
}

export interface ExchangeRateChild {
  child_id: number;
  name: string;
  words_per_coin: number | null;
}

export interface ExchangeRateResponse {
  family_rate: number;
  children: ExchangeRateChild[];
}

export async function fetchExchangeRate(): Promise<ExchangeRateResponse> {
  return fetchJson<ExchangeRateResponse>('/rewards/exchange-rate');
}

export async function setExchangeRate(wordsPerCoin: number, childId?: number): Promise<unknown> {
  return fetchJson('/rewards/exchange-rate', {
    method: 'PUT',
    body: JSON.stringify({ words_per_coin: wordsPerCoin, child_id: childId ?? null }),
  });
}

export async function clearChildExchangeRate(childId: number): Promise<unknown> {
  return fetchJson(`/rewards/exchange-rate/${childId}`, { method: 'DELETE' });
}

// --- Stock Market ---

export interface StockInfoResponse {
  id: number;
  symbol: string;
  name: string;
  emoji: string;
  category: string;
  description: string | null;
  current_price: number;
  change_pct: number;
  type: string;
  dividend_yield: number;
}

export interface StockPricePointResponse {
  price: number;
  change_pct: number;
  market_day: string;
}

export interface StockDetailResponse {
  stock: StockInfoResponse;
  history: StockPricePointResponse[];
  story: { headline: string; body: string } | null;
}

export interface StockPortfolioResponse {
  coins: number;
  holdings: {
    stock_id: number;
    symbol: string;
    name: string;
    emoji: string;
    shares: number;
    current_price: number;
    value: number;
  }[];
  total_value: number;
}

export interface StockNewsItemResponse {
  stock_symbol: string;
  stock_name: string;
  stock_emoji: string;
  direction: string;
  headline: string;
  body: string;
  change_pct: number;
}

export interface StockTradeResponseData {
  action: string;
  symbol: string;
  shares: number;
  price_per_share: number;
  total: number;
  coins_remaining: number;
}

export async function fetchStocks(): Promise<StockInfoResponse[]> {
  return fetchJson<StockInfoResponse[]>('/stockmarket/stocks');
}

export async function fetchStockDetail(stockId: number, childId: string): Promise<StockDetailResponse> {
  return fetchJson<StockDetailResponse>(`/stockmarket/stocks/${stockId}?child_id=${childId}`);
}

export async function fetchStockPortfolio(childId: string): Promise<StockPortfolioResponse> {
  return fetchJson<StockPortfolioResponse>(`/stockmarket/portfolio?child_id=${childId}`);
}

export async function fetchStockNews(childId: string): Promise<StockNewsItemResponse[]> {
  return fetchJson<StockNewsItemResponse[]>(`/stockmarket/news?child_id=${childId}`);
}

export async function buyStock(stockId: number, shares: number, childId: string): Promise<StockTradeResponseData> {
  return fetchJson<StockTradeResponseData>(`/stockmarket/buy?child_id=${childId}`, {
    method: 'POST',
    body: JSON.stringify({ stock_id: stockId, shares }),
  });
}

export async function sellStock(stockId: number, shares: number, childId: string): Promise<StockTradeResponseData> {
  return fetchJson<StockTradeResponseData>(`/stockmarket/sell?child_id=${childId}`, {
    method: 'POST',
    body: JSON.stringify({ stock_id: stockId, shares }),
  });
}

export async function depositStockCoins(childId: string, coins: number): Promise<{ coins_deposited: number; words_spent: number; stock_balance: number; words_remaining: number }> {
  return fetchJson(`/stockmarket/deposit?child_id=${childId}`, {
    method: 'POST',
    body: JSON.stringify({ coins }),
  });
}

export async function createStock(data: {
  symbol: string; name: string; emoji: string; category: string;
  description?: string; base_price: number; volatility: number;
  type?: string; dividend_yield?: number;
}): Promise<StockInfoResponse> {
  return fetchJson<StockInfoResponse>('/stockmarket/admin/stocks', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateStock(stockId: number, data: {
  symbol: string; name: string; emoji: string; category: string;
  description?: string; base_price: number; volatility: number;
  type?: string; dividend_yield?: number;
}): Promise<StockInfoResponse> {
  return fetchJson<StockInfoResponse>(`/stockmarket/admin/stocks/${stockId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteStock(stockId: number): Promise<void> {
  await fetchJson(`/stockmarket/admin/stocks/${stockId}`, { method: 'DELETE' });
}

// --- Math Module ---

export interface MathSubjectInfo {
  subject: string;
  display_name: string;
  emoji: string;
  grades: number[];
  grade_names: string[];
  input_mode: 'speech' | 'tap';
  description: string;
  coming_soon: boolean;
}

export interface MathProgressEntry {
  subject: string;
  grade_level: number;
  problems_attempted: number;
  problems_correct: number;
  streak: number;
  best_streak: number;
  accuracy: number;
  set_by: string;
}

export interface MathSessionResponse {
  id: number;
  child_id: number;
  subject: string;
  grade_level: number;
  started_at: string | null;
}

export interface MathProblemResponse {
  problem_id: number;
  display: string;
  problem_data: { a: number; b: number; operation: string };
  problem_number: number;
}

export interface MathAnswerResponse {
  correct: boolean;
  correct_answer: string;
  child_answer: string;
  problem_id: number;
}

export interface MathSessionCompleteResponse {
  session_id: number;
  subject: string;
  problems_attempted: number;
  problems_correct: number;
  accuracy: number;
  streak: number;
  best_streak: number;
  grade_level: number;
  advanced: boolean;
  perfect: boolean;
}

export interface MathBalanceResponse {
  child_id: number;
  problems_available: number;
  math_problems_per_coin: number;
  coins_convertible: number;
}

export async function fetchMathSubjects(): Promise<MathSubjectInfo[]> {
  return fetchJson<MathSubjectInfo[]>('/math/subjects');
}

export async function fetchMathProgress(childId: string): Promise<MathProgressEntry[]> {
  return fetchJson<MathProgressEntry[]>(`/math/progress/${childId}`);
}

export async function setMathGradeLevel(childId: string, subject: string, gradeLevel: number): Promise<unknown> {
  return fetchJson(`/math/progress/${childId}/${subject}`, {
    method: 'PUT',
    body: JSON.stringify({ grade_level: gradeLevel }),
  });
}

export async function startMathSession(childId: string, subject: string): Promise<MathSessionResponse> {
  return fetchJson<MathSessionResponse>('/math/sessions', {
    method: 'POST',
    body: JSON.stringify({ child_id: childId, subject }),
  });
}

export async function fetchMathProblem(sessionId: number): Promise<MathProblemResponse> {
  return fetchJson<MathProblemResponse>(`/math/sessions/${sessionId}/problem`, {
    method: 'POST',
  });
}

export async function submitMathAnswer(
  sessionId: number,
  answer: string,
  transcript?: string,
  alternatives?: string[],
): Promise<MathAnswerResponse> {
  return fetchJson<MathAnswerResponse>(`/math/sessions/${sessionId}/answer`, {
    method: 'POST',
    body: JSON.stringify({ answer, transcript, alternatives }),
  });
}

export async function completeMathSession(sessionId: number): Promise<MathSessionCompleteResponse> {
  return fetchJson<MathSessionCompleteResponse>(`/math/sessions/${sessionId}/complete`, {
    method: 'POST',
  });
}

export async function fetchMathBalance(childId: string): Promise<MathBalanceResponse> {
  return fetchJson<MathBalanceResponse>(`/math/balance/${childId}`);
}

export async function convertMathToCoins(childId: string, coins: number): Promise<ConvertResult> {
  return fetchJson<ConvertResult>(`/math/convert/${childId}?coins=${coins}`, {
    method: 'POST',
  });
}

export async function fetchMathExchangeRate(): Promise<{ family_rate: number; children: { child_id: number; name: string; math_problems_per_coin: number | null }[] }> {
  return fetchJson('/math/exchange-rate');
}

export async function setMathExchangeRate(mathProblemsPerCoin: number, childId?: number): Promise<unknown> {
  return fetchJson('/math/exchange-rate', {
    method: 'PUT',
    body: JSON.stringify({ math_problems_per_coin: mathProblemsPerCoin, child_id: childId ?? null }),
  });
}
