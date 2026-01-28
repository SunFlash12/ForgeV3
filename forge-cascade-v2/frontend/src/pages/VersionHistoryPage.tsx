import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  History,
  GitCommit,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Clock,
  User,
  Diff,
  Eye,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';
import { api } from '../api/client';
import {
  Card,
  Button,
  LoadingSpinner,
  EmptyState,
  Modal,
  ApiErrorState,
} from '../components/common';

interface CapsuleVersion {
  id: string;
  capsule_id: string;
  version_number: string;
  content_hash: string;
  snapshot_type: 'full' | 'diff';
  trust_at_version: number;
  created_at: string;
  created_by: string;
  change_type: string;
  parent_version_id: string | null;
  content_preview?: string;
}

interface VersionDiff {
  version_a: string;
  version_b: string;
  changes: {
    field: string;
    old_value: string | null;
    new_value: string | null;
    change_type: 'added' | 'removed' | 'modified';
  }[];
  lines_added: number;
  lines_removed: number;
}

const changeTypeColors: Record<string, string> = {
  create: 'bg-green-500/15 text-green-400',
  update: 'bg-blue-500/15 text-blue-400',
  fork: 'bg-purple-500/15 text-purple-400',
  merge: 'bg-orange-500/15 text-orange-400',
};

const snapshotTypeIcons: Record<string, string> = {
  full: 'bg-green-500',
  diff: 'bg-yellow-500',
};

export default function VersionHistoryPage() {
  const { capsuleId } = useParams<{ capsuleId: string }>();
  const [expandedVersionId, setExpandedVersionId] = useState<string | null>(null);
  const [showDiffModal, setShowDiffModal] = useState(false);
  const [selectedVersionA, setSelectedVersionA] = useState<string | null>(null);
  const [selectedVersionB, setSelectedVersionB] = useState<string | null>(null);

  // Capsule type for display
  interface CapsuleDetails {
    id: string;
    title: string;
    type: string;
    trust_level: number;
  }

  // Fetch capsule details
  const { data: capsule, isLoading: capsuleLoading, isError: capsuleError, error: capsuleErrorObj, refetch: refetchCapsule } = useQuery<CapsuleDetails>({
    queryKey: ['capsule', capsuleId],
    queryFn: () => api.get(`/capsules/${capsuleId}`),
    enabled: !!capsuleId,
  });

  // Fetch version history
  const { data: versionsData, isLoading: versionsLoading, refetch } = useQuery<{ versions: CapsuleVersion[] }>({
    queryKey: ['versions', capsuleId],
    queryFn: () => api.get(`/graph/temporal/versions/${capsuleId}`),
    enabled: !!capsuleId,
  });

  const versions: CapsuleVersion[] = versionsData?.versions || [];

  // Fetch diff between two versions
  const { data: diffData, isLoading: diffLoading } = useQuery<VersionDiff>({
    queryKey: ['version-diff', selectedVersionA, selectedVersionB],
    queryFn: () => api.get(
      `/graph/temporal/diff?version_a=${selectedVersionA}&version_b=${selectedVersionB}`
    ),
    enabled: !!selectedVersionA && !!selectedVersionB && showDiffModal,
  });

  const openDiffModal = (versionA: string, versionB: string) => {
    setSelectedVersionA(versionA);
    setSelectedVersionB(versionB);
    setShowDiffModal(true);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Validate capsuleId parameter
  if (!capsuleId) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<AlertTriangle className="w-10 h-10 text-amber-500" />}
          title="Invalid Capsule"
          description="No capsule ID was provided. Please select a valid capsule."
          action={
            <Link to="/capsules">
              <Button variant="primary">Back to Capsules</Button>
            </Link>
          }
        />
      </div>
    );
  }

  if (capsuleLoading || versionsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (capsuleError) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            to="/capsules"
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-slate-400" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <History className="w-6 h-6" />
              Version History
            </h1>
            <p className="text-slate-400">
              Unable to load capsule details
            </p>
          </div>
        </div>
        <ApiErrorState
          error={capsuleErrorObj}
          onRetry={() => refetchCapsule()}
          title="Unable to Load Version History"
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/capsules"
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-slate-400" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <History className="w-6 h-6" />
              Version History
            </h1>
            <p className="text-slate-400">
              {capsule?.title || 'Capsule'} - {versions.length} versions
            </p>
          </div>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Capsule Info */}
      <Card className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">
              {capsule?.title || 'Untitled Capsule'}
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Type: {capsule?.type} | Trust: {capsule?.trust_level}
            </p>
          </div>
          <Link to={`/capsules/${capsuleId}`}>
            <Button variant="outline" size="sm">
              <Eye className="w-4 h-4 mr-1" />
              View Capsule
            </Button>
          </Link>
        </div>
      </Card>

      {/* Version Timeline */}
      {versions.length === 0 ? (
        <EmptyState
          icon={<History className="w-10 h-10" />}
          title="No Version History"
          description="This capsule has no recorded version history yet."
        />
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-white/10" />

          {/* Versions */}
          <div className="space-y-4">
            {versions.map((version, index) => {
              const isExpanded = expandedVersionId === version.id;
              const isLatest = index === 0;
              const previousVersion = versions[index + 1];

              return (
                <div key={version.id} className="relative pl-12">
                  {/* Timeline dot */}
                  <div
                    className={`absolute left-4 w-4 h-4 rounded-full border-2 border-surface-900 ${
                      isLatest ? 'bg-green-500' : snapshotTypeIcons[version.snapshot_type]
                    }`}
                  />

                  <Card className="overflow-hidden">
                    <div
                      className="p-4 cursor-pointer hover:bg-white/5"
                      onClick={() => setExpandedVersionId(isExpanded ? null : version.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <GitCommit className="w-5 h-5 text-slate-400" />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm font-medium text-slate-100">
                                v{version.version_number}
                              </span>
                              {isLatest && (
                                <span className="px-2 py-0.5 text-xs bg-green-500/15 text-green-400 rounded">
                                  CURRENT
                                </span>
                              )}
                              <span className={`px-2 py-0.5 text-xs rounded ${changeTypeColors[version.change_type] || 'bg-white/5'}`}>
                                {version.change_type.toUpperCase()}
                              </span>
                              <span className={`px-2 py-0.5 text-xs rounded ${version.snapshot_type === 'full' ? 'bg-blue-500/15 text-blue-400' : 'bg-yellow-500/15 text-yellow-400'}`}>
                                {version.snapshot_type.toUpperCase()}
                              </span>
                            </div>
                            <div className="flex items-center gap-4 mt-1 text-sm text-slate-400">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatDate(version.created_at)}
                              </span>
                              <span className="flex items-center gap-1">
                                <User className="w-3 h-3" />
                                {version.created_by || 'System'}
                              </span>
                              <span>Trust: {version.trust_at_version}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {previousVersion && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                openDiffModal(previousVersion.id, version.id);
                              }}
                            >
                              <Diff className="w-4 h-4 mr-1" />
                              Diff
                            </Button>
                          )}
                          {isExpanded ? (
                            <ChevronUp className="w-5 h-5 text-slate-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-slate-400" />
                          )}
                        </div>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="px-4 pb-4 border-t border-white/10">
                        <div className="mt-4 space-y-3">
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                              <span className="text-slate-400">Version ID:</span>
                              <code className="ml-2 text-xs bg-white/5 px-2 py-0.5 rounded">
                                {version.id}
                              </code>
                            </div>
                            <div>
                              <span className="text-slate-400">Content Hash:</span>
                              <code className="ml-2 text-xs bg-white/5 px-2 py-0.5 rounded">
                                {version.content_hash?.substring(0, 12)}...
                              </code>
                            </div>
                            {version.parent_version_id && (
                              <div>
                                <span className="text-slate-400">Parent Version:</span>
                                <code className="ml-2 text-xs bg-white/5 px-2 py-0.5 rounded">
                                  {version.parent_version_id.substring(0, 12)}...
                                </code>
                              </div>
                            )}
                          </div>

                          {version.content_preview && (
                            <div>
                              <span className="text-sm text-slate-400">Content Preview:</span>
                              <div className="mt-2 p-3 bg-white/5 rounded-lg text-sm font-mono whitespace-pre-wrap">
                                {version.content_preview}
                              </div>
                            </div>
                          )}

                          <div className="flex gap-2 pt-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => api.get(`/graph/temporal/versions/${capsuleId}/at?version_id=${version.id}`)}
                            >
                              <Eye className="w-4 h-4 mr-1" />
                              View Full Content
                            </Button>
                            {index > 0 && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openDiffModal(versions[0].id, version.id)}
                              >
                                <Diff className="w-4 h-4 mr-1" />
                                Compare to Current
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </Card>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Diff Modal */}
      <Modal
        isOpen={showDiffModal}
        onClose={() => {
          setShowDiffModal(false);
          setSelectedVersionA(null);
          setSelectedVersionB(null);
        }}
        title="Version Diff"
        size="lg"
      >
        {diffLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="lg" />
          </div>
        ) : diffData ? (
          <div className="space-y-4">
            {/* Summary */}
            <div className="flex items-center gap-4 text-sm">
              <span className="text-green-400">+{diffData.lines_added} added</span>
              <span className="text-red-400">-{diffData.lines_removed} removed</span>
              <span className="text-slate-400">{diffData.changes.length} changes</span>
            </div>

            {/* Changes */}
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {diffData.changes.length === 0 ? (
                <p className="text-slate-400 text-center py-4">No changes between versions</p>
              ) : (
                diffData.changes.map((change, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-lg ${
                      change.change_type === 'added'
                        ? 'bg-green-500/10 border-l-4 border-green-500'
                        : change.change_type === 'removed'
                        ? 'bg-red-500/10 border-l-4 border-red-500'
                        : 'bg-yellow-500/10 border-l-4 border-yellow-500'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{change.field}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        change.change_type === 'added'
                          ? 'bg-green-500/15 text-green-400'
                          : change.change_type === 'removed'
                          ? 'bg-red-500/15 text-red-400'
                          : 'bg-yellow-500/15 text-yellow-400'
                      }`}>
                        {change.change_type}
                      </span>
                    </div>
                    <div className="text-sm space-y-1">
                      {change.old_value && (
                        <div className="flex gap-2">
                          <span className="text-red-400 font-mono">-</span>
                          <span className="text-slate-400 font-mono text-xs">
                            {change.old_value}
                          </span>
                        </div>
                      )}
                      {change.new_value && (
                        <div className="flex gap-2">
                          <span className="text-green-400 font-mono">+</span>
                          <span className="text-slate-400 font-mono text-xs">
                            {change.new_value}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Actions */}
            <div className="flex justify-end pt-4 border-t border-white/10">
              <Button
                variant="outline"
                onClick={() => setShowDiffModal(false)}
              >
                Close
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-slate-400 text-center py-4">Failed to load diff</p>
        )}
      </Modal>
    </div>
  );
}
