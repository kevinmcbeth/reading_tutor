import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ChildLoginPage from './pages/ChildLoginPage'
import StoryLibraryPage from './pages/StoryLibraryPage'
import ReadingPage from './pages/ReadingPage'
import SessionResultPage from './pages/SessionResultPage'
import ParentLoginPage from './pages/ParentLoginPage'
import ParentDashboard from './pages/ParentDashboard'
import StoryManagementPage from './pages/StoryManagementPage'
import GenerationLogsPage from './pages/GenerationLogsPage'
import QueueMonitorPage from './pages/QueueMonitorPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/parent" replace />
  return <>{children}</>
}

function ChildRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, selectedChild } = useAuth()
  if (!isAuthenticated) return <Navigate to="/parent" replace />
  if (!selectedChild) return <Navigate to="/" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/parent" element={<ParentLoginPage />} />
      <Route path="/" element={<ProtectedRoute><ChildLoginPage /></ProtectedRoute>} />
      <Route path="/library" element={<ChildRoute><StoryLibraryPage /></ChildRoute>} />
      <Route path="/read/:storyId" element={<ChildRoute><ReadingPage /></ChildRoute>} />
      <Route path="/results/:sessionId" element={<ChildRoute><SessionResultPage /></ChildRoute>} />
      <Route path="/parent/dashboard" element={<ProtectedRoute><ParentDashboard /></ProtectedRoute>} />
      <Route path="/parent/stories" element={<ProtectedRoute><StoryManagementPage /></ProtectedRoute>} />
      <Route path="/parent/queue" element={<ProtectedRoute><QueueMonitorPage /></ProtectedRoute>} />
      <Route path="/parent/logs/:jobId" element={<ProtectedRoute><GenerationLogsPage /></ProtectedRoute>} />
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App
