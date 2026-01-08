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
} from 'lucide-react';
import { api } from '../api/client';
import { Card, Button, LoadingSpinner, EmptyState, Modal } from '../components/common';
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
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : toast.type === 'error'
              ? 'bg-red-50 border-red-200 text-red-800'
              : 'bg-sky-50 border-sky-200 text-sky-800'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0" />
          ) : toast.type === 'error' ? (
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          ) : (
            <Info className="w-5 h-5 text-sky-500 flex-shrink-0" />
          )}
          <div className="flex-1">
            {toast.title && <p className="font-semibold text-sm">{toast.title}</p>}
            <p className="text-sm">{toast.message}</p>
          </div>
          <button
            onClick={() => onRemove(toast.id)}
            className="text-slate-400 hover:text-slate-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}

function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substr(2, 9);
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
  MEMORY: 'bg-slate-500/20 text-slate-500 border-slate-500/30',
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

  const { data: capsulesData, isLoading } = useQuery({
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-white">Knowledge Capsules</h1>
          <p className="text-slate-500 dark:text-slate-400">Manage institutional knowledge and wisdom</p>
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
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input
            type="text"
            placeholder="Search capsules..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input pl-10"
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
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
        </div>
      </div>

      {/* Results Info */}
      {searchQuery.length > 2 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            {isSearching ? 'Searching...' : `${searchResults?.length || 0} results for "${searchQuery}"`}
          </span>
          <button
            onClick={() => setSearchQuery('')}
            className="text-sky-400 hover:text-forge-300 flex items-center gap-1"
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
          title="No capsules found"
          description={searchQuery ? "Try adjusting your search terms" : "Create your first knowledge capsule to get started"}
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
                  ? 'bg-sky-600 text-slate-800'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-100'
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
            title: 'Capsule Created!',
            message: 'Your knowledge capsule is now being processed through the pipeline.',
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
        <span className="text-xs text-slate-500 dark:text-slate-400">v{capsule.version}</span>
      </div>

      <h3 className="text-lg font-semibold text-slate-800 dark:text-white mb-2 line-clamp-2">
        {capsule.title}
      </h3>

      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 line-clamp-3">
        {capsule.content}
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {capsule.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 dark:bg-slate-800 rounded text-xs text-slate-600 dark:text-slate-400"
          >
            <Tag className="w-3 h-3" />
            {tag}
          </span>
        ))}
        {capsule.tags.length > 3 && (
          <span className="text-xs text-slate-500 dark:text-slate-400">+{capsule.tags.length - 3} more</span>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
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
      <div className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
        <Sparkles className="w-4 h-4 text-sky-500 animate-pulse" />
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
                  ? 'bg-sky-50 dark:bg-sky-900/20 border border-sky-200 dark:border-sky-800'
                  : isComplete
                  ? 'bg-emerald-50 dark:bg-emerald-900/20'
                  : 'bg-slate-50 dark:bg-slate-800/50'
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center ${
                  isComplete
                    ? 'bg-emerald-500 text-white'
                    : isCurrent
                    ? 'bg-sky-500 text-white'
                    : 'bg-slate-200 dark:bg-slate-700 text-slate-400'
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
                      ? 'text-slate-800 dark:text-white'
                      : 'text-slate-400 dark:text-slate-500'
                  }`}
                >
                  {s.name}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{s.description}</p>
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
    onError: (error: Error) => {
      setIsProcessing(false);
      setPipelineStep(0);
      onError?.(error.message || 'Failed to create capsule. Please try again.');
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
                className="text-xs text-sky-500 hover:text-sky-600 flex items-center gap-1"
              >
                <Info className="w-3 h-3" />
                {showTypeInfo ? 'Hide info' : 'What are these?'}
              </button>
            </div>

            {showTypeInfo && (
              <div className="mb-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg text-sm text-slate-600 dark:text-slate-400">
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
                        ? 'border-sky-500 bg-sky-50 dark:bg-sky-900/20'
                        : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                    }`}
                  >
                    <Icon
                      className={`w-5 h-5 ${
                        isSelected ? 'text-sky-500' : 'text-slate-400'
                      }`}
                    />
                    <span
                      className={`text-sm font-medium ${
                        isSelected
                          ? 'text-sky-700 dark:text-sky-300'
                          : 'text-slate-600 dark:text-slate-400'
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
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400 italic">
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
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
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
                  className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-sm text-slate-600 dark:text-slate-400"
                >
                  <Tag className="w-3 h-3" />
                  {tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
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
            <div className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-sm text-amber-700 dark:text-amber-400">
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
  canEdit: boolean;
  canDelete: boolean;
}

function CapsuleDetailModal({ capsule, onClose, onDelete, canEdit, canDelete }: CapsuleDetailModalProps) {
  const TypeIcon = CAPSULE_TYPE_INFO[capsule.type]?.icon || BookOpen;

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={capsule.title || 'Untitled Capsule'}
      size="lg"
      footer={
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
          {canEdit && (
            <Button variant="secondary" icon={<Edit className="w-4 h-4" />}>
              Edit
            </Button>
          )}
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <span className={`badge border ${typeColors[capsule.type]} flex items-center gap-1.5`}>
            <TypeIcon className="w-3 h-3" />
            {capsule.type}
          </span>
          <span className="text-sm text-slate-500 dark:text-slate-400">Version {capsule.version}</span>
        </div>

        <div className="max-w-none">
          <p className="text-slate-600 dark:text-slate-300 whitespace-pre-wrap">{capsule.content}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {capsule.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-sm text-slate-600 dark:text-slate-400"
            >
              <Tag className="w-3 h-3" />
              {tag}
            </span>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-200 dark:border-slate-700">
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Trust Score</p>
            <p className="text-lg font-semibold text-slate-800 dark:text-white">{capsule.trust_level}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Access Count</p>
            <p className="text-lg font-semibold text-slate-800 dark:text-white">{capsule.view_count}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Created</p>
            <p className="text-sm text-slate-800 dark:text-slate-200">{new Date(capsule.created_at).toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Updated</p>
            <p className="text-sm text-slate-800 dark:text-slate-200">{new Date(capsule.updated_at).toLocaleString()}</p>
          </div>
        </div>

        {capsule.parent_id && (
          <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
            <p className="text-sm font-medium text-slate-800 dark:text-white mb-2 flex items-center gap-2">
              <GitBranch className="w-4 h-4" />
              Lineage
            </p>
            <div className="text-sm">
              <p className="text-slate-500">Parent: {capsule.parent_id}</p>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
