import axios from 'axios';
import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type {
  User,
  TrustInfo,
  Capsule,
  CapsuleLineage,
  CreateCapsuleRequest,
  UpdateCapsuleRequest,
  Proposal,
  Vote,
  GhostCouncilRecommendation,
  CreateProposalRequest,
  CastVoteRequest,
  Overlay,
  OverlayMetrics,
  CanaryDeployment,
  SystemHealth,
  SystemMetrics,
  CircuitBreaker,
  Anomaly,
  SystemEvent,
  PaginatedResponse,
  PaginationParams,
} from '../types';

// ============================================================================
// API Client Setup
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// New login response type (tokens are in httpOnly cookies)
interface LoginResponse {
  csrf_token: string;
  expires_in: number;
  user: User;
}

interface RefreshResponse {
  csrf_token: string;
  expires_in: number;
}

// CSRF token storage (in memory only - not localStorage!)
let csrfToken: string | null = null;

// Helper to get CSRF token from cookie (fallback)
function getCsrfTokenFromCookie(): string | null {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

// Get current CSRF token
function getCSRFToken(): string | null {
  return csrfToken || getCsrfTokenFromCookie();
}

// Set CSRF token (called after login/refresh)
function setCSRFToken(token: string | null): void {
  csrfToken = token;
}

// Clear CSRF token (called on logout)
function clearCSRFToken(): void {
  csrfToken = null;
}

class ForgeApiClient {
  private client: AxiosInstance;
  private refreshPromise: Promise<string> | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      // CRITICAL: Enable credentials for cookie-based auth
      withCredentials: true,
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor - add CSRF token for state-changing requests
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // Add CSRF token for state-changing methods
        const statefulMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];
        if (statefulMethods.includes(config.method?.toUpperCase() || '')) {
          const token = getCSRFToken();
          if (token && config.headers) {
            config.headers['X-CSRF-Token'] = token;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle 401 and refresh token
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await this.refreshToken();
            // Retry the original request (cookies are automatically included)
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed - redirect to login
            clearCSRFToken();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        // Handle CSRF errors
        if (error.response?.status === 403) {
          const data = error.response.data;
          // Type-safe CSRF error detection
          const errorMessage = typeof data === 'object' && data !== null && 'error' in data
            ? String(data.error)
            : '';
          const detailMessage = typeof data === 'object' && data !== null && 'detail' in data
            ? String(data.detail)
            : '';

          if (errorMessage.includes('CSRF') || detailMessage.includes('CSRF')) {
            // CSRF token expired/invalid - try to refresh
            try {
              await this.refreshToken();
              // Retry with new CSRF token
              if (originalRequest) {
                return this.client(originalRequest);
              }
            } catch {
              clearCSRFToken();
              window.location.href = '/login';
            }
          }
        }

        return Promise.reject(error);
      }
    );
  }

  private async refreshToken(): Promise<void> {
    // Prevent multiple simultaneous refresh calls
    if (this.refreshPromise) {
      await this.refreshPromise;
      return;
    }

    this.refreshPromise = (async () => {
      try {
        // Refresh token is in httpOnly cookie, sent automatically
        const response = await axios.post<RefreshResponse>(
          `${API_BASE_URL}/auth/refresh`,
          {},
          { withCredentials: true }
        );

        // Update CSRF token
        setCSRFToken(response.data.csrf_token);

        return response.data.csrf_token;
      } finally {
        this.refreshPromise = null;
      }
    })();

    await this.refreshPromise;
  }

  // ============================================================================
  // Auth Endpoints
  // ============================================================================

  async register(username: string, email: string, password: string): Promise<User> {
    const response = await this.client.post<User>('/auth/register', {
      username,
      email,
      password,
    });
    return response.data;
  }

  async login(username: string, password: string): Promise<LoginResponse> {
    const response = await this.client.post<LoginResponse>('/auth/login', {
      username,
      password,
    });

    // Store CSRF token in memory (NOT localStorage!)
    setCSRFToken(response.data.csrf_token);

    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/auth/logout');
    } finally {
      // Clear CSRF token
      clearCSRFToken();
    }
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/auth/me');
    return response.data;
  }

  async updateProfile(data: { display_name?: string; email?: string; metadata?: Record<string, unknown> }): Promise<User> {
    const response = await this.client.patch<User>('/auth/me', data);
    return response.data;
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.client.post('/auth/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  async getTrustInfo(): Promise<TrustInfo> {
    const response = await this.client.get<TrustInfo>('/auth/me/trust');
    return response.data;
  }

  // Check if user is authenticated (has valid session)
  async checkAuth(): Promise<boolean> {
    try {
      await this.getCurrentUser();
      return true;
    } catch {
      return false;
    }
  }

  // ============================================================================
  // Capsule Endpoints
  // ============================================================================

  async createCapsule(data: CreateCapsuleRequest): Promise<Capsule> {
    const response = await this.client.post<Capsule>('/capsules', data);
    return response.data;
  }

  async getCapsule(id: string): Promise<Capsule> {
    const response = await this.client.get<Capsule>(`/capsules/${id}`);
    return response.data;
  }

  async updateCapsule(id: string, data: UpdateCapsuleRequest): Promise<Capsule> {
    const response = await this.client.patch<Capsule>(`/capsules/${id}`, data);
    return response.data;
  }

  async deleteCapsule(id: string): Promise<void> {
    await this.client.delete(`/capsules/${id}`);
  }

  async listCapsules(params?: PaginationParams & { type?: string; owner_id?: string; tag?: string }): Promise<PaginatedResponse<Capsule>> {
    const response = await this.client.get<PaginatedResponse<Capsule>>('/capsules', { params });
    return response.data;
  }

  async getCapsuleLineage(id: string, depth?: number): Promise<CapsuleLineage> {
    const response = await this.client.get<CapsuleLineage>(`/capsules/${id}/lineage`, {
      params: { depth },
    });
    return response.data;
  }

  async linkCapsules(childId: string, parentId: string): Promise<void> {
    await this.client.post(`/capsules/${childId}/link/${parentId}`);
  }

  async searchCapsules(query: string, params?: { limit?: number; type?: string; min_trust?: number }): Promise<Capsule[]> {
    const response = await this.client.post<{ results: Capsule[] }>('/capsules/search', {
      query,
      ...params,
    });
    return response.data.results;
  }

  async getRecentCapsules(limit?: number): Promise<Capsule[]> {
    const response = await this.client.get<{ capsules: Capsule[] }>('/capsules/search/recent', {
      params: { limit },
    });
    return response.data.capsules;
  }

  // ============================================================================
  // Governance Endpoints
  // ============================================================================

  async createProposal(data: CreateProposalRequest): Promise<Proposal> {
    const response = await this.client.post<Proposal>('/governance/proposals', data);
    return response.data;
  }

  async getProposal(id: string): Promise<Proposal> {
    const response = await this.client.get<Proposal>(`/governance/proposals/${id}`);
    return response.data;
  }

  async listProposals(params?: PaginationParams & { status?: string; type?: string }): Promise<PaginatedResponse<Proposal>> {
    const response = await this.client.get<PaginatedResponse<Proposal>>('/governance/proposals', { params });
    return response.data;
  }

  async getActiveProposals(): Promise<Proposal[]> {
    const response = await this.client.get<{ proposals: Proposal[] }>('/governance/proposals/active');
    return response.data.proposals;
  }

  async withdrawProposal(id: string): Promise<void> {
    await this.client.delete(`/governance/proposals/${id}`);
  }

  async castVote(proposalId: string, data: CastVoteRequest): Promise<Vote> {
    const response = await this.client.post<Vote>(`/governance/proposals/${proposalId}/vote`, data);
    return response.data;
  }

  async getProposalVotes(proposalId: string): Promise<Vote[]> {
    const response = await this.client.get<{ votes: Vote[] }>(`/governance/proposals/${proposalId}/votes`);
    return response.data.votes;
  }

  async getMyVote(proposalId: string): Promise<Vote | null> {
    try {
      const response = await this.client.get<Vote>(`/governance/proposals/${proposalId}/my-vote`);
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  async getGhostCouncilRecommendation(proposalId: string): Promise<GhostCouncilRecommendation> {
    const response = await this.client.get<GhostCouncilRecommendation>(`/governance/proposals/${proposalId}/ghost-council`);
    return response.data;
  }

  async getGhostCouncilMembers(): Promise<Array<{ id: string; name: string; role: string; weight: number }>> {
    const response = await this.client.get<Array<{ id: string; name: string; role: string; weight: number }>>('/governance/ghost-council/members');
    return response.data;
  }

  async getGhostCouncilIssues(): Promise<Array<{
    id: string;
    category: string;
    severity: string;
    title: string;
    description: string;
    affected_entities: string[];
    detected_at: string;
    source: string;
    resolved: boolean;
    resolution: string | null;
    has_ghost_council_opinion: boolean;
  }>> {
    const response = await this.client.get('/governance/ghost-council/issues');
    return response.data;
  }

  async getGhostCouncilStats(): Promise<{
    proposals_reviewed: number;
    issues_responded: number;
    unanimous_decisions: number;
    split_decisions: number;
    cache_hits: number;
    active_issues: number;
    total_issues_tracked: number;
    council_members: number;
  }> {
    const response = await this.client.get('/governance/ghost-council/stats');
    return response.data;
  }

  async finalizeProposal(proposalId: string): Promise<Proposal> {
    const response = await this.client.post<Proposal>(`/governance/proposals/${proposalId}/finalize`);
    return response.data;
  }

  // ============================================================================
  // Overlay Endpoints
  // ============================================================================

  async listOverlays(): Promise<Overlay[]> {
    const response = await this.client.get<{ overlays: Overlay[] }>('/overlays');
    return response.data.overlays;
  }

  async getActiveOverlays(): Promise<Overlay[]> {
    const response = await this.client.get<{ overlays: Overlay[] }>('/overlays/active');
    return response.data.overlays;
  }

  async getOverlay(id: string): Promise<Overlay> {
    const response = await this.client.get<Overlay>(`/overlays/${id}`);
    return response.data;
  }

  async activateOverlay(id: string): Promise<Overlay> {
    const response = await this.client.post<Overlay>(`/overlays/${id}/activate`);
    return response.data;
  }

  async deactivateOverlay(id: string): Promise<Overlay> {
    const response = await this.client.post<Overlay>(`/overlays/${id}/deactivate`);
    return response.data;
  }

  async getOverlayMetrics(id: string): Promise<OverlayMetrics> {
    const response = await this.client.get<OverlayMetrics>(`/overlays/${id}/metrics`);
    return response.data;
  }

  async getCanaryStatus(overlayId: string): Promise<CanaryDeployment | null> {
    try {
      const response = await this.client.get<CanaryDeployment>(`/overlays/${overlayId}/canary`);
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  async startCanary(overlayId: string): Promise<CanaryDeployment> {
    const response = await this.client.post<CanaryDeployment>(`/overlays/${overlayId}/canary/start`);
    return response.data;
  }

  async advanceCanary(overlayId: string): Promise<CanaryDeployment> {
    const response = await this.client.post<CanaryDeployment>(`/overlays/${overlayId}/canary/advance`);
    return response.data;
  }

  async rollbackCanary(overlayId: string): Promise<void> {
    await this.client.post(`/overlays/${overlayId}/canary/rollback`);
  }

  // ============================================================================
  // System Endpoints
  // ============================================================================

  async getSystemHealth(): Promise<SystemHealth> {
    const response = await this.client.get<SystemHealth>('/system/health');
    return response.data;
  }

  async getSystemMetrics(): Promise<SystemMetrics> {
    const response = await this.client.get<SystemMetrics>('/system/metrics');
    return response.data;
  }

  async getCircuitBreakers(): Promise<CircuitBreaker[]> {
    const response = await this.client.get<{ circuit_breakers: CircuitBreaker[] }>('/system/circuit-breakers');
    return response.data.circuit_breakers;
  }

  async resetCircuitBreaker(name: string): Promise<void> {
    await this.client.post(`/system/circuit-breakers/${name}/reset`);
  }

  async getAnomalies(params?: { severity?: string; resolved?: boolean; hours?: number }): Promise<Anomaly[]> {
    const response = await this.client.get<{ anomalies: Anomaly[] }>('/system/anomalies', { params });
    return response.data.anomalies;
  }

  async acknowledgeAnomaly(id: string, notes?: string): Promise<Anomaly> {
    const response = await this.client.post<Anomaly>(`/system/anomalies/${id}/acknowledge`, { notes });
    return response.data;
  }

  async resolveAnomaly(id: string, notes?: string): Promise<Anomaly> {
    const response = await this.client.post<Anomaly>(`/system/anomalies/${id}/resolve`, { notes });
    return response.data;
  }

  async getRecentEvents(params?: { limit?: number; event_type?: string }): Promise<SystemEvent[]> {
    const response = await this.client.get<{ events: SystemEvent[] }>('/system/events/recent', { params });
    return response.data.events;
  }

  async getCanaryDeployments(): Promise<CanaryDeployment[]> {
    const response = await this.client.get<{ deployments: CanaryDeployment[] }>('/system/canaries');
    return response.data.deployments;
  }

  async getSystemInfo(): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>('/system/info');
    return response.data;
  }

  // ============================================================================
  // Generic HTTP Methods (for custom endpoints)
  // ============================================================================

  async get<T = unknown>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T = unknown>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  async put<T = unknown>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.put<T>(url, data);
    return response.data;
  }

  async patch<T = unknown>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.patch<T>(url, data);
    return response.data;
  }

  async delete<T = unknown>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }
}

// Export singleton instance
export const api = new ForgeApiClient();
export default api;

// Export CSRF helper for components that need it
export { getCSRFToken, setCSRFToken, clearCSRFToken };

// Type augmentation for axios
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    _retry?: boolean;
  }
}
