import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Filter, Grid, List, ShoppingCart, Check, AlertCircle, RefreshCw } from 'lucide-react';
import { useCapsules } from '../hooks/useCapsules';
import { useCart } from '../contexts/CartContext';
import type { CapsuleFilters, Capsule } from '../types';

const CATEGORIES = ['All', 'Knowledge', 'Code', 'Data', 'Research'];

// Loading skeleton component
function CapsuleSkeleton({ viewMode }: { viewMode: 'grid' | 'list' }) {
  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 flex gap-4 animate-pulse">
        <div className="w-32 h-24 bg-gray-200 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-3">
          <div className="h-4 bg-gray-200 rounded w-20" />
          <div className="h-5 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-full" />
        </div>
        <div className="w-24 h-10 bg-gray-200 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden animate-pulse">
      <div className="h-40 bg-gray-200" />
      <div className="p-4 space-y-3">
        <div className="h-4 bg-gray-200 rounded w-20" />
        <div className="h-5 bg-gray-200 rounded w-3/4" />
        <div className="h-4 bg-gray-200 rounded w-full" />
        <div className="flex justify-between items-center pt-2">
          <div className="h-5 bg-gray-200 rounded w-16" />
          <div className="h-10 bg-gray-200 rounded-lg w-28" />
        </div>
      </div>
    </div>
  );
}

export default function Browse() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filters, setFilters] = useState<CapsuleFilters>({
    page: 1,
    per_page: 12,
    is_public: true,
  });

  const { addItem, isInCart } = useCart();
  const { data, isLoading, error, refetch } = useCapsules(filters);

  // Sync URL params with filters
  useEffect(() => {
    const search = searchParams.get('search');
    const category = searchParams.get('category');
    const page = searchParams.get('page');

    setFilters(prev => ({
      ...prev,
      search: search || undefined,
      category: category && category !== 'All' ? category.toLowerCase() : undefined,
      page: page ? parseInt(page, 10) : 1,
    }));
  }, [searchParams]);

  const handleCategoryChange = (category: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (category === 'All') {
      newParams.delete('category');
    } else {
      newParams.set('category', category.toLowerCase());
    }
    newParams.delete('page');
    setSearchParams(newParams);
  };

  const handlePageChange = (page: number) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('page', String(page));
    setSearchParams(newParams);
  };

  const handleAddToCart = (capsule: Capsule) => {
    addItem(capsule);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Browse Capsules</h1>
          <p className="text-gray-600 mt-1">
            {filters.search
              ? `Search results for "${filters.search}"`
              : 'Discover knowledge from the community'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded ${viewMode === 'grid' ? 'bg-indigo-100 text-indigo-600' : 'text-gray-400'}`}
          >
            <Grid className="w-5 h-5" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded ${viewMode === 'list' ? 'bg-indigo-100 text-indigo-600' : 'text-gray-400'}`}
          >
            <List className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="flex gap-8">
        {/* Sidebar Filters */}
        <aside className="w-64 flex-shrink-0 hidden lg:block">
          <div className="bg-white rounded-lg border border-gray-200 p-4 sticky top-24">
            <div className="flex items-center gap-2 mb-4">
              <Filter className="w-5 h-5 text-gray-500" />
              <h2 className="font-semibold">Filters</h2>
            </div>

            {/* Category Filter */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Category</h3>
              <div className="space-y-2">
                {CATEGORIES.map((cat) => (
                  <label key={cat} className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      name="category"
                      checked={
                        (cat === 'All' && !filters.category) ||
                        filters.category === cat.toLowerCase()
                      }
                      onChange={() => handleCategoryChange(cat)}
                      className="rounded text-indigo-600"
                    />
                    <span className="ml-2 text-sm text-gray-600">{cat}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Trust Level */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">Trust Level</h3>
              <div className="space-y-2">
                {['Verified', 'Standard', 'Community'].map((level) => (
                  <label key={level} className="flex items-center">
                    <input type="checkbox" className="rounded text-indigo-600" />
                    <span className="ml-2 text-sm text-gray-600">{level}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* Capsule Grid */}
        <main className="flex-1" aria-label="Capsule listings">
          {isLoading ? (
            <div className={viewMode === 'grid'
              ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
              : "space-y-4"
            } aria-label="Loading capsules">
              {Array.from({ length: 6 }).map((_, i) => (
                <CapsuleSkeleton key={i} viewMode={viewMode} />
              ))}
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-red-700 mb-2">Failed to load capsules</h3>
              <p className="text-red-600 mb-6">Something went wrong. Please try again.</p>
              <button
                onClick={() => refetch()}
                className="inline-flex items-center gap-2 bg-red-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-red-700 transition focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
            </div>
          ) : data?.capsules.length === 0 ? (
            <div className="text-center py-20">
              <p className="text-gray-500 mb-4">No capsules found</p>
              <Link to="/browse" className="text-indigo-600 hover:text-indigo-700">
                Clear filters
              </Link>
            </div>
          ) : (
            <>
              <div className={viewMode === 'grid'
                ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
                : "space-y-4"
              }>
                {data?.capsules.map((capsule) => (
                  <CapsuleCard
                    key={capsule.id}
                    capsule={capsule}
                    viewMode={viewMode}
                    onAddToCart={() => handleAddToCart(capsule)}
                    inCart={isInCart(capsule.id)}
                  />
                ))}
              </div>

              {/* Pagination */}
              {data && data.total_pages > 1 && (
                <div className="mt-8 flex justify-center">
                  <nav className="flex items-center gap-2">
                    <button
                      onClick={() => handlePageChange(data.page - 1)}
                      disabled={data.page <= 1}
                      className="px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>
                    {Array.from({ length: Math.min(5, data.total_pages) }, (_, i) => {
                      const page = i + 1;
                      return (
                        <button
                          key={page}
                          onClick={() => handlePageChange(page)}
                          className={`px-4 py-2 rounded-lg ${
                            data.page === page
                              ? 'bg-indigo-600 text-white'
                              : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                          }`}
                        >
                          {page}
                        </button>
                      );
                    })}
                    <button
                      onClick={() => handlePageChange(data.page + 1)}
                      disabled={data.page >= data.total_pages}
                      className="px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </nav>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

interface CapsuleCardProps {
  capsule: Capsule;
  viewMode: 'grid' | 'list';
  onAddToCart: () => void;
  inCart: boolean;
}

function CapsuleCard({ capsule, viewMode, onAddToCart, inCart }: CapsuleCardProps) {
  if (viewMode === 'list') {
    return (
      <article
        className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 flex gap-4 hover:shadow-lg hover:border-indigo-200 transition-all duration-200 group"
        aria-label={`${capsule.title} - ${capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}`}
      >
        <Link to={`/capsule/${capsule.id}`} className="w-32 h-24 flex-shrink-0">
          <div className="w-full h-full bg-gradient-to-br from-indigo-100 to-purple-100 rounded-lg group-hover:from-indigo-200 group-hover:to-purple-200 transition-colors duration-200" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-start gap-4">
            <div className="min-w-0">
              <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
                {capsule.category}
              </span>
              <Link
                to={`/capsule/${capsule.id}`}
                className="block mt-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded"
              >
                <h3 className="font-semibold text-gray-900 hover:text-indigo-600 transition truncate">{capsule.title}</h3>
              </Link>
              <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                {capsule.summary || capsule.content.substring(0, 100)}...
              </p>
              {capsule.author_name && (
                <p className="text-xs text-gray-400 mt-1">by {capsule.author_name}</p>
              )}
            </div>
            <div className="text-right flex-shrink-0">
              <span className="font-bold text-gray-900 text-lg">
                {capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center flex-shrink-0">
          <button
            onClick={onAddToCart}
            disabled={inCart}
            aria-label={inCart ? `${capsule.title} is in cart` : `Add ${capsule.title} to cart`}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-offset-2 ${
              inCart
                ? 'bg-green-100 text-green-700 focus:ring-green-500'
                : 'bg-indigo-600 text-white hover:bg-indigo-700 hover:scale-105 focus:ring-indigo-500'
            }`}
          >
            {inCart ? <Check className="w-4 h-4" aria-hidden="true" /> : <ShoppingCart className="w-4 h-4" aria-hidden="true" />}
            {inCart ? 'In Cart' : 'Add'}
          </button>
        </div>
      </article>
    );
  }

  return (
    <article
      className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-lg hover:border-indigo-200 transition-all duration-200 group"
      aria-label={`${capsule.title} - ${capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}`}
    >
      <Link to={`/capsule/${capsule.id}`} className="block overflow-hidden">
        <div className="h-40 bg-gradient-to-br from-indigo-100 to-purple-100 group-hover:from-indigo-200 group-hover:to-purple-200 transition-colors duration-200 group-hover:scale-105 transform" />
      </Link>
      <div className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
            {capsule.category}
          </span>
          {!capsule.price && (
            <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded">
              Free
            </span>
          )}
        </div>
        <Link
          to={`/capsule/${capsule.id}`}
          className="block focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded"
        >
          <h3 className="font-semibold text-gray-900 mb-1 hover:text-indigo-600 transition line-clamp-1">{capsule.title}</h3>
        </Link>
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">
          {capsule.summary || capsule.content.substring(0, 80)}...
        </p>
        {capsule.author_name && (
          <p className="text-xs text-gray-400 mb-3">by {capsule.author_name}</p>
        )}
        <div className="flex justify-between items-center pt-2 border-t border-gray-100">
          <span className="font-bold text-gray-900 text-lg">
            {capsule.price ? `$${capsule.price.toFixed(2)}` : 'Free'}
          </span>
          <button
            onClick={onAddToCart}
            disabled={inCart}
            aria-label={inCart ? `${capsule.title} is in cart` : `Add ${capsule.title} to cart`}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-offset-2 ${
              inCart
                ? 'bg-green-100 text-green-700 focus:ring-green-500'
                : 'bg-indigo-600 text-white hover:bg-indigo-700 hover:scale-105 focus:ring-indigo-500'
            }`}
          >
            {inCart ? <Check className="w-4 h-4" aria-hidden="true" /> : <ShoppingCart className="w-4 h-4" aria-hidden="true" />}
            {inCart ? 'In Cart' : 'Add to Cart'}
          </button>
        </div>
      </div>
    </article>
  );
}
