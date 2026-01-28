import { Navigate, Link } from 'react-router-dom';
import { Package, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useMyPurchases } from '../../hooks/useMarketplace';

export default function MarketplacePurchases() {
  const { user, isLoading: authLoading, isAuthenticated } = useAuthStore();
  const { data: purchases, isLoading: purchasesLoading, error, refetch } = useMyPurchases();

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-forge-400" />
        <span className="ml-3 text-slate-400">Loading purchases...</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" />;
  }

  const purchaseCount = purchases?.length ?? 0;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-100">My Purchases</h1>
        <p className="mt-1 text-slate-400">
          {purchasesLoading
            ? 'Loading...'
            : `${purchaseCount} capsule${purchaseCount !== 1 ? 's' : ''} purchased`}
        </p>
      </div>

      {/* Purchase List */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        {purchasesLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-forge-400" />
            <span className="ml-2 text-slate-400">Loading purchases...</span>
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
            <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-red-300 mb-4">Failed to load purchases</p>
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
            <Package className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 mb-4">No purchases yet</p>
            <Link
              to="/marketplace/browse"
              className="text-forge-400 hover:text-forge-300 font-medium"
            >
              Browse the marketplace
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {purchases!.map((capsule) => (
              <div
                key={capsule.id}
                className="flex items-center gap-4 p-4 border border-white/10 rounded-xl hover:bg-white/5 transition"
              >
                <div className="w-12 h-12 bg-gradient-to-br from-forge-500/20 to-ghost-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Package className="w-6 h-6 text-forge-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <Link
                    to={`/marketplace/capsule/${capsule.id}`}
                    className="font-semibold text-slate-100 hover:text-forge-400 truncate block"
                  >
                    {capsule.title}
                  </Link>
                  <p className="text-sm text-slate-400">
                    {capsule.category || capsule.type}
                    {capsule.author_name && ` · by ${capsule.author_name}`}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="font-bold text-slate-100">
                    {capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}
                  </p>
                  <p className="text-xs text-slate-500">
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
