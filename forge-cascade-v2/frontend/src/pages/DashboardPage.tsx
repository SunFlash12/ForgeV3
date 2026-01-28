import { useQuery } from '@tanstack/react-query';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  Database,
  Activity,
  Shield,
  Zap,
  AlertTriangle,
  Vote,
  ArrowRight,
} from 'lucide-react';
import { api } from '../api/client';
import { Card, StatCard, StatusBadge, LoadingSpinner, SeverityBadge, ApiErrorState } from '../components/common';
import type { HealthStatus } from '../types';

// Fallback data for when API returns empty results (initial state)
const fallbackActivityData = [
  { time: '00:00', capsules: 0, votes: 0, events: 0 },
  { time: '04:00', capsules: 0, votes: 0, events: 0 },
  { time: '08:00', capsules: 0, votes: 0, events: 0 },
  { time: '12:00', capsules: 0, votes: 0, events: 0 },
  { time: '16:00', capsules: 0, votes: 0, events: 0 },
  { time: '20:00', capsules: 0, votes: 0, events: 0 },
];

const fallbackTrustDistribution = [
  { name: 'Core', value: 0, color: '#8b5cf6' },
  { name: 'Trusted', value: 0, color: '#22c55e' },
  { name: 'Standard', value: 0, color: '#3b82f6' },
  { name: 'Sandbox', value: 0, color: '#f59e0b' },
  { name: 'Untrusted', value: 0, color: '#ef4444' },
];

const fallbackPipelinePhases = [
  { phase: 'Validation', duration: 0 },
  { phase: 'Security', duration: 0 },
  { phase: 'Intelligence', duration: 0 },
  { phase: 'Governance', duration: 0 },
  { phase: 'Lineage', duration: 0 },
  { phase: 'Consensus', duration: 0 },
  { phase: 'Commit', duration: 0 },
];

export default function DashboardPage() {
  const { data: metrics, isLoading: metricsLoading, isError: metricsError, error: metricsErrorObj, refetch: refetchMetrics } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: () => api.getSystemMetrics(),
    refetchInterval: 10000,
  });

  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.getSystemHealth(),
    refetchInterval: 30000,
  });

  const { data: anomalies } = useQuery({
    queryKey: ['recent-anomalies'],
    queryFn: () => api.getAnomalies({ resolved: false }),
  });

  const { data: activeProposals } = useQuery({
    queryKey: ['active-proposals'],
    queryFn: () => api.getActiveProposals(),
  });

  const { data: recentCapsules } = useQuery({
    queryKey: ['recent-capsules'],
    queryFn: () => api.getRecentCapsules(5),
  });

  // Dashboard chart data from API
  const { data: activityTimeline } = useQuery({
    queryKey: ['activity-timeline'],
    queryFn: () => api.getActivityTimeline(24),
    refetchInterval: 60000, // Refresh every minute
  });

  const { data: trustDistributionData } = useQuery({
    queryKey: ['trust-distribution'],
    queryFn: () => api.getTrustDistribution(),
    refetchInterval: 120000, // Refresh every 2 minutes
  });

  const { data: pipelinePerformance } = useQuery({
    queryKey: ['pipeline-performance'],
    queryFn: () => api.getPipelinePerformance(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Use API data or fallback to empty state
  const activityData = activityTimeline?.data ?? fallbackActivityData;
  const trustDistribution = trustDistributionData?.distribution ?? fallbackTrustDistribution;
  const pipelinePhases = pipelinePerformance?.phases ?? fallbackPipelinePhases;

  if (metricsLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" label="Loading dashboard..." />
      </div>
    );
  }

  if (metricsError) {
    return (
      <div className="space-y-4 sm:space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Welcome to Forge</h1>
          <p className="text-slate-400 mt-1">Your institutional knowledge at a glance</p>
        </div>
        <ApiErrorState
          error={metricsErrorObj}
          onRetry={() => refetchMetrics()}
          title="Unable to Load Dashboard"
        />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Welcome to Forge</h1>
          <p className="text-slate-400 mt-1">Your institutional knowledge at a glance</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
          Live updates enabled
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          label="Active Capsules"
          value={metrics?.pipeline_executions || 0}
          icon={<Database className="w-5 h-5" />}
          trend={{ value: 12, isPositive: true }}
        />
        <StatCard
          label="Active Overlays"
          value={metrics?.active_overlays || 0}
          icon={<Zap className="w-5 h-5" />}
        />
        <StatCard
          label="Events Processed"
          value={(metrics?.events_processed_total || 0).toLocaleString()}
          icon={<Activity className="w-5 h-5" />}
        />
        <StatCard
          label="Active Anomalies"
          value={metrics?.active_anomalies || 0}
          icon={<AlertTriangle className="w-5 h-5" />}
          color={metrics?.active_anomalies && metrics.active_anomalies > 0 ? 'warning' : 'default'}
        />
      </div>

      {/* Health Status */}
      {health && (
        <Card>
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-slate-100">System Health</h2>
            <StatusBadge status={health.status} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            {Object.entries(health.components).map(([name, component]) => {
              const comp = component as { status: string; active_overlays?: number; total_overlays?: number };
              return (
                <div
                  key={name}
                  className="p-4 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-colors"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-slate-300 capitalize">{name.replace('_', ' ')}</span>
                    <StatusBadge status={comp.status as HealthStatus} />
                  </div>
                  {name === 'database' && (
                    <p className="text-xs text-slate-400">Neo4j Graph Database</p>
                  )}
                  {name === 'overlay_manager' && comp.active_overlays !== undefined && (
                    <p className="text-xs text-slate-400">
                      {comp.active_overlays} / {comp.total_overlays} active
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity Timeline */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-100 mb-5">Activity Timeline</h2>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={activityData}>
              <defs>
                <linearGradient id="colorCapsules" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a855f7" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f0f2e',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)',
                }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="capsules"
                stroke="#6366f1"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorCapsules)"
                name="Capsules"
              />
              <Area
                type="monotone"
                dataKey="events"
                stroke="#a855f7"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorEvents)"
                name="Events"
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        {/* Trust Distribution */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-100 mb-5">Trust Distribution</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={trustDistribution}
                cx="50%"
                cy="50%"
                innerRadius={70}
                outerRadius={110}
                paddingAngle={3}
                dataKey="value"
                label={({ name, percent }) => `${name || ''} (${((percent ?? 0) * 100).toFixed(0)}%)`}
                labelLine={false}
              >
                {trustDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f0f2e',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Pipeline Performance */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-100 mb-5">Pipeline Phase Performance</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={pipelinePhases} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis type="number" stroke="#64748b" fontSize={12} />
            <YAxis type="category" dataKey="phase" stroke="#64748b" fontSize={12} width={100} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f0f2e',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '12px',
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)',
              }}
              formatter={(value) => [`${value}ms`, 'Avg Duration']}
            />
            <Bar dataKey="duration" fill="#6366f1" radius={[0, 6, 6, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-4 flex items-center justify-center gap-2 text-sm text-slate-400">
          <Zap className="w-4 h-4 text-amber-500" />
          Average total pipeline execution: <span className="font-semibold text-slate-200">{metrics?.average_pipeline_duration_ms?.toFixed(1) || 0}ms</span>
        </div>
      </Card>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Anomalies */}
        <Card>
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-slate-100">Active Anomalies</h2>
            <span className="text-sm font-medium text-slate-400">{anomalies?.length || 0} total</span>
          </div>
          {anomalies && anomalies.length > 0 ? (
            <div className="space-y-3">
              {anomalies.slice(0, 5).map((anomaly) => (
                <div
                  key={anomaly.id}
                  className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-colors cursor-pointer"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-200">{anomaly.metric_name}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{anomaly.anomaly_type}</p>
                  </div>
                  <SeverityBadge severity={anomaly.severity} />
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-10 text-slate-400">
              <Shield className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="font-medium text-emerald-400">All Clear!</p>
              <p className="text-sm mt-1">No issues detected. Your systems are running smoothly.</p>
            </div>
          )}
        </Card>

        {/* Active Proposals */}
        <Card>
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-slate-100">Active Proposals</h2>
            <span className="text-sm font-medium text-slate-400">{activeProposals?.length || 0} active</span>
          </div>
          {activeProposals && activeProposals.length > 0 ? (
            <div className="space-y-3">
              {activeProposals.slice(0, 5).map((proposal) => (
                <div
                  key={proposal.id}
                  className="p-4 bg-white/5 rounded-xl border border-white/5 hover:border-forge-500/30 hover:bg-forge-500/5 transition-all cursor-pointer"
                >
                  <p className="text-sm font-medium text-slate-200 truncate">{proposal.title}</p>
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-xs font-medium text-slate-400 bg-white/5 px-2 py-1 rounded-lg">{proposal.proposal_type}</span>
                    <div className="flex items-center gap-3 text-xs font-medium">
                      <span className="text-emerald-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                        {proposal.votes_for}
                      </span>
                      <span className="text-red-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-red-500 rounded-full" />
                        {proposal.votes_against}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-10 text-slate-400">
              <Vote className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="font-medium">No proposals pending</p>
              <p className="text-sm mt-1">Head to Governance to propose changes to the knowledge base.</p>
            </div>
          )}
        </Card>

        {/* Recent Capsules */}
        <Card>
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-slate-100">Recent Capsules</h2>
            <a href="/capsules" className="text-sm font-medium text-cyber-blue hover:text-cyan-300 flex items-center gap-1 transition-colors">
              View all <ArrowRight className="w-4 h-4" />
            </a>
          </div>
          {recentCapsules && recentCapsules.length > 0 ? (
            <div className="space-y-3">
              {recentCapsules.map((capsule) => (
                <div
                  key={capsule.id}
                  className="p-4 bg-white/5 rounded-xl border border-white/5 hover:border-forge-500/30 hover:bg-forge-500/5 transition-all cursor-pointer"
                >
                  <p className="text-sm font-medium text-slate-200 truncate">{capsule.title}</p>
                  <div className="flex items-center justify-between mt-3">
                    <span className="inline-block px-2.5 py-1 bg-white/5 rounded-lg text-xs font-medium text-slate-400">
                      {capsule.type}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">
                      v{capsule.version}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-10 text-slate-400">
              <Database className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="font-medium">Your knowledge journey starts here</p>
              <p className="text-sm mt-1">Create your first capsule to begin building institutional memory.</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
