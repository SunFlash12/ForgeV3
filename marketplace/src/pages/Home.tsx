import { Link } from 'react-router-dom';
import { Sparkles, Shield, Zap, ArrowRight, Loader2, ShoppingCart } from 'lucide-react';
import { useFeaturedCapsules } from '../hooks/useCapsules';
import { useCart } from '../contexts/CartContext';
import type { Capsule } from '../types';

export default function Home() {
  const { data: featuredCapsules, isLoading } = useFeaturedCapsules(4);
  const { addItem, isInCart } = useCart();

  const handleAddToCart = (capsule: Capsule) => {
    addItem(capsule);
  };

  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <div className="text-center">
            <h1 className="text-5xl font-bold mb-6">
              The Marketplace for<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-yellow-200 to-pink-200">
                Knowledge Capsules
              </span>
            </h1>
            <p className="text-xl text-indigo-100 mb-8 max-w-2xl mx-auto">
              Discover, purchase, and trade verified knowledge assets with full
              provenance tracking and blockchain-backed ownership.
            </p>
            <div className="flex justify-center gap-4">
              <Link
                to="/browse"
                className="bg-white text-indigo-600 px-8 py-3 rounded-lg font-semibold hover:bg-indigo-50 transition"
              >
                Browse Capsules
              </Link>
              <a
                href="https://forgecascade.org"
                className="border border-white text-white px-8 py-3 rounded-lg font-semibold hover:bg-white/10 transition"
              >
                Create Your Own
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-12">Why Forge Shop?</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center p-6">
              <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="w-8 h-8 text-indigo-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Verified Provenance</h3>
              <p className="text-gray-600">
                Every capsule tracks its complete lineage and evolution history,
                ensuring authenticity and attribution.
              </p>
            </div>
            <div className="text-center p-6">
              <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-8 h-8 text-purple-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">AI-Enhanced Search</h3>
              <p className="text-gray-600">
                Semantic search powered by advanced embeddings helps you find
                exactly what you need.
              </p>
            </div>
            <div className="text-center p-6">
              <div className="w-16 h-16 bg-pink-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="w-8 h-8 text-pink-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Instant Delivery</h3>
              <p className="text-gray-600">
                Purchase and access capsules instantly. Integrate them directly
                into your Forge Cascade workspace.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Capsules */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-8">
            <h2 className="text-3xl font-bold">Featured Capsules</h2>
            <Link
              to="/browse"
              className="text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
            >
              View All <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
            </div>
          ) : featuredCapsules && featuredCapsules.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {featuredCapsules.map((capsule) => (
                <div
                  key={capsule.id}
                  className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition"
                >
                  <Link to={`/capsule/${capsule.id}`}>
                    <div className="h-40 bg-gradient-to-br from-indigo-100 to-purple-100" />
                  </Link>
                  <div className="p-4">
                    <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
                      {capsule.category}
                    </span>
                    <Link to={`/capsule/${capsule.id}`}>
                      <h3 className="font-semibold mt-2 mb-1 hover:text-indigo-600">
                        {capsule.title}
                      </h3>
                    </Link>
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                      {capsule.summary || capsule.content.substring(0, 80)}...
                    </p>
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-gray-900">
                        {capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}
                      </span>
                      <button
                        onClick={() => handleAddToCart(capsule)}
                        disabled={isInCart(capsule.id)}
                        className={`text-sm font-medium flex items-center gap-1 ${
                          isInCart(capsule.id)
                            ? 'text-green-600'
                            : 'text-indigo-600 hover:text-indigo-700'
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
              <p className="text-gray-500 mb-4">No capsules available yet.</p>
              <a
                href="https://forgecascade.org"
                className="text-indigo-600 hover:text-indigo-700 font-medium"
              >
                Create the first one on Forge Cascade
              </a>
            </div>
          )}
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-indigo-600 text-white">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Get Started?</h2>
          <p className="text-indigo-100 mb-8">
            Join thousands of creators and learners on Forge Shop.
          </p>
          <Link
            to="/login"
            className="bg-white text-indigo-600 px-8 py-3 rounded-lg font-semibold hover:bg-indigo-50 transition inline-block"
          >
            Create Free Account
          </Link>
        </div>
      </section>
    </div>
  );
}
