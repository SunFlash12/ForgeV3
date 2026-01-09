import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Globe,
  Plus,
  RefreshCw,
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Link2,
  TrendingUp,
  TrendingDown,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Trash2,
} from 'lucide-react';
import { api } from '../api/client';
import {
  Card,
  Button,
  Badge,
  Modal,
  EmptyState,
} from '../components/common';

// Types
interface FederatedPeer {
  id: string;
  name: string;
  url: string;
  public_key: string;
  trust_score: number;
  trust_tier: string;
  status: 'pending' | 'active' | 'degraded' | 'suspended' | 'offline' | 'revoked';
  sync_direction: 'push' | 'pull' | 'bidirectional';
  sync_interval_minutes: number;
  conflict_resolution: string;
  sync_capsule_types: string[];
  min_trust_to_sync: number;
  description: string | null;
  admin_contact: string | null;
  registered_at: string;
  last_sync_at: string | null;
  last_seen_at: string | null;
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
  capsules_received: number;
  capsules_sent: number;
}

interface SyncState {
  id: string;
  peer_id: string;
  peer_name: string;
  direction: string;
  status: string;
  phase: string;
  started_at: string;
  completed_at: string | null;
  capsules_fetched: number;
  capsules_created: number;
  capsules_updated: number;
  capsules_skipped: number;
  capsules_conflicted: number;
  error_message: string | null;
}

interface FederationStats {
  total_peers: number;
  active_peers: number;
  pending_peers: number;
  total_federated_capsules: number;
  synced_capsules: number;
  pending_capsules: number;
  conflicted_capsules: number;
  network_health: {
    average_trust: number;
    tier_distribution: Record<string, number>;
    healthy_peers: number;
    at_risk_peers: number;
  };
}

// Status badge colors
const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  degraded: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  suspended: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  offline: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  revoked: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
};

// Trust tier icons
const trustTierIcons: Record<string, React.ReactNode> = {
  CORE: <ShieldCheck className="w-5 h-5 text-green-500" />,
  TRUSTED: <Shield className="w-5 h-5 text-blue-500" />,
  STANDARD: <Shield className="w-5 h-5 text-gray-500" />,
  LIMITED: <ShieldAlert className="w-5 h-5 text-orange-500" />,
  QUARANTINE: <ShieldX className="w-5 h-5 text-red-500" />,
};

export default function FederationPage() {
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [_selectedPeer, _setSelectedPeer] = useState<FederatedPeer | null>(null);
  const [expandedPeerId, setExpandedPeerId] = useState<string | null>(null);

  // Fetch peers
  const { data: peers = [], isLoading: peersLoading } = useQuery<FederatedPeer[]>({
    queryKey: ['federation-peers'],
    queryFn: () => api.get('/federation/peers'),
  });

  // Fetch stats
  const { data: stats } = useQuery<FederationStats>({
    queryKey: ['federation-stats'],
    queryFn: () => api.get('/federation/stats'),
  });

  // Fetch sync history
  const { data: syncHistory } = useQuery<{ syncs: SyncState[] }>({
    queryKey: ['federation-syncs'],
    queryFn: () => api.get('/federation/sync/status'),
  });

  // Trigger sync mutation
  const syncMutation = useMutation({
    mutationFn: (peerId: string) => api.post(`/federation/sync/${peerId}`, { force: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['federation-peers'] });
      queryClient.invalidateQueries({ queryKey: ['federation-syncs'] });
    },
    onError: (error) => {
      console.error('Sync failed:', error);
    },
  });

  // Remove peer mutation
  const removeMutation = useMutation({
    mutationFn: (peerId: string) => api.delete(`/federation/peers/${peerId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['federation-peers'] });
      queryClient.invalidateQueries({ queryKey: ['federation-stats'] });
    },
    onError: (error) => {
      console.error('Remove peer failed:', error);
    },
  });

  // Adjust trust mutation
  const adjustTrustMutation = useMutation({
    mutationFn: ({ peerId, delta, reason }: { peerId: string; delta: number; reason: string }) =>
      api.post(`/federation/peers/${peerId}/trust`, { delta, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['federation-peers'] });
    },
    onError: (error) => {
      console.error('Trust adjustment failed:', error);
    },
  });

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatSyncRate = (peer: FederatedPeer) => {
    if (peer.total_syncs === 0) return '0%';
    return `${Math.round((peer.successful_syncs / peer.total_syncs) * 100)}%`;
  };

  if (peersLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Globe className="w-7 h-7" />
            Federation
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Manage federated peers and knowledge sharing
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ['federation-peers'] })}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setShowAddModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Peer
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Total Peers</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_peers}</p>
              </div>
              <Globe className="w-8 h-8 text-blue-500 opacity-50" />
            </div>
            <div className="mt-2 flex gap-2 text-sm">
              <span className="text-green-600">{stats.active_peers} active</span>
              <span className="text-gray-400">|</span>
              <span className="text-yellow-600">{stats.pending_peers} pending</span>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Network Trust</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {(stats.network_health.average_trust * 100).toFixed(0)}%
                </p>
              </div>
              <Shield className="w-8 h-8 text-green-500 opacity-50" />
            </div>
            <div className="mt-2 flex gap-2 text-sm">
              <span className="text-green-600">{stats.network_health.healthy_peers} healthy</span>
              <span className="text-gray-400">|</span>
              <span className="text-orange-600">{stats.network_health.at_risk_peers} at risk</span>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Federated Capsules</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_federated_capsules}</p>
              </div>
              <Link2 className="w-8 h-8 text-purple-500 opacity-50" />
            </div>
            <div className="mt-2 flex gap-2 text-sm">
              <span className="text-green-600">{stats.synced_capsules} synced</span>
              <span className="text-gray-400">|</span>
              <span className="text-red-600">{stats.conflicted_capsules} conflicts</span>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Trust Distribution</p>
                <div className="flex gap-1 mt-1">
                  {Object.entries(stats.network_health.tier_distribution).map(([tier, count]) => (
                    <span
                      key={tier}
                      className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-700"
                      title={tier}
                    >
                      {count}
                    </span>
                  ))}
                </div>
              </div>
              <Activity className="w-8 h-8 text-indigo-500 opacity-50" />
            </div>
          </Card>
        </div>
      )}

      {/* Peers List */}
      <Card>
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Federated Peers</h2>
        </div>

        {peers.length === 0 ? (
          <EmptyState
            icon={<Globe className="w-12 h-12" />}
            title="No Federated Peers"
            description="Add a peer to start sharing knowledge across Forge instances."
            action={
              <Button onClick={() => setShowAddModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Add First Peer
              </Button>
            }
          />
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {peers.map((peer) => {
              const isExpanded = expandedPeerId === peer.id;

              return (
                <div key={peer.id} className="p-4">
                  {/* Peer Header */}
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedPeerId(isExpanded ? null : peer.id)}
                  >
                    <div className="flex items-center gap-4">
                      {trustTierIcons[peer.trust_tier] || trustTierIcons.STANDARD}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 dark:text-white">
                            {peer.name}
                          </span>
                          <Badge className={statusColors[peer.status]}>
                            {peer.status.toUpperCase()}
                          </Badge>
                          <Badge className="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                            {peer.trust_tier}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                          {peer.url}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right text-sm">
                        <div className="text-gray-900 dark:text-white font-medium">
                          {(peer.trust_score * 100).toFixed(0)}% trust
                        </div>
                        <div className="text-gray-500 dark:text-gray-400">
                          Last sync: {formatDate(peer.last_sync_at)}
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            syncMutation.mutate(peer.id);
                          }}
                          disabled={syncMutation.isPending || peer.status !== 'active'}
                        >
                          <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                        </Button>
                        {isExpanded ? (
                          <ChevronUp className="w-5 h-5 text-gray-400" />
                        ) : (
                          <ChevronDown className="w-5 h-5 text-gray-400" />
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Sync Stats */}
                        <div>
                          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                            Sync Statistics
                          </h4>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-500">Total Syncs</span>
                              <span className="text-gray-900 dark:text-white">{peer.total_syncs}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Success Rate</span>
                              <span className="text-green-600">{formatSyncRate(peer)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Capsules Received</span>
                              <span className="text-gray-900 dark:text-white">{peer.capsules_received}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Capsules Sent</span>
                              <span className="text-gray-900 dark:text-white">{peer.capsules_sent}</span>
                            </div>
                          </div>
                        </div>

                        {/* Configuration */}
                        <div>
                          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                            Configuration
                          </h4>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-500">Sync Direction</span>
                              <span className="text-gray-900 dark:text-white capitalize">
                                {peer.sync_direction}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Interval</span>
                              <span className="text-gray-900 dark:text-white">
                                {peer.sync_interval_minutes} min
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Conflict Resolution</span>
                              <span className="text-gray-900 dark:text-white capitalize">
                                {peer.conflict_resolution.replace('_', ' ')}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Min Trust to Sync</span>
                              <span className="text-gray-900 dark:text-white">{peer.min_trust_to_sync}</span>
                            </div>
                          </div>
                        </div>

                        {/* Actions */}
                        <div>
                          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                            Actions
                          </h4>
                          <div className="space-y-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full justify-start"
                              onClick={() => adjustTrustMutation.mutate({
                                peerId: peer.id,
                                delta: 0.1,
                                reason: 'Manual trust increase',
                              })}
                            >
                              <TrendingUp className="w-4 h-4 mr-2 text-green-500" />
                              Increase Trust
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full justify-start"
                              onClick={() => adjustTrustMutation.mutate({
                                peerId: peer.id,
                                delta: -0.1,
                                reason: 'Manual trust decrease',
                              })}
                            >
                              <TrendingDown className="w-4 h-4 mr-2 text-red-500" />
                              Decrease Trust
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full justify-start text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                              onClick={() => {
                                if (confirm(`Remove peer "${peer.name}"?`)) {
                                  removeMutation.mutate(peer.id);
                                }
                              }}
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              Remove Peer
                            </Button>
                          </div>
                        </div>
                      </div>

                      {/* Description & Contact */}
                      {(peer.description || peer.admin_contact) && (
                        <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 text-sm">
                          {peer.description && (
                            <p className="text-gray-600 dark:text-gray-400">{peer.description}</p>
                          )}
                          {peer.admin_contact && (
                            <p className="text-gray-500 dark:text-gray-500 mt-1">
                              Contact: {peer.admin_contact}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Recent Sync Activity */}
      {syncHistory && syncHistory.syncs.length > 0 && (
        <Card>
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Sync Activity</h2>
          </div>
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {syncHistory.syncs.slice(0, 5).map((sync) => (
              <div key={sync.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {sync.status === 'completed' ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : sync.status === 'failed' ? (
                    <XCircle className="w-5 h-5 text-red-500" />
                  ) : sync.status === 'running' ? (
                    <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-yellow-500" />
                  )}
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {sync.peer_name}
                    </p>
                    <p className="text-sm text-gray-500">
                      {sync.direction} | {sync.capsules_created + sync.capsules_updated} capsules
                    </p>
                  </div>
                </div>
                <div className="text-right text-sm">
                  <p className={`font-medium ${
                    sync.status === 'completed' ? 'text-green-600' :
                    sync.status === 'failed' ? 'text-red-600' :
                    'text-gray-600'
                  }`}>
                    {sync.status.toUpperCase()}
                  </p>
                  <p className="text-gray-500">{formatDate(sync.started_at)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Add Peer Modal */}
      <AddPeerModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSuccess={() => {
          setShowAddModal(false);
          queryClient.invalidateQueries({ queryKey: ['federation-peers'] });
        }}
      />
    </div>
  );
}

// Add Peer Modal Component
function AddPeerModal({
  isOpen,
  onClose,
  onSuccess,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [description, setDescription] = useState('');
  const [adminContact, setAdminContact] = useState('');
  const [syncDirection, setSyncDirection] = useState<'push' | 'pull' | 'bidirectional'>('bidirectional');
  const [syncInterval, setSyncInterval] = useState(60);

  const registerMutation = useMutation({
    mutationFn: () => api.post('/federation/peers', {
      name,
      url,
      description: description || null,
      admin_contact: adminContact || null,
      sync_direction: syncDirection,
      sync_interval_minutes: syncInterval,
    }),
    onSuccess: () => {
      onSuccess();
      // Reset form
      setName('');
      setUrl('');
      setDescription('');
      setAdminContact('');
      setSyncDirection('bidirectional');
      setSyncInterval(60);
    },
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Federated Peer" size="md">
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Peer Name *
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Research Lab Instance"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Peer URL *
          </label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://other-forge.example.com"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description of this peer"
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Admin Contact
          </label>
          <input
            type="text"
            value={adminContact}
            onChange={(e) => setAdminContact(e.target.value)}
            placeholder="admin@example.com"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Sync Direction
            </label>
            <select
              value={syncDirection}
              onChange={(e) => setSyncDirection(e.target.value as 'push' | 'pull' | 'bidirectional')}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            >
              <option value="bidirectional">Bidirectional</option>
              <option value="push">Push Only</option>
              <option value="pull">Pull Only</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Sync Interval (min)
            </label>
            <input
              type="number"
              value={syncInterval}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                setSyncInterval(isNaN(val) ? 60 : Math.max(5, val));
              }}
              min={5}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {registerMutation.isError && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300 text-sm">
            Failed to register peer. Please check the URL and try again.
          </div>
        )}

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => registerMutation.mutate()}
            disabled={!name || !url || registerMutation.isPending}
          >
            {registerMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Add Peer
              </>
            )}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
