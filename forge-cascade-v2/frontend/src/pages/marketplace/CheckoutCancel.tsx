import { Link, useSearchParams } from 'react-router-dom';
import { XCircle, ShoppingCart, ArrowRight, HelpCircle, ExternalLink } from 'lucide-react';

export default function CheckoutCancel() {
  const [searchParams] = useSearchParams();
  const txHash = searchParams.get('tx');
  const errorMessage = searchParams.get('error');

  const formatTxHash = (hash: string) => {
    return `${hash.slice(0, 10)}...${hash.slice(-8)}`;
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-6">
          <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mx-auto">
            <XCircle className="w-10 h-10 text-slate-400" />
          </div>
        </div>

        <h1 className="text-3xl font-bold text-slate-100 mb-2">
          Transaction Failed
        </h1>

        <p className="text-slate-400 mb-8">
          {errorMessage || 'Your transaction was cancelled or failed. No tokens were transferred. Your cart items are still saved.'}
        </p>

        {txHash && (
          <div className="bg-white/5 rounded-xl p-4 mb-8 text-left border border-white/10">
            <h2 className="font-semibold text-slate-100 mb-2">Failed Transaction</h2>
            <a
              href={`https://basescan.org/tx/${txHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-forge-400 hover:underline flex items-center gap-1 text-sm"
            >
              {formatTxHash(txHash)}
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}

        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 mb-8 text-left">
          <h2 className="font-semibold text-amber-200 mb-2 flex items-center gap-2">
            <HelpCircle className="w-4 h-4" />
            Common Issues
          </h2>
          <ul className="text-sm text-amber-300 space-y-1 list-disc list-inside">
            <li>Insufficient $VIRTUAL balance</li>
            <li>Insufficient ETH for gas fees</li>
            <li>Transaction rejected in wallet</li>
            <li>Network congestion - try again later</li>
          </ul>
        </div>

        <div className="space-y-3">
          <Link
            to="/marketplace/cart"
            className="flex items-center justify-center gap-2 w-full bg-forge-500 text-white py-3 px-6 rounded-lg font-semibold hover:bg-forge-600 transition"
          >
            <ShoppingCart className="w-5 h-5" />
            Return to Cart
          </Link>

          <Link
            to="/marketplace/browse"
            className="flex items-center justify-center gap-2 w-full border border-white/10 text-slate-200 py-3 px-6 rounded-lg font-semibold hover:bg-white/5 transition"
          >
            Continue Shopping
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>

        <p className="mt-8 text-xs text-slate-400">
          Need help? Contact us at support@forgecascade.org
        </p>
      </div>
    </div>
  );
}
