import { createContext, useContext, useState, ReactNode, useCallback } from 'react';
import * as auth from '../services/auth';

interface SelectedChild {
  id: string;
  name: string;
  avatar: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  familyName: string | null;
  selectedChild: SelectedChild | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  selectChild: (child: SelectedChild) => void;
  clearChild: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => !!auth.getAccessToken());
  const [familyName, setFamilyName] = useState<string | null>(
    () => localStorage.getItem('familyName'),
  );
  const [selectedChild, setSelectedChild] = useState<SelectedChild | null>(() => {
    const stored = localStorage.getItem('selectedChild');
    if (!stored) return null;
    try {
      return JSON.parse(stored);
    } catch {
      return null;
    }
  });

  const handleLogin = useCallback(async (username: string, password: string) => {
    const data = await auth.login(username, password);
    setIsAuthenticated(true);
    const name = data.display_name || username;
    setFamilyName(name);
    localStorage.setItem('familyName', name);
  }, []);

  const handleRegister = useCallback(
    async (username: string, password: string, displayName?: string) => {
      const data = await auth.register(username, password, displayName);
      setIsAuthenticated(true);
      const name = data.display_name || displayName || username;
      setFamilyName(name);
      localStorage.setItem('familyName', name);
    },
    [],
  );

  const handleLogout = useCallback(() => {
    auth.logout();
    setIsAuthenticated(false);
    setFamilyName(null);
    setSelectedChild(null);
  }, []);

  const selectChild = useCallback((child: SelectedChild) => {
    setSelectedChild(child);
    localStorage.setItem('selectedChild', JSON.stringify(child));
  }, []);

  const clearChild = useCallback(() => {
    setSelectedChild(null);
    localStorage.removeItem('selectedChild');
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        familyName,
        selectedChild,
        login: handleLogin,
        register: handleRegister,
        logout: handleLogout,
        selectChild,
        clearChild,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
