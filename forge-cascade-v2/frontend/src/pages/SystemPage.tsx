import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Server,
  Database,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Clock,
  Shield,
  Zap,
  ChevronRight,
  Power,
  Loader2,
  Lock,
  AlertCircle,
} from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { format, formatDistanceToNow } from 'date-fns';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';
import { api } from '../api/client';
import type { Anomaly, SystemHealth, CircuitBreaker } from '../types';
import {
  Card,
  Button,
  SeverityBadge,
  LoadingSpinner,
  EmptyState,
  Modal,
} from '../components/common';

// Component icon mapping
const componentIcons: Record<string, typeof Database> = {
  database: Database,
  event_system: Zap,
  overlay_manager: Activity,
  circuit_breakers: Shield,
  anomaly_system: AlertTriangle,
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'healthy': return 'text-green-400';
    case 'degraded': return 'text-amber-400';
    case 'unhealthy': return 'text-red-400';
    default: return 'text-slate-500';
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

export default function SystemPage() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);
  const [showResolveModal, setShowResolveModal] = useState(false);
  const [resolveNotes, setResolveNotes] = useState('');
  const [showMaintenanceModal, setShowMaintenanceModal] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState('System is undergoing scheduled maintenance. Please check back later.');
  const [maintenanceDuration, setMaintenanceDuration] = useState(60);

  const isCore = user?.trust_level === 'CORE';

  // Queries
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.getSystemHealth(),
    refetchInterval: 30000,
  });

  const { data: metrics } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: () => api.getSystemMetrics(),
    refetchInterval: 10000,
  });

  const { data: anomalies = [] } = useQuery({
    queryKey: ['anomalies'],
    queryFn: () => api.getAnomalies({ resolved: false }),
    refetchInterval: 30000,
  });

  const { data: circuitBreakers = [] } = useQuery({
    queryKey: ['circuit-breakers'],
    queryFn: () => api.getCircuitBreakers(),
    refetchInterval: 15000,
  });

  const { data: maintenanceStatus, isLoading: maintenanceLoading } = useQuery({
    queryKey: ['maintenance-status'],
    queryFn: () => api.getMaintenanceStatus(),
    refetchInterval: 30000,
  });

  // Mutations
  const acknowledgeMutation = useMutation({
    mutationFn: (id: string) => api.acknowledgeAnomaly(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['anomalies'] }),
  });

  const resolveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) => api.resolveAnomaly(id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      setShowResolveModal(false);
      setSelectedAnomaly(null);
      setResolveNotes('');
    },
  });

  const resetBreakerMutation = useMutation({
    mutationFn: (name: string) => api.resetCircuitBreaker(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['circuit-breakers'] }),
  });

  const enableMaintenanceMutation = useMutation({
    mutationFn: (options: { message?: string; duration_minutes?: number }) => api.enableMaintenance(options),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance-status'] });
      setShowMaintenanceModal(false);
    },
  });

  const disableMaintenanceMutation = useMutation({
    mutationFn: () => api.disableMaintenance(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['maintenance-status'] }),
  });

  // Mock historical data for charts (stable placeholder values)
  const chartData = useMemo(() => Array.from({ length: 24 }, (_, i) => ({
    time: `${i}:00`,
    events: 50 + (i * 3) % 40,  // Deterministic pattern
    errors: i % 5,              // Deterministic pattern
    latency: 20 + (i * 2) % 30, // Deterministic pattern
  })), []);

  if (healthLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" label="Loading system status..." />
      </div>
    );
  }

  const healthData = health as SystemHealth | undefined;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 mb-2">System Monitor</h1>
          <p className="text-slate-500">
            Real-time system health and performance monitoring
          </p>
        </div>
        <Button
          variant="ghost"
          icon={<RefreshCw className="w-4 h-4" />}
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['system-health'] });
            queryClient.invalidateQueries({ queryKey: ['system-metrics'] });
            queryClient.invalidateQueries({ queryKey: ['anomalies'] });
          }}
        >
          Refresh All
        </Button>
      </div>

      {/* Overall Status */}
      <Card className="p-6 mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl ${
              healthData?.status === 'healthy' ? 'bg-green-500/20' :
              healthData?.status === 'degraded' ? 'bg-amber-500/20' : 'bg-red-500/20'
            }`}>
              <Server className={`w-8 h-8 ${getStatusColor(healthData?.status || 'unknown')}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold text-slate-800">System Status</h2>
                <span className={`px-2 py-1 rounded text-sm font-medium capitalize ${
                  healthData?.status === 'healthy' ? 'bg-green-500/20 text-green-400' :
                  healthData?.status === 'degraded' ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'
                }`}>
                  {healthData?.status || 'Unknown'}
                </span>
              </div>
              <p className="text-slate-500">
                Uptime: {healthData?.uptime_seconds ? `${Math.floor(healthData.uptime_seconds / 3600)}h ${Math.floor((healthData.uptime_seconds % 3600) / 60)}m` : 'N/A'}
                {healthData?.timestamp && ` • Last check: ${format(new Date(healthData.timestamp), 'HH:mm:ss')}`}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-500">Version</div>
            <div className="text-slate-800 font-mono">{healthData?.version || 'N/A'}</div>
          </div>
        </div>
      </Card>

      {/* Maintenance Mode */}
      <Card className="p-6 mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl ${
              maintenanceStatus?.enabled ? 'bg-amber-500/20' : 'bg-slate-100'
            }`}>
              <Power className={`w-8 h-8 ${
                maintenanceStatus?.enabled ? 'text-amber-500' : 'text-slate-400'
              }`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold text-slate-800">Maintenance Mode</h2>
                {maintenanceLoading ? (
                  <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
                ) : (
                  <span className={`px-2 py-1 rounded text-sm font-medium ${
                    maintenanceStatus?.enabled
                      ? 'bg-amber-500/20 text-amber-600'
                      : 'bg-green-500/20 text-green-600'
                  }`}>
                    {maintenanceStatus?.enabled ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                )}
              </div>
              <p className="text-slate-500 mt-1">
                {maintenanceStatus?.enabled
                  ? maintenanceStatus.message || 'System is under maintenance'
                  : 'System is operating normally'}
              </p>
              {maintenanceStatus?.enabled && maintenanceStatus.ends_at && (
                <p className="text-sm text-amber-600 mt-1">
                  Ends: {format(new Date(maintenanceStatus.ends_at), 'PPpp')}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {!isCore ? (
              <div className="flex items-center gap-2 text-slate-500">
                <Lock className="w-4 h-4" />
                <span className="text-sm">CORE access required</span>
              </div>
            ) : maintenanceStatus?.enabled ? (
              <Button
                variant="secondary"
                icon={<Power className="w-4 h-4" />}
                onClick={() => disableMaintenanceMutation.mutate()}
                loading={disableMaintenanceMutation.isPending}
              >
                Disable Maintenance
              </Button>
            ) : (
              <Button
                variant="primary"
                icon={<AlertCircle className="w-4 h-4" />}
                onClick={() => setShowMaintenanceModal(true)}
              >
                Enable Maintenance Mode
              </Button>
            )}
          </div>
        </div>

        {/* Active Maintenance Details */}
        {maintenanceStatus?.enabled && (
          <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h4 className="font-medium text-amber-800">Maintenance Active</h4>
                <p className="text-sm text-amber-700 mt-1">
                  External users and non-essential services are restricted during maintenance.
                  Only CORE and TRUSTED users have access to critical functions.
                </p>
                {maintenanceStatus.started_at && (
                  <p className="text-xs text-amber-600 mt-2">
                    Started: {formatDistanceToNow(new Date(maintenanceStatus.started_at))} ago
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Activity className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">{metrics?.events_processed_total || 0}</div>
              <div className="text-xs text-slate-500">Events Processed</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <Zap className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">{metrics?.active_overlays || 0}</div>
              <div className="text-xs text-slate-500">Active Overlays</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Clock className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">{metrics?.average_pipeline_duration_ms?.toFixed(0) || 0}ms</div>
              <div className="text-xs text-slate-500">Avg Pipeline Time</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">{metrics?.active_anomalies || 0}</div>
              <div className="text-xs text-slate-500">Active Anomalies</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <Shield className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">{metrics?.open_circuit_breakers || 0}</div>
              <div className="text-xs text-slate-500">Open Breakers</div>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-8">
        {/* Component Health */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">Component Health</h3>
          <div className="space-y-3">
            {healthData?.components && Object.entries(healthData.components).map(([name, component]) => {
              const Icon = componentIcons[name] || Activity;
              // ComponentHealth type has status field - safely access it
              const componentStatus = component.status || 'unknown';
              const StatusIcon = getStatusIcon(componentStatus);
              return (
                <div key={name} className="flex items-center justify-between p-3 bg-slate-100/30 rounded-lg">
                  <div className="flex items-center gap-3">
                    <Icon className="w-5 h-5 text-slate-500" />
                    <span className="text-slate-800 capitalize">{name.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusIcon className={`w-5 h-5 ${getStatusColor(componentStatus)}`} />
                    <span className={`text-sm capitalize ${getStatusColor(componentStatus)}`}>
                      {componentStatus}
                    </span>
                  </div>
                </div>
              );
            })}
            {(!healthData?.components || Object.keys(healthData.components).length === 0) && (
              <p className="text-slate-500 text-center py-4">No component data available</p>
            )}
          </div>
        </Card>

        {/* Circuit Breakers */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">Circuit Breakers</h3>
          <div className="space-y-3">
            {circuitBreakers.map((breaker: CircuitBreaker) => (
              <div key={breaker.name} className="flex items-center justify-between p-3 bg-slate-100/30 rounded-lg">
                <div className="flex items-center gap-3">
                  <Shield className={`w-5 h-5 ${
                    breaker.state === 'CLOSED' ? 'text-green-400' :
                    breaker.state === 'HALF_OPEN' ? 'text-amber-400' : 'text-red-400'
                  }`} />
                  <div>
                    <span className="text-slate-800">{breaker.name}</span>
                    <div className="text-xs text-slate-500">
                      {breaker.failure_count} failures / {breaker.success_count} successes
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    breaker.state === 'CLOSED' ? 'bg-green-500/20 text-green-400' :
                    breaker.state === 'HALF_OPEN' ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {breaker.state}
                  </span>
                  {breaker.state !== 'CLOSED' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => resetBreakerMutation.mutate(breaker.name)}
                      loading={resetBreakerMutation.isPending}
                    >
                      Reset
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {circuitBreakers.length === 0 && (
              <p className="text-slate-500 text-center py-4">No circuit breakers configured</p>
            )}
          </div>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">Event Processing (24h)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                labelStyle={{ color: '#f8fafc' }}
              />
              <Area type="monotone" dataKey="events" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">Response Latency (24h)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                labelStyle={{ color: '#f8fafc' }}
              />
              <Line type="monotone" dataKey="latency" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Active Anomalies */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-800">Active Anomalies</h3>
          <span className="text-sm text-slate-500">{anomalies.length} unresolved</span>
        </div>

        {anomalies.length > 0 ? (
          <div className="space-y-3">
            {anomalies.map((anomaly: Anomaly) => (
              <div
                key={anomaly.id}
                className="flex items-center justify-between p-4 bg-slate-100/30 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
                onClick={() => setSelectedAnomaly(anomaly)}
              >
                <div className="flex items-center gap-4">
                  <SeverityBadge severity={anomaly.severity} />
                  <div>
                    <div className="text-slate-800 font-medium">{anomaly.metric_name}</div>
                    <div className="text-sm text-slate-500">
                      {anomaly.anomaly_type} • Score: {anomaly.anomaly_score.toFixed(2)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right text-sm">
                    <div className="text-slate-500">
                      {formatDistanceToNow(new Date(anomaly.detected_at))} ago
                    </div>
                    {anomaly.acknowledged && (
                      <div className="text-amber-400">Acknowledged</div>
                    )}
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-500" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<CheckCircle className="w-12 h-12" />}
            title="No Active Anomalies"
            description="All systems operating normally"
          />
        )}
      </Card>

      {/* Anomaly Detail Modal */}
      <Modal
        isOpen={!!selectedAnomaly}
        onClose={() => setSelectedAnomaly(null)}
        title="Anomaly Details"
        size="lg"
      >
        {selectedAnomaly && (
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <SeverityBadge severity={selectedAnomaly.severity} />
              <div>
                <h3 className="text-lg font-medium text-slate-800">{selectedAnomaly.metric_name}</h3>
                <p className="text-sm text-slate-500">{selectedAnomaly.anomaly_type}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-slate-100/30 rounded-lg">
                <div className="text-sm text-slate-500 mb-1">Actual Value</div>
                <div className="text-xl font-bold text-slate-800">{selectedAnomaly.value.toFixed(2)}</div>
              </div>
              <div className="p-4 bg-slate-100/30 rounded-lg">
                <div className="text-sm text-slate-500 mb-1">Expected Value</div>
                <div className="text-xl font-bold text-slate-800">
                  {selectedAnomaly.expected_value?.toFixed(2) || 'N/A'}
                </div>
              </div>
              <div className="p-4 bg-slate-100/30 rounded-lg">
                <div className="text-sm text-slate-500 mb-1">Anomaly Score</div>
                <div className="text-xl font-bold text-slate-800">{selectedAnomaly.anomaly_score.toFixed(3)}</div>
              </div>
              <div className="p-4 bg-slate-100/30 rounded-lg">
                <div className="text-sm text-slate-500 mb-1">Detected</div>
                <div className="text-slate-800">{format(new Date(selectedAnomaly.detected_at), 'PPpp')}</div>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              {!selectedAnomaly.acknowledged && (
                <Button
                  variant="secondary"
                  onClick={() => acknowledgeMutation.mutate(selectedAnomaly.id)}
                  loading={acknowledgeMutation.isPending}
                >
                  Acknowledge
                </Button>
              )}
              <Button
                onClick={() => setShowResolveModal(true)}
              >
                Resolve
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Resolve Modal */}
      <Modal
        isOpen={showResolveModal}
        onClose={() => setShowResolveModal(false)}
        title="Resolve Anomaly"
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="label">Resolution Notes</label>
            <textarea
              className="input min-h-[100px]"
              value={resolveNotes}
              onChange={(e) => setResolveNotes(e.target.value)}
              placeholder="Describe how this anomaly was resolved..."
            />
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setShowResolveModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => selectedAnomaly && resolveMutation.mutate({ id: selectedAnomaly.id, notes: resolveNotes })}
              loading={resolveMutation.isPending}
            >
              Mark as Resolved
            </Button>
          </div>
        </div>
      </Modal>

      {/* Enable Maintenance Mode Modal */}
      <Modal
        isOpen={showMaintenanceModal}
        onClose={() => setShowMaintenanceModal(false)}
        title="Enable Maintenance Mode"
        size="md"
      >
        <div className="space-y-6">
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-medium text-amber-800">Warning</h4>
                <p className="text-sm text-amber-700 mt-1">
                  Enabling maintenance mode will restrict access for most users. Only CORE and
                  TRUSTED users will have limited access to critical functions.
                </p>
              </div>
            </div>
          </div>

          <div>
            <label className="label">Maintenance Message</label>
            <textarea
              className="input min-h-[80px]"
              value={maintenanceMessage}
              onChange={(e) => setMaintenanceMessage(e.target.value)}
              placeholder="Message to display to users..."
            />
            <p className="text-xs text-slate-500 mt-1">
              This message will be shown to users attempting to access the system.
            </p>
          </div>

          <div>
            <label className="label">Duration (minutes)</label>
            <div className="flex items-center gap-4">
              <input
                type="number"
                className="input w-32"
                value={maintenanceDuration}
                onChange={(e) => setMaintenanceDuration(parseInt(e.target.value) || 60)}
                min={1}
                max={1440}
              />
              <div className="flex gap-2">
                {[30, 60, 120, 240].map((mins) => (
                  <button
                    key={mins}
                    type="button"
                    onClick={() => setMaintenanceDuration(mins)}
                    className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                      maintenanceDuration === mins
                        ? 'bg-sky-100 border-sky-300 text-sky-700'
                        : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {mins < 60 ? `${mins}m` : `${mins / 60}h`}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Maintenance will automatically end after this duration.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
            <Button variant="ghost" onClick={() => setShowMaintenanceModal(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              icon={<Power className="w-4 h-4" />}
              onClick={() => enableMaintenanceMutation.mutate({
                message: maintenanceMessage,
                duration_minutes: maintenanceDuration,
              })}
              loading={enableMaintenanceMutation.isPending}
            >
              Enable Maintenance Mode
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
