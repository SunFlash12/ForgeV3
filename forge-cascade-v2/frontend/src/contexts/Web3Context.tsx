/**
 * Web3 Context - Wallet Connection for Forge Cascade Marketplace
 *
 * Provides wallet connection via RainbowKit and wagmi for
 * purchasing capsules with $VIRTUAL on Base.
 */

import { createContext, useContext, ReactNode } from 'react';
import { WagmiProvider } from 'wagmi';
import { base, baseSepolia } from 'wagmi/chains';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  RainbowKitProvider,
  getDefaultConfig,
  darkTheme,
} from '@rainbow-me/rainbowkit';
import '@rainbow-me/rainbowkit/styles.css';

// Environment configuration
const WALLETCONNECT_PROJECT_ID = import.meta.env.VITE_WALLETCONNECT_PROJECT_ID || 'forge-cascade-dev';
const IS_TESTNET = import.meta.env.VITE_USE_TESTNET === 'true';

// $VIRTUAL token addresses
export const VIRTUAL_TOKEN = {
  mainnet: '0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b',
  testnet: '0x832F65733f8DB2B4f6FA3370acD5Fa7EA585A0A4', // tVIRTUAL on Base Sepolia
};

// Marketplace contract addresses (to be deployed)
export const MARKETPLACE_CONTRACT = {
  mainnet: import.meta.env.VITE_MARKETPLACE_CONTRACT_MAINNET || '',
  testnet: import.meta.env.VITE_MARKETPLACE_CONTRACT_TESTNET || '',
};

// Configure wagmi with RainbowKit's getDefaultConfig
const config = getDefaultConfig({
  appName: 'Forge Cascade',
  projectId: WALLETCONNECT_PROJECT_ID,
  chains: IS_TESTNET ? [baseSepolia] : [base],
  ssr: false,
});

// Separate query client for wagmi (doesn't conflict with app's main QueryClient)
const wagmiQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

// Web3 context type
interface Web3ContextType {
  virtualTokenAddress: string;
  marketplaceAddress: string;
  chainId: number;
  isTestnet: boolean;
}

const Web3Context = createContext<Web3ContextType | undefined>(undefined);

// Provider component
export function Web3Provider({ children }: { children: ReactNode }) {
  const contextValue: Web3ContextType = {
    virtualTokenAddress: IS_TESTNET ? VIRTUAL_TOKEN.testnet : VIRTUAL_TOKEN.mainnet,
    marketplaceAddress: IS_TESTNET ? MARKETPLACE_CONTRACT.testnet : MARKETPLACE_CONTRACT.mainnet,
    chainId: IS_TESTNET ? baseSepolia.id : base.id,
    isTestnet: IS_TESTNET,
  };

  return (
    <Web3Context.Provider value={contextValue}>
      <WagmiProvider config={config}>
        <QueryClientProvider client={wagmiQueryClient}>
          <RainbowKitProvider
            theme={darkTheme()}
            modalSize="compact"
          >
            {children}
          </RainbowKitProvider>
        </QueryClientProvider>
      </WagmiProvider>
    </Web3Context.Provider>
  );
}

// Hook to use Web3 context
export function useWeb3Config() {
  const context = useContext(Web3Context);
  if (context === undefined) {
    throw new Error('useWeb3Config must be used within a Web3Provider');
  }
  return context;
}

// Re-export wagmi hooks for convenience
export {
  useAccount,
  useConnect,
  useDisconnect,
  useBalance,
  useChainId,
  useSwitchChain,
  useWriteContract,
  useReadContract,
  useWaitForTransactionReceipt,
} from 'wagmi';

// Re-export RainbowKit components
export { ConnectButton } from '@rainbow-me/rainbowkit';
