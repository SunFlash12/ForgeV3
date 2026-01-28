import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Database,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Clock,
  Cpu,
  Zap,
  Brain,
  Search,
  HardDrive,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import axios from 'axios';
import {
  Card,
  Button,
  LoadingSpinner,
} from '../components/common';

// Types for detailed health response
interface ComponentStatus {
  connected?: boolean;
  latency_ms?: number;
  version?: string;
  error?: string;
  provider?: string;
  is_mock?: boolean;
  operational?: boolean;
  dimensions?: number;
  type?: string;
}

interface DetailedHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  uptime_seconds: number;
  components: {
    database: ComponentStatus;
    llm_provider: ComponentStatus;
    embedding_provider: ComponentStatus;
    cache: ComponentStatus;
    event_system: ComponentStatus;
    immune_system: ComponentStatus;
  };
  warnings: string[];
  environment: string;
}

// API base URL (same derivation as useBackendHealth)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
const HEALTH_BASE_URL = new URL(API_BASE_URL).origin;

const getStatusColor = (status: string) => {
  switch (status) {
    case 'healthy': return 'text-green-400';
    case 'degraded': return 'text-amber-400';
    case 'unhealthy': return 'text-red-400';
    default: return 'text-slate-400';
  }
};

const getStatusBgColor = (status: string) => {
  switch (status) {
    case 'healthy': return 'bg-green-500/10 border-green-500/30';
    case 'degraded': return 'bg-amber-500/10 border-amber-500/30';
    case 'unhealthy': return 'bg-red-500/10 border-red-500/30';
    default: return 'bg-slate-500/10 border-slate-500/30';
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'healthy': return CheckCircle;
    case 'degraded': return AlertTriangle;
    case 'unhealthy': return XCircle;
    default: return Activity;
  }
};

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

interface ComponentCardProps {
  name: string;
  icon: typeof Database;
  status: ComponentStatus;
  isMockable?: boolean;
}

function ComponentCard({ name, icon: Icon, status, isMockable }: ComponentCardProps) {
  const isConnected = status.connected ?? status.operational ?? false;
  const isMock = isMockable && status.is_mock;

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isConnected ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
            <Icon className={`w-5 h-5 ${isConnected ? 'text-green-400' : 'text-red-400'}`} />
          </div>
          <div>
            <h3 className="font-medium text-white">{name}</h3>
            {status.provider && (
              <p className="text-sm text-slate-400">
                Provider: {status.provider}
                {isMock && <span className="ml-2 text-amber-400">(MOCK)</span>}
              </p>
            )}
            {status.latency_ms !== undefined && status.latency_ms !== null && (
              <p className="text-sm text-slate-400">Latency: {status.latency_ms}ms</p>
            )}
            {status.dimensions && (
              <p className="text-sm text-slate-400">Dimensions: {status.dimensions}</p>
            )}
            {status.type && (
              <p className="text-sm text-slate-400">Type: {status.type}</p>
            )}
            {status.error && (
              <p className="text-sm text-red-400">{status.error}</p>
            )}
          </div>
        </div>
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${
          isConnected
            ? isMock
              ? 'bg-amber-500/10 text-amber-400'
              : 'bg-green-500/10 text-green-400'
            : 'bg-red-500/10 text-red-400'
        }`}>
          {isConnected ? (isMock ? 'Mock' : 'Online') : 'Offline'}
        </div>
      </div>
    </Card>
  );
}

export default function DiagnosticsPage() {
  const queryClient = useQueryClient();

  // Fetch detailed health
  const { data: health, isLoading, isError, error, refetch } = useQuery<DetailedHealth>({
    queryKey: ['health-detailed'],
    queryFn: async () => {
      const response = await axios.get<DetailedHealth>(`${HEALTH_BASE_URL}/health/detailed`, {
        timeout: 10000,
      });
      return response.data;
    },
    refetchInterval: 15000,
    retry: 1,
  });

  // Basic connectivity check
  const { data: basicHealth, isError: basicError } = useQuery({
    queryKey: ['health-basic'],
    queryFn: async () => {
      const response = await axios.get(`${HEALTH_BASE_URL}/health`, { timeout: 5000 });
      return response.data;
    },
    refetchInterval: 10000,
    retry: 1,
  });

  const handleRefresh = () => {
    refetch();
    queryClient.invalidateQueries({ queryKey: ['health-basic'] });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const isBackendReachable = !basicError;
  const overallStatus = health?.status ?? (isBackendReachable ? 'unknown' : 'unhealthy');
  const StatusIcon = getStatusIcon(overallStatus);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">System Diagnostics</h1>
          <p className="text-slate-400 mt-1">
            Real-time status of all system components
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleRefresh}
          className="flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      {/* Overall Status Banner */}
      <Card className={`p-6 border ${getStatusBgColor(overallStatus)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-full ${getStatusBgColor(overallStatus)}`}>
              {isBackendReachable ? (
                <StatusIcon className={`w-8 h-8 ${getStatusColor(overallStatus)}`} />
              ) : (
                <WifiOff className="w-8 h-8 text-red-400" />
              )}
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">
                {isBackendReachable ? (
                  `System ${overallStatus.charAt(0).toUpperCase() + overallStatus.slice(1)}`
                ) : (
                  'Backend Unreachable'
                )}
              </h2>
              {health && (
                <div className="flex items-center gap-4 mt-1 text-sm text-slate-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    Uptime: {formatUptime(health.uptime_seconds)}
                  </span>
                  <span>Environment: {health.environment}</span>
                  <span>
                    Last check: {formatDistanceToNow(new Date(health.timestamp), { addSuffix: true })}
                  </span>
                </div>
              )}
            </div>
          </div>
          {isBackendReachable && (
            <div className="flex items-center gap-2 text-green-400">
              <Wifi className="w-5 h-5" />
              <span className="text-sm font-medium">Connected</span>
            </div>
          )}
        </div>
      </Card>

      {/* Warnings */}
      {health?.warnings && health.warnings.length > 0 && (
        <Card className="p-4 bg-amber-500/10 border-amber-500/30">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5" />
            <div>
              <h3 className="font-medium text-amber-400">Warnings</h3>
              <ul className="mt-2 space-y-1">
                {health.warnings.map((warning, index) => (
                  <li key={index} className="text-sm text-amber-300/80">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      )}

      {/* Components Grid */}
      {health ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <ComponentCard
            name="Database (Neo4j)"
            icon={Database}
            status={health.components.database}
          />
          <ComponentCard
            name="LLM Provider"
            icon={Brain}
            status={health.components.llm_provider}
            isMockable
          />
          <ComponentCard
            name="Embedding Provider"
            icon={Search}
            status={health.components.embedding_provider}
            isMockable
          />
          <ComponentCard
            name="Query Cache"
            icon={HardDrive}
            status={health.components.cache}
          />
          <ComponentCard
            name="Event System"
            icon={Zap}
            status={health.components.event_system}
          />
          <ComponentCard
            name="Immune System"
            icon={Cpu}
            status={health.components.immune_system}
          />
        </div>
      ) : isError ? (
        <Card className="p-8">
          <div className="flex flex-col items-center justify-center text-center">
            <WifiOff className="w-12 h-12 text-red-400 mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">Cannot Connect to Backend</h3>
            <p className="text-slate-400 mb-4 max-w-md">
              The backend server at {HEALTH_BASE_URL} is not responding.
              Make sure the Forge backend is running.
            </p>
            <p className="text-sm text-slate-500 mb-4">
              Error: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
            <Button onClick={handleRefresh} variant="primary">
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry Connection
            </Button>
          </div>
        </Card>
      ) : null}

      {/* Endpoints Info */}
      <Card className="p-4">
        <h3 className="font-medium text-white mb-3">Health Endpoints</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-2">
            <code className="px-2 py-1 bg-surface-700 rounded text-forge-400">GET /health</code>
            <span className="text-slate-400">Basic liveness</span>
          </div>
          <div className="flex items-center gap-2">
            <code className="px-2 py-1 bg-surface-700 rounded text-forge-400">GET /ready</code>
            <span className="text-slate-400">Readiness + DB check</span>
          </div>
          <div className="flex items-center gap-2">
            <code className="px-2 py-1 bg-surface-700 rounded text-forge-400">GET /health/detailed</code>
            <span className="text-slate-400">Full diagnostics</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
