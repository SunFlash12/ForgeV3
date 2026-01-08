import { useParams } from 'react-router-dom';
import { ShoppingCart, Share2, Heart, GitBranch, Shield, Star } from 'lucide-react';

export default function CapsuleDetail() {
  const { id } = useParams();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Preview */}
          <div className="bg-gradient-to-br from-indigo-100 to-purple-100 rounded-xl h-96 mb-6" />

          {/* Description */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">Description</h2>
            <p className="text-gray-600 leading-relaxed">
              This is a detailed description of the capsule. It explains what knowledge
              or content is contained within, how it was created, and what makes it
              valuable. The description helps buyers understand exactly what they're
              getting before making a purchase.
            </p>
          </div>

          {/* Lineage */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <GitBranch className="w-5 h-5 text-indigo-600" />
              <h2 className="text-xl font-semibold">Lineage</h2>
            </div>
            <div className="border-l-2 border-indigo-200 pl-4 space-y-4">
              <div className="relative">
                <div className="absolute -left-6 w-3 h-3 bg-indigo-600 rounded-full" />
                <p className="text-sm text-gray-500">Current Version</p>
                <p className="font-medium">Capsule #{id}</p>
              </div>
              <div className="relative">
                <div className="absolute -left-6 w-3 h-3 bg-gray-300 rounded-full" />
                <p className="text-sm text-gray-500">Derived from</p>
                <p className="font-medium text-gray-600">Original Research v1.2</p>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border border-gray-200 p-6 sticky top-8">
            <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
              Knowledge
            </span>
            <h1 className="text-2xl font-bold mt-3 mb-2">Sample Capsule Title</h1>

            {/* Rating */}
            <div className="flex items-center gap-1 mb-4">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star
                  key={star}
                  className={`w-4 h-4 ${star <= 4 ? 'text-yellow-400 fill-yellow-400' : 'text-gray-300'}`}
                />
              ))}
              <span className="text-sm text-gray-600 ml-2">(24 reviews)</span>
            </div>

            {/* Trust Badge */}
            <div className="flex items-center gap-2 mb-6 text-green-600">
              <Shield className="w-5 h-5" />
              <span className="text-sm font-medium">Verified Creator</span>
            </div>

            {/* Price */}
            <div className="mb-6">
              <span className="text-3xl font-bold text-gray-900">$29.99</span>
              <span className="text-gray-500 ml-2 line-through">$49.99</span>
            </div>

            {/* Actions */}
            <div className="space-y-3">
              <button className="w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 transition flex items-center justify-center gap-2">
                <ShoppingCart className="w-5 h-5" />
                Add to Cart
              </button>
              <div className="flex gap-3">
                <button className="flex-1 border border-gray-300 py-3 rounded-lg font-medium hover:bg-gray-50 transition flex items-center justify-center gap-2">
                  <Heart className="w-5 h-5" />
                  Save
                </button>
                <button className="flex-1 border border-gray-300 py-3 rounded-lg font-medium hover:bg-gray-50 transition flex items-center justify-center gap-2">
                  <Share2 className="w-5 h-5" />
                  Share
                </button>
              </div>
            </div>

            {/* Creator Info */}
            <div className="mt-6 pt-6 border-t border-gray-200">
              <p className="text-sm text-gray-500 mb-2">Created by</p>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-indigo-100 rounded-full" />
                <div>
                  <p className="font-medium">Creator Name</p>
                  <p className="text-sm text-gray-500">42 capsules</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
