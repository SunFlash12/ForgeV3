import { useQuery } from '@tanstack/react-query';
import {
  Ghost,
  Users,
  AlertTriangle,
  CheckCircle,
  Clock,
  Shield,
  Brain,
  GitBranch,
  Eye,
  Scale,
  Activity,
  FileText,
  TrendingUp,
} from 'lucide-react';
import { api } from '../api/client';
import { Card, LoadingSpinner, EmptyState } from '../components/common';
import { Link } from 'react-router-dom';

// Council member icons by role
const memberIcons: Record<string, typeof Shield> = {
  'Ethics Advisor': Scale,
  'Security Expert': Shield,
  'Governance Expert': GitBranch,
  'Technical Expert': Brain,
  'Community Advocate': Users,
};

export default function GhostCouncilPage() {
  // Fetch council members
  const { data: members = [], isLoading: membersLoading } = useQuery({
    queryKey: ['ghost-council-members'],
    queryFn: () => api.getGhostCouncilMembers(),
  });

  // Fetch active issues
  const { data: issues = [], isLoading: issuesLoading } = useQuery({
    queryKey: ['ghost-council-issues'],
    queryFn: () => api.getGhostCouncilIssues(),
  });

  // Fetch council stats
  const { data: stats } = useQuery({
    queryKey: ['ghost-council-stats'],
    queryFn: () => api.getGhostCouncilStats(),
  });

  // Fetch active proposals for recommendation display
  const { data: activeProposals } = useQuery({
    queryKey: ['active-proposals'],
    queryFn: () => api.getActiveProposals(),
  });

  const isLoading = membersLoading || issuesLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" label="Loading Ghost Council..." />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="p-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-sky-500/20 border border-violet-500/30">
          <Ghost className="w-10 h-10 text-violet-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Ghost Council</h1>
          <p className="text-slate-500">
            AI Advisory Board for Governance & System Issues
          </p>
        </div>
      </div>

      {/* Explanation Card */}
      <Card className="bg-gradient-to-r from-violet-50 to-sky-50 border-violet-200">
        <div className="flex gap-4">
          <div className="flex-shrink-0">
            <Brain className="w-8 h-8 text-violet-500" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-800 mb-2">What is the Ghost Council?</h3>
            <p className="text-slate-600 text-sm leading-relaxed">
              The Ghost Council is an AI-powered advisory board that provides recommendations on governance
              proposals and responds to serious system issues. When critical situations arise or proposals
              require deliberation, the council members analyze the situation from their unique perspectives
              (ethics, security, governance, technical, and community) and provide weighted recommendations.
            </p>
            <p className="text-slate-500 text-xs mt-2">
              Note: The Ghost Council provides advisory opinions only. Final decisions rest with the community through the governance process.
            </p>
          </div>
        </div>
      </Card>

      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <FileText className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">
                {stats?.proposals_reviewed || 0}
              </div>
              <div className="text-sm text-slate-500">Proposals Reviewed</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">
                {stats?.issues_responded || 0}
              </div>
              <div className="text-sm text-slate-500">Issues Addressed</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">
                {stats?.unanimous_decisions || 0}
              </div>
              <div className="text-sm text-slate-500">Unanimous Decisions</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-sky-500/20 rounded-lg">
              <TrendingUp className="w-5 h-5 text-sky-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">
                {stats?.cache_hits || 0}
              </div>
              <div className="text-sm text-slate-500">Cached Opinions</div>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Council Members */}
        <Card className="lg:col-span-1">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-violet-400" />
            Council Members
          </h2>

          {members.length === 0 ? (
            <p className="text-slate-500 text-sm">No council members configured</p>
          ) : (
            <div className="space-y-3">
              {members.map((member) => {
                const Icon = memberIcons[member.role] || Ghost;
                return (
                  <div
                    key={member.id}
                    className="p-3 bg-white rounded-lg border border-slate-200 hover:border-violet-300 transition"
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-violet-100 rounded-lg flex-shrink-0">
                        <Icon className="w-4 h-4 text-violet-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <h4 className="font-medium text-slate-800 truncate">{member.name}</h4>
                          <span className="text-xs bg-violet-100 text-violet-600 px-2 py-0.5 rounded">
                            {member.weight}x
                          </span>
                        </div>
                        <p className="text-xs text-slate-500">{member.role}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Active Issues */}
        <Card className="lg:col-span-2">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            Active Issues Requiring Attention
          </h2>

          {issues.length === 0 ? (
            <EmptyState
              icon={<CheckCircle className="w-10 h-10" />}
              title="No Active Issues"
              description="The system is running smoothly. The Ghost Council will be notified when serious issues arise."
            />
          ) : (
            <div className="space-y-3">
              {issues.map((issue) => (
                <div
                  key={issue.id}
                  className={`p-4 rounded-lg border ${
                    issue.severity === 'critical'
                      ? 'bg-red-50 border-red-200'
                      : issue.severity === 'high'
                      ? 'bg-amber-50 border-amber-200'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          issue.severity === 'critical'
                            ? 'bg-red-200 text-red-700'
                            : issue.severity === 'high'
                            ? 'bg-amber-200 text-amber-700'
                            : 'bg-slate-200 text-slate-700'
                        }`}>
                          {issue.severity.toUpperCase()}
                        </span>
                        <span className="text-xs text-slate-500">{issue.category}</span>
                      </div>
                      <h4 className="font-medium text-slate-800">{issue.title}</h4>
                      <p className="text-sm text-slate-600 mt-1">{issue.description}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                        <span>Source: {issue.source}</span>
                        <span>Detected: {new Date(issue.detected_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      {issue.has_ghost_council_opinion ? (
                        <div className="flex items-center gap-1 text-green-600">
                          <CheckCircle className="w-4 h-4" />
                          <span className="text-xs">Reviewed</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-amber-600">
                          <Clock className="w-4 h-4" />
                          <span className="text-xs">Pending</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Proposals Awaiting Recommendation */}
      {activeProposals && activeProposals.length > 0 && (
        <Card>
          <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Scale className="w-5 h-5 text-sky-400" />
            Proposals for Council Review
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            These active proposals can receive Ghost Council recommendations to help inform voting.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeProposals.slice(0, 6).map((proposal) => (
              <Link
                key={proposal.id}
                to={`/governance?proposal=${proposal.id}`}
                className="p-4 bg-white rounded-lg border border-slate-200 hover:border-sky-300 hover:shadow-sm transition group"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs bg-sky-100 text-sky-600 px-2 py-0.5 rounded">
                    {proposal.proposal_type}
                  </span>
                  <Activity className="w-4 h-4 text-slate-400 group-hover:text-sky-500" />
                </div>
                <h4 className="font-medium text-slate-800 group-hover:text-sky-600 mb-1">
                  {proposal.title}
                </h4>
                <p className="text-xs text-slate-500 line-clamp-2">
                  {proposal.description}
                </p>
                <div className="flex items-center gap-3 mt-3 text-xs text-slate-500">
                  <span className="text-green-600">{proposal.votes_for} for</span>
                  <span className="text-red-600">{proposal.votes_against} against</span>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* How It Works */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Eye className="w-5 h-5 text-violet-400" />
          How the Ghost Council Works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 bg-violet-100 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-violet-600">1</span>
            </div>
            <h4 className="font-medium text-slate-800 mb-1">Issue Detection</h4>
            <p className="text-sm text-slate-500">
              The system monitors for serious issues (security threats, trust violations,
              governance conflicts) and escalates them to the Ghost Council.
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 bg-sky-100 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-sky-600">2</span>
            </div>
            <h4 className="font-medium text-slate-800 mb-1">AI Deliberation</h4>
            <p className="text-sm text-slate-500">
              Each council member analyzes the issue from their unique perspective
              (ethics, security, governance, technical, community) and provides a weighted vote.
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 bg-green-100 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-green-600">3</span>
            </div>
            <h4 className="font-medium text-slate-800 mb-1">Recommendation</h4>
            <p className="text-sm text-slate-500">
              The council reaches consensus and provides a recommendation. For proposals,
              this informs community voting. For issues, it guides resolution.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
