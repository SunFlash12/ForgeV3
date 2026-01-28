import { Link } from 'react-router-dom';
import { Sparkles, Shield, Zap, ArrowRight, Loader2, ShoppingCart, Users, TrendingUp } from 'lucide-react';
import { useFeaturedCapsules } from '../../hooks/useMarketplace';
import { useCartStore } from '../../stores/cartStore';
import { ApiErrorState } from '../../components/common/ApiErrorState';
import type { FeaturedListing, TokenizationInfo } from '../../types/marketplace';

// Tier badge colors
const tierColors: Record<string, string> = {
  TIER_1: 'from-amber-400 to-orange-500',
  TIER_2: 'from-cyan-400 to-blue-500',
  TIER_3: 'from-violet-400 to-purple-600',
};

const tierLabels: Record<string, string> = {
  TIER_1: 'Genesis T1',
  TIER_2: 'Genesis T2',
  TIER_3: 'Genesis T3',
};

function VirtualsProtocolBadge({ tokenization }: { tokenization: TokenizationInfo }) {
  const isGenesis = tokenization.launch_type === 'GENESIS';
  const tierGradient = tokenization.genesis_tier
    ? tierColors[tokenization.genesis_tier] || 'from-slate-400 to-slate-500'
    : 'from-blue-400 to-cyan-500';
  const tierLabel = tokenization.genesis_tier
    ? tierLabels[tokenization.genesis_tier] || 'Genesis'
    : 'Standard';

  return (
    <div className="mt-3 pt-3 border-t border-white/10">
      {/* Token symbol + launch type */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold px-2 py-0.5 rounded bg-gradient-to-r ${tierGradient} text-white`}>
            ${tokenization.token_symbol}
          </span>
          <span className="text-xs text-slate-400">
            {isGenesis ? tierLabel : 'Standard Launch'}
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-slate-400">
          <Users className="w-3 h-3" />
          <span>{tokenization.total_holders.toLocaleString()}</span>
        </div>
      </div>

      {/* Bonding curve progress bar */}
      <div className="relative">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-slate-400">Bonding Curve</span>
          <span className="text-slate-300 font-medium">{tokenization.graduation_progress.toFixed(1)}%</span>
        </div>
        <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${
              tokenization.graduation_progress >= 90
                ? 'from-emerald-400 to-green-500'
                : tokenization.graduation_progress >= 60
                  ? 'from-cyan-400 to-blue-500'
                  : 'from-amber-400 to-orange-500'
            } transition-all duration-500`}
            style={{ width: `${Math.min(tokenization.graduation_progress, 100)}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs mt-1">
          <span className="text-slate-500">
            {Math.round(tokenization.bonding_curve_virtual_accumulated).toLocaleString()} VIRTUAL
          </span>
          <span className="text-slate-500">
            {Math.round(tokenization.graduation_threshold).toLocaleString()}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function MarketplaceHome() {
  const { data: featuredCapsules, isLoading, isError, error, refetch } = useFeaturedCapsules(16);
  const { addItem, isInCart } = useCartStore();

  const handleAddToCart = (listing: FeaturedListing) => {
    // Convert FeaturedListing to the MarketplaceCapsule shape cartStore expects
    addItem({
      id: listing.capsule_id,
      title: listing.title,
      content: listing.preview_content,
      type: listing.category as 'KNOWLEDGE' | 'INSIGHT' | 'TEMPLATE' | 'CODE' | 'PRINCIPLE' | 'DECISION',
      version: '1.0.0',
      owner_id: '',
      parent_id: null,
      trust_level: 60,
      created_at: '',
      updated_at: '',
      is_archived: false,
      view_count: listing.view_count,
      fork_count: 0,
      tags: listing.tags,
      metadata: {},
      summary: listing.description,
      category: listing.category,
      author_name: listing.author_name,
      price: listing.price,
      is_public: true,
    });
  };

  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-surface-800 via-forge-950 to-surface-900 text-white relative overflow-hidden">
        {/* Subtle inner glow overlay */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-forge-500/10 via-transparent to-transparent pointer-events-none" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 relative z-10">
          <div className="text-center">
            <h1 className="text-5xl font-bold mb-6">
              The Marketplace for<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyber-blue to-forge-300">
                Knowledge Capsules
              </span>
            </h1>
            <p className="text-xl text-slate-300 mb-8 max-w-2xl mx-auto">
              Discover, purchase, and trade verified knowledge assets with full
              provenance tracking and blockchain-backed ownership.
            </p>
            <div className="flex justify-center gap-4">
              <Link
                to="/marketplace/browse"
                className="bg-forge-500 text-white px-8 py-3 rounded-lg font-semibold hover:bg-forge-600 transition"
              >
                Browse Capsules
              </Link>
              <Link
                to="/capsules"
                className="border border-white/20 text-slate-200 px-8 py-3 rounded-lg font-semibold hover:bg-white/10 transition"
              >
                Create Your Own
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center text-slate-100 mb-12">Why Forge Shop?</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center p-6">
              <div className="w-16 h-16 bg-forge-500/15 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="w-8 h-8 text-forge-400" />
              </div>
              <h3 className="text-xl font-semibold text-slate-100 mb-2">Verified Provenance</h3>
              <p className="text-slate-400">
                Every capsule tracks its complete lineage and evolution history,
                ensuring authenticity and attribution.
              </p>
            </div>
            <div className="text-center p-6">
              <div className="w-16 h-16 bg-ghost-500/15 rounded-full flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-8 h-8 text-ghost-400" />
              </div>
              <h3 className="text-xl font-semibold text-slate-100 mb-2">AI-Enhanced Search</h3>
              <p className="text-slate-400">
                Semantic search powered by advanced embeddings helps you find
                exactly what you need.
              </p>
            </div>
            <div className="text-center p-6">
              <div className="w-16 h-16 bg-pink-500/15 rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="w-8 h-8 text-pink-400" />
              </div>
              <h3 className="text-xl font-semibold text-slate-100 mb-2">Instant Delivery</h3>
              <p className="text-slate-400">
                Purchase and access capsules instantly. Integrate them directly
                into your Forge Cascade workspace.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Capsules */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h2 className="text-3xl font-bold text-slate-100">Featured Capsules</h2>
              <p className="text-sm text-slate-400 mt-1 flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4" />
                Powered by Virtuals Protocol token launches
              </p>
            </div>
            <Link
              to="/marketplace/browse"
              className="text-forge-400 hover:text-forge-300 font-medium flex items-center gap-1"
            >
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-forge-400" />
            </div>
          ) : isError ? (
            <ApiErrorState error={error} onRetry={() => refetch()} title="Unable to Load Featured Capsules" />
          ) : featuredCapsules && featuredCapsules.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {featuredCapsules.map((listing: FeaturedListing) => (
                <div
                  key={listing.id}
                  className="bg-white/5 rounded-xl border border-white/10 overflow-hidden hover:border-forge-500/30 transition group"
                >
                  <Link to={`/marketplace/capsule/${listing.capsule_id}`}>
                    <div className="h-32 bg-gradient-to-br from-forge-500/20 to-ghost-500/20 relative">
                      {listing.tokenization && (
                        <div className="absolute top-3 right-3 flex items-center gap-1.5">
                          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-black/40 backdrop-blur-sm text-emerald-300 border border-emerald-500/30">
                            ${listing.tokenization.token_symbol}
                          </span>
                        </div>
                      )}
                      <div className="absolute bottom-3 left-3 flex items-center gap-2">
                        <span className="text-xs font-medium text-forge-300 bg-forge-500/20 backdrop-blur-sm px-2 py-1 rounded border border-forge-500/20">
                          {listing.category}
                        </span>
                      </div>
                    </div>
                  </Link>
                  <div className="p-4">
                    <Link to={`/marketplace/capsule/${listing.capsule_id}`}>
                      <h3 className="font-semibold text-slate-100 mb-1 group-hover:text-forge-400 transition line-clamp-2">
                        {listing.title}
                      </h3>
                    </Link>
                    <p className="text-xs text-slate-500 mb-2">by {listing.author_name}</p>
                    <p className="text-sm text-slate-400 mb-3 line-clamp-2">
                      {listing.preview_content.substring(0, 120)}...
                    </p>

                    <div className="flex justify-between items-center">
                      <span className="font-bold text-slate-100">
                        {listing.price > 0
                          ? `${listing.price.toLocaleString()} ${listing.currency}`
                          : 'Free'}
                      </span>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          handleAddToCart(listing);
                        }}
                        disabled={isInCart(listing.capsule_id)}
                        className={`text-sm font-medium flex items-center gap-1 ${
                          isInCart(listing.capsule_id)
                            ? 'text-emerald-400'
                            : 'text-forge-400 hover:text-forge-300'
                        }`}
                      >
                        {isInCart(listing.capsule_id) ? (
                          'In Cart'
                        ) : (
                          <>
                            <ShoppingCart className="w-4 h-4" />
                            Add
                          </>
                        )}
                      </button>
                    </div>

                    {/* Virtuals Protocol Badge */}
                    {listing.tokenization && (
                      <VirtualsProtocolBadge tokenization={listing.tokenization} />
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-slate-400 mb-4">No capsules available yet.</p>
              <Link
                to="/capsules"
                className="text-forge-400 hover:text-forge-300 font-medium"
              >
                Create the first one on Forge Cascade
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <div className="bg-forge-500/10 border border-forge-500/30 rounded-2xl py-16 px-8">
            <h2 className="text-3xl font-bold text-slate-100 mb-4">Ready to Get Started?</h2>
            <p className="text-slate-300 mb-8">
              Join thousands of creators and learners on Forge Shop.
            </p>
            <Link
              to="/login"
              className="bg-forge-500 text-white px-8 py-3 rounded-lg font-semibold hover:bg-forge-600 transition inline-block"
            >
              Create Free Account
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
