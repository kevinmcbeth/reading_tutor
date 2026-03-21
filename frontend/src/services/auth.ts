const TOKEN_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  family_id: number;
  display_name: string | null;
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(data.detail || 'Login failed');
  }
  const data: TokenResponse = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function register(
  username: string,
  password: string,
  displayName?: string,
): Promise<TokenResponse> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, display_name: displayName || username }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Registration failed' }));
    throw new Error(data.detail || 'Registration failed');
  }
  const data: TokenResponse = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  const res = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  });

  if (!res.ok) {
    clearTokens();
    return null;
  }

  const data: TokenResponse = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data.access_token;
}

export function logout(): void {
  clearTokens();
  localStorage.removeItem('familyName');
  localStorage.removeItem('selectedChild');
}
