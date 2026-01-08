import { Link, useNavigate } from 'react-router-dom';
import { Trash2, CreditCard, ShoppingBag, ArrowLeft } from 'lucide-react';
import { useCart } from '../contexts/CartContext';
import { useAuth } from '../contexts/AuthContext';

const PLATFORM_FEE_RATE = 0.10;

export default function Cart() {
  const { items, total, removeItem, clearCart } = useCart();
  const { isAuthenticated } = useAuth();

  const subtotal = items.reduce((sum, item) => sum + (item.capsule.price || 0), 0);
  const platformFee = subtotal * PLATFORM_FEE_RATE;

  const navigate = useNavigate();

  const handleCheckout = () => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/cart');
      return;
    }
    // TODO: Implement checkout flow
    alert('Checkout functionality coming soon!');
  };

  if (items.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center" role="status" aria-label="Empty cart">
          <ShoppingBag className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Your cart is empty</h1>
          <p className="text-gray-500 mb-8">
            Looks like you haven't added any capsules yet.
          </p>
          <Link
            to="/browse"
            className="inline-flex items-center gap-2 bg-indigo-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-indigo-700 transition focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            <ArrowLeft className="w-5 h-5" aria-hidden="true" />
            Browse Capsules
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Shopping Cart</h1>
          <p className="text-gray-500 mt-1">{items.length} {items.length === 1 ? 'item' : 'items'}</p>
        </div>
        <button
          onClick={clearCart}
          className="text-sm text-gray-500 hover:text-red-600 transition focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 rounded px-2 py-1"
          aria-label="Clear all items from cart"
        >
          Clear Cart
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Cart Items */}
        <div className="lg:col-span-2 space-y-4">
          {items.map((item) => (
            <div
              key={item.capsule.id}
              className="bg-white rounded-xl border border-gray-200 p-4 flex gap-4"
            >
              <div className="w-24 h-24 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-lg flex-shrink-0" />
              <div className="flex-1">
                <div className="flex justify-between">
                  <div>
                    <Link
                      to={`/capsule/${item.capsule.id}`}
                      className="font-semibold hover:text-indigo-600"
                    >
                      {item.capsule.title}
                    </Link>
                    <p className="text-sm text-gray-500">{item.capsule.category}</p>
                    {item.capsule.author_name && (
                      <p className="text-xs text-gray-400 mt-1">
                        by {item.capsule.author_name}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => removeItem(item.capsule.id)}
                    className="text-gray-400 hover:text-red-500 transition p-1 rounded focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                    aria-label={`Remove ${item.capsule.title} from cart`}
                  >
                    <Trash2 className="w-5 h-5" aria-hidden="true" />
                  </button>
                </div>
                <p className="font-bold mt-2">
                  {item.capsule.price ? `$${item.capsule.price.toFixed(2)}` : 'Free'}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Order Summary */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border border-gray-200 p-6 sticky top-24">
            <h2 className="text-xl font-semibold mb-4">Order Summary</h2>

            <div className="space-y-3 mb-6">
              <div className="flex justify-between text-gray-600">
                <span>Subtotal ({items.length} items)</span>
                <span>${subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Platform Fee (10%)</span>
                <span>${platformFee.toFixed(2)}</span>
              </div>
              <div className="border-t border-gray-200 pt-3 flex justify-between font-bold text-lg">
                <span>Total</span>
                <span>${total.toFixed(2)}</span>
              </div>
            </div>

            <button
              onClick={handleCheckout}
              className="w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 transition flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
              aria-label={isAuthenticated ? `Proceed to checkout with ${items.length} items for $${total.toFixed(2)}` : 'Sign in to checkout'}
            >
              <CreditCard className="w-5 h-5" aria-hidden="true" />
              {isAuthenticated ? 'Proceed to Checkout' : 'Sign in to Checkout'}
            </button>

            <p className="text-xs text-gray-500 text-center mt-4">
              Secure payment powered by blockchain
            </p>

            <div className="mt-6 pt-6 border-t border-gray-200">
              <Link
                to="/browse"
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
              >
                &larr; Continue Shopping
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
