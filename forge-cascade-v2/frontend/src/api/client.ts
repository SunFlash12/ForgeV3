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
      // Request timeout - prevents hanging requests
      timeout: 30000, // 30 seconds
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
          // Type-safe CSRF error detection - case-insensitive for robustness
          const errorMessage = typeof data === 'object' && data !== null && 'error' in data
            ? String(data.error).toLowerCase()
            : '';
          const detailMessage = typeof data === 'object' && data !== null && 'detail' in data
            ? String(data.detail).toLowerCase()
            : '';
          const errorCode = typeof data === 'object' && data !== null && 'code' in data
            ? String(data.code).toUpperCase()
            : '';

          // SECURITY FIX (Audit 4 - M): Primary detection via error code (most reliable)
          // Backend returns code: "CSRF_MISSING" or "CSRF_INVALID"
          const isCodeCsrfError = errorCode === 'CSRF_MISSING' || errorCode === 'CSRF_INVALID';

          // Fallback: pattern matching for backwards compatibility
          const csrfPatterns = ['csrf', 'cross-site', 'token invalid', 'token missing'];
          const isPatternCsrfError = csrfPatterns.some(pattern =>
            errorMessage.includes(pattern) ||
            detailMessage.includes(pattern) ||
            errorCode.toLowerCase().includes(pattern)
          );

          const isCsrfError = isCodeCsrfError || isPatternCsrfError;

          if (isCsrfError) {
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

  // ============================================================================
  // MFA Endpoints
  // ============================================================================

  async getMfaStatus(): Promise<{ enabled: boolean; backup_codes_remaining?: number }> {
    const response = await this.client.get<{ enabled: boolean; backup_codes_remaining?: number }>('/auth/me/mfa/status');
    return response.data;
  }

  async setupMfa(): Promise<{ secret: string; qr_code: string; backup_codes: string[] }> {
    const response = await this.client.post<{ secret: string; qr_code: string; backup_codes: string[] }>('/auth/me/mfa/setup');
    return response.data;
  }

  async verifyMfa(code: string): Promise<void> {
    await this.client.post('/auth/me/mfa/verify', { code });
  }

  async disableMfa(code: string): Promise<void> {
    await this.client.delete('/auth/me/mfa', { data: { code } });
  }

  async regenerateBackupCodes(code: string): Promise<{ backup_codes: string[] }> {
    const response = await this.client.post<{ backup_codes: string[] }>('/auth/me/mfa/backup-codes', { code });
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
  // Google OAuth
  // ============================================================================

  async googleAuth(idToken: string, source: 'cascade' | 'shop' = 'cascade'): Promise<LoginResponse> {
    const response = await this.client.post<LoginResponse>('/auth/google', {
      id_token: idToken,
      source,
    });

    // Store CSRF token in memory (NOT localStorage!)
    setCSRFToken(response.data.csrf_token);

    return response.data;
  }

  async linkGoogleAccount(idToken: string): Promise<void> {
    await this.client.post('/auth/google/link', { id_token: idToken });
  }

  async unlinkGoogleAccount(): Promise<void> {
    await this.client.delete('/auth/google/unlink');
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

  async linkCapsules(childId: string, parentId: string): Promise<Capsule> {
    const response = await this.client.post<Capsule>(`/capsules/${childId}/link/${parentId}`);
    return response.data;
  }

  async forkCapsule(id: string, data: {
    title?: string;
    content?: string;
    evolution_reason: string;
  }): Promise<Capsule> {
    const response = await this.client.post<Capsule>(`/capsules/${id}/fork`, data);
    return response.data;
  }

  async verifyCapsuleIntegrity(id: string): Promise<{
    capsule_id: string;
    is_valid: boolean;
    content_hash_valid: boolean;
    signature_valid: boolean | null;
    merkle_chain_valid: boolean | null;
    verified_at: string;
    issues: string[];
  }> {
    const response = await this.client.get(`/capsules/${id}/integrity`);
    return response.data;
  }

  async verifyLineageIntegrity(id: string): Promise<{
    capsule_id: string;
    chain_length: number;
    all_valid: boolean;
    broken_links: string[];
    verified_capsules: Array<{
      id: string;
      title: string;
      is_valid: boolean;
      issues: string[];
    }>;
    verified_at: string;
  }> {
    const response = await this.client.get(`/capsules/${id}/lineage/integrity`);
    return response.data;
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

  async getConstitutionalAnalysis(proposalId: string): Promise<{
    proposal_id: string;
    is_constitutional: boolean;
    principles_checked: Array<{
      principle: string;
      compliant: boolean;
      notes: string;
    }>;
    summary: string;
    analyzed_at: string;
  }> {
    const response = await this.client.get(`/governance/proposals/${proposalId}/constitutional-analysis`);
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

  // Dashboard Metrics Endpoints
  async getActivityTimeline(hours?: number): Promise<{
    data: Array<{ time: string; capsules: number; votes: number; events: number }>;
    total_capsules: number;
    total_votes: number;
    total_events: number;
    period_hours: number;
  }> {
    const response = await this.client.get('/system/metrics/activity-timeline', {
      params: hours ? { hours } : undefined,
    });
    return response.data;
  }

  async getTrustDistribution(): Promise<{
    distribution: Array<{ name: string; value: number; color: string }>;
    total_users: number;
  }> {
    const response = await this.client.get('/system/metrics/trust-distribution');
    return response.data;
  }

  async getPipelinePerformance(): Promise<{
    phases: Array<{ phase: string; duration: number; execution_count: number }>;
    total_executions: number;
    average_total_duration_ms: number;
  }> {
    const response = await this.client.get('/system/metrics/pipeline-performance');
    return response.data;
  }

  // ============================================================================
  // Diagnosis / PrimeKG Endpoints
  // ============================================================================

  async createDiagnosisSession(data: {
    phenotypes?: string[];
    genetic_variants?: string[];
    patient_demographics?: Record<string, unknown>;
    medical_history?: string[];
  }): Promise<{
    session_id: string;
    status: string;
    created_at: string;
  }> {
    const response = await this.client.post('/diagnosis/sessions', data);
    return response.data;
  }

  async getDiagnosisSession(sessionId: string): Promise<{
    session_id: string;
    status: string;
    current_questions?: Array<{ question_id: string; text: string; options?: string[] }>;
    progress: number;
  }> {
    const response = await this.client.get(`/diagnosis/sessions/${sessionId}`);
    return response.data;
  }

  async startDiagnosis(sessionId: string, data: {
    symptoms: string[];
    duration?: string;
    severity?: string;
  }): Promise<{
    session_id: string;
    status: string;
    follow_up_questions?: Array<{ question_id: string; text: string; options?: string[] }>;
  }> {
    const response = await this.client.post(`/diagnosis/sessions/${sessionId}/start`, data);
    return response.data;
  }

  async answerDiagnosisQuestion(sessionId: string, data: {
    question_id: string;
    answer: string;
  }): Promise<{
    session_id: string;
    status: string;
    next_questions?: Array<{ question_id: string; text: string; options?: string[] }>;
    progress: number;
  }> {
    const response = await this.client.post(`/diagnosis/sessions/${sessionId}/answer`, data);
    return response.data;
  }

  async getDiagnosisResults(sessionId: string): Promise<{
    session_id: string;
    diagnoses: Array<{
      disease_id: string;
      disease_name: string;
      confidence: number;
      matching_phenotypes: string[];
      evidence: string[];
    }>;
    recommendations: string[];
    generated_at: string;
  }> {
    const response = await this.client.get(`/diagnosis/sessions/${sessionId}/results`);
    return response.data;
  }

  async searchPhenotypes(query: string): Promise<{
    phenotypes: Array<{
      hpo_id: string;
      name: string;
      definition?: string;
    }>;
  }> {
    const response = await this.client.post('/primekg/phenotype-search', { query, limit: 20 });
    return response.data;
  }

  async getDrugDiseaseInfo(diseaseId: string): Promise<{
    disease_id: string;
    disease_name: string;
    drugs: Array<{
      drug_id: string;
      drug_name: string;
      relationship: string;
      evidence_level?: string;
    }>;
  }> {
    const response = await this.client.post('/primekg/drug-disease', { disease_id: diseaseId });
    return response.data;
  }

  async getGeneAssociations(diseaseId: string): Promise<{
    disease_id: string;
    genes: Array<{
      gene_id: string;
      gene_symbol: string;
      association_type: string;
      evidence?: string;
    }>;
  }> {
    const response = await this.client.post('/primekg/gene-association', { disease_id: diseaseId });
    return response.data;
  }

  // ============================================================================
  // Notifications Endpoints
  // ============================================================================

  async getNotifications(params?: { unread_only?: boolean; limit?: number }): Promise<{
    notifications: Array<{
      id: string;
      type: string;
      title: string;
      message: string;
      priority: string;
      read: boolean;
      created_at: string;
      data?: Record<string, unknown>;
    }>;
    unread_count: number;
  }> {
    const response = await this.client.get('/notifications', { params });
    return response.data;
  }

  async markNotificationRead(id: string): Promise<void> {
    await this.client.post(`/notifications/${id}/read`);
  }

  async deleteNotification(id: string): Promise<void> {
    await this.client.delete(`/notifications/${id}`);
  }

  // ============================================================================
  // Maintenance Mode Endpoints
  // ============================================================================

  async getMaintenanceStatus(): Promise<{
    enabled: boolean;
    message?: string;
    estimated_end?: string;
  }> {
    const response = await this.client.get('/system/maintenance');
    return response.data;
  }

  async enableMaintenance(data: { message: string; estimated_minutes?: number }): Promise<void> {
    await this.client.post('/system/maintenance/enable', data);
  }

  async disableMaintenance(): Promise<void> {
    await this.client.post('/system/maintenance/disable');
  }

  // ============================================================================
  // Knowledge Query Endpoints
  // ============================================================================

  async executeKnowledgeQuery(query: string): Promise<{
    results: Array<Record<string, unknown>>;
    query_type: string;
    execution_time_ms: number;
    cached: boolean;
  }> {
    const response = await this.client.post('/graph/query/knowledge', { query });
    return response.data;
  }

  // ============================================================================
  // Delegation Endpoints
  // ============================================================================

  async createDelegation(data: {
    delegate_to: string;
    proposal_type?: string;
    expires_at?: string;
  }): Promise<{
    id: string;
    delegator_id: string;
    delegate_id: string;
    proposal_type: string | null;
    created_at: string;
    expires_at: string | null;
  }> {
    const response = await this.client.post('/governance/delegations', data);
    return response.data;
  }

  async getMyDelegations(): Promise<Array<{
    id: string;
    delegate_id: string;
    delegate_username: string;
    proposal_type: string | null;
    created_at: string;
    expires_at: string | null;
  }>> {
    const response = await this.client.get('/governance/delegations');
    return response.data;
  }

  async revokeDelegation(id: string): Promise<void> {
    await this.client.delete(`/governance/delegations/${id}`);
  }

  // ============================================================================
  // User Directory Endpoints
  // ============================================================================

  async searchUsers(query: string, params?: { limit?: number }): Promise<{
    users: Array<{
      id: string;
      username: string;
      display_name: string | null;
      trust_level: string;
      created_at: string;
    }>;
  }> {
    const response = await this.client.get('/users/search', { params: { q: query, ...params } });
    return response.data;
  }

  async getUserProfile(userId: string): Promise<{
    id: string;
    username: string;
    display_name: string | null;
    trust_level: string;
    capsules_created: number;
    proposals_made: number;
    votes_cast: number;
    created_at: string;
  }> {
    const response = await this.client.get(`/users/${userId}`);
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
