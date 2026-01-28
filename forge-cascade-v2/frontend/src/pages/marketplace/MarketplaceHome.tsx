import { Link } from 'react-router-dom';
import { Sparkles, Shield, Zap, ArrowRight, Loader2, ShoppingCart } from 'lucide-react';
import { useFeaturedCapsules } from '../../hooks/useMarketplace';
import { useCartStore } from '../../stores/cartStore';
import type { MarketplaceCapsule } from '../../types/marketplace';

export default function MarketplaceHome() {
  const { data: featuredCapsules, isLoading } = useFeaturedCapsules(4);
  const { addItem, isInCart } = useCartStore();

  const handleAddToCart = (capsule: MarketplaceCapsule) => {
    addItem(capsule);
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
            <h2 className="text-3xl font-bold text-slate-100">Featured Capsules</h2>
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
          ) : featuredCapsules && featuredCapsules.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {featuredCapsules.map((capsule: MarketplaceCapsule) => (
                <div
                  key={capsule.id}
                  className="bg-white/5 rounded-xl border border-white/10 overflow-hidden hover:border-forge-500/30 transition"
                >
                  <Link to={`/marketplace/capsule/${capsule.id}`}>
                    <div className="h-40 bg-gradient-to-br from-forge-500/20 to-ghost-500/20" />
                  </Link>
                  <div className="p-4">
                    <span className="text-xs font-medium text-forge-400 bg-forge-500/15 px-2 py-1 rounded">
                      {capsule.category}
                    </span>
                    <Link to={`/marketplace/capsule/${capsule.id}`}>
                      <h3 className="font-semibold text-slate-100 mt-2 mb-1 hover:text-forge-400 transition">
                        {capsule.title}
                      </h3>
                    </Link>
                    <p className="text-sm text-slate-400 mb-3 line-clamp-2">
                      {capsule.summary || capsule.content.substring(0, 80)}...
                    </p>
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-slate-100">
                        {capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}
                      </span>
                      <button
                        onClick={() => handleAddToCart(capsule)}
                        disabled={isInCart(capsule.id)}
                        className={`text-sm font-medium flex items-center gap-1 ${
                          isInCart(capsule.id)
                            ? 'text-emerald-400'
                            : 'text-forge-400 hover:text-forge-300'
                        }`}
                      >
                        {isInCart(capsule.id) ? (
                          'In Cart'
                        ) : (
                          <>
                            <ShoppingCart className="w-4 h-4" />
                            Add
                          </>
                        )}
                      </button>
                    </div>
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
