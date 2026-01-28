import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  Plus,
  Search,
  Database,
  Clock,
  Tag,
  GitBranch,
  ChevronDown,
  Eye,
  Edit,
  Trash2,
  X,
  CheckCircle,
  AlertCircle,
  Lightbulb,
  Gavel,
  BookOpen,
  AlertTriangle,
  Compass,
  Brain,
  Info,
  Loader2,
  RefreshCw,
  Sparkles,
  GitFork,
  Shield,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { api } from '../api/client';
import { Card, Button, LoadingSpinner, EmptyState, Modal, ApiErrorState } from '../components/common';
import { useAuthStore } from '../stores/authStore';
import type { Capsule, CapsuleType, CreateCapsuleRequest } from '../types';

// ============================================================================
// Toast Notification System
// ============================================================================

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
  title?: string;
}

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 p-4 rounded-xl shadow-lg border backdrop-blur-sm animate-slide-in-right max-w-sm ${
            toast.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : toast.type === 'error'
              ? 'bg-red-500/10 border-red-500/30 text-red-400'
              : 'bg-forge-500/10 border-forge-500/30 text-cyber-blue'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0" />
          ) : toast.type === 'error' ? (
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          ) : (
            <Info className="w-5 h-5 text-forge-400 flex-shrink-0" />
          )}
          <div className="flex-1">
            {toast.title && <p className="font-semibold text-sm">{toast.title}</p>}
            <p className="text-sm">{toast.message}</p>
          </div>
          <button
            onClick={() => onRemove(toast.id)}
            className="text-slate-400 hover:text-slate-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}

let toastCounter = 0;

function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = `toast-${++toastCounter}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => removeToast(id), 5000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return { toasts, addToast, removeToast };
}

// Capsule type definitions with descriptions and icons
const CAPSULE_TYPE_INFO: Record<CapsuleType, { icon: typeof Lightbulb; description: string; example: string }> = {
  INSIGHT: {
    icon: Lightbulb,
    description: 'A discovery or understanding gained from analysis',
    example: 'e.g., "User engagement increases 40% with personalized recommendations"',
  },
  DECISION: {
    icon: Gavel,
    description: 'A documented choice with reasoning',
    example: 'e.g., "Chose PostgreSQL over MongoDB for ACID compliance"',
  },
  LESSON: {
    icon: BookOpen,
    description: 'Knowledge learned from experience',
    example: 'e.g., "Always test migrations on staging before production"',
  },
  WARNING: {
    icon: AlertTriangle,
    description: 'A caution or risk to be aware of',
    example: 'e.g., "API rate limits can cause silent data loss"',
  },
  PRINCIPLE: {
    icon: Compass,
    description: 'A fundamental rule or guideline',
    example: 'e.g., "Security reviews required for all external integrations"',
  },
  MEMORY: {
    icon: Brain,
    description: 'Historical context or past events',
    example: 'e.g., "The 2023 outage was caused by cascading timeouts"',
  },
  // Backend-only types
  KNOWLEDGE: { icon: BookOpen, description: 'General knowledge', example: '' },
  CODE: { icon: BookOpen, description: 'Code snippet', example: '' },
  CONFIG: { icon: BookOpen, description: 'Configuration', example: '' },
  TEMPLATE: { icon: BookOpen, description: 'Template', example: '' },
  DOCUMENT: { icon: BookOpen, description: 'Document', example: '' },
};

const CAPSULE_TYPES: CapsuleType[] = ['INSIGHT', 'DECISION', 'LESSON', 'WARNING', 'PRINCIPLE', 'MEMORY'];

const typeColors: Record<CapsuleType, string> = {
  INSIGHT: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  DECISION: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  LESSON: 'bg-green-500/20 text-green-400 border-green-500/30',
  WARNING: 'bg-red-500/20 text-red-400 border-red-500/30',
  PRINCIPLE: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  MEMORY: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  // Backend-only types (may appear in responses)
  KNOWLEDGE: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  CODE: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  CONFIG: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  TEMPLATE: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  DOCUMENT: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
};

export default function CapsulesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedCapsule, setSelectedCapsule] = useState<Capsule | null>(null);
  const [filterType, setFilterType] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const { toasts, addToast, removeToast } = useToast();

  const { data: capsulesData, isLoading, isError, error: capsulesError, refetch } = useQuery({
    queryKey: ['capsules', filterType, searchParams.get('page')],
    queryFn: () => api.listCapsules({
      page: parseInt(searchParams.get('page') || '1'),
      page_size: 12,
      type: filterType || undefined,
    }),
  });

  const { data: searchResults, isLoading: isSearching } = useQuery({
    queryKey: ['capsule-search', searchQuery],
    queryFn: () => api.searchCapsules(searchQuery),
    enabled: searchQuery.length > 2,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteCapsule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['capsules'] });
      setSelectedCapsule(null);
      addToast({
        type: 'success',
        title: 'Capsule Deleted',
        message: 'The capsule has been permanently removed.',
      });
    },
    onError: (error: Error) => {
      addToast({
        type: 'error',
        title: 'Delete Failed',
        message: error.message || 'Failed to delete capsule. Please try again.',
      });
    },
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['capsules'] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const displayCapsules = searchQuery.length > 2 ? searchResults : capsulesData?.items;

  return (
    <div className="space-y-6">
      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Knowledge Capsules</h1>
          <p className="text-slate-400">Manage institutional knowledge and wisdom</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />}
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setIsCreateModalOpen(true)}
          >
            Create Capsule
          </Button>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            placeholder="Search capsules..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input pl-11"
          />
        </div>
        <div className="relative">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="input pr-10 appearance-none cursor-pointer"
          >
            <option value="">All Types</option>
            {CAPSULE_TYPES.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Results Info */}
      {searchQuery.length > 2 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">
            {isSearching ? 'Searching...' : `${searchResults?.length || 0} results for "${searchQuery}"`}
          </span>
          <button
            onClick={() => setSearchQuery('')}
            className="text-forge-400 hover:text-forge-300 flex items-center gap-1"
          >
            <X className="w-4 h-4" /> Clear search
          </button>
        </div>
      )}

      {/* Capsules Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" label="Loading capsules..." />
        </div>
      ) : isError ? (
        <ApiErrorState error={capsulesError} onRetry={() => refetch()} title="Unable to Load Capsules" />
      ) : displayCapsules && displayCapsules.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayCapsules.map((capsule) => (
            <CapsuleCard
              key={capsule.id}
              capsule={capsule}
              onClick={() => setSelectedCapsule(capsule)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Database className="w-8 h-8" />}
          title={searchQuery ? "No matches found" : "Start building knowledge"}
          description={searchQuery ? "Try different keywords or clear your search" : "Create your first capsule to capture and preserve institutional wisdom"}
          action={
            <Button
              variant="primary"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setIsCreateModalOpen(true)}
            >
              Create Capsule
            </Button>
          }
        />
      )}

      {/* Pagination */}
      {capsulesData && capsulesData.total_pages > 1 && !searchQuery && (
        <div className="flex items-center justify-center gap-2">
          {Array.from({ length: capsulesData.total_pages }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              onClick={() => setSearchParams({ page: page.toString() })}
              className={`w-10 h-10 rounded-lg transition-colors ${
                page === capsulesData.page
                  ? 'bg-forge-500 text-white'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            >
              {page}
            </button>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <CreateCapsuleModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={() => {
          addToast({
            type: 'success',
            title: '✨ Capsule Created!',
            message: 'Your knowledge has been captured and added to the graph.',
          });
        }}
        onError={(error: string) => {
          addToast({
            type: 'error',
            title: 'Creation Failed',
            message: error,
          });
        }}
      />

      {/* View/Edit Modal */}
      {selectedCapsule && (
        <CapsuleDetailModal
          capsule={selectedCapsule}
          onClose={() => setSelectedCapsule(null)}
          onDelete={() => deleteMutation.mutate(selectedCapsule.id)}
          onUpdate={() => {
            addToast({
              type: 'success',
              title: 'Capsule Updated',
              message: 'Your changes have been saved successfully.',
            });
            setSelectedCapsule(null);
          }}
          onFork={(forkedCapsule) => {
            addToast({
              type: 'success',
              title: 'Capsule Forked',
              message: `Created new capsule: ${forkedCapsule.title}`,
            });
            setSelectedCapsule(null);
          }}
          canEdit={user?.id === selectedCapsule.owner_id || user?.trust_level === 'TRUSTED' || user?.trust_level === 'CORE'}
          canDelete={user?.trust_level === 'TRUSTED' || user?.trust_level === 'CORE'}
        />
      )}
    </div>
  );
}

// ============================================================================
// Capsule Card Component
// ============================================================================

function CapsuleCard({ capsule, onClick }: { capsule: Capsule; onClick: () => void }) {
  const TypeIcon = CAPSULE_TYPE_INFO[capsule.type]?.icon || BookOpen;

  return (
    <Card hover onClick={onClick}>
      <div className="flex items-start justify-between mb-3">
        <span className={`badge border ${typeColors[capsule.type]} flex items-center gap-1.5`}>
          <TypeIcon className="w-3 h-3" />
          {capsule.type}
        </span>
        <span className="text-xs text-slate-400">v{capsule.version}</span>
      </div>

      <h3 className="text-lg font-semibold text-slate-100 mb-2 line-clamp-2">
        {capsule.title}
      </h3>

      <p className="text-sm text-slate-400 mb-4 line-clamp-3">
        {capsule.content}
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {capsule.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/5 rounded text-xs text-slate-300"
          >
            <Tag className="w-3 h-3" />
            {tag}
          </span>
        ))}
        {capsule.tags.length > 3 && (
          <span className="text-xs text-slate-400">+{capsule.tags.length - 3} more</span>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-1">
          <Eye className="w-3 h-3" />
          {capsule.view_count}
        </div>
        <div className="flex items-center gap-1">
          <GitBranch className="w-3 h-3" />
          {capsule.parent_id ? 1 : 0} parents
        </div>
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {new Date(capsule.created_at).toLocaleDateString()}
        </div>
      </div>
    </Card>
  );
}

// ============================================================================
// Pipeline Status Indicator
// ============================================================================

const PIPELINE_STEPS = [
  { id: 1, name: 'Validation', description: 'Checking content format' },
  { id: 2, name: 'Classification', description: 'Determining type & tags' },
  { id: 3, name: 'Trust Scoring', description: 'Calculating trust level' },
  { id: 4, name: 'Indexing', description: 'Adding to knowledge base' },
];

function PipelineProgress({ step, isProcessing }: { step: number; isProcessing: boolean }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
        <Sparkles className="w-4 h-4 text-cyber-blue animate-pulse" />
        Processing through pipeline...
      </div>
      <div className="space-y-2">
        {PIPELINE_STEPS.map((s, idx) => {
          const isComplete = idx < step;
          const isCurrent = idx === step && isProcessing;

          return (
            <div
              key={s.id}
              className={`flex items-center gap-3 p-2 rounded-lg transition-colors ${
                isCurrent
                  ? 'bg-forge-500/10 border border-forge-500/30'
                  : isComplete
                  ? 'bg-emerald-500/10'
                  : 'bg-white/5'
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center ${
                  isComplete
                    ? 'bg-emerald-500 text-white'
                    : isCurrent
                    ? 'bg-forge-500 text-white'
                    : 'bg-white/10 text-slate-400'
                }`}
              >
                {isComplete ? (
                  <CheckCircle className="w-4 h-4" />
                ) : isCurrent ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <span className="text-xs font-medium">{s.id}</span>
                )}
              </div>
              <div className="flex-1">
                <p
                  className={`text-sm font-medium ${
                    isCurrent || isComplete
                      ? 'text-slate-100'
                      : 'text-slate-400'
                  }`}
                >
                  {s.name}
                </p>
                <p className="text-xs text-slate-400">{s.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// Create Capsule Modal
// ============================================================================

interface CreateCapsuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

function CreateCapsuleModal({ isOpen, onClose, onSuccess, onError }: CreateCapsuleModalProps) {
  const [formData, setFormData] = useState<CreateCapsuleRequest>({
    type: 'INSIGHT',
    title: '',
    content: '',
    tags: [],
  });
  const [tagInput, setTagInput] = useState('');
  const [pipelineStep, setPipelineStep] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showTypeInfo, setShowTypeInfo] = useState(false);

  const queryClient = useQueryClient();
  const selectedTypeInfo = CAPSULE_TYPE_INFO[formData.type];

  // Simulate pipeline progression for visual feedback
  useEffect(() => {
    if (isProcessing && pipelineStep < PIPELINE_STEPS.length) {
      const timer = setTimeout(() => {
        setPipelineStep((prev) => prev + 1);
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [isProcessing, pipelineStep]);

  const createMutation = useMutation({
    mutationFn: (data: CreateCapsuleRequest) => api.createCapsule(data),
    onMutate: () => {
      setIsProcessing(true);
      setPipelineStep(0);
    },
    onSuccess: () => {
      // Wait for pipeline animation to complete
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['capsules'] });
        onClose();
        setFormData({ type: 'INSIGHT', title: '', content: '', tags: [] });
        setIsProcessing(false);
        setPipelineStep(0);
        onSuccess?.();
      }, PIPELINE_STEPS.length * 600 + 200);
    },
    onError: (error: Error & { response?: { status?: number; data?: { detail?: string } } }) => {
      setIsProcessing(false);
      setPipelineStep(0);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      let message: string;
      if (status === 401) {
        message = 'You must be logged in to create capsules. Please sign in and try again.';
      } else if (status === 403) {
        message = 'Your account does not have permission to create capsules.';
      } else if (detail) {
        message = detail;
      } else if (error.message?.includes('Network Error')) {
        message = 'Cannot reach the server. Please check that the backend is running.';
      } else {
        message = error.message || 'Failed to create capsule. Please try again.';
      }
      onError?.(message);
    },
  });

  const handleAddTag = () => {
    if (tagInput.trim() && !formData.tags?.includes(tagInput.trim())) {
      setFormData({
        ...formData,
        tags: [...(formData.tags || []), tagInput.trim()],
      });
      setTagInput('');
    }
  };

  const handleRemoveTag = (tag: string) => {
    setFormData({
      ...formData,
      tags: formData.tags?.filter((t) => t !== tag),
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      onError?.('Please enter a title for your capsule.');
      return;
    }
    if (!formData.content.trim()) {
      onError?.('Please enter content for your capsule.');
      return;
    }
    createMutation.mutate(formData);
  };

  const isValid = formData.title.trim() && formData.content.trim();

  return (
    <Modal
      isOpen={isOpen}
      onClose={isProcessing ? () => {} : onClose}
      title="Create Knowledge Capsule"
      size="lg"
      footer={
        isProcessing ? null : (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              loading={createMutation.isPending}
              disabled={!isValid}
              icon={<Sparkles className="w-4 h-4" />}
            >
              Create Capsule
            </Button>
          </>
        )
      }
    >
      {isProcessing ? (
        <PipelineProgress step={pipelineStep} isProcessing={isProcessing} />
      ) : (
        <form className="space-y-5">
          {/* Type Selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="label mb-0">Capsule Type</label>
              <button
                type="button"
                onClick={() => setShowTypeInfo(!showTypeInfo)}
                className="text-xs text-cyber-blue hover:text-cyan-300 flex items-center gap-1"
              >
                <Info className="w-3 h-3" />
                {showTypeInfo ? 'Hide info' : 'What are these?'}
              </button>
            </div>

            {showTypeInfo && (
              <div className="mb-3 p-3 bg-white/5 rounded-lg text-sm text-slate-300">
                <p className="mb-2">Choose the type that best describes your knowledge:</p>
                <ul className="space-y-1 text-xs">
                  {CAPSULE_TYPES.map((type) => {
                    const info = CAPSULE_TYPE_INFO[type];
                    const Icon = info.icon;
                    return (
                      <li key={type} className="flex items-start gap-2">
                        <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <span><strong>{type}</strong>: {info.description}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {CAPSULE_TYPES.map((type) => {
                const info = CAPSULE_TYPE_INFO[type];
                const Icon = info.icon;
                const isSelected = formData.type === type;

                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setFormData({ ...formData, type })}
                    className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-all text-left ${
                      isSelected
                        ? 'border-forge-500 bg-forge-500/10'
                        : 'border-white/10 hover:border-white/20'
                    }`}
                  >
                    <Icon
                      className={`w-5 h-5 ${
                        isSelected ? 'text-cyber-blue' : 'text-slate-400'
                      }`}
                    />
                    <span
                      className={`text-sm font-medium ${
                        isSelected
                          ? 'text-cyan-300'
                          : 'text-slate-300'
                      }`}
                    >
                      {type}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Selected type hint */}
            {selectedTypeInfo?.example && (
              <p className="mt-2 text-xs text-slate-400 italic">
                {selectedTypeInfo.example}
              </p>
            )}
          </div>

          {/* Title */}
          <div>
            <label className="label">Title</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="input"
              placeholder="Enter a descriptive title"
              required
            />
          </div>

          {/* Content */}
          <div>
            <label className="label">Content</label>
            <textarea
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              className="input min-h-32"
              placeholder="Enter the knowledge content..."
              required
            />
            <p className="mt-1 text-xs text-slate-400">
              Be specific and concise. Include context and examples if helpful.
            </p>
          </div>

          {/* Tags */}
          <div>
            <label className="label">Tags (optional)</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                className="input flex-1"
                placeholder="Add a tag..."
              />
              <Button type="button" variant="secondary" onClick={handleAddTag}>
                Add
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {formData.tags?.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-white/5 rounded text-sm text-slate-300"
                >
                  <Tag className="w-3 h-3" />
                  {tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="text-slate-400 hover:text-slate-100"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {(!formData.tags || formData.tags.length === 0) && (
                <span className="text-xs text-slate-400 italic">No tags added</span>
              )}
            </div>
          </div>

          {/* Validation Summary */}
          {!isValid && (formData.title || formData.content) && (
            <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-400">
              <AlertTriangle className="w-4 h-4" />
              {!formData.title.trim()
                ? 'Please enter a title'
                : 'Please enter content for your capsule'}
            </div>
          )}
        </form>
      )}
    </Modal>
  );
}

// ============================================================================
// Capsule Detail Modal
// ============================================================================

interface CapsuleDetailModalProps {
  capsule: Capsule;
  onClose: () => void;
  onDelete: () => void;
  onUpdate?: () => void;
  onFork?: (forkedCapsule: Capsule) => void;
  canEdit: boolean;
  canDelete: boolean;
}

function CapsuleDetailModal({ capsule, onClose, onDelete, onUpdate, onFork, canEdit, canDelete }: CapsuleDetailModalProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [showLineage, setShowLineage] = useState(false);
  const [showForkModal, setShowForkModal] = useState(false);
  const [editData, setEditData] = useState({
    title: capsule.title || '',
    content: capsule.content || '',
    tags: capsule.tags || [],
  });
  const [tagInput, setTagInput] = useState('');
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  // Fetch lineage data
  const { data: lineageData, isLoading: lineageLoading } = useQuery({
    queryKey: ['capsule-lineage', capsule.id],
    queryFn: () => api.getCapsuleLineage(capsule.id, 5),
    enabled: showLineage,
  });

  // Verify integrity
  const { data: integrityData, isLoading: integrityLoading, refetch: refetchIntegrity } = useQuery({
    queryKey: ['capsule-integrity', capsule.id],
    queryFn: () => api.verifyCapsuleIntegrity(capsule.id),
    enabled: false,
  });

  const TypeIcon = CAPSULE_TYPE_INFO[capsule.type]?.icon || BookOpen;

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; content?: string; tags?: string[] }) =>
      api.updateCapsule(capsule.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['capsules'] });
      setIsEditing(false);
      onUpdate?.();
    },
  });

  const handleAddTag = () => {
    if (tagInput.trim() && !editData.tags.includes(tagInput.trim())) {
      setEditData({
        ...editData,
        tags: [...editData.tags, tagInput.trim()],
      });
      setTagInput('');
    }
  };

  const handleRemoveTag = (tag: string) => {
    setEditData({
      ...editData,
      tags: editData.tags.filter((t) => t !== tag),
    });
  };

  const handleSave = () => {
    if (!editData.title.trim() || !editData.content.trim()) {
      return;
    }
    updateMutation.mutate({
      title: editData.title,
      content: editData.content,
      tags: editData.tags,
    });
  };

  const handleCancelEdit = () => {
    setEditData({
      title: capsule.title || '',
      content: capsule.content || '',
      tags: capsule.tags || [],
    });
    setIsEditing(false);
  };

  return (
    <Modal
      isOpen={true}
      onClose={isEditing ? handleCancelEdit : onClose}
      title={isEditing ? 'Edit Capsule' : (capsule.title || 'Untitled Capsule')}
      size="lg"
      footer={
        isEditing ? (
          <>
            <Button variant="secondary" onClick={handleCancelEdit}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              loading={updateMutation.isPending}
              disabled={!editData.title.trim() || !editData.content.trim()}
              icon={<CheckCircle className="w-4 h-4" />}
            >
              Save Changes
            </Button>
          </>
        ) : (
          <>
            {canDelete && (
              <Button
                variant="danger"
                onClick={() => {
                  if (confirm('Are you sure you want to delete this capsule?')) {
                    onDelete();
                  }
                }}
                icon={<Trash2 className="w-4 h-4" />}
              >
                Delete
              </Button>
            )}
            {user && ['STANDARD', 'TRUSTED', 'CORE'].includes(user.trust_level) && (
              <Button
                variant="secondary"
                icon={<GitFork className="w-4 h-4" />}
                onClick={() => setShowForkModal(true)}
              >
                Fork
              </Button>
            )}
            {canEdit && (
              <Button
                variant="secondary"
                icon={<Edit className="w-4 h-4" />}
                onClick={() => setIsEditing(true)}
              >
                Edit
              </Button>
            )}
            <Button variant="primary" onClick={onClose}>
              Close
            </Button>
          </>
        )
      }
    >
      {isEditing ? (
        // Edit Form
        <div className="space-y-4">
          <div>
            <label className="label">Title</label>
            <input
              type="text"
              value={editData.title}
              onChange={(e) => setEditData({ ...editData, title: e.target.value })}
              className="input"
              placeholder="Enter a descriptive title"
            />
          </div>

          <div>
            <label className="label">Content</label>
            <textarea
              value={editData.content}
              onChange={(e) => setEditData({ ...editData, content: e.target.value })}
              className="input min-h-32"
              placeholder="Enter the knowledge content..."
            />
          </div>

          <div>
            <label className="label">Tags</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                className="input flex-1"
                placeholder="Add a tag..."
              />
              <Button type="button" variant="secondary" onClick={handleAddTag}>
                Add
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {editData.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-white/5 rounded text-sm text-slate-300"
                >
                  <Tag className="w-3 h-3" />
                  {tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="text-slate-400 hover:text-slate-100"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {editData.tags.length === 0 && (
                <span className="text-xs text-slate-400 italic">No tags</span>
              )}
            </div>
          </div>

          {updateMutation.isError && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
              <AlertCircle className="w-4 h-4" />
              {updateMutation.error?.message || 'Failed to update capsule'}
            </div>
          )}
        </div>
      ) : (
        // View Mode
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className={`badge border ${typeColors[capsule.type]} flex items-center gap-1.5`}>
              <TypeIcon className="w-3 h-3" />
              {capsule.type}
            </span>
            <span className="text-sm text-slate-400">Version {capsule.version}</span>
          </div>

          <div className="max-w-none">
            <p className="text-slate-300 whitespace-pre-wrap">{capsule.content}</p>
          </div>

          <div className="flex flex-wrap gap-2">
            {capsule.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2 py-1 bg-white/5 rounded text-sm text-slate-300"
              >
                <Tag className="w-3 h-3" />
                {tag}
              </span>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/10">
            <div>
              <p className="text-xs text-slate-400 mb-1">Trust Score</p>
              <p className="text-lg font-semibold text-slate-100">{capsule.trust_level}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">Access Count</p>
              <p className="text-lg font-semibold text-slate-100">{capsule.view_count}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">Created</p>
              <p className="text-sm text-slate-200">{new Date(capsule.created_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">Updated</p>
              <p className="text-sm text-slate-200">{new Date(capsule.updated_at).toLocaleString()}</p>
            </div>
          </div>

          {/* Lineage Section */}
          <div className="pt-4 border-t border-white/10">
            <button
              onClick={() => setShowLineage(!showLineage)}
              className="w-full flex items-center justify-between text-sm font-medium text-slate-100 mb-2"
            >
              <span className="flex items-center gap-2">
                <GitBranch className="w-4 h-4" />
                Lineage (Isnad Chain)
              </span>
              <ChevronRight className={`w-4 h-4 transition-transform ${showLineage ? 'rotate-90' : ''}`} />
            </button>

            {showLineage && (
              <div className="mt-3 space-y-3">
                {lineageLoading ? (
                  <div className="flex items-center gap-2 text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Loading lineage...</span>
                  </div>
                ) : lineageData ? (
                  <div className="space-y-3">
                    {/* Ancestors */}
                    {lineageData.ancestors && lineageData.ancestors.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Ancestors</p>
                        <div className="space-y-2">
                          {lineageData.ancestors.map((ancestor: { id: string; title: string; type: string; depth: number }, idx: number) => (
                            <div
                              key={ancestor.id}
                              className="flex items-center gap-2 p-2 bg-white/5 rounded-lg"
                              style={{ marginLeft: `${idx * 12}px` }}
                            >
                              <GitBranch className="w-4 h-4 text-slate-400" />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-slate-100 truncate">{ancestor.title}</p>
                                <p className="text-xs text-slate-400">{ancestor.type} • Depth: {ancestor.depth}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Current Capsule */}
                    <div className="p-3 bg-forge-500/10 border border-forge-500/30 rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 bg-forge-500 rounded-full flex items-center justify-center">
                          <CheckCircle className="w-4 h-4 text-white" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-100">{capsule.title}</p>
                          <p className="text-xs text-slate-400">Current capsule</p>
                        </div>
                      </div>
                    </div>

                    {/* Descendants */}
                    {lineageData.descendants && lineageData.descendants.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Descendants (Forks)</p>
                        <div className="space-y-2">
                          {lineageData.descendants.map((descendant: { id: string; title: string; type: string; depth: number }) => (
                            <div
                              key={descendant.id}
                              className="flex items-center gap-2 p-2 bg-white/5 rounded-lg"
                            >
                              <GitFork className="w-4 h-4 text-slate-400" />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-slate-100 truncate">{descendant.title}</p>
                                <p className="text-xs text-slate-400">{descendant.type}</p>
                              </div>
                              <ExternalLink className="w-4 h-4 text-slate-400" />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Stats */}
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span>Chain depth: {lineageData.depth || 0}</span>
                      <span>Forks: {capsule.fork_count || 0}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">No lineage data available</p>
                )}

                {/* Integrity Check Button */}
                <div className="pt-3 border-t border-white/10">
                  <button
                    onClick={() => refetchIntegrity()}
                    disabled={integrityLoading}
                    className="flex items-center gap-2 text-sm text-cyber-blue hover:text-cyan-300"
                  >
                    {integrityLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Shield className="w-4 h-4" />
                    )}
                    Verify Integrity
                  </button>

                  {integrityData && (
                    <div className={`mt-2 p-3 rounded-lg ${
                      integrityData.is_valid
                        ? 'bg-emerald-500/10 border border-emerald-500/30'
                        : 'bg-red-500/10 border border-red-500/30'
                    }`}>
                      <div className="flex items-center gap-2 mb-2">
                        {integrityData.is_valid ? (
                          <CheckCircle className="w-5 h-5 text-emerald-400" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-red-400" />
                        )}
                        <span className={`font-medium ${
                          integrityData.is_valid ? 'text-emerald-400' : 'text-red-400'
                        }`}>
                          {integrityData.is_valid ? 'Integrity Verified' : 'Integrity Issues Found'}
                        </span>
                      </div>
                      <div className="text-xs space-y-1">
                        <p className={integrityData.content_hash_valid ? 'text-emerald-400' : 'text-red-400'}>
                          Content Hash: {integrityData.content_hash_valid ? 'Valid' : 'Invalid'}
                        </p>
                        {integrityData.signature_valid !== null && (
                          <p className={integrityData.signature_valid ? 'text-emerald-400' : 'text-red-400'}>
                            Signature: {integrityData.signature_valid ? 'Valid' : 'Invalid'}
                          </p>
                        )}
                        {integrityData.issues && integrityData.issues.length > 0 && (
                          <div className="mt-2 text-red-400">
                            <p className="font-medium">Issues:</p>
                            <ul className="list-disc list-inside">
                              {integrityData.issues.map((issue: string, idx: number) => (
                                <li key={idx}>{issue}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fork Modal */}
      {showForkModal && (
        <ForkCapsuleModal
          capsule={capsule}
          onClose={() => setShowForkModal(false)}
          onSuccess={(forkedCapsule) => {
            setShowForkModal(false);
            onFork?.(forkedCapsule);
          }}
        />
      )}
    </Modal>
  );
}

// ============================================================================
// Fork Capsule Modal
// ============================================================================

interface ForkCapsuleModalProps {
  capsule: Capsule;
  onClose: () => void;
  onSuccess: (forkedCapsule: Capsule) => void;
}

function ForkCapsuleModal({ capsule, onClose, onSuccess }: ForkCapsuleModalProps) {
  const [formData, setFormData] = useState({
    title: `Fork of: ${capsule.title}`,
    content: capsule.content,
    evolution_reason: '',
  });
  const queryClient = useQueryClient();

  const forkMutation = useMutation({
    mutationFn: (data: { title?: string; content?: string; evolution_reason: string }) =>
      api.forkCapsule(capsule.id, data),
    onSuccess: (forkedCapsule) => {
      queryClient.invalidateQueries({ queryKey: ['capsules'] });
      queryClient.invalidateQueries({ queryKey: ['capsule-lineage', capsule.id] });
      onSuccess(forkedCapsule);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.evolution_reason.trim()) return;
    forkMutation.mutate(formData);
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Fork Capsule"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={forkMutation.isPending}
            disabled={!formData.evolution_reason.trim()}
            icon={<GitFork className="w-4 h-4" />}
          >
            Create Fork
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="p-4 bg-forge-500/10 border border-forge-500/30 rounded-lg">
          <div className="flex items-start gap-3">
            <GitBranch className="w-5 h-5 text-cyber-blue flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-medium text-cyan-300">Forking from:</h4>
              <p className="text-sm text-cyan-300">{capsule.title}</p>
              <p className="text-xs text-cyan-400 mt-1">
                The new capsule will be linked to this parent in the lineage chain.
              </p>
            </div>
          </div>
        </div>

        <div>
          <label className="label">Title</label>
          <input
            type="text"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            className="input"
            placeholder="Title for the forked capsule"
          />
        </div>

        <div>
          <label className="label">Content</label>
          <textarea
            value={formData.content}
            onChange={(e) => setFormData({ ...formData, content: e.target.value })}
            className="input min-h-32"
            placeholder="Modify the content as needed..."
          />
        </div>

        <div>
          <label className="label">Evolution Reason *</label>
          <textarea
            value={formData.evolution_reason}
            onChange={(e) => setFormData({ ...formData, evolution_reason: e.target.value })}
            className="input min-h-20"
            placeholder="Why are you creating this fork? What's different?"
            required
          />
          <p className="text-xs text-slate-400 mt-1">
            Explain why this fork is needed and what changes were made.
          </p>
        </div>

        {forkMutation.isError && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
            <AlertCircle className="w-4 h-4" />
            {forkMutation.error?.message || 'Failed to fork capsule'}
          </div>
        )}
      </div>
    </Modal>
  );
}
