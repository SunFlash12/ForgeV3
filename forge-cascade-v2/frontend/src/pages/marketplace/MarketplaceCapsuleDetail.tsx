import { useParams, Link } from 'react-router-dom';
import { ShoppingCart, Share2, Heart, GitBranch, Shield, AlertCircle, Loader2 } from 'lucide-react';
import { useMarketplaceCapsule } from '../../hooks/useMarketplace';
import { useCartStore } from '../../stores/cartStore';

export default function MarketplaceCapsuleDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: capsule, isLoading, error } = useMarketplaceCapsule(id || '');
  const { addItem, isInCart } = useCartStore();

  // Loading state
  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-forge-400" />
          <span className="ml-3 text-slate-400">Loading capsule...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !capsule) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col items-center justify-center h-96 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
          <h2 className="text-xl font-semibold text-slate-100 mb-2">Capsule Not Found</h2>
          <p className="text-slate-400 mb-4">
            {error instanceof Error ? error.message : 'The requested capsule could not be loaded.'}
          </p>
          <Link to="/marketplace/browse" className="text-forge-400 hover:text-forge-300 font-medium">
            Browse Capsules
          </Link>
        </div>
      </div>
    );
  }

  // Trust level badge color
  const trustColors: Record<string, string> = {
    'verified': 'text-emerald-400',
    'trusted': 'text-forge-400',
    'community': 'text-amber-400',
    'sandbox': 'text-slate-400',
  };
  const trustColor = trustColors[capsule.trust_level?.toLowerCase()] || 'text-slate-400';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Preview */}
          <div className="bg-gradient-to-br from-forge-500/20 to-ghost-500/20 rounded-xl h-96 mb-6 flex items-center justify-center">
            <span className="text-forge-400 text-lg">{capsule.type || 'Knowledge'} Capsule</span>
          </div>

          {/* Description */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4 text-slate-100">Content</h2>
            <p className="text-slate-300 leading-relaxed whitespace-pre-wrap">
              {capsule.content || 'No content available.'}
            </p>
          </div>

          {/* Lineage */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center gap-2 mb-4">
              <GitBranch className="w-5 h-5 text-forge-400" />
              <h2 className="text-xl font-semibold text-slate-100">Lineage</h2>
            </div>
            <div className="border-l-2 border-forge-500/30 pl-4 space-y-4">
              <div className="relative">
                <div className="absolute -left-6 w-3 h-3 bg-forge-500 rounded-full" />
                <p className="text-sm text-slate-400">Current Version</p>
                <p className="font-medium text-slate-100">{capsule.version || 'v1.0'}</p>
              </div>
              {capsule.parent_id && (
                <div className="relative">
                  <div className="absolute -left-6 w-3 h-3 bg-slate-600 rounded-full" />
                  <p className="text-sm text-slate-400">Derived from</p>
                  <Link to={`/marketplace/capsule/${capsule.parent_id}`} className="font-medium text-forge-400 hover:text-forge-300">
                    Parent Capsule
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Tags */}
          {capsule.tags && capsule.tags.length > 0 && (
            <div className="bg-white/5 rounded-xl border border-white/10 p-6 mt-6">
              <h2 className="text-xl font-semibold mb-4 text-slate-100">Tags</h2>
              <div className="flex flex-wrap gap-2">
                {capsule.tags.map((tag: string) => (
                  <span key={tag} className="px-3 py-1 bg-white/10 text-slate-300 rounded-full text-sm">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-white/5 rounded-xl border border-white/10 p-6 sticky top-8">
            <span className="text-xs font-medium text-forge-400 bg-forge-500/15 px-2 py-1 rounded">
              {capsule.type || 'Knowledge'}
            </span>
            <h1 className="text-2xl font-bold mt-3 mb-2 text-slate-100">{capsule.title || `Capsule ${id}`}</h1>

            {/* Trust Badge */}
            <div className={`flex items-center gap-2 mb-6 ${trustColor}`}>
              <Shield className="w-5 h-5" />
              <span className="text-sm font-medium capitalize">{capsule.trust_level || 'Unknown'} Trust</span>
            </div>

            {/* Stats */}
            <div className="flex items-center gap-4 mb-6 text-sm text-slate-400">
              <span>{capsule.view_count || 0} views</span>
              <span>{capsule.fork_count || 0} forks</span>
            </div>

            {/* Actions */}
            <div className="space-y-3">
              <button
                onClick={() => addItem(capsule)}
                disabled={isInCart(capsule.id)}
                className="w-full bg-forge-500 text-white py-3 rounded-lg font-semibold hover:bg-forge-600 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ShoppingCart className="w-5 h-5" />
                {isInCart(capsule.id) ? 'In Cart' : 'Add to Cart'}
              </button>
              <div className="flex gap-3">
                <button className="flex-1 border border-white/10 py-3 rounded-lg font-medium hover:bg-white/5 text-slate-300 transition flex items-center justify-center gap-2">
                  <Heart className="w-5 h-5" />
                  Save
                </button>
                <button className="flex-1 border border-white/10 py-3 rounded-lg font-medium hover:bg-white/5 text-slate-300 transition flex items-center justify-center gap-2">
                  <Share2 className="w-5 h-5" />
                  Share
                </button>
              </div>
            </div>

            {/* Creator Info */}
            <div className="mt-6 pt-6 border-t border-white/10">
              <p className="text-sm text-slate-400 mb-2">Created by</p>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-forge-500/15 rounded-full flex items-center justify-center">
                  <span className="text-forge-400 font-medium">
                    {capsule.owner_id?.charAt(0)?.toUpperCase() || '?'}
                  </span>
                </div>
                <div>
                  <p className="font-medium text-slate-100">{capsule.owner_id || 'Unknown'}</p>
                  <p className="text-sm text-slate-400">
                    {capsule.created_at ? new Date(capsule.created_at).toLocaleDateString() : ''}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
