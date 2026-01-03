import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  Vote,
  Clock,
  CheckCircle,
  XCircle,
  ChevronDown,
  Ghost,
  Users,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { api } from '../api/client';
import {
  Card,
  Button,
  LoadingSpinner,
  EmptyState,
  Modal,
  ProgressBar,
} from '../components/common';
import { useAuthStore } from '../stores/authStore';
import type {
  Proposal,
  ProposalType,
  ProposalStatus,
  VoteChoice,
  CreateProposalRequest,
} from '../types';

const PROPOSAL_TYPES: ProposalType[] = ['POLICY', 'SYSTEM', 'OVERLAY', 'CAPSULE', 'TRUST', 'CONSTITUTIONAL'];

const statusColors: Record<ProposalStatus, string> = {
  DRAFT: 'bg-slate-500/20 text-slate-500 border-slate-500/30',
  ACTIVE: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  PASSED: 'bg-green-500/20 text-green-400 border-green-500/30',
  REJECTED: 'bg-red-500/20 text-red-400 border-red-500/30',
  WITHDRAWN: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  EXPIRED: 'bg-slate-500/20 text-slate-500 border-slate-500/30',
};

export default function GovernancePage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('ACTIVE');
  const [filterType, setFilterType] = useState<string>('');

  const { user } = useAuthStore();

  const { data: proposalsData, isLoading } = useQuery({
    queryKey: ['proposals', filterStatus, filterType],
    queryFn: () => api.listProposals({
      page: 1,
      per_page: 20,
      status: filterStatus || undefined,
      type: filterType || undefined,
    }),
  });

  const { data: activeProposals } = useQuery({
    queryKey: ['active-proposals'],
    queryFn: () => api.getActiveProposals(),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Governance</h1>
          <p className="text-slate-500">Participate in community decision-making</p>
        </div>
        <Button
          variant="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={() => setIsCreateModalOpen(true)}
          disabled={!user || !['STANDARD', 'TRUSTED', 'CORE'].includes(user.trust_level)}
        >
          Create Proposal
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
              <Vote className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Active Proposals</p>
              <p className="text-2xl font-bold text-slate-800">{activeProposals?.length || 0}</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/20 text-green-400">
              <CheckCircle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Passed</p>
              <p className="text-2xl font-bold text-slate-800">
                {proposalsData?.items?.filter(p => p.status === 'PASSED').length || 0}
              </p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-red-500/20 text-red-400">
              <XCircle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Rejected</p>
              <p className="text-2xl font-bold text-slate-800">
                {proposalsData?.items?.filter(p => p.status === 'REJECTED').length || 0}
              </p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-violet-500/20 text-violet-400">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Your Trust Weight</p>
              <p className="text-2xl font-bold text-slate-800">
                {user ? ((user.trust_score / 100) ** 1.5).toFixed(2) : '0.00'}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input pr-10 appearance-none cursor-pointer"
          >
            <option value="">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="PASSED">Passed</option>
            <option value="REJECTED">Rejected</option>
            <option value="EXPIRED">Expired</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
        </div>
        <div className="relative">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="input pr-10 appearance-none cursor-pointer"
          >
            <option value="">All Types</option>
            {PROPOSAL_TYPES.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
        </div>
      </div>

      {/* Proposals List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" label="Loading proposals..." />
        </div>
      ) : proposalsData?.items && proposalsData.items.length > 0 ? (
        <div className="space-y-4">
          {proposalsData.items.map((proposal) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              onClick={() => setSelectedProposal(proposal)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Vote className="w-8 h-8" />}
          title="No proposals found"
          description="Be the first to create a governance proposal"
          action={
            <Button
              variant="primary"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setIsCreateModalOpen(true)}
            >
              Create Proposal
            </Button>
          }
        />
      )}

      {/* Create Modal */}
      <CreateProposalModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />

      {/* Detail Modal */}
      {selectedProposal && (
        <ProposalDetailModal
          proposal={selectedProposal}
          onClose={() => setSelectedProposal(null)}
        />
      )}
    </div>
  );
}

// ============================================================================
// Proposal Card Component
// ============================================================================

function ProposalCard({ proposal, onClick }: { proposal: Proposal; onClick: () => void }) {
  const totalVotes = proposal.weight_for + proposal.weight_against;
  const approvalPercent = totalVotes > 0 ? (proposal.weight_for / totalVotes) * 100 : 0;

  return (
    <Card hover onClick={onClick}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className={`badge border ${statusColors[proposal.status]}`}>
              {proposal.status}
            </span>
            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
              {proposal.proposal_type}
            </span>
          </div>
          
          <h3 className="text-lg font-semibold text-slate-800 mb-1">{proposal.title}</h3>
          <p className="text-sm text-slate-500 line-clamp-2">{proposal.description}</p>
          
          <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <Users className="w-3 h-3" />
              {proposal.votes_for + proposal.votes_against + proposal.votes_abstain} voters
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Expires {proposal.voting_ends_at ? formatDistanceToNow(new Date(proposal.voting_ends_at), { addSuffix: true }) : 'Not set'}
            </span>
          </div>
        </div>

        <div className="w-full md:w-48">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-green-400">{proposal.votes_for} for</span>
            <span className="text-red-400">{proposal.votes_against} against</span>
          </div>
          <ProgressBar
            value={approvalPercent}
            color={approvalPercent >= 65 ? 'emerald' : approvalPercent >= 50 ? 'amber' : 'red'}
          />
          <p className="text-xs text-slate-500 text-center mt-1">
            {approvalPercent.toFixed(1)}% approval
          </p>
        </div>
      </div>
    </Card>
  );
}

// ============================================================================
// Create Proposal Modal
// ============================================================================

function CreateProposalModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [formData, setFormData] = useState<CreateProposalRequest>({
    proposal_type: 'POLICY',
    title: '',
    description: '',
    voting_period_days: 7, // 1 week default
  });

  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: CreateProposalRequest) => api.createProposal(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['active-proposals'] });
      onClose();
      setFormData({ proposal_type: 'POLICY', title: '', description: '', voting_period_days: 7 });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Governance Proposal"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={createMutation.isPending}
          >
            Submit Proposal
          </Button>
        </>
      }
    >
      <form className="space-y-4">
        <div>
          <label className="label">Proposal Type</label>
          <select
            value={formData.proposal_type}
            onChange={(e) => setFormData({ ...formData, proposal_type: e.target.value as ProposalType })}
            className="input"
          >
            {PROPOSAL_TYPES.map((type) => (
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
            placeholder="Clear, concise proposal title"
            required
          />
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className="input min-h-32"
            placeholder="Detailed explanation of the proposal..."
            required
          />
        </div>

        <div>
          <label className="label">Voting Period</label>
          <select
            value={formData.voting_period_days}
            onChange={(e) => setFormData({ ...formData, voting_period_days: parseInt(e.target.value) })}
            className="input"
          >
            <option value={24}>24 hours</option>
            <option value={72}>3 days</option>
            <option value={168}>1 week</option>
            <option value={336}>2 weeks</option>
            <option value={720}>30 days</option>
          </select>
        </div>
      </form>
    </Modal>
  );
}

// ============================================================================
// Proposal Detail Modal
// ============================================================================

function ProposalDetailModal({ proposal, onClose }: { proposal: Proposal; onClose: () => void }) {
  const [voteChoice, setVoteChoice] = useState<VoteChoice | null>(null);
  const [rationale, setRationale] = useState('');
  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const { data: ghostRecommendation } = useQuery({
    queryKey: ['ghost-council', proposal.id],
    queryFn: () => api.getGhostCouncilRecommendation(proposal.id),
    enabled: proposal.status === 'ACTIVE',
  });

  const { data: myVote } = useQuery({
    queryKey: ['my-vote', proposal.id],
    queryFn: () => api.getMyVote(proposal.id),
    enabled: proposal.status === 'ACTIVE',
  });

  const voteMutation = useMutation({
    mutationFn: (data: { choice: VoteChoice; rationale?: string }) =>
      api.castVote(proposal.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['my-vote', proposal.id] });
      setVoteChoice(null);
      setRationale('');
    },
  });

  const totalVotes = proposal.weight_for + proposal.weight_against;
  const approvalPercent = totalVotes > 0 ? (proposal.weight_for / totalVotes) * 100 : 0;

  const canVote = proposal.status === 'ACTIVE' && !myVote && user &&
    ['STANDARD', 'TRUSTED', 'CORE'].includes(user.trust_level);

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={proposal.title}
      size="xl"
      footer={
        canVote ? (
          <>
            <Button variant="secondary" onClick={onClose}>Close</Button>
            <Button
              variant="primary"
              onClick={() => voteChoice && voteMutation.mutate({ choice: voteChoice, rationale })}
              loading={voteMutation.isPending}
              disabled={!voteChoice}
            >
              Cast Vote
            </Button>
          </>
        ) : (
          <Button variant="primary" onClick={onClose}>Close</Button>
        )
      }
    >
      <div className="space-y-6">
        {/* Status and Type */}
        <div className="flex items-center gap-2">
          <span className={`badge border ${statusColors[proposal.status]}`}>
            {proposal.status}
          </span>
          <span className="text-sm text-slate-500">{proposal.proposal_type}</span>
        </div>

        {/* Description */}
        <div>
          <h4 className="text-sm font-medium text-slate-500 mb-2">Description</h4>
          <p className="text-slate-800 whitespace-pre-wrap">{proposal.description}</p>
        </div>

        {/* Voting Progress */}
        <div className="p-4 bg-white rounded-lg">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-green-400 flex items-center gap-1">
              <CheckCircle className="w-4 h-4" />
              {proposal.votes_for} votes ({proposal.weight_for.toFixed(2)} weight)
            </span>
            <span className="text-red-400 flex items-center gap-1">
              <XCircle className="w-4 h-4" />
              {proposal.votes_against} votes ({proposal.weight_against.toFixed(2)} weight)
            </span>
          </div>
          <ProgressBar
            value={approvalPercent}
            color={approvalPercent >= 65 ? 'emerald' : approvalPercent >= 50 ? 'amber' : 'red'}
          />
          <div className="flex justify-between mt-2 text-xs text-slate-500">
            <span>{proposal.votes_for + proposal.votes_against + proposal.votes_abstain} total voters</span>
            <span>{approvalPercent.toFixed(1)}% approval</span>
          </div>
        </div>

        {/* Ghost Council */}
        {ghostRecommendation && (
          <div className="ghost-glow p-4 bg-white rounded-lg border border-violet-500/30">
            <div className="flex items-center gap-2 mb-3">
              <Ghost className="w-5 h-5 text-violet-400" />
              <h4 className="font-medium text-slate-800">Ghost Council Recommendation</h4>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <span className={`badge ${
                ghostRecommendation.recommendation === 'APPROVE'
                  ? 'bg-green-500/20 text-green-400'
                  : ghostRecommendation.recommendation === 'REJECT'
                  ? 'bg-red-500/20 text-red-400'
                  : 'bg-slate-500/20 text-slate-500'
              }`}>
                {ghostRecommendation.recommendation}
              </span>
              <span className="text-sm text-slate-500">
                {(ghostRecommendation.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
            <p className="text-sm text-slate-600">{ghostRecommendation.reasoning}</p>
          </div>
        )}

        {/* Already Voted */}
        {myVote && (
          <div className="p-4 bg-white rounded-lg border border-sky-500/30">
            <p className="text-sm text-slate-500 mb-1">You voted:</p>
            <span className={`badge ${
              myVote.choice === 'APPROVE'
                ? 'bg-green-500/20 text-green-400'
                : myVote.choice === 'REJECT'
                ? 'bg-red-500/20 text-red-400'
                : 'bg-slate-500/20 text-slate-500'
            }`}>
              {myVote.choice}
            </span>
            <p className="text-xs text-slate-500 mt-2">Weight: {myVote.weight.toFixed(2)}</p>
          </div>
        )}

        {/* Vote Form */}
        {canVote && (
          <div>
            <h4 className="text-sm font-medium text-slate-800 mb-3">Cast Your Vote</h4>
            <div className="flex gap-2 mb-4">
              {(['APPROVE', 'REJECT', 'ABSTAIN'] as VoteChoice[]).map((choice) => (
                <button
                  key={choice}
                  onClick={() => setVoteChoice(choice)}
                  className={`flex-1 py-2 px-4 rounded-lg border transition-colors ${
                    voteChoice === choice
                      ? choice === 'APPROVE'
                        ? 'bg-green-500/20 border-green-500 text-green-400'
                        : choice === 'REJECT'
                        ? 'bg-red-500/20 border-red-500 text-red-400'
                        : 'bg-slate-500/20 border-slate-500 text-slate-500'
                      : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300'
                  }`}
                >
                  {choice}
                </button>
              ))}
            </div>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Optional: Explain your reasoning..."
              className="input"
            />
          </div>
        )}

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-200 text-sm">
          <div>
            <p className="text-slate-500">Proposer</p>
            <p className="text-slate-800">{proposal.proposer_id}</p>
          </div>
          <div>
            <p className="text-slate-500">Voting Ends</p>
            <p className="text-slate-800">
              {proposal.voting_ends_at ? formatDistanceToNow(new Date(proposal.voting_ends_at), { addSuffix: true }) : 'Not set'}
            </p>
          </div>
        </div>
      </div>
    </Modal>
  );
}
