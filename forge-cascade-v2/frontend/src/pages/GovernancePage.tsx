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
  ArrowRightLeft,
  UserCheck,
  Trash2,
  Loader2,
  Search,
  Scale,
  AlertTriangle,
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
  VOTING: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  PASSED: 'bg-green-500/20 text-green-400 border-green-500/30',
  REJECTED: 'bg-red-500/20 text-red-400 border-red-500/30',
  EXECUTED: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  CANCELLED: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
};

export default function GovernancePage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('ACTIVE');
  const [filterType, setFilterType] = useState<string>('');
  const [showDelegationPanel, setShowDelegationPanel] = useState(false);
  const [showDelegationModal, setShowDelegationModal] = useState(false);

  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const { data: proposalsData, isLoading } = useQuery({
    queryKey: ['proposals', filterStatus, filterType],
    queryFn: () => api.listProposals({
      page: 1,
      page_size: 20,
      status: filterStatus || undefined,
      type: filterType || undefined,
    }),
  });

  const { data: activeProposals } = useQuery({
    queryKey: ['active-proposals'],
    queryFn: () => api.getActiveProposals(),
  });

  // Delegation queries
  const { data: delegations, isLoading: delegationsLoading } = useQuery({
    queryKey: ['my-delegations'],
    queryFn: () => api.getDelegations(),
    enabled: !!user,
  });

  const { data: receivedDelegations } = useQuery({
    queryKey: ['received-delegations'],
    queryFn: () => api.getDelegations(), // This would need a different endpoint for received delegations
    enabled: !!user,
  });

  // Revoke delegation mutation
  const revokeDelegationMutation = useMutation({
    mutationFn: (id: string) => api.revokeDelegation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-delegations'] });
    },
  });

  // Calculate delegation stats
  const activeDelegations = delegations?.filter((d: { is_active: boolean }) => d.is_active) || [];
  const totalDelegatedWeight = activeDelegations.reduce((sum: number, d: { weight: number }) => sum + (d.weight || 0), 0);

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

      {/* Delegation Management */}
      <Card className="overflow-hidden">
        <button
          onClick={() => setShowDelegationPanel(!showDelegationPanel)}
          className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-violet-500/20 text-violet-400">
              <ArrowRightLeft className="w-5 h-5" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-slate-800">Vote Delegation</h3>
              <p className="text-sm text-slate-500">
                {activeDelegations.length} active delegation{activeDelegations.length !== 1 ? 's' : ''}
                {totalDelegatedWeight > 0 && ` • ${totalDelegatedWeight.toFixed(2)} weight delegated`}
              </p>
            </div>
          </div>
          <ChevronDown className={`w-5 h-5 text-slate-400 transition-transform ${showDelegationPanel ? 'rotate-180' : ''}`} />
        </button>

        {showDelegationPanel && (
          <div className="border-t border-slate-100 p-4">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-slate-600">
                Delegate your voting power to trusted community members who can vote on your behalf.
              </p>
              <Button
                variant="primary"
                size="sm"
                icon={<Plus className="w-4 h-4" />}
                onClick={() => setShowDelegationModal(true)}
                disabled={!user || !['STANDARD', 'TRUSTED', 'CORE'].includes(user.trust_level)}
              >
                Add Delegation
              </Button>
            </div>

            {delegationsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
              </div>
            ) : activeDelegations.length > 0 ? (
              <div className="space-y-3">
                {activeDelegations.map((delegation: {
                  id: string;
                  delegate_id: string;
                  delegate_username?: string;
                  proposal_types: string[];
                  weight: number;
                  created_at: string;
                  expires_at?: string;
                }) => (
                  <div
                    key={delegation.id}
                    className="flex items-center justify-between p-3 bg-slate-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center text-white font-semibold">
                        {(delegation.delegate_username || delegation.delegate_id)[0].toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-slate-800">
                          {delegation.delegate_username || delegation.delegate_id}
                        </p>
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <span>Weight: {delegation.weight?.toFixed(2) || '1.00'}</span>
                          {delegation.proposal_types && delegation.proposal_types.length > 0 && (
                            <>
                              <span>•</span>
                              <span>{delegation.proposal_types.join(', ')}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {delegation.expires_at && (
                        <span className="text-xs text-slate-500">
                          Expires {formatDistanceToNow(new Date(delegation.expires_at), { addSuffix: true })}
                        </span>
                      )}
                      <button
                        onClick={() => revokeDelegationMutation.mutate(delegation.id)}
                        className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        title="Revoke delegation"
                        disabled={revokeDelegationMutation.isPending}
                      >
                        {revokeDelegationMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <UserCheck className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <p className="text-slate-500 text-sm">No active delegations</p>
                <p className="text-xs text-slate-400 mt-1">
                  Delegate your voting power to participate even when you're away
                </p>
              </div>
            )}
          </div>
        )}
      </Card>

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

      {/* Delegation Modal */}
      <CreateDelegationModal
        isOpen={showDelegationModal}
        onClose={() => setShowDelegationModal(false)}
      />
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

  const { data: constitutionalAnalysis, isLoading: analysisLoading } = useQuery({
    queryKey: ['constitutional-analysis', proposal.id],
    queryFn: () => api.getConstitutionalAnalysis(proposal.id),
    enabled: proposal.proposal_type === 'CONSTITUTIONAL' || proposal.status === 'ACTIVE',
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

        {/* Constitutional Analysis */}
        {(proposal.proposal_type === 'CONSTITUTIONAL' || constitutionalAnalysis) && (
          <div className={`p-4 rounded-lg border ${
            analysisLoading ? 'bg-slate-50 border-slate-200' :
            constitutionalAnalysis?.is_constitutional
              ? 'bg-emerald-50 border-emerald-200'
              : 'bg-red-50 border-red-200'
          }`}>
            <div className="flex items-center gap-2 mb-3">
              <Scale className={`w-5 h-5 ${
                analysisLoading ? 'text-slate-400' :
                constitutionalAnalysis?.is_constitutional ? 'text-emerald-600' : 'text-red-600'
              }`} />
              <h4 className="font-medium text-slate-800">Constitutional Analysis</h4>
              {constitutionalAnalysis && (
                <span className={`ml-auto text-sm font-medium ${
                  constitutionalAnalysis.is_constitutional ? 'text-emerald-600' : 'text-red-600'
                }`}>
                  {constitutionalAnalysis.is_constitutional ? 'COMPLIANT' : 'NON-COMPLIANT'}
                </span>
              )}
            </div>

            {analysisLoading ? (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Analyzing constitutional compliance...</span>
              </div>
            ) : constitutionalAnalysis ? (
              <div className="space-y-3">
                <p className="text-sm text-slate-700">{constitutionalAnalysis.summary}</p>

                {/* Principles Checked */}
                <div className="space-y-2">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Principles Checked</p>
                  {constitutionalAnalysis.principles_checked.map((principle, idx) => (
                    <div
                      key={idx}
                      className={`flex items-start gap-2 p-2 rounded ${
                        principle.compliant ? 'bg-white/50' : 'bg-red-100/50'
                      }`}
                    >
                      {principle.compliant ? (
                        <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                      )}
                      <div>
                        <p className="text-sm font-medium text-slate-800">{principle.principle}</p>
                        <p className="text-xs text-slate-600">{principle.notes}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">Constitutional analysis not available.</p>
            )}
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

// ============================================================================
// Create Delegation Modal
// ============================================================================

function CreateDelegationModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [delegateSearch, setDelegateSearch] = useState('');
  const [selectedDelegate, setSelectedDelegate] = useState<{ id: string; username: string } | null>(null);
  const [selectedTypes, setSelectedTypes] = useState<ProposalType[]>([]);
  const [expirationDays, setExpirationDays] = useState(30);
  const queryClient = useQueryClient();

  // Search for users to delegate to
  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['user-search', delegateSearch],
    queryFn: () => api.searchUsers({ query: delegateSearch, limit: 5 }),
    enabled: delegateSearch.length >= 2,
  });

  const createDelegationMutation = useMutation({
    mutationFn: (data: {
      delegate_id: string;
      proposal_types?: ProposalType[];
      expires_in_days?: number;
    }) => api.createDelegation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-delegations'] });
      onClose();
      // Reset form
      setDelegateSearch('');
      setSelectedDelegate(null);
      setSelectedTypes([]);
      setExpirationDays(30);
    },
  });

  const handleSubmit = () => {
    if (!selectedDelegate) return;
    createDelegationMutation.mutate({
      delegate_id: selectedDelegate.id,
      proposal_types: selectedTypes.length > 0 ? selectedTypes : undefined,
      expires_in_days: expirationDays,
    });
  };

  const toggleType = (type: ProposalType) => {
    setSelectedTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Vote Delegation"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={createDelegationMutation.isPending}
            disabled={!selectedDelegate}
            icon={<UserCheck className="w-4 h-4" />}
          >
            Create Delegation
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {/* Delegate Search */}
        <div>
          <label className="label">Delegate To</label>
          {selectedDelegate ? (
            <div className="flex items-center justify-between p-3 bg-violet-50 border border-violet-200 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center text-white font-semibold">
                  {selectedDelegate.username[0].toUpperCase()}
                </div>
                <span className="font-medium text-slate-800">{selectedDelegate.username}</span>
              </div>
              <button
                onClick={() => setSelectedDelegate(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={delegateSearch}
                onChange={(e) => setDelegateSearch(e.target.value)}
                placeholder="Search for a user by username..."
                className="input pl-10"
              />
              {delegateSearch.length >= 2 && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {searchLoading ? (
                    <div className="p-4 text-center">
                      <Loader2 className="w-5 h-5 text-slate-400 animate-spin mx-auto" />
                    </div>
                  ) : searchResults?.users && searchResults.users.length > 0 ? (
                    searchResults.users.map((user: { id: string; username: string; display_name?: string; trust_level: string }) => (
                      <button
                        key={user.id}
                        onClick={() => {
                          setSelectedDelegate({ id: user.id, username: user.username });
                          setDelegateSearch('');
                        }}
                        className="w-full flex items-center gap-3 p-3 hover:bg-slate-50 transition-colors text-left"
                      >
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-sky-500 to-violet-500 flex items-center justify-center text-white text-sm font-semibold">
                          {user.username[0].toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-slate-800">{user.display_name || user.username}</p>
                          <p className="text-xs text-slate-500">{user.trust_level}</p>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="p-4 text-center text-slate-500 text-sm">
                      No users found
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          <p className="text-xs text-slate-500 mt-1">
            Choose a trusted community member to vote on your behalf
          </p>
        </div>

        {/* Proposal Types */}
        <div>
          <label className="label">Proposal Types (Optional)</label>
          <p className="text-xs text-slate-500 mb-2">
            Leave empty to delegate for all proposal types, or select specific types
          </p>
          <div className="flex flex-wrap gap-2">
            {PROPOSAL_TYPES.map((type) => (
              <button
                key={type}
                onClick={() => toggleType(type)}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  selectedTypes.includes(type)
                    ? 'bg-violet-100 border-violet-300 text-violet-700'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Expiration */}
        <div>
          <label className="label">Delegation Duration</label>
          <div className="flex gap-2">
            {[7, 30, 90, 365].map((days) => (
              <button
                key={days}
                onClick={() => setExpirationDays(days)}
                className={`flex-1 py-2 text-sm rounded-lg border transition-colors ${
                  expirationDays === days
                    ? 'bg-violet-100 border-violet-300 text-violet-700'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                {days < 30 ? `${days} days` : days < 365 ? `${days / 30} month${days > 30 ? 's' : ''}` : '1 year'}
              </button>
            ))}
          </div>
        </div>

        {/* Warning */}
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm text-amber-800">
            <strong>Note:</strong> The delegate will be able to vote on your behalf using your voting weight.
            You can revoke this delegation at any time.
          </p>
        </div>

        {createDelegationMutation.isError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            Failed to create delegation. Please try again.
          </div>
        )}
      </div>
    </Modal>
  );
}
