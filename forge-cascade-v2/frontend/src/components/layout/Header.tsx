import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Bell, AlertCircle, CheckCircle, AlertTriangle, RefreshCw } from 'lucide-react';
import api from '../../api/client';

export function Header() {
  const [searchQuery, setSearchQuery] = useState('');

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.getSystemHealth(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: anomalies } = useQuery({
    queryKey: ['active-anomalies'],
    queryFn: () => api.getAnomalies({ resolved: false }),
    refetchInterval: 60000,
  });

  const unresolvedCount = anomalies?.length || 0;

  const getStatusIcon = () => {
    if (healthLoading) {
      return <RefreshCw className="w-4 h-4 text-slate-400 animate-spin" />;
    }
    switch (health?.status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case 'degraded':
        return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      case 'unhealthy':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <AlertCircle className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusText = () => {
    if (healthLoading) return 'Checking...';
    switch (health?.status) {
      case 'healthy': return 'All Systems Operational';
      case 'degraded': return 'Degraded Performance';
      case 'unhealthy': return 'System Issues Detected';
      default: return 'Status Unknown';
    }
  };

  const getStatusBg = () => {
    switch (health?.status) {
      case 'healthy': return 'bg-emerald-50 border-emerald-200 text-emerald-700';
      case 'degraded': return 'bg-amber-50 border-amber-200 text-amber-700';
      case 'unhealthy': return 'bg-red-50 border-red-200 text-red-700';
      default: return 'bg-slate-50 border-slate-200 text-slate-600';
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Navigate to search results
      window.location.href = `/capsules?search=${encodeURIComponent(searchQuery)}`;
    }
  };

  return (
    <header className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur-sm px-6 flex items-center justify-between">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex-1 max-w-xl" role="search">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search capsules, governance, or system..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search capsules, governance, or system"
            className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 placeholder-slate-400 focus:outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 transition-all"
          />
        </div>
      </form>

      {/* Status & Notifications */}
      <div className="flex items-center gap-3">
        {/* System Status */}
        <button
          type="button"
          onClick={() => refetchHealth()}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl border transition-all hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 ${getStatusBg()}`}
          aria-label={`System status: ${getStatusText()}. Click to refresh`}
        >
          {getStatusIcon()}
          <span className="text-sm font-medium">{getStatusText()}</span>
        </button>

        {/* Notifications */}
        <button
          type="button"
          className="relative p-2.5 rounded-xl hover:bg-slate-100 transition-colors border border-transparent hover:border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
          aria-label={unresolvedCount > 0 ? `Notifications: ${unresolvedCount} unresolved anomalies` : 'Notifications: No new alerts'}
        >
          <Bell className="w-5 h-5 text-slate-500" aria-hidden="true" />
          {unresolvedCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs text-white flex items-center justify-center font-semibold shadow-lg shadow-red-500/30" aria-hidden="true">
              {unresolvedCount > 9 ? '9+' : unresolvedCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
