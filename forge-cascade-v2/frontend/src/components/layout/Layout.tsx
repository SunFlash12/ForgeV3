import { useState, useEffect, useCallback } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { NetworkBackground } from '../common/NetworkBackground';
import { ConnectionBanner } from '../common/ConnectionBanner';

type ScreenSize = 'phone' | 'tablet' | 'desktop';

function getScreenSize(): ScreenSize {
  if (typeof window === 'undefined') return 'desktop';
  if (window.innerWidth < 640) return 'phone';
  if (window.innerWidth < 1024) return 'tablet';
  return 'desktop';
}

export default function Layout() {
  const { isAuthenticated, isLoading } = useAuthStore();
  const [screenSize, setScreenSize] = useState<ScreenSize>(getScreenSize);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  useEffect(() => {
    const handler = () => setScreenSize(getScreenSize());
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  // Auto-close mobile drawer when leaving phone breakpoint
  useEffect(() => {
    if (screenSize !== 'phone') setIsMobileSidebarOpen(false);
  }, [screenSize]);

  const openMobileSidebar = useCallback(() => setIsMobileSidebarOpen(true), []);
  const closeMobileSidebar = useCallback(() => setIsMobileSidebarOpen(false), []);

  const isPhone = screenSize === 'phone';
  const isTablet = screenSize === 'tablet';

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-900">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-forge-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400 font-medium">Loading Forge...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen bg-surface-900 overflow-hidden">
      <NetworkBackground />
      <div className="relative z-10 flex flex-1 overflow-hidden">
        <Sidebar
          isMobileOpen={isMobileSidebarOpen}
          onMobileClose={closeMobileSidebar}
          isPhone={isPhone}
          isTablet={isTablet}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <ConnectionBanner />
          <Header
            onOpenMobileSidebar={openMobileSidebar}
            isPhone={isPhone}
          />
          <main className="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-6 bg-transparent">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
