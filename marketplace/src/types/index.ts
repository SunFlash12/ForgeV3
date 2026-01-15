// Forge Shop - Type Definitions

export interface User {
  id: string;
  email: string;
  username: string;
  display_name?: string;
  avatar_url?: string;
  trust_level: 'SANDBOX' | 'STANDARD' | 'TRUSTED' | 'CORE';
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export type CapsuleType =
  | 'INSIGHT' | 'DECISION' | 'LESSON' | 'WARNING' | 'PRINCIPLE' | 'MEMORY'
  | 'KNOWLEDGE' | 'CODE' | 'CONFIG' | 'TEMPLATE' | 'DOCUMENT';

export type TrustLevel = 'QUARANTINE' | 'SANDBOX' | 'STANDARD' | 'TRUSTED' | 'CORE';

export interface Capsule {
  id: string;
  title: string;
  content: string;
  summary?: string;
  description?: string;
  category?: string;
  type: CapsuleType;
  tags: string[];
  // Owner fields - support both naming conventions
  owner_id: string;
  author_id?: string;
  author_name?: string;
  // Trust fields
  trust_level: TrustLevel;
  trust_score?: number;
  // Version control
  version: string;
  parent_id: string | null;
  // Stats
  view_count: number;
  fork_count: number;
  access_count?: number;
  // Metadata
  metadata?: Record<string, unknown>;
  is_archived: boolean;
  is_public?: boolean;
  price?: number;
  created_at: string;
  updated_at: string;
}

export interface CapsuleSearchResult {
  capsules: Capsule[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface CartItem {
  capsule: Capsule;
  quantity: number;
  added_at: Date;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  display_name?: string;
}

export interface ApiError {
  error: string;
  status_code: number;
  details?: unknown;
}

export interface PaginationParams {
  page?: number;
  per_page?: number;
}

export interface CapsuleFilters extends PaginationParams {
  category?: string;
  search?: string;
  tags?: string[];
  min_trust?: number;
  is_public?: boolean;
  author_id?: string;
}
