import { useState } from 'react';
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
  Database,
  Lightbulb,
  AlertCircle,
  BookOpen,
  Cpu,
  Landmark,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Sparkles,
} from 'lucide-react';
import { api } from '../api/client';
import { Card, LoadingSpinner, EmptyState } from '../components/common';
import { Link } from 'react-router-dom';
import type { Proposal } from '../types';

// Council member icons by icon field (new mapping for expanded council)
const memberIconMap: Record<string, typeof Shield> = {
  'scale': Scale,
  'shield': Shield,
  'landmark': Landmark,
  'cpu': Cpu,
  'database': Database,
  'lightbulb': Lightbulb,
  'users': Users,
  'trending-up': TrendingUp,
  'alert-triangle': AlertCircle,
  'book-open': BookOpen,
  // Legacy role-based mapping
  'Ethics Advisor': Scale,
  'Security Expert': Shield,
  'Governance Expert': GitBranch,
  'Technical Expert': Brain,
  'Community Advocate': Users,
};

// Domain colors for visual distinction
const domainColors: Record<string, { bg: string; text: string; border: string }> = {
  ethics: { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/30' },
  security: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30' },
  governance: { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/30' },
  engineering: { bg: 'bg-cyan-500/15', text: 'text-cyan-400', border: 'border-cyan-500/30' },
  data: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  innovation: { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30' },
  community: { bg: 'bg-pink-500/15', text: 'text-pink-400', border: 'border-pink-500/30' },
  economics: { bg: 'bg-green-500/15', text: 'text-green-400', border: 'border-green-500/30' },
  risk: { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30' },
  history: { bg: 'bg-indigo-500/15', text: 'text-indigo-400', border: 'border-indigo-500/30' },
  general: { bg: 'bg-white/5', text: 'text-slate-300', border: 'border-white/10' },
};

interface CouncilMember {
  id: string;
  name: string;
  role: string;
  domain?: string;
  icon?: string;
  weight: number;
  persona?: string;
}

interface CouncilIssue {
  id: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  affected_entities: string[];
  detected_at: string;
  source: string;
  resolved: boolean;
  resolution: string | null;
  has_ghost_council_opinion: boolean;
}

export default function GhostCouncilPage() {
  const [expandedMember, setExpandedMember] = useState<string | null>(null);
  const [showPerspectiveInfo, setShowPerspectiveInfo] = useState(false);

  // Fetch council members
  const { data: members = [], isLoading: membersLoading } = useQuery<CouncilMember[]>({
    queryKey: ['ghost-council-members'],
    queryFn: () => api.getGhostCouncilMembers(),
  });

  // Fetch active issues
  const { data: issues = [], isLoading: issuesLoading } = useQuery<CouncilIssue[]>({
    queryKey: ['ghost-council-issues'],
    queryFn: () => api.getGhostCouncilIssues(),
  });

  // Fetch council stats
  const { data: stats } = useQuery({
    queryKey: ['ghost-council-stats'],
    queryFn: () => api.getGhostCouncilStats(),
  });

  // Fetch active proposals for recommendation display
  const { data: activeProposals } = useQuery<Proposal[]>({
    queryKey: ['active-proposals'],
    queryFn: () => api.getActiveProposals(),
  });

  const isLoading = membersLoading || issuesLoading;

  // Group members by category
  const groupedMembers = {
    core: members.filter(m => ['gc_ethics', 'gc_security', 'gc_governance'].includes(m.id)),
    technical: members.filter(m => ['gc_technical', 'gc_data', 'gc_innovation'].includes(m.id)),
    community: members.filter(m => ['gc_community', 'gc_economics', 'gc_risk'].includes(m.id)),
    wisdom: members.filter(m => ['gc_history'].includes(m.id)),
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" label="Loading Ghost Council..." />
      </div>
    );
  }

  const getMemberIcon = (member: CouncilMember) => {
    if (member.icon && memberIconMap[member.icon]) {
      return memberIconMap[member.icon];
    }
    if (memberIconMap[member.role]) {
      return memberIconMap[member.role];
    }
    return Ghost;
  };

  const getDomainStyle = (domain?: string) => {
    return domainColors[domain || 'general'] || domainColors.general;
  };

  return (
    <div className="px-3 sm:px-4 lg:px-6 py-4 sm:py-6 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="p-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-sky-500/20 border border-violet-500/30">
          <Ghost className="w-10 h-10 text-violet-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Ghost Council</h1>
          <p className="text-slate-400">
            AI Advisory Board with Tri-Perspective Analysis
          </p>
        </div>
      </div>

      {/* Enhanced Explanation Card */}
      <Card className="bg-gradient-to-r from-violet-900/20 to-sky-900/20 border-violet-700">
        <div className="flex gap-4">
          <div className="flex-shrink-0">
            <Brain className="w-8 h-8 text-violet-500" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-slate-100 mb-2">What is the Ghost Council?</h3>
            <p className="text-slate-300 text-sm leading-relaxed">
              The Ghost Council is an expanded AI-powered advisory board consisting of <strong>{members.length} specialized members</strong>.
              Each member analyzes every proposal from <strong>three distinct perspectives</strong> before synthesizing a final position,
              ensuring thorough, unbiased analysis that considers all angles.
            </p>

            {/* Tri-Perspective Toggle */}
            <button
              onClick={() => setShowPerspectiveInfo(!showPerspectiveInfo)}
              className="mt-3 flex items-center gap-2 text-violet-400 text-sm hover:text-violet-300"
            >
              {showPerspectiveInfo ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              <span>Learn about Tri-Perspective Analysis</span>
            </button>

            {showPerspectiveInfo && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-3 bg-green-900/30 rounded-lg border border-green-700">
                  <div className="flex items-center gap-2 mb-2">
                    <ThumbsUp className="w-4 h-4 text-green-400" />
                    <span className="font-medium text-green-300">Optimistic</span>
                  </div>
                  <p className="text-xs text-green-400">
                    Best-case outcomes, benefits, opportunities, and positive precedents
                  </p>
                </div>
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-600">
                  <div className="flex items-center gap-2 mb-2">
                    <Minus className="w-4 h-4 text-slate-300" />
                    <span className="font-medium text-slate-300">Balanced</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Objective facts, trade-offs, implementation realities, alternatives
                  </p>
                </div>
                <div className="p-3 bg-red-900/30 rounded-lg border border-red-700">
                  <div className="flex items-center gap-2 mb-2">
                    <ThumbsDown className="w-4 h-4 text-red-400" />
                    <span className="font-medium text-red-300">Critical</span>
                  </div>
                  <p className="text-xs text-red-400">
                    Risks, concerns, worst-case scenarios, failure modes
                  </p>
                </div>
              </div>
            )}

            <p className="text-slate-400 text-xs mt-3">
              Note: The Ghost Council provides advisory opinions only. Final decisions rest with the community through the governance process.
            </p>
          </div>
        </div>
      </Card>

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/20 rounded-lg">
              <Users className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">
                {members.length}
              </div>
              <div className="text-sm text-slate-400">Council Members</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-forge-500/20 rounded-lg">
              <FileText className="w-5 h-5 text-forge-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">
                {stats?.proposals_reviewed || 0}
              </div>
              <div className="text-sm text-slate-400">Proposals Reviewed</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">
                {stats?.issues_responded || 0}
              </div>
              <div className="text-sm text-slate-400">Issues Addressed</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">
                {stats?.unanimous_decisions || 0}
              </div>
              <div className="text-sm text-slate-400">Unanimous</div>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-pink-500/20 rounded-lg">
              <TrendingUp className="w-5 h-5 text-pink-400" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-100">
                {stats?.cache_hits || 0}
              </div>
              <div className="text-sm text-slate-400">Cache Hits</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Council Members - Expanded Grid */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
          <Users className="w-5 h-5 text-violet-400" />
          Council Members ({members.length})
        </h2>

        {members.length === 0 ? (
          <p className="text-slate-400 text-sm">No council members configured</p>
        ) : (
          <div className="space-y-6">
            {/* Core Advisors */}
            {groupedMembers.core.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
                  <Sparkles className="w-4 h-4" />
                  Core Advisors (Higher Weight)
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {groupedMembers.core.map((member) => (
                    <MemberCard
                      key={member.id}
                      member={member}
                      isExpanded={expandedMember === member.id}
                      onToggle={() => setExpandedMember(expandedMember === member.id ? null : member.id)}
                      icon={getMemberIcon(member)}
                      domainStyle={getDomainStyle(member.domain)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Technical Specialists */}
            {groupedMembers.technical.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
                  <Cpu className="w-4 h-4" />
                  Technical Specialists
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {groupedMembers.technical.map((member) => (
                    <MemberCard
                      key={member.id}
                      member={member}
                      isExpanded={expandedMember === member.id}
                      onToggle={() => setExpandedMember(expandedMember === member.id ? null : member.id)}
                      icon={getMemberIcon(member)}
                      domainStyle={getDomainStyle(member.domain)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Community & Human Factors */}
            {groupedMembers.community.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
                  <Users className="w-4 h-4" />
                  Community & Human Factors
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {groupedMembers.community.map((member) => (
                    <MemberCard
                      key={member.id}
                      member={member}
                      isExpanded={expandedMember === member.id}
                      onToggle={() => setExpandedMember(expandedMember === member.id ? null : member.id)}
                      icon={getMemberIcon(member)}
                      domainStyle={getDomainStyle(member.domain)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Wisdom & Context */}
            {groupedMembers.wisdom.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
                  <BookOpen className="w-4 h-4" />
                  Wisdom & Context
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {groupedMembers.wisdom.map((member) => (
                    <MemberCard
                      key={member.id}
                      member={member}
                      isExpanded={expandedMember === member.id}
                      onToggle={() => setExpandedMember(expandedMember === member.id ? null : member.id)}
                      icon={getMemberIcon(member)}
                      domainStyle={getDomainStyle(member.domain)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Active Issues */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
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
                    ? 'bg-red-900/20 border-red-700'
                    : issue.severity === 'high'
                    ? 'bg-amber-900/20 border-amber-700'
                    : 'bg-slate-800/50 border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                        issue.severity === 'critical'
                          ? 'bg-red-500/15 text-red-400'
                          : issue.severity === 'high'
                          ? 'bg-amber-500/15 text-amber-400'
                          : 'bg-white/10 text-slate-300'
                      }`}>
                        {issue.severity.toUpperCase()}
                      </span>
                      <span className="text-xs text-slate-400">{issue.category}</span>
                    </div>
                    <h4 className="font-medium text-slate-100">{issue.title}</h4>
                    <p className="text-sm text-slate-300 mt-1">{issue.description}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                      <span>Source: {issue.source}</span>
                      <span>Detected: {new Date(issue.detected_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    {issue.has_ghost_council_opinion ? (
                      <div className="flex items-center gap-1 text-green-400">
                        <CheckCircle className="w-4 h-4" />
                        <span className="text-xs">Reviewed</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-amber-400">
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

      {/* Proposals Awaiting Recommendation */}
      {activeProposals && activeProposals.length > 0 && (
        <Card>
          <h2 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
            <Scale className="w-5 h-5 text-forge-400" />
            Proposals for Council Review
          </h2>
          <p className="text-sm text-slate-400 mb-4">
            These active proposals can receive Ghost Council recommendations with full tri-perspective analysis.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeProposals.slice(0, 6).map((proposal) => (
              <Link
                key={proposal.id}
                to={`/governance?proposal=${proposal.id}`}
                className="p-4 bg-surface-800 rounded-lg border border-white/10 hover:border-forge-500/40 hover:shadow-sm transition group"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs bg-forge-500/10 text-forge-400 px-2 py-0.5 rounded">
                    {proposal.proposal_type}
                  </span>
                  <Activity className="w-4 h-4 text-slate-400 group-hover:text-forge-400" />
                </div>
                <h4 className="font-medium text-slate-100 group-hover:text-forge-400 mb-1">
                  {proposal.title}
                </h4>
                <p className="text-xs text-slate-400 line-clamp-2">
                  {proposal.description}
                </p>
                <div className="flex items-center gap-3 mt-3 text-xs text-slate-400">
                  <span className="text-green-400">{proposal.votes_for} for</span>
                  <span className="text-red-400">{proposal.votes_against} against</span>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* How It Works - Updated for Tri-Perspective */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
          <Eye className="w-5 h-5 text-violet-400" />
          How the Ghost Council Works
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 bg-violet-900/30 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-violet-400">1</span>
            </div>
            <h4 className="font-medium text-slate-100 mb-1">Issue Detection</h4>
            <p className="text-sm text-slate-400">
              System monitors for serious issues and escalates them to the council.
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 bg-forge-500/20 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-forge-400">2</span>
            </div>
            <h4 className="font-medium text-slate-100 mb-1">Tri-Perspective Analysis</h4>
            <p className="text-sm text-slate-400">
              Each member analyzes from <strong>optimistic</strong>, <strong>balanced</strong>, and <strong>critical</strong> viewpoints.
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 bg-amber-900/30 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-amber-400">3</span>
            </div>
            <h4 className="font-medium text-slate-100 mb-1">Synthesis</h4>
            <p className="text-sm text-slate-400">
              Members synthesize all perspectives into a weighted final position.
            </p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-3 bg-green-900/30 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-green-400">4</span>
            </div>
            <h4 className="font-medium text-slate-100 mb-1">Recommendation</h4>
            <p className="text-sm text-slate-400">
              Council reaches consensus with aggregated perspectives summary.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Member Card Component
function MemberCard({
  member,
  isExpanded,
  onToggle,
  icon: IconComponent,
  domainStyle,
}: {
  member: CouncilMember;
  isExpanded: boolean;
  onToggle: () => void;
  icon: typeof Shield;
  domainStyle: { bg: string; text: string; border: string };
}) {
  return (
    <div
      className={`p-3 bg-surface-800 rounded-lg border transition cursor-pointer hover:shadow-sm ${
        isExpanded ? `${domainStyle.border} shadow-sm` : 'border-white/10 hover:border-violet-600'
      }`}
      onClick={onToggle}
    >
      <div className="flex items-start gap-3">
        <div className={`p-2 ${domainStyle.bg} rounded-lg flex-shrink-0`}>
          <IconComponent className={`w-4 h-4 ${domainStyle.text}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-slate-100 truncate">{member.name}</h4>
            <span className={`text-xs ${domainStyle.bg} ${domainStyle.text} px-2 py-0.5 rounded`}>
              {member.weight}x
            </span>
          </div>
          <p className="text-xs text-slate-400">{member.role}</p>
          {member.domain && (
            <p className="text-xs text-slate-400 mt-0.5">Domain: {member.domain}</p>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
        )}
      </div>

      {isExpanded && member.persona && (
        <div className="mt-3 pt-3 border-t border-white/10">
          <p className="text-xs text-slate-300 whitespace-pre-line leading-relaxed">
            {member.persona.split('\n').slice(0, 6).join('\n')}
          </p>
          <div className="mt-2 flex gap-2">
            <span className="inline-flex items-center gap-1 text-xs text-green-400">
              <ThumbsUp className="w-3 h-3" /> Optimistic
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-slate-400">
              <Minus className="w-3 h-3" /> Balanced
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-red-400">
              <ThumbsDown className="w-3 h-3" /> Critical
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
