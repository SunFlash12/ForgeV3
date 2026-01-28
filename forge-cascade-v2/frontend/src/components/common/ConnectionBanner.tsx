import { WifiOff, Loader2, RefreshCw } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useBackendHealth } from '../../hooks/useBackendHealth';

export function ConnectionBanner() {
  const { status, backendStatus } = useBackendHealth();
  const queryClient = useQueryClient();

  // Don't flash banner during initial load
  if (status === 'checking') {
    return null;
  }

  // All good — render nothing
  if (status === 'connected' && backendStatus !== 'starting') {
    return null;
  }

  const handleRetry = () => {
    queryClient.invalidateQueries({ queryKey: ['backend-health-ping'] });
  };

  // Backend is starting up
  if (status === 'connected' && backendStatus === 'starting') {
    return (
      <div className="bg-amber-500/15 border-b border-amber-500/30 px-4 py-2 flex items-center justify-center gap-3 text-sm">
        <Loader2 className="w-4 h-4 text-amber-400 animate-spin flex-shrink-0" />
        <span className="text-amber-300">
          Forge backend is starting up. Data may be unavailable momentarily.
        </span>
      </div>
    );
  }

  // Backend is unreachable
  return (
    <div className="bg-red-500/15 border-b border-red-500/30 px-4 py-2 flex items-center justify-center gap-3 text-sm">
      <WifiOff className="w-4 h-4 text-red-400 flex-shrink-0" />
      <span className="text-red-300">
        Cannot connect to Forge backend. Data on this page may be stale or unavailable.
      </span>
      <button
        onClick={handleRetry}
        className="text-red-300 hover:text-red-200 underline underline-offset-2 flex items-center gap-1 flex-shrink-0"
      >
        <RefreshCw className="w-3 h-3" />
        Retry
      </button>
    </div>
  );
}
