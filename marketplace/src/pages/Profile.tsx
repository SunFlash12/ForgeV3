import { User, Package, Heart, Settings } from 'lucide-react';

export default function Profile() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Profile Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-6">
          <div className="w-20 h-20 bg-indigo-100 rounded-full flex items-center justify-center">
            <User className="w-10 h-10 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Username</h1>
            <p className="text-gray-500">Member since January 2025</p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <Package className="w-8 h-8 text-indigo-600 mx-auto mb-2" />
          <p className="text-2xl font-bold">12</p>
          <p className="text-sm text-gray-500">Purchases</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <Heart className="w-8 h-8 text-pink-600 mx-auto mb-2" />
          <p className="text-2xl font-bold">8</p>
          <p className="text-sm text-gray-500">Wishlist</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
          <Settings className="w-8 h-8 text-gray-600 mx-auto mb-2" />
          <p className="text-sm font-medium mt-2">Settings</p>
        </div>
      </div>

      {/* Recent Purchases */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-xl font-semibold mb-4">Recent Purchases</h2>
        <div className="space-y-4">
          <p className="text-gray-500 text-center py-8">No purchases yet</p>
        </div>
      </div>
    </div>
  );
}
