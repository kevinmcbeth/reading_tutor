import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ParentLoginPage() {
  const navigate = useNavigate();
  const { isAuthenticated, login, register } = useAuth();

  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // If already authenticated, redirect to dashboard
  if (isAuthenticated) {
    navigate('/parent/dashboard', { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;

    setLoading(true);
    setError('');

    try {
      if (isRegister) {
        await register(username.trim(), password, displayName.trim() || undefined);
      } else {
        await login(username.trim(), password);
      }
      navigate('/parent/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-6">
      <button
        onClick={() => navigate('/')}
        className="absolute top-4 left-4 text-gray-500 hover:text-gray-700 px-4 py-2 rounded-full bg-white shadow transition"
      >
        &larr; Back
      </button>

      <div className="bg-white rounded-3xl shadow-xl p-8 max-w-sm w-full">
        <h1 className="text-3xl font-bold text-gray-800 mb-2 text-center">
          {isRegister ? 'Create Account' : 'Parent Login'}
        </h1>
        <p className="text-gray-500 text-center mb-6">
          {isRegister ? 'Set up your family account' : 'Sign in to your family account'}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full p-3 border-2 border-gray-200 rounded-xl focus:border-blue-400 focus:outline-none text-lg"
            autoFocus
            autoComplete="username"
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full p-3 border-2 border-gray-200 rounded-xl focus:border-blue-400 focus:outline-none text-lg"
            autoComplete={isRegister ? 'new-password' : 'current-password'}
          />

          {isRegister && (
            <input
              type="text"
              placeholder="Family Display Name (optional)"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full p-3 border-2 border-gray-200 rounded-xl focus:border-blue-400 focus:outline-none text-lg"
            />
          )}

          {error && (
            <p className="text-red-500 text-center text-sm font-medium">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password.trim()}
            className="w-full py-3 bg-blue-500 text-white rounded-xl font-bold text-lg hover:bg-blue-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Please wait...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <button
          onClick={() => {
            setIsRegister(!isRegister);
            setError('');
          }}
          className="w-full mt-4 text-blue-500 hover:text-blue-700 text-sm font-medium transition"
        >
          {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
        </button>
      </div>
    </div>
  );
}
