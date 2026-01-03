import { useState } from 'react';
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
} from 'lucide-react';
import { api } from '../api/client';
import { Card, Button, LoadingSpinner, EmptyState, Modal } from '../components/common';
import { useAuthStore } from '../stores/authStore';
import type { Capsule, CapsuleType, CreateCapsuleRequest } from '../types';

const CAPSULE_TYPES: CapsuleType[] = ['INSIGHT', 'DECISION', 'LESSON', 'WARNING', 'PRINCIPLE', 'MEMORY'];

const typeColors: Record<CapsuleType, string> = {
  INSIGHT: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  DECISION: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  LESSON: 'bg-green-500/20 text-green-400 border-green-500/30',
  WARNING: 'bg-red-500/20 text-red-400 border-red-500/30',
  PRINCIPLE: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  MEMORY: 'bg-slate-500/20 text-slate-500 border-slate-500/30',
};

export default function CapsulesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedCapsule, setSelectedCapsule] = useState<Capsule | null>(null);
  const [filterType, setFilterType] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '');
  
  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const { data: capsulesData, isLoading } = useQuery({
    queryKey: ['capsules', filterType, searchParams.get('page')],
    queryFn: () => api.listCapsules({
      page: parseInt(searchParams.get('page') || '1'),
      per_page: 12,
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
    },
  });

  const displayCapsules = searchQuery.length > 2 ? searchResults : capsulesData?.items;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Knowledge Capsules</h1>
          <p className="text-slate-500">Manage institutional knowledge and wisdom</p>
        </div>
        <Button
          variant="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={() => setIsCreateModalOpen(true)}
        >
          Create Capsule
        </Button>
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
  return (
    <Card hover onClick={onClick}>
      <div className="flex items-start justify-between mb-3">
        <span className={`badge border ${typeColors[capsule.type]}`}>
          {capsule.type}
        </span>
        <span className="text-xs text-slate-500">v{capsule.version}</span>
      </div>
      
      <h3 className="text-lg font-semibold text-slate-800 mb-2 line-clamp-2">
        {capsule.title}
      </h3>
      
      <p className="text-sm text-slate-500 mb-4 line-clamp-3">
        {capsule.content}
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {capsule.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 rounded text-xs text-slate-600"
          >
            <Tag className="w-3 h-3" />
            {tag}
          </span>
        ))}
        {capsule.tags.length > 3 && (
          <span className="text-xs text-slate-500">+{capsule.tags.length - 3} more</span>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500">
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
// Create Capsule Modal
// ============================================================================

function CreateCapsuleModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [formData, setFormData] = useState<CreateCapsuleRequest>({
    type: 'INSIGHT',
    title: '',
    content: '',
    tags: [],
  });
  const [tagInput, setTagInput] = useState('');
  
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: CreateCapsuleRequest) => api.createCapsule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['capsules'] });
      onClose();
      setFormData({ type: 'INSIGHT', title: '', content: '', tags: [] });
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
    createMutation.mutate(formData);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Knowledge Capsule"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={createMutation.isPending}
          >
            Create Capsule
          </Button>
        </>
      }
    >
      <form className="space-y-4">
        <div>
          <label className="label">Type</label>
          <select
            value={formData.type}
            onChange={(e) => setFormData({ ...formData, type: e.target.value as CapsuleType })}
            className="input"
          >
            {CAPSULE_TYPES.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

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

        <div>
          <label className="label">Content</label>
          <textarea
            value={formData.content}
            onChange={(e) => setFormData({ ...formData, content: e.target.value })}
            className="input min-h-32"
            placeholder="Enter the knowledge content..."
            required
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
            {formData.tags?.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 rounded text-sm text-slate-600"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => handleRemoveTag(tag)}
                  className="text-slate-500 hover:text-slate-800"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
      </form>
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
          <span className={`badge border ${typeColors[capsule.type]}`}>
            {capsule.type}
          </span>
          <span className="text-sm text-slate-500">Version {capsule.version}</span>
        </div>

        <div className="prose prose-invert max-w-none">
          <p className="text-slate-600 whitespace-pre-wrap">{capsule.content}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {capsule.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 rounded text-sm text-slate-600"
            >
              <Tag className="w-3 h-3" />
              {tag}
            </span>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-200">
          <div>
            <p className="text-xs text-slate-500 mb-1">Trust Score</p>
            <p className="text-lg font-semibold text-slate-800">{capsule.trust_level}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Access Count</p>
            <p className="text-lg font-semibold text-slate-800">{capsule.view_count}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Created</p>
            <p className="text-sm text-slate-800">{new Date(capsule.created_at).toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Updated</p>
            <p className="text-sm text-slate-800">{new Date(capsule.updated_at).toLocaleString()}</p>
          </div>
        </div>

        {capsule.parent_id && (
          <div className="pt-4 border-t border-slate-200">
            <p className="text-sm font-medium text-slate-800 mb-2 flex items-center gap-2">
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
