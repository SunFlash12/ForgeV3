import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle, Package, ArrowRight, Loader2, ExternalLink } from 'lucide-react';
import { api } from '../services/api';
import { useCart } from '../contexts/CartContext';
import type { TransactionStatus } from '../types';

export default function CheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const txHash = searchParams.get('tx');
  const { clearCart } = useCart();

  const [transaction, setTransaction] = useState<TransactionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Clear cart on successful checkout
    clearCart();

    // Fetch transaction details if we have a tx hash
    if (txHash) {
      const checkTransaction = async () => {
        try {
          const data = await api.getTransactionStatus(txHash);
          setTransaction(data);
          setLoading(false);

          // If still pending, poll for updates
          if (data.status === 'pending') {
            setTimeout(checkTransaction, 5000);
          }
        } catch (err) {
          console.error('Failed to fetch transaction:', err);
          setError('Could not verify transaction details');
          setLoading(false);
        }
      };

      checkTransaction();
    } else {
      setLoading(false);
    }
  }, [txHash, clearCart]);

  const formatTxHash = (hash: string) => {
    return `${hash.slice(0, 10)}...${hash.slice(-8)}`;
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-6">
          <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle className="w-10 h-10 text-green-600 dark:text-green-400" />
          </div>
        </div>

        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
          Purchase Successful!
        </h1>

        <p className="text-slate-600 dark:text-slate-400 mb-8">
          Your transaction has been confirmed on Base. Your capsules are now available in your library.
        </p>

        {loading ? (
          <div className="flex items-center justify-center gap-2 text-slate-500 dark:text-slate-400 mb-8">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Verifying transaction...</span>
          </div>
        ) : error ? (
          <p className="text-amber-600 dark:text-amber-400 text-sm mb-8">{error}</p>
        ) : transaction ? (
          <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4 mb-8 text-left border border-slate-200 dark:border-slate-700">
            <h2 className="font-semibold text-slate-900 dark:text-white mb-3">Transaction Details</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400">Transaction</span>
                <a
                  href={`https://basescan.org/tx/${transaction.transaction_hash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
                >
                  {formatTxHash(transaction.transaction_hash)}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">Status</span>
                <span className={`font-medium capitalize ${
                  transaction.status === 'confirmed'
                    ? 'text-green-600 dark:text-green-400'
                    : transaction.status === 'pending'
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-red-600 dark:text-red-400'
                }`}>
                  {transaction.status}
                </span>
              </div>
              {transaction.block_number && (
                <div className="flex justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Block</span>
                  <span className="font-mono text-slate-900 dark:text-slate-200">
                    {transaction.block_number.toLocaleString()}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">Confirmations</span>
                <span className="text-slate-900 dark:text-slate-200">
                  {transaction.confirmations}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">Amount</span>
                <span className="font-semibold text-purple-600 dark:text-purple-400">
                  {parseFloat(transaction.total_virtual).toLocaleString()} $VIRTUAL
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">Capsules</span>
                <span className="text-slate-900 dark:text-slate-200">
                  {transaction.capsule_ids.length} purchased
                </span>
              </div>
            </div>
          </div>
        ) : txHash ? (
          <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4 mb-8 text-left border border-slate-200 dark:border-slate-700">
            <h2 className="font-semibold text-slate-900 dark:text-white mb-3">Transaction</h2>
            <a
              href={`https://basescan.org/tx/${txHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
            >
              {formatTxHash(txHash)}
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        ) : null}

        <div className="space-y-3">
          <Link
            to="/profile"
            className="flex items-center justify-center gap-2 w-full bg-indigo-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-indigo-700 transition"
          >
            <Package className="w-5 h-5" />
            View My Capsules
          </Link>

          <Link
            to="/browse"
            className="flex items-center justify-center gap-2 w-full border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 py-3 px-6 rounded-lg font-semibold hover:bg-slate-50 dark:hover:bg-slate-800 transition"
          >
            Continue Shopping
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>

        <p className="mt-8 text-xs text-slate-500 dark:text-slate-400">
          Your capsules have been added to your account and are ready to use.
        </p>
      </div>
    </div>
  );
}
