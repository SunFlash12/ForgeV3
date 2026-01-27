import { Navigate, Link } from 'react-router-dom';
import {
  Package,
  Heart,
  Settings,
  Loader2,
  AlertCircle,
  RefreshCw,
  Mail,
  Award,
  Calendar,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useMyPurchases } from '../hooks/useCapsules';

const trustBadgeColors: Record<string, string> = {
  CORE: 'bg-red-100 text-red-700',
  TRUSTED: 'bg-blue-100 text-blue-700',
  STANDARD: 'bg-yellow-100 text-yellow-700',
  SANDBOX: 'bg-gray-100 text-gray-600',
};

export default function Profile() {
  const { user, isLoading: authLoading, isAuthenticated, logout } = useAuth();
  const { data: purchases, isLoading: purchasesLoading, error, refetch } = useMyPurchases();

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <span className="ml-3 text-gray-600">Loading profile...</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" />;
  }

  const memberSince = new Date(user.created_at).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });

  const purchaseCount = purchases?.length ?? 0;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Profile Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 bg-indigo-100 rounded-full flex items-center justify-center">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.username}
                  className="w-20 h-20 rounded-full object-cover"
                />
              ) : (
                <span className="text-3xl font-bold text-indigo-600">
                  {(user.display_name || user.username).charAt(0).toUpperCase()}
                </span>
              )}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {user.display_name || user.username}
              </h1>
              <p className="text-gray-500 flex items-center gap-1 mt-1">
                <Mail className="w-4 h-4" />
                {user.email}
              </p>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-gray-500 text-sm flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  Member since {memberSince}
                </span>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${trustBadgeColors[user.trust_level] || trustBadgeColors.SANDBOX}`}
                >
                  <Award className="w-3 h-3" />
                  {user.trust_level}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 border border-gray-300 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition text-gray-700"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <Package className="w-8 h-8 text-indigo-600 mx-auto mb-2" />
          <p className="text-2xl font-bold">{purchasesLoading ? '—' : purchaseCount}</p>
          <p className="text-sm text-gray-500">Purchases</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <Heart className="w-8 h-8 text-pink-600 mx-auto mb-2" />
          <p className="text-2xl font-bold">—</p>
          <p className="text-sm text-gray-500">Wishlist</p>
        </div>
        <Link
          to="/settings"
          className="bg-white rounded-xl border border-gray-200 p-4 text-center hover:bg-gray-50 transition"
        >
          <Settings className="w-8 h-8 text-gray-600 mx-auto mb-2" />
          <p className="text-sm font-medium mt-2">Settings</p>
        </Link>
      </div>

      {/* Recent Purchases */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-xl font-semibold mb-4">Recent Purchases</h2>
        {purchasesLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            <span className="ml-2 text-gray-500">Loading purchases...</span>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-red-600 mb-4">Failed to load purchases</p>
            <button
              onClick={() => refetch()}
              className="inline-flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>
          </div>
        ) : purchaseCount === 0 ? (
          <div className="text-center py-12">
            <Package className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-4">No purchases yet</p>
            <Link
              to="/browse"
              className="text-indigo-600 hover:text-indigo-700 font-medium"
            >
              Browse the marketplace
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {purchases!.map((capsule) => (
              <div
                key={capsule.id}
                className="flex items-center gap-4 p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition"
              >
                <div className="w-12 h-12 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Package className="w-6 h-6 text-indigo-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <Link
                    to={`/capsule/${capsule.id}`}
                    className="font-semibold text-gray-900 hover:text-indigo-600 truncate block"
                  >
                    {capsule.title}
                  </Link>
                  <p className="text-sm text-gray-500">
                    {capsule.category || capsule.type}
                    {capsule.author_name && ` · by ${capsule.author_name}`}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="font-bold text-gray-900">
                    {capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}
                  </p>
                  <p className="text-xs text-gray-400">
                    {new Date(capsule.updated_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
