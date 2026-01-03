import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useAuthStore } from './stores/authStore';
import Layout from './components/layout/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import CapsulesPage from './pages/CapsulesPage';
import GovernancePage from './pages/GovernancePage';
import GhostCouncilPage from './pages/GhostCouncilPage';
import OverlaysPage from './pages/OverlaysPage';
import SystemPage from './pages/SystemPage';
import SettingsPage from './pages/SettingsPage';

function App() {
  const { isAuthenticated, fetchCurrentUser, isLoading } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
      fetchCurrentUser();
    }
  }, [isAuthenticated, fetchCurrentUser]);

  if (isLoading && isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-forge-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-400">Loading Forge...</p>
        </div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="capsules" element={<CapsulesPage />} />
        <Route path="governance" element={<GovernancePage />} />
        <Route path="ghost-council" element={<GhostCouncilPage />} />
        <Route path="overlays" element={<OverlaysPage />} />
        <Route path="system" element={<SystemPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
