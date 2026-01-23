import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  Users,
  ChevronDown,
  Shield,
  User,
  Mail,
  Calendar,
  Award,
  TrendingUp,
  Filter,
  Loader2,
} from 'lucide-react';
import { format } from 'date-fns';
import { api } from '../api/client';
import {
  Card,
  Button,
  LoadingSpinner,
  EmptyState,
  Modal,
} from '../components/common';
import { useAuthStore } from '../stores/authStore';

const TRUST_LEVELS = ['QUARANTINE', 'SANDBOX', 'STANDARD', 'TRUSTED', 'CORE'];

const trustLevelColors: Record<string, string> = {
  QUARANTINE: 'bg-red-100 text-red-700 border-red-200',
  SANDBOX: 'bg-amber-100 text-amber-700 border-amber-200',
  STANDARD: 'bg-blue-100 text-blue-700 border-blue-200',
  TRUSTED: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  CORE: 'bg-violet-100 text-violet-700 border-violet-200',
};

const trustLevelGradients: Record<string, string> = {
  QUARANTINE: 'from-red-500 to-red-600',
  SANDBOX: 'from-amber-500 to-orange-500',
  STANDARD: 'from-blue-500 to-sky-500',
  TRUSTED: 'from-emerald-500 to-teal-500',
  CORE: 'from-violet-500 to-purple-600',
};

interface UserResult {
  id: string;
  username: string;
  display_name?: string;
  email?: string;
  trust_level: string;
  trust_score: number;
  created_at: string;
  last_active_at?: string;
  capsule_count?: number;
  vote_count?: number;
}

export default function UserDirectoryPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTrustLevel, setFilterTrustLevel] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('trust_score');
  const [selectedUser, setSelectedUser] = useState<UserResult | null>(null);
  const { user: currentUser } = useAuthStore();

  const canViewDirectory = currentUser && ['TRUSTED', 'CORE'].includes(currentUser.trust_level);

  const { data: usersData, isLoading } = useQuery({
    queryKey: ['user-directory', searchQuery, filterTrustLevel, sortBy],
    queryFn: () => api.searchUsers({
      query: searchQuery || undefined,
      trust_level: filterTrustLevel || undefined,
      sort_by: sortBy,
      limit: 50,
    }),
    enabled: canViewDirectory,
  });

  const users = usersData?.users || [];

  if (!canViewDirectory) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <Card className="p-12 text-center">
          <Shield className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-800 mb-2">Access Restricted</h2>
          <p className="text-slate-500 max-w-md mx-auto">
            The User Directory is only available to TRUSTED and CORE level users.
            Continue contributing to the community to increase your trust level.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 mb-2">User Directory</h1>
          <p className="text-slate-500">
            Browse and search community members
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Users className="w-4 h-4" />
          <span>{users.length} users</span>
        </div>
      </div>

      {/* Search and Filters */}
      <Card className="p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by username or display name..."
              className="input pl-10 w-full"
            />
          </div>

          {/* Trust Level Filter */}
          <div className="relative w-full md:w-48">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <select
              value={filterTrustLevel}
              onChange={(e) => setFilterTrustLevel(e.target.value)}
              className="input pl-9 pr-10 appearance-none cursor-pointer w-full"
            >
              <option value="">All Trust Levels</option>
              {TRUST_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          </div>

          {/* Sort */}
          <div className="relative w-full md:w-48">
            <TrendingUp className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="input pl-9 pr-10 appearance-none cursor-pointer w-full"
            >
              <option value="trust_score">Trust Score</option>
              <option value="created_at">Join Date</option>
              <option value="username">Username</option>
              <option value="last_active">Last Active</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          </div>
        </div>
      </Card>

      {/* Users Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" label="Loading users..." />
        </div>
      ) : users.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {users.map((user: UserResult) => (
            <UserCard
              key={user.id}
              user={user}
              onClick={() => setSelectedUser(user)}
              isCurrentUser={user.id === currentUser?.id}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Users className="w-12 h-12" />}
          title="No users found"
          description={searchQuery ? "Try adjusting your search query" : "No users match the current filters"}
        />
      )}

      {/* User Detail Modal */}
      {selectedUser && (
        <UserDetailModal
          user={selectedUser}
          onClose={() => setSelectedUser(null)}
          isCurrentUser={selectedUser.id === currentUser?.id}
        />
      )}
    </div>
  );
}

// ============================================================================
// User Card Component
// ============================================================================

function UserCard({
  user,
  onClick,
  isCurrentUser,
}: {
  user: UserResult;
  onClick: () => void;
  isCurrentUser: boolean;
}) {
  return (
    <Card
      hover
      onClick={onClick}
      className={`relative overflow-hidden ${isCurrentUser ? 'ring-2 ring-sky-500' : ''}`}
    >
      {isCurrentUser && (
        <div className="absolute top-2 right-2 px-2 py-0.5 bg-sky-100 text-sky-700 text-xs rounded-full">
          You
        </div>
      )}

      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className={`w-14 h-14 rounded-full bg-gradient-to-br ${trustLevelGradients[user.trust_level] || 'from-slate-400 to-slate-500'} flex items-center justify-center text-white text-xl font-bold shadow-lg`}>
          {(user.display_name || user.username)[0].toUpperCase()}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-800 truncate">
            {user.display_name || user.username}
          </h3>
          <p className="text-sm text-slate-500 truncate">@{user.username}</p>

          <div className="flex items-center gap-2 mt-2">
            <span className={`text-xs px-2 py-0.5 rounded-full border ${trustLevelColors[user.trust_level]}`}>
              {user.trust_level}
            </span>
            <span className="text-xs text-slate-500">
              Score: {user.trust_score.toFixed(0)}
            </span>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mt-4 pt-4 border-t border-slate-100 text-xs text-slate-500">
        {user.capsule_count !== undefined && (
          <span>{user.capsule_count} capsules</span>
        )}
        {user.vote_count !== undefined && (
          <span>{user.vote_count} votes</span>
        )}
        <span className="ml-auto">
          Joined {format(new Date(user.created_at), 'MMM yyyy')}
        </span>
      </div>
    </Card>
  );
}

// ============================================================================
// User Detail Modal
// ============================================================================

function UserDetailModal({
  user,
  onClose,
  isCurrentUser,
}: {
  user: UserResult;
  onClose: () => void;
  isCurrentUser: boolean;
}) {
  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="User Profile"
      size="md"
    >
      <div className="space-y-6">
        {/* Profile Header */}
        <div className="flex items-center gap-4">
          <div className={`w-20 h-20 rounded-full bg-gradient-to-br ${trustLevelGradients[user.trust_level] || 'from-slate-400 to-slate-500'} flex items-center justify-center text-white text-3xl font-bold shadow-lg`}>
            {(user.display_name || user.username)[0].toUpperCase()}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-slate-800">
                {user.display_name || user.username}
              </h2>
              {isCurrentUser && (
                <span className="px-2 py-0.5 bg-sky-100 text-sky-700 text-xs rounded-full">
                  You
                </span>
              )}
            </div>
            <p className="text-slate-500">@{user.username}</p>
            <span className={`inline-block mt-2 text-sm px-3 py-1 rounded-full border ${trustLevelColors[user.trust_level]}`}>
              {user.trust_level}
            </span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 text-slate-500 mb-1">
              <Award className="w-4 h-4" />
              <span className="text-sm">Trust Score</span>
            </div>
            <p className="text-2xl font-bold text-slate-800">{user.trust_score.toFixed(0)}</p>
          </div>

          {user.capsule_count !== undefined && (
            <div className="p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                <Users className="w-4 h-4" />
                <span className="text-sm">Capsules</span>
              </div>
              <p className="text-2xl font-bold text-slate-800">{user.capsule_count}</p>
            </div>
          )}

          {user.vote_count !== undefined && (
            <div className="p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                <TrendingUp className="w-4 h-4" />
                <span className="text-sm">Votes Cast</span>
              </div>
              <p className="text-2xl font-bold text-slate-800">{user.vote_count}</p>
            </div>
          )}

          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 text-slate-500 mb-1">
              <Calendar className="w-4 h-4" />
              <span className="text-sm">Joined</span>
            </div>
            <p className="text-lg font-semibold text-slate-800">
              {format(new Date(user.created_at), 'MMM d, yyyy')}
            </p>
          </div>
        </div>

        {/* Additional Info */}
        <div className="space-y-3 pt-4 border-t border-slate-200">
          <div className="flex items-center gap-3">
            <User className="w-4 h-4 text-slate-400" />
            <span className="text-sm text-slate-600">User ID: {user.id}</span>
          </div>

          {user.last_active_at && (
            <div className="flex items-center gap-3">
              <Calendar className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-600">
                Last active: {format(new Date(user.last_active_at), 'PPpp')}
              </span>
            </div>
          )}
        </div>

        {/* Trust Level Description */}
        <div className={`p-4 rounded-lg ${
          user.trust_level === 'CORE' ? 'bg-violet-50 border border-violet-200' :
          user.trust_level === 'TRUSTED' ? 'bg-emerald-50 border border-emerald-200' :
          user.trust_level === 'STANDARD' ? 'bg-blue-50 border border-blue-200' :
          user.trust_level === 'SANDBOX' ? 'bg-amber-50 border border-amber-200' :
          'bg-red-50 border border-red-200'
        }`}>
          <h4 className="font-medium text-slate-800 mb-1">Trust Level: {user.trust_level}</h4>
          <p className="text-sm text-slate-600">
            {user.trust_level === 'CORE' && 'Core member with full system access and administrative capabilities.'}
            {user.trust_level === 'TRUSTED' && 'Trusted member with access to advanced features and federation.'}
            {user.trust_level === 'STANDARD' && 'Standard member with full voting and capsule creation rights.'}
            {user.trust_level === 'SANDBOX' && 'New member with limited capabilities while building trust.'}
            {user.trust_level === 'QUARANTINE' && 'Account under review with restricted access.'}
          </p>
        </div>
      </div>
    </Modal>
  );
}
