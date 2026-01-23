import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Trash2, Wallet, ShoppingBag, ArrowLeft, Loader2, ShieldCheck, ExternalLink } from 'lucide-react';
import { useCart } from '../contexts/CartContext';
import { useAuth } from '../contexts/AuthContext';
import {
  useWeb3Config,
  useAccount,
  useBalance,
  useChainId,
  useSwitchChain,
  ConnectButton,
} from '../contexts/Web3Context';
import { api } from '../services/api';
import { base } from 'wagmi/chains';

const PLATFORM_FEE_RATE = 0.10;

export default function Cart() {
  const { items, total, removeItem, clearCart } = useCart();
  const { isAuthenticated } = useAuth();
  const { virtualTokenAddress, chainId: expectedChainId, isTestnet } = useWeb3Config();

  // Wagmi hooks
  const { address: walletAddress, isConnected } = useAccount();
  const currentChainId = useChainId();
  const { switchChain } = useSwitchChain();

  // Get $VIRTUAL balance
  const { data: virtualBalance } = useBalance({
    address: walletAddress,
    token: virtualTokenAddress as `0x${string}`,
  });

  const [isPurchasing, setIsPurchasing] = useState(false);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [virtualPrice, setVirtualPrice] = useState<number>(0);

  const subtotal = items.reduce((sum, item) => sum + (item.capsule.price || 0), 0);
  const platformFee = subtotal * PLATFORM_FEE_RATE;
  const totalVirtual = virtualPrice > 0 ? total / virtualPrice : 0;

  const navigate = useNavigate();
  const isCorrectChain = currentChainId === expectedChainId;

  useEffect(() => {
    fetchVirtualPrice();
  }, []);

  const fetchVirtualPrice = async () => {
    try {
      const { price_usd } = await api.getVirtualPrice();
      setVirtualPrice(price_usd);
    } catch (error) {
      console.error('Failed to fetch $VIRTUAL price:', error);
      setVirtualPrice(0.10); // Fallback
    }
  };

  const handleSwitchChain = async () => {
    try {
      await switchChain({ chainId: expectedChainId });
    } catch (error) {
      console.error('Failed to switch chain:', error);
      setPurchaseError('Failed to switch to Base network. Please switch manually in your wallet.');
    }
  };

  const handlePurchase = async () => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/cart');
      return;
    }

    if (!isConnected || !walletAddress) {
      setPurchaseError('Please connect your wallet first');
      return;
    }

    if (!isCorrectChain) {
      setPurchaseError(`Please switch to ${isTestnet ? 'Base Sepolia' : 'Base'} network`);
      return;
    }

    // Check balance
    const requiredAmount = BigInt(Math.floor(totalVirtual * 1e18));
    const currentBalance = virtualBalance?.value || BigInt(0);
    if (currentBalance < requiredAmount) {
      setPurchaseError(
        `Insufficient $VIRTUAL balance. You have ${parseFloat(virtualBalance?.formatted || '0').toFixed(2)} but need ${totalVirtual.toFixed(2)}`
      );
      return;
    }

    setIsPurchasing(true);
    setPurchaseError(null);

    try {
      // For now, show coming soon - full implementation requires smart contract deployment
      setPurchaseError(
        'Web3 purchase integration coming soon! The marketplace smart contract is being deployed to Base. ' +
        'Connect your wallet to be ready when it launches.'
      );

      // TODO: Full purchase flow when contract is deployed:
      // 1. Call $VIRTUAL token approve() for marketplace contract
      // 2. Call marketplace.purchaseCapsules(capsuleIds, totalWei)
      // 3. Wait for transaction confirmation
      // 4. Submit purchase to backend with tx hash
      // 5. Navigate to success page with tx hash

    } catch (error) {
      console.error('Purchase failed:', error);
      setPurchaseError(
        error instanceof Error
          ? error.message
          : 'Failed to complete purchase. Please try again.'
      );
    } finally {
      setIsPurchasing(false);
    }
  };

  if (items.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center" role="status" aria-label="Empty cart">
          <ShoppingBag className="w-16 h-16 text-slate-300 dark:text-slate-600 mx-auto mb-4" aria-hidden="true" />
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Your cart is empty</h1>
          <p className="text-slate-500 dark:text-slate-400 mb-8">
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
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Shopping Cart</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">{items.length} {items.length === 1 ? 'item' : 'items'}</p>
        </div>
        <button
          onClick={clearCart}
          className="text-sm text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 transition focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 rounded px-2 py-1"
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
              className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 flex gap-4"
            >
              <div className="w-24 h-24 bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900/50 dark:to-purple-900/50 rounded-lg flex-shrink-0" />
              <div className="flex-1">
                <div className="flex justify-between">
                  <div>
                    <Link
                      to={`/capsule/${item.capsule.id}`}
                      className="font-semibold text-slate-900 dark:text-white hover:text-indigo-600 dark:hover:text-indigo-400"
                    >
                      {item.capsule.title}
                    </Link>
                    <p className="text-sm text-slate-500 dark:text-slate-400">{item.capsule.category}</p>
                    {item.capsule.author_name && (
                      <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                        by {item.capsule.author_name}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => removeItem(item.capsule.id)}
                    className="text-slate-400 hover:text-red-500 transition p-1 rounded focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                    aria-label={`Remove ${item.capsule.title} from cart`}
                  >
                    <Trash2 className="w-5 h-5" aria-hidden="true" />
                  </button>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <p className="font-bold text-slate-900 dark:text-white">
                    {item.capsule.price ? `$${item.capsule.price.toFixed(2)}` : 'Free'}
                  </p>
                  {item.capsule.price && virtualPrice > 0 && (
                    <p className="text-sm text-purple-600 dark:text-purple-400">
                      ({(item.capsule.price / virtualPrice).toFixed(2)} $VIRTUAL)
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Order Summary */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 sticky top-24">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">Order Summary</h2>

            <div className="space-y-3 mb-6">
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Subtotal ({items.length} items)</span>
                <span>${subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Platform Fee (10%)</span>
                <span>${platformFee.toFixed(2)}</span>
              </div>
              <div className="border-t border-slate-200 dark:border-slate-700 pt-3">
                <div className="flex justify-between font-bold text-lg text-slate-900 dark:text-white">
                  <span>Total (USD)</span>
                  <span>${total.toFixed(2)}</span>
                </div>
                {virtualPrice > 0 && (
                  <div className="flex justify-between text-purple-600 dark:text-purple-400 font-medium mt-1">
                    <span>Total ($VIRTUAL)</span>
                    <span>{totalVirtual.toFixed(2)} $VIRTUAL</span>
                  </div>
                )}
              </div>
            </div>

            {/* Wallet Connection via RainbowKit */}
            <div className="mb-4">
              <ConnectButton.Custom>
                {({ account, chain, openAccountModal, openChainModal, openConnectModal, mounted }) => {
                  const ready = mounted;
                  const connected = ready && account && chain;

                  return (
                    <div
                      {...(!ready && {
                        'aria-hidden': true,
                        style: {
                          opacity: 0,
                          pointerEvents: 'none',
                          userSelect: 'none',
                        },
                      })}
                    >
                      {!connected ? (
                        <button
                          onClick={openConnectModal}
                          className="w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 transition flex items-center justify-center gap-2"
                        >
                          <Wallet className="w-5 h-5" />
                          Connect Wallet
                        </button>
                      ) : chain.unsupported ? (
                        <button
                          onClick={openChainModal}
                          className="w-full bg-red-600 text-white py-3 rounded-lg font-semibold hover:bg-red-700 transition"
                        >
                          Switch to Base
                        </button>
                      ) : (
                        <div className="p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg">
                          <div className="flex items-center justify-between mb-2">
                            <button
                              onClick={openChainModal}
                              className="flex items-center gap-2 text-sm hover:opacity-80"
                            >
                              {chain.hasIcon && chain.iconUrl && (
                                <img src={chain.iconUrl} alt={chain.name} className="w-4 h-4" />
                              )}
                              <span className="text-slate-600 dark:text-slate-300">{chain.name}</span>
                            </button>
                            <button
                              onClick={openAccountModal}
                              className="text-sm font-mono text-indigo-600 dark:text-indigo-400 hover:underline"
                            >
                              {account.displayName}
                            </button>
                          </div>
                          {virtualBalance && (
                            <div className="text-sm text-purple-600 dark:text-purple-400">
                              Balance: {parseFloat(virtualBalance.formatted).toFixed(2)} $VIRTUAL
                            </div>
                          )}
                          {walletAddress && (
                            <a
                              href={`https://basescan.org/address/${walletAddress}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-slate-400 hover:text-indigo-600 flex items-center gap-1 mt-1"
                            >
                              View on Basescan <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  );
                }}
              </ConnectButton.Custom>
            </div>

            {purchaseError && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
                {purchaseError}
              </div>
            )}

            {isConnected && (
              <button
                onClick={handlePurchase}
                disabled={isPurchasing || !isCorrectChain}
                className="w-full bg-purple-600 text-white py-3 rounded-lg font-semibold hover:bg-purple-700 transition flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label={`Purchase ${items.length} items for ${totalVirtual.toFixed(2)} $VIRTUAL`}
              >
                {isPurchasing ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                    Processing...
                  </>
                ) : !isCorrectChain ? (
                  <>
                    <Wallet className="w-5 h-5" aria-hidden="true" />
                    Switch to Base
                  </>
                ) : (
                  <>
                    <Wallet className="w-5 h-5" aria-hidden="true" />
                    Purchase with $VIRTUAL
                  </>
                )}
              </button>
            )}

            <div className="flex items-center justify-center gap-2 mt-4 text-xs text-slate-500 dark:text-slate-400">
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              <span>Secured by Base blockchain</span>
            </div>

            {/* $VIRTUAL info */}
            <div className="mt-4 p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
              <p className="text-xs text-purple-700 dark:text-purple-300">
                <strong>$VIRTUAL</strong> is the native token of Virtuals Protocol on Base.
                {virtualPrice > 0 && (
                  <span className="block mt-1">
                    Current price: ${virtualPrice.toFixed(4)} USD
                  </span>
                )}
              </p>
            </div>

            <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
              <Link
                to="/browse"
                className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 font-medium"
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
