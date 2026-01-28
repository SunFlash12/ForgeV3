// ============================================================================
// Marketplace Types
// ============================================================================
// Types specific to the marketplace / Web3 purchasing functionality.
// Core types (User, Capsule, TrustLevel, CapsuleType) are in ./index.ts

import type { Capsule } from './index';

// Extended capsule with marketplace-specific fields
export interface MarketplaceCapsule extends Capsule {
  summary?: string;
  description?: string;
  category?: string;
  author_id?: string;
  author_name?: string;
  access_count?: number;
  is_public?: boolean;
  price?: number;
}

export interface CartItem {
  capsule: MarketplaceCapsule;
  quantity: number;
  added_at: Date;
}

export interface CapsuleFilters {
  page?: number;
  per_page?: number;
  category?: string;
  search?: string;
  tags?: string[];
  min_trust?: number;
  is_public?: boolean;
  author_id?: string;
}

export interface CapsuleSearchResult {
  capsules: MarketplaceCapsule[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// Web3 / Virtuals Protocol Types

export interface PurchaseItem {
  listing_id: string;
  capsule_id: string;
  title: string;
  price_virtual: string; // Price in $VIRTUAL tokens (wei)
  price_usd?: number;    // Estimated USD value
}

export interface WalletInfo {
  address: string;
  chain_id: number;
  balance_virtual?: string;
  balance_eth?: string;
}

export interface PurchaseRequest {
  items: PurchaseItem[];
  wallet_address: string;
  transaction_hash?: string;
}

export interface PurchaseResponse {
  purchase_id: string;
  status: 'pending' | 'confirmed' | 'failed';
  transaction_hash: string | null;
  capsule_ids: string[];
  total_virtual: string;
  created_at: string;
}

export interface TransactionStatus {
  transaction_hash: string;
  status: 'pending' | 'confirmed' | 'failed';
  block_number: number | null;
  confirmations: number;
  capsule_ids: string[];
  total_virtual: string;
}
