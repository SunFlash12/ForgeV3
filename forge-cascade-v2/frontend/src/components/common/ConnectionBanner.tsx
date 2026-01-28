import { WifiOff, Loader2, RefreshCw, AlertTriangle, X } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useBackendHealth } from '../../hooks/useBackendHealth';

export function ConnectionBanner() {
  const { status, backendStatus, isUsingMockLLM, isUsingMockEmbeddings } = useBackendHealth();
  const queryClient = useQueryClient();
  const [dismissedMockWarning, setDismissedMockWarning] = useState(false);

  // Don't flash banner during initial load
  if (status === 'checking') {
    return null;
  }

  const handleRetry = () => {
    queryClient.invalidateQueries({ queryKey: ['backend-health-ping'] });
    queryClient.invalidateQueries({ queryKey: ['backend-health-detailed'] });
  };

  // Backend is unreachable - highest priority
  if (status === 'disconnected') {
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

  // Connected but using mock providers - show dismissible warning
  const hasMockProviders = isUsingMockLLM || isUsingMockEmbeddings;
  if (status === 'connected' && hasMockProviders && !dismissedMockWarning) {
    const mockDetails = [
      isUsingMockLLM && 'LLM',
      isUsingMockEmbeddings && 'Embeddings',
    ].filter(Boolean).join(' & ');

    return (
      <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center justify-center gap-3 text-sm">
        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
        <span className="text-amber-300/90">
          Running with mock {mockDetails} provider{isUsingMockLLM && isUsingMockEmbeddings ? 's' : ''}.
          AI features may be limited.
        </span>
        <button
          onClick={() => setDismissedMockWarning(true)}
          className="text-amber-400/60 hover:text-amber-300 flex-shrink-0 p-0.5"
          aria-label="Dismiss warning"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  // All good — render nothing
  return null;
}
