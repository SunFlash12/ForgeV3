import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Layers,
  Play,
  Pause,
  Activity,
  CheckCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Zap,
  Shield,
  Brain,
  GitBranch,
  Eye,
} from 'lucide-react';
import { api } from '../api/client';
import type { Overlay, OverlayMetrics, CanaryDeployment } from '../types';
import {
  Card,
  Button,
  LoadingSpinner,
  EmptyState,
  Modal,
  ProgressBar,
} from '../components/common';

// Overlay icon mapping
const overlayIcons: Record<string, typeof Shield> = {
  security_validator: Shield,
  ml_intelligence: Brain,
  governance: GitBranch,
  lineage_tracker: Eye,
};

export default function OverlaysPage() {
  const queryClient = useQueryClient();
  const [expandedOverlays, setExpandedOverlays] = useState<Set<string>>(new Set());
  const [showCanaryModal, setShowCanaryModal] = useState(false);
  const [selectedOverlayForCanary, setSelectedOverlayForCanary] = useState<Overlay | null>(null);

  // Fetch all overlays
  const { data: overlays = [], isLoading } = useQuery({
    queryKey: ['overlays'],
    queryFn: () => api.listOverlays(),
  });

  // Fetch metrics for each overlay
  const { data: metricsMap = {} } = useQuery({
    queryKey: ['overlay-metrics', overlays.map((o: Overlay) => o.id)],
    queryFn: async () => {
      const metrics: Record<string, OverlayMetrics> = {};
      for (const overlay of overlays) {
        try {
          metrics[overlay.id] = await api.getOverlayMetrics(overlay.id);
        } catch {
          // Ignore errors for individual metrics
        }
      }
      return metrics;
    },
    enabled: overlays.length > 0,
  });

  // Fetch canary statuses
  const { data: canaryMap = {} } = useQuery({
    queryKey: ['canary-status', overlays.map((o: Overlay) => o.id)],
    queryFn: async () => {
      const canaries: Record<string, CanaryDeployment | null> = {};
      for (const overlay of overlays) {
        try {
          canaries[overlay.id] = await api.getCanaryStatus(overlay.id);
        } catch {
          canaries[overlay.id] = null;
        }
      }
      return canaries;
    },
    enabled: overlays.length > 0,
  });

  // Mutations
  const activateMutation = useMutation({
    mutationFn: (id: string) => api.activateOverlay(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['overlays'] }),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api.deactivateOverlay(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['overlays'] }),
  });

  const startCanaryMutation = useMutation({
    mutationFn: (id: string) => api.startCanary(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canary-status'] });
      setShowCanaryModal(false);
    },
  });

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedOverlays);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedOverlays(newExpanded);
  };

  const getIcon = (name: string) => {
    return overlayIcons[name] || Layers;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" label="Loading overlays..." />
      </div>
    );
  }

  if (overlays.length === 0) {
    return (
      <div className="px-3 sm:px-4 lg:px-6 py-4 sm:py-6 max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-100 mb-2">Overlay Management</h1>
          <p className="text-slate-400">Manage system overlays and intelligence modules</p>
        </div>
        <EmptyState
          icon={<Layers className="w-12 h-12" />}
          title="No Overlays Registered"
          description="No overlay modules have been registered in the system yet. Overlays provide modular intelligence capabilities like security validation, ML processing, and lineage tracking."
        />
      </div>
    );
  }

  const activeCount = overlays.filter((o: Overlay) => o.enabled).length;

  return (
    <div className="px-3 sm:px-4 lg:px-6 py-4 sm:py-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 mb-2">Overlay Management</h1>
          <p className="text-slate-400">
            {activeCount} of {overlays.length} overlays active
          </p>
        </div>
        <Button
          variant="ghost"
          icon={<RefreshCw className="w-4 h-4" />}
          onClick={() => queryClient.invalidateQueries({ queryKey: ['overlays'] })}
        >
          Refresh
        </Button>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Layers className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">{overlays.length}</div>
              <div className="text-sm text-slate-400">Total Overlays</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">{activeCount}</div>
              <div className="text-sm text-slate-400">Active</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Activity className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">
                {Object.values(canaryMap).filter(c => c !== null).length}
              </div>
              <div className="text-sm text-slate-400">Canary Deployments</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Zap className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">
                {Object.values(metricsMap).reduce((sum, m) => sum + (m?.total_executions || 0), 0)}
              </div>
              <div className="text-sm text-slate-400">Total Executions</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Overlay List */}
      <div className="space-y-4">
        {overlays.map((overlay: Overlay) => {
          const Icon = getIcon(overlay.name);
          const metrics = metricsMap[overlay.id];
          const canary = canaryMap[overlay.id];
          const isExpanded = expandedOverlays.has(overlay.id);

          return (
            <Card key={overlay.id} className="overflow-hidden">
              {/* Header Row */}
              <div
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors"
                onClick={() => toggleExpanded(overlay.id)}
              >
                <div className="flex items-center gap-4">
                  <div className={`p-2 rounded-lg ${overlay.enabled ? 'bg-green-500/20' : 'bg-white/5'}`}>
                    <Icon className={`w-5 h-5 ${overlay.enabled ? 'text-green-400' : 'text-slate-400'}`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-slate-100">{overlay.name}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded ${overlay.enabled ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-slate-400'}`}>
                        {overlay.enabled ? 'Active' : 'Inactive'}
                      </span>
                      {overlay.critical && (
                        <span className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400">Critical</span>
                      )}
                      {canary && (
                        <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">Canary</span>
                      )}
                    </div>
                    <p className="text-sm text-slate-400">{overlay.description}</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right text-sm">
                    <div className="text-slate-400">Phase {overlay.phase}</div>
                    <div className="text-slate-400">Priority: {overlay.priority}</div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-5 h-5 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-slate-400" />
                  )}
                </div>
              </div>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="border-t border-white/10 p-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Metrics */}
                    <div>
                      <h4 className="text-sm font-medium text-slate-400 mb-3">Performance Metrics</h4>
                      {metrics ? (
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-slate-400">Total Executions</span>
                            <span className="text-slate-100">{metrics.total_executions}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Success Rate</span>
                            <span className={metrics.error_rate < 0.05 ? 'text-green-400' : 'text-amber-400'}>
                              {((1 - metrics.error_rate) * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Avg Duration</span>
                            <span className="text-slate-100">{metrics.average_duration_ms.toFixed(1)}ms</span>
                          </div>
                        </div>
                      ) : (
                        <p className="text-slate-400">No metrics available</p>
                      )}
                    </div>

                    {/* Canary Status */}
                    <div>
                      <h4 className="text-sm font-medium text-slate-400 mb-3">Canary Deployment</h4>
                      {canary ? (
                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-slate-400">Stage</span>
                            <span className="text-slate-100">{canary.current_stage}/{canary.total_stages}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Traffic</span>
                            <span className="text-slate-100">{canary.traffic_percentage}%</span>
                          </div>
                          <ProgressBar
                            value={(canary.current_stage / canary.total_stages) * 100}
                            color="amber"
                            size="sm"
                          />
                        </div>
                      ) : (
                        <p className="text-slate-400">No active canary</p>
                      )}
                    </div>

                    {/* Actions */}
                    <div>
                      <h4 className="text-sm font-medium text-slate-400 mb-3">Actions</h4>
                      <div className="flex flex-wrap gap-2">
                        {overlay.enabled ? (
                          <Button
                            variant="secondary"
                            size="sm"
                            icon={<Pause className="w-4 h-4" />}
                            onClick={() => deactivateMutation.mutate(overlay.id)}
                            loading={deactivateMutation.isPending}
                            disabled={overlay.critical}
                          >
                            Deactivate
                          </Button>
                        ) : (
                          <Button
                            variant="primary"
                            size="sm"
                            icon={<Play className="w-4 h-4" />}
                            onClick={() => activateMutation.mutate(overlay.id)}
                            loading={activateMutation.isPending}
                          >
                            Activate
                          </Button>
                        )}
                        {!canary && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedOverlayForCanary(overlay);
                              setShowCanaryModal(true);
                            }}
                          >
                            Start Canary
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Canary Modal */}
      <Modal
        isOpen={showCanaryModal}
        onClose={() => setShowCanaryModal(false)}
        title="Start Canary Deployment"
        size="sm"
      >
        {selectedOverlayForCanary && (
          <div className="space-y-4">
            <p className="text-slate-400">
              Start a canary deployment for <span className="text-slate-100 font-medium">{selectedOverlayForCanary.name}</span>?
              This will gradually roll out changes while monitoring for issues.
            </p>

            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-slate-400 mb-2">Deployment Stages</div>
              <div className="flex gap-2">
                {[10, 25, 50, 75, 100].map((stage) => (
                  <div key={stage} className="flex-1 text-center">
                    <div className="h-2 bg-slate-600 rounded-full mb-1" />
                    <span className="text-xs text-slate-400">{stage}%</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button variant="ghost" onClick={() => setShowCanaryModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => startCanaryMutation.mutate(selectedOverlayForCanary.id)}
                loading={startCanaryMutation.isPending}
              >
                Start Canary
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
