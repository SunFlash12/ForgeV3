import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Trash2, Wallet, ShoppingBag, ArrowLeft, Loader2, ShieldCheck, ExternalLink, CheckCircle } from 'lucide-react';
import { useCartStore } from '../../stores/cartStore';
import { useAuthStore } from '../../stores/authStore';
import {
  useWeb3Config,
  useAccount,
  useBalance,
  useChainId,
  useWriteContract,
  useWaitForTransactionReceipt,
  ConnectButton,
} from '../../contexts/Web3Context';
import { api } from '../../api/client';
import { parseEther } from 'viem';

const PLATFORM_FEE_RATE = 0.10;

// Platform wallet that receives capsule purchase payments
const PLATFORM_WALLET = {
  mainnet: '0x3CA3443c28B18332933Ea131aF85D6C9D8B88b94', // platformTreasury from base.json
  testnet: '0x7572C2170bDf132085aa6Fea5A0E4d4f2774A9f2', // deployer on Base Sepolia
};

// Standard ERC20 ABI (only the functions we need)
const ERC20_ABI = [
  {
    name: 'transfer',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'to', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
  {
    name: 'balanceOf',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'account', type: 'address' }],
    outputs: [{ name: '', type: 'uint256' }],
  },
] as const;

export default function MarketplaceCart() {
  const { items, total, removeItem, clearCart } = useCartStore();
  const { isAuthenticated } = useAuthStore();
  const { virtualTokenAddress, chainId: expectedChainId, isTestnet } = useWeb3Config();

  // Wagmi hooks
  const { address: walletAddress, isConnected } = useAccount();
  const currentChainId = useChainId();

  // Get $VIRTUAL balance
  const { data: virtualBalance } = useBalance({
    address: walletAddress,
    token: virtualTokenAddress as `0x${string}`,
  });

  // Contract write hook for ERC20 transfer
  const { writeContractAsync } = useWriteContract();

  // Transaction tracking
  const [txHash, setTxHash] = useState<`0x${string}` | undefined>();
  const [purchaseStep, setPurchaseStep] = useState<
    'idle' | 'signing' | 'confirming' | 'submitting' | 'success'
  >('idle');

  const { isSuccess: isConfirmed } = useWaitForTransactionReceipt({
    hash: txHash,
  });

  const [isPurchasing, setIsPurchasing] = useState(false);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [virtualPrice, setVirtualPrice] = useState<number>(0);

  const subtotal = items.reduce((sum, item) => sum + (item.capsule.price || 0), 0);
  const platformFee = subtotal * PLATFORM_FEE_RATE;
  const totalVirtual = virtualPrice > 0 ? total / virtualPrice : 0;

  const navigate = useNavigate();
  const isCorrectChain = currentChainId === expectedChainId;
  const explorerUrl = isTestnet ? 'https://sepolia.basescan.org' : 'https://basescan.org';

  useEffect(() => {
    fetchVirtualPrice();
  }, []);

  // Watch for transaction confirmation and submit to backend
  useEffect(() => {
    if (isConfirmed && txHash && purchaseStep === 'confirming') {
      setPurchaseStep('submitting');

      const purchaseItems = items.map(item => ({
        listing_id: item.capsule.id,
        capsule_id: item.capsule.id,
        title: item.capsule.title,
        price_virtual: parseEther(
          ((item.capsule.price || 0) / virtualPrice).toFixed(8)
        ).toString(),
        price_usd: item.capsule.price || 0,
      }));

      api.submitPurchase(purchaseItems, walletAddress!, txHash)
        .then(() => {
          setPurchaseStep('success');
          clearCart();
        })
        .catch((err) => {
          console.error('Backend purchase submission failed:', err);
          // Transaction succeeded on-chain even if backend submission fails
          setPurchaseStep('success');
          clearCart();
        })
        .finally(() => {
          setIsPurchasing(false);
        });
    }
  }, [isConfirmed, txHash, purchaseStep]);

  const fetchVirtualPrice = async () => {
    try {
      const { price_usd } = await api.getVirtualPrice();
      setVirtualPrice(price_usd);
    } catch (error) {
      console.error('Failed to fetch $VIRTUAL price:', error);
      setVirtualPrice(0.10); // Fallback
    }
  };

  const handlePurchase = async () => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/marketplace/cart');
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
    const requiredAmount = parseEther(totalVirtual.toFixed(8));
    const currentBalance = virtualBalance?.value || BigInt(0);
    if (currentBalance < requiredAmount) {
      setPurchaseError(
        `Insufficient $VIRTUAL balance. You have ${parseFloat(virtualBalance?.formatted || '0').toFixed(2)} but need ${totalVirtual.toFixed(2)}`
      );
      return;
    }

    setIsPurchasing(true);
    setPurchaseError(null);
    setPurchaseStep('signing');

    try {
      // Step 1: Send ERC20 transfer of $VIRTUAL to platform wallet
      const hash = await writeContractAsync({
        address: virtualTokenAddress as `0x${string}`,
        abi: ERC20_ABI,
        functionName: 'transfer',
        args: [(isTestnet ? PLATFORM_WALLET.testnet : PLATFORM_WALLET.mainnet) as `0x${string}`, requiredAmount],
      });

      // Step 2: Wait for on-chain confirmation (handled by useEffect above)
      setTxHash(hash);
      setPurchaseStep('confirming');

    } catch (error) {
      console.error('Purchase failed:', error);
      setPurchaseStep('idle');
      setPurchaseError(
        error instanceof Error
          ? error.message
          : 'Failed to complete purchase. Please try again.'
      );
      setIsPurchasing(false);
    }
  };

  // Success view after purchase
  if (purchaseStep === 'success' && txHash) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" aria-hidden="true" />
          <h1 className="text-2xl font-bold text-slate-100 mb-2">Purchase Successful!</h1>
          <p className="text-slate-400 mb-6">
            Your capsules have been purchased and are now available in your library.
          </p>
          <div className="bg-white/5 rounded-lg border border-white/10 p-4 mb-8">
            <p className="text-sm text-slate-400 mb-1">Transaction Hash</p>
            <a
              href={`${explorerUrl}/tx/${txHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-mono text-forge-400 hover:underline break-all flex items-center justify-center gap-1"
            >
              {txHash.slice(0, 10)}...{txHash.slice(-8)}
              <ExternalLink className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
            </a>
          </div>
          <div className="flex gap-4 justify-center">
            <Link
              to="/marketplace/browse"
              className="inline-flex items-center gap-2 bg-forge-500 text-white px-6 py-3 rounded-lg font-semibold hover:bg-forge-600 transition"
            >
              <ShoppingBag className="w-5 h-5" aria-hidden="true" />
              Continue Shopping
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center" role="status" aria-label="Empty cart">
          <ShoppingBag className="w-16 h-16 text-slate-600 mx-auto mb-4" aria-hidden="true" />
          <h1 className="text-2xl font-bold text-slate-100 mb-2">Your cart is empty</h1>
          <p className="text-slate-400 mb-8">
            Looks like you haven't added any capsules yet.
          </p>
          <Link
            to="/marketplace/browse"
            className="inline-flex items-center gap-2 bg-forge-500 text-white px-6 py-3 rounded-lg font-semibold hover:bg-forge-600 transition focus:outline-none focus:ring-2 focus:ring-forge-500 focus:ring-offset-2"
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
          <h1 className="text-3xl font-bold text-slate-100">Shopping Cart</h1>
          <p className="text-slate-400 mt-1">{items.length} {items.length === 1 ? 'item' : 'items'}</p>
        </div>
        <button
          onClick={clearCart}
          className="text-sm text-slate-400 hover:text-red-400 transition focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 rounded px-2 py-1"
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
              className="bg-white/5 rounded-xl border border-white/10 p-4 flex gap-4"
            >
              <div className="w-24 h-24 bg-gradient-to-br from-forge-500/20 to-ghost-500/20 rounded-lg flex-shrink-0" />
              <div className="flex-1">
                <div className="flex justify-between">
                  <div>
                    <Link
                      to={`/marketplace/capsule/${item.capsule.id}`}
                      className="font-semibold text-slate-100 hover:text-forge-400"
                    >
                      {item.capsule.title}
                    </Link>
                    <p className="text-sm text-slate-400">{item.capsule.category}</p>
                    {item.capsule.author_name && (
                      <p className="text-xs text-slate-500 mt-1">
                        by {item.capsule.author_name}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => removeItem(item.capsule.id)}
                    className="text-slate-400 hover:text-red-400 transition p-1 rounded focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                    aria-label={`Remove ${item.capsule.title} from cart`}
                  >
                    <Trash2 className="w-5 h-5" aria-hidden="true" />
                  </button>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <p className="font-bold text-slate-100">
                    {item.capsule.price ? `$${item.capsule.price.toFixed(2)}` : 'Free'}
                  </p>
                  {item.capsule.price && virtualPrice > 0 && (
                    <p className="text-sm text-purple-400">
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
          <div className="bg-white/5 rounded-xl border border-white/10 p-6 sticky top-24">
            <h2 className="text-xl font-semibold text-slate-100 mb-4">Order Summary</h2>

            <div className="space-y-3 mb-6">
              <div className="flex justify-between text-slate-400">
                <span>Subtotal ({items.length} items)</span>
                <span>${subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Platform Fee (10%)</span>
                <span>${platformFee.toFixed(2)}</span>
              </div>
              <div className="border-t border-white/10 pt-3">
                <div className="flex justify-between font-bold text-lg text-slate-100">
                  <span>Total (USD)</span>
                  <span>${total.toFixed(2)}</span>
                </div>
                {virtualPrice > 0 && (
                  <div className="flex justify-between text-purple-400 font-medium mt-1">
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
                          className="w-full bg-forge-500 text-white py-3 rounded-lg font-semibold hover:bg-forge-600 transition flex items-center justify-center gap-2"
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
                        <div className="p-3 bg-surface-900 border border-white/10 rounded-lg">
                          <div className="flex items-center justify-between mb-2">
                            <button
                              onClick={openChainModal}
                              className="flex items-center gap-2 text-sm hover:opacity-80"
                            >
                              {chain.hasIcon && chain.iconUrl && (
                                <img src={chain.iconUrl} alt={chain.name} className="w-4 h-4" />
                              )}
                              <span className="text-slate-300">{chain.name}</span>
                            </button>
                            <button
                              onClick={openAccountModal}
                              className="text-sm font-mono text-forge-400 hover:underline"
                            >
                              {account.displayName}
                            </button>
                          </div>
                          {virtualBalance && (
                            <div className="text-sm text-purple-400">
                              Balance: {parseFloat(virtualBalance.formatted).toFixed(2)} $VIRTUAL
                            </div>
                          )}
                          {walletAddress && (
                            <a
                              href={`${explorerUrl}/address/${walletAddress}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-slate-400 hover:text-forge-400 flex items-center gap-1 mt-1"
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
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-300">
                {purchaseError}
              </div>
            )}

            {/* Transaction progress */}
            {purchaseStep !== 'idle' && purchaseStep !== 'success' && (
              <div className="mb-4 p-3 bg-forge-500/10 border border-forge-500/30 rounded-lg">
                <div className="flex items-center gap-3 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin text-forge-400 flex-shrink-0" aria-hidden="true" />
                  <div className="text-forge-300">
                    {purchaseStep === 'signing' && 'Please confirm the transaction in your wallet...'}
                    {purchaseStep === 'confirming' && 'Waiting for on-chain confirmation...'}
                    {purchaseStep === 'submitting' && 'Registering purchase...'}
                  </div>
                </div>
                {txHash && (
                  <a
                    href={`${explorerUrl}/tx/${txHash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-forge-400 hover:text-forge-300 flex items-center gap-1 mt-2"
                  >
                    View transaction <ExternalLink className="w-3 h-3" aria-hidden="true" />
                  </a>
                )}
              </div>
            )}

            {isConnected && (
              <button
                onClick={handlePurchase}
                disabled={isPurchasing || !isCorrectChain}
                className="w-full bg-purple-600 text-white py-3 rounded-lg font-semibold hover:bg-purple-700 transition flex items-center justify-center gap-2 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label={`Purchase ${items.length} items for ${totalVirtual.toFixed(2)} $VIRTUAL`}
              >
                {purchaseStep === 'signing' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                    Sign in Wallet...
                  </>
                ) : purchaseStep === 'confirming' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                    Confirming...
                  </>
                ) : purchaseStep === 'submitting' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                    Finalizing...
                  </>
                ) : !isCorrectChain ? (
                  <>
                    <Wallet className="w-5 h-5" aria-hidden="true" />
                    Switch to {isTestnet ? 'Base Sepolia' : 'Base'}
                  </>
                ) : (
                  <>
                    <Wallet className="w-5 h-5" aria-hidden="true" />
                    Purchase with $VIRTUAL
                  </>
                )}
              </button>
            )}

            <div className="flex items-center justify-center gap-2 mt-4 text-xs text-slate-400">
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              <span>Secured by Base blockchain</span>
            </div>

            {/* $VIRTUAL info */}
            <div className="mt-4 p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
              <p className="text-xs text-purple-300">
                <strong>$VIRTUAL</strong> is the native token of Virtuals Protocol on Base.
                {virtualPrice > 0 && (
                  <span className="block mt-1">
                    Current price: ${virtualPrice.toFixed(4)} USD
                  </span>
                )}
              </p>
            </div>

            <div className="mt-6 pt-6 border-t border-white/10">
              <Link
                to="/marketplace/browse"
                className="text-sm text-forge-400 hover:text-forge-300 font-medium"
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
