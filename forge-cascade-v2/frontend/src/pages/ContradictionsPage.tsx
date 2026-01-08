import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  GitMerge,
  ArrowRight,
  Eye,
  Filter,
} from 'lucide-react';
import { api } from '../api/client';
import {
  Card,
  Button,
  LoadingSpinner,
  EmptyState,
  Modal,
} from '../components/common';

interface Capsule {
  id: string;
  title: string;
  type: string;
  trust_level: number;
}

interface Contradiction {
  edge_id: string;
  capsule_a: Capsule;
  capsule_b: Capsule;
  severity: 'high' | 'medium' | 'low';
  tags: string[];
  created_at: string;
}

interface ContradictionStats {
  total: number;
  resolved: number;
  unresolved: number;
  by_severity: Record<string, number>;
}

type ResolutionType = 'keep_both' | 'supersede' | 'merge' | 'dismiss';

const severityColors: Record<string, string> = {
  high: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  low: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
};

export default function ContradictionsPage() {
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [selectedContradiction, setSelectedContradiction] = useState<Contradiction | null>(null);
  const [resolutionType, setResolutionType] = useState<ResolutionType>('keep_both');
  const [winningCapsuleId, setWinningCapsuleId] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  // Fetch statistics
  const { data: stats, isLoading: statsLoading } = useQuery<ContradictionStats>({
    queryKey: ['contradiction-stats'],
    queryFn: () => api.get('/graph/contradictions/stats'),
  });

  // Fetch unresolved contradictions
  const { data: contradictionsData, isLoading } = useQuery({
    queryKey: ['contradictions', severityFilter],
    queryFn: () => api.get('/graph/contradictions/unresolved?limit=100'),
  });

  const contradictions: Contradiction[] = contradictionsData?.contradictions || [];

  // Filter by severity
  const filteredContradictions = severityFilter === 'all'
    ? contradictions
    : contradictions.filter(c => c.severity === severityFilter);

  // Resolve mutation
  const resolveMutation = useMutation({
    mutationFn: ({ edgeId, resolution }: { edgeId: string; resolution: object }) =>
      api.post(`/graph/contradictions/${edgeId}/resolve`, resolution),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contradictions'] });
      queryClient.invalidateQueries({ queryKey: ['contradiction-stats'] });
      setResolveModalOpen(false);
      setSelectedContradiction(null);
      setNotes('');
      setWinningCapsuleId(null);
    },
  });

  const handleResolve = () => {
    if (!selectedContradiction) return;

    resolveMutation.mutate({
      edgeId: selectedContradiction.edge_id,
      resolution: {
        resolution_type: resolutionType,
        winning_capsule_id: resolutionType === 'supersede' ? winningCapsuleId : null,
        notes: notes || null,
      },
    });
  };

  const openResolveModal = (contradiction: Contradiction) => {
    setSelectedContradiction(contradiction);
    setResolutionType('keep_both');
    setWinningCapsuleId(null);
    setNotes('');
    setResolveModalOpen(true);
  };

  if (isLoading || statsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Contradiction Resolution
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
            Review and resolve conflicting knowledge in the system
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['contradictions'] });
            queryClient.invalidateQueries({ queryKey: ['contradiction-stats'] });
          }}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">Total</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {stats?.total || 0}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-lg">
              <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">Unresolved</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {stats?.unresolved || 0}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">Resolved</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {stats?.resolved || 0}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-orange-600 dark:text-orange-400" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">High Severity</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {stats?.by_severity?.high || 0}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-4">
        <Filter className="w-5 h-5 text-gray-400" />
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
        >
          <option value="all">All Severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <span className="text-sm text-gray-500">
          {filteredContradictions.length} contradictions
        </span>
      </div>

      {/* Contradictions List */}
      {filteredContradictions.length === 0 ? (
        <EmptyState
          icon={CheckCircle}
          title="No Contradictions Found"
          description="There are no unresolved contradictions in the knowledge base."
        />
      ) : (
        <div className="space-y-4">
          {filteredContradictions.map((contradiction) => (
            <Card key={contradiction.edge_id} className="overflow-hidden">
              <div
                className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
                onClick={() => setExpandedId(
                  expandedId === contradiction.edge_id ? null : contradiction.edge_id
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className={`px-2 py-1 text-xs font-medium rounded ${severityColors[contradiction.severity]}`}>
                      {contradiction.severity.toUpperCase()}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {contradiction.capsule_a.title || 'Untitled'}
                      </span>
                      <ArrowRight className="w-4 h-4 text-red-500" />
                      <XCircle className="w-4 h-4 text-red-500" />
                      <ArrowRight className="w-4 h-4 text-red-500" />
                      <span className="font-medium text-gray-900 dark:text-white">
                        {contradiction.capsule_b.title || 'Untitled'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={(e) => {
                        e.stopPropagation();
                        openResolveModal(contradiction);
                      }}
                    >
                      Resolve
                    </Button>
                    {expandedId === contradiction.edge_id ? (
                      <ChevronUp className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    )}
                  </div>
                </div>
              </div>

              {expandedId === contradiction.edge_id && (
                <div className="px-4 pb-4 border-t border-gray-200 dark:border-gray-700">
                  <div className="grid grid-cols-2 gap-4 mt-4">
                    {/* Capsule A */}
                    <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                      <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                        {contradiction.capsule_a.title || 'Untitled'}
                      </h4>
                      <div className="space-y-1 text-sm">
                        <p className="text-gray-500">
                          Type: <span className="text-gray-700 dark:text-gray-300">{contradiction.capsule_a.type}</span>
                        </p>
                        <p className="text-gray-500">
                          Trust: <span className="text-gray-700 dark:text-gray-300">{contradiction.capsule_a.trust_level}</span>
                        </p>
                        <p className="text-gray-500">
                          ID: <code className="text-xs">{contradiction.capsule_a.id}</code>
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-2"
                        onClick={() => window.open(`/capsules/${contradiction.capsule_a.id}`, '_blank')}
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        View
                      </Button>
                    </div>

                    {/* Capsule B */}
                    <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                      <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                        {contradiction.capsule_b.title || 'Untitled'}
                      </h4>
                      <div className="space-y-1 text-sm">
                        <p className="text-gray-500">
                          Type: <span className="text-gray-700 dark:text-gray-300">{contradiction.capsule_b.type}</span>
                        </p>
                        <p className="text-gray-500">
                          Trust: <span className="text-gray-700 dark:text-gray-300">{contradiction.capsule_b.trust_level}</span>
                        </p>
                        <p className="text-gray-500">
                          ID: <code className="text-xs">{contradiction.capsule_b.id}</code>
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-2"
                        onClick={() => window.open(`/capsules/${contradiction.capsule_b.id}`, '_blank')}
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        View
                      </Button>
                    </div>
                  </div>

                  {/* Tags */}
                  {contradiction.tags.length > 0 && (
                    <div className="mt-4">
                      <p className="text-sm text-gray-500 mb-2">Related Tags:</p>
                      <div className="flex flex-wrap gap-2">
                        {contradiction.tags.map((tag, i) => (
                          <span
                            key={i}
                            className="px-2 py-1 text-xs bg-gray-200 dark:bg-gray-700 rounded"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Resolution Modal */}
      <Modal
        isOpen={resolveModalOpen}
        onClose={() => setResolveModalOpen(false)}
        title="Resolve Contradiction"
      >
        {selectedContradiction && (
          <div className="space-y-4">
            <p className="text-gray-600 dark:text-gray-300">
              Choose how to resolve the contradiction between:
            </p>
            <div className="p-3 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm">
              <strong>{selectedContradiction.capsule_a.title}</strong>
              <span className="mx-2 text-red-500">contradicts</span>
              <strong>{selectedContradiction.capsule_b.title}</strong>
            </div>

            {/* Resolution Type Selection */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Resolution Type
              </label>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="resolution"
                    value="keep_both"
                    checked={resolutionType === 'keep_both'}
                    onChange={() => setResolutionType('keep_both')}
                    className="text-blue-600"
                  />
                  <span>Keep Both - Acknowledge the contradiction but keep both capsules</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="resolution"
                    value="supersede"
                    checked={resolutionType === 'supersede'}
                    onChange={() => setResolutionType('supersede')}
                    className="text-blue-600"
                  />
                  <span>Supersede - One capsule replaces the other</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="resolution"
                    value="dismiss"
                    checked={resolutionType === 'dismiss'}
                    onChange={() => setResolutionType('dismiss')}
                    className="text-blue-600"
                  />
                  <span>Dismiss - Not a real contradiction</span>
                </label>
              </div>
            </div>

            {/* Winner Selection (for supersede) */}
            {resolutionType === 'supersede' && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Which capsule should be kept?
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="winner"
                      value={selectedContradiction.capsule_a.id}
                      checked={winningCapsuleId === selectedContradiction.capsule_a.id}
                      onChange={() => setWinningCapsuleId(selectedContradiction.capsule_a.id)}
                      className="text-blue-600"
                    />
                    <span>{selectedContradiction.capsule_a.title} (Trust: {selectedContradiction.capsule_a.trust_level})</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="winner"
                      value={selectedContradiction.capsule_b.id}
                      checked={winningCapsuleId === selectedContradiction.capsule_b.id}
                      onChange={() => setWinningCapsuleId(selectedContradiction.capsule_b.id)}
                      className="text-blue-600"
                    />
                    <span>{selectedContradiction.capsule_b.title} (Trust: {selectedContradiction.capsule_b.trust_level})</span>
                  </label>
                </div>
              </div>
            )}

            {/* Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Notes (optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
                placeholder="Explain the resolution decision..."
              />
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
              <Button
                variant="outline"
                onClick={() => setResolveModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleResolve}
                disabled={resolveMutation.isPending || (resolutionType === 'supersede' && !winningCapsuleId)}
              >
                {resolveMutation.isPending ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    Resolving...
                  </>
                ) : (
                  <>
                    <GitMerge className="w-4 h-4 mr-2" />
                    Resolve
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
