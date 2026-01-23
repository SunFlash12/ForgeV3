// Forge Shop - API Client
import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  User,
  Capsule,
  CapsuleSearchResult,
  LoginCredentials,
  RegisterData,
  AuthTokens,
  ApiError,
  CapsuleFilters,
  PurchaseItem,
  PurchaseResponse,
  TransactionStatus,
} from '../types';

const CASCADE_API_URL = import.meta.env.VITE_CASCADE_API_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private client: AxiosInstance;
  private csrfToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: CASCADE_API_URL,
      withCredentials: true, // Send cookies for auth
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // SECURITY FIX (Audit 3): Request interceptor to add CSRF token to state-changing requests
    this.client.interceptors.request.use(
      (config) => {
        // Add CSRF token for state-changing requests
        if (['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase() || '')) {
          const token = this.csrfToken || this.getCsrfTokenFromCookie();
          if (token) {
            config.headers['X-CSRF-Token'] = token;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError<ApiError>) => {
        if (error.response?.status === 401) {
          // Token expired or invalid - clear auth state
          window.dispatchEvent(new CustomEvent('auth:logout'));
        }
        return Promise.reject(error);
      }
    );
  }

  // SECURITY FIX (Audit 3): Get CSRF token from cookie
  private getCsrfTokenFromCookie(): string | null {
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? match[1] : null;
  }

  // SECURITY FIX (Audit 3): Set CSRF token from login response
  setCsrfToken(token: string): void {
    this.csrfToken = token;
  }

  // ==========================================================================
  // Auth
  // ==========================================================================

  async login(credentials: LoginCredentials): Promise<User> {
    const { data } = await this.client.post<User>('/auth/login', credentials);
    return data;
  }

  async register(userData: RegisterData): Promise<User> {
    const { data } = await this.client.post<User>('/auth/register', userData);
    return data;
  }

  async logout(): Promise<void> {
    await this.client.post('/auth/logout');
  }

  async getCurrentUser(): Promise<User> {
    const { data } = await this.client.get<User>('/auth/me');
    return data;
  }

  async refreshToken(): Promise<AuthTokens> {
    const { data } = await this.client.post<AuthTokens>('/auth/refresh');
    return data;
  }

  // ==========================================================================
  // Capsules
  // ==========================================================================

  async getCapsules(filters?: CapsuleFilters): Promise<CapsuleSearchResult> {
    const params = new URLSearchParams();

    if (filters) {
      if (filters.page) params.append('page', String(filters.page));
      if (filters.per_page) params.append('per_page', String(filters.per_page));
      if (filters.category) params.append('category', filters.category);
      if (filters.search) params.append('search', filters.search);
      if (filters.min_trust) params.append('min_trust', String(filters.min_trust));
      if (filters.is_public !== undefined) params.append('is_public', String(filters.is_public));
      if (filters.author_id) params.append('author_id', filters.author_id);
      if (filters.tags?.length) {
        filters.tags.forEach(tag => params.append('tags', tag));
      }
    }

    const { data } = await this.client.get<CapsuleSearchResult>(`/capsules?${params.toString()}`);
    return data;
  }

  async getCapsule(id: string): Promise<Capsule> {
    const { data } = await this.client.get<Capsule>(`/capsules/${id}`);
    return data;
  }

  async searchCapsules(query: string, filters?: CapsuleFilters): Promise<CapsuleSearchResult> {
    const { data } = await this.client.post<CapsuleSearchResult>('/capsules/search', {
      query,
      ...filters,
    });
    return data;
  }

  async getFeaturedCapsules(limit: number = 4): Promise<Capsule[]> {
    const { data } = await this.client.get<CapsuleSearchResult>('/capsules', {
      params: {
        per_page: limit,
        is_public: true,
      },
    });
    return data.capsules;
  }

  // ==========================================================================
  // User
  // ==========================================================================

  async getUserProfile(userId: string): Promise<User> {
    const { data } = await this.client.get<User>(`/users/${userId}`);
    return data;
  }

  async updateProfile(updates: Partial<User>): Promise<User> {
    const { data } = await this.client.patch<User>('/auth/me', updates);
    return data;
  }

  // ==========================================================================
  // Google OAuth
  // ==========================================================================

  async googleAuth(idToken: string, source: 'cascade' | 'shop' = 'shop'): Promise<User> {
    const { data } = await this.client.post<User>('/auth/google', {
      id_token: idToken,
      source,
    });
    return data;
  }

  // ==========================================================================
  // Web3 / Virtuals Protocol Purchases
  // ==========================================================================

  /**
   * Submit a purchase after on-chain transaction is confirmed.
   * Backend will verify the transaction on Base and grant capsule access.
   */
  async submitPurchase(
    items: PurchaseItem[],
    walletAddress: string,
    transactionHash: string
  ): Promise<PurchaseResponse> {
    const { data } = await this.client.post<PurchaseResponse>(
      '/marketplace/purchase',
      {
        items,
        wallet_address: walletAddress,
        transaction_hash: transactionHash,
      }
    );
    return data;
  }

  /**
   * Check status of a purchase by transaction hash.
   */
  async getTransactionStatus(transactionHash: string): Promise<TransactionStatus> {
    const { data } = await this.client.get<TransactionStatus>(
      `/marketplace/transaction/${transactionHash}`
    );
    return data;
  }

  /**
   * Get current $VIRTUAL token price in USD.
   */
  async getVirtualPrice(): Promise<{ price_usd: number; updated_at: string }> {
    const { data } = await this.client.get<{ price_usd: number; updated_at: string }>(
      '/marketplace/virtual-price'
    );
    return data;
  }

  // ==========================================================================
  // Marketplace Purchases
  // ==========================================================================

  async purchaseCapsule(capsuleId: string): Promise<{ success: boolean; transaction_id: string }> {
    const { data } = await this.client.post(`/marketplace/listings/${capsuleId}/purchase`, {
      capsule_id: capsuleId,
    });
    return data;
  }

  async getMyPurchases(): Promise<Capsule[]> {
    const { data } = await this.client.get<{ capsules: Capsule[] }>('/marketplace/purchases');
    return data.capsules;
  }
}

// Singleton instance
export const api = new ApiClient();
export default api;
