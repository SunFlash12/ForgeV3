// ============================================================================
// Base Types
// ============================================================================

export type UUID = string;

// Trust levels - QUARANTINE is the backend's lowest level (maps to UNTRUSTED conceptually)
export type TrustLevel = 'QUARANTINE' | 'SANDBOX' | 'STANDARD' | 'TRUSTED' | 'CORE';

// Legacy alias for backwards compatibility
export type TrustLevelLegacy = 'UNTRUSTED' | 'SANDBOX' | 'STANDARD' | 'TRUSTED' | 'CORE';

export type UserRole = 'USER' | 'MODERATOR' | 'ADMIN' | 'SYSTEM';

// CapsuleType includes all backend types
export type CapsuleType =
  | 'INSIGHT' | 'DECISION' | 'LESSON' | 'WARNING' | 'PRINCIPLE' | 'MEMORY'  // Frontend display types
  | 'KNOWLEDGE' | 'CODE' | 'CONFIG' | 'TEMPLATE' | 'DOCUMENT';              // Backend-only types

// ProposalStatus matches backend exactly
export type ProposalStatus = 'DRAFT' | 'ACTIVE' | 'VOTING' | 'PASSED' | 'REJECTED' | 'EXECUTED' | 'CANCELLED';

export type ProposalType = 'POLICY' | 'SYSTEM' | 'OVERLAY' | 'CAPSULE' | 'TRUST' | 'CONSTITUTIONAL';

// VoteChoice - FOR/AGAINST are deprecated aliases in backend
export type VoteChoice = 'APPROVE' | 'REJECT' | 'ABSTAIN';

export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';
export type AnomalySeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

// ============================================================================
// User Types
// ============================================================================

export interface User {
  id: UUID;
  username: string;
  email: string;
  display_name: string | null;
  trust_level: TrustLevel;
  trust_score: number;
  roles: string[];  // Backend returns role values as strings
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface TrustInfo {
  current_level: string;  // Backend returns enum name as string
  trust_score: number;
  next_level: string | null;
  score_to_next: number | null;
  thresholds: Record<string, number>;
}

// ============================================================================
// Capsule Types
// ============================================================================

export interface Capsule {
  id: UUID;
  type: CapsuleType;
  title: string | null;
  content: string;
  owner_id: UUID;
  trust_level: TrustLevel;
  version: string;
  parent_id: UUID | null;
  tags: string[];
  metadata: Record<string, unknown>;
  view_count: number;
  fork_count: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface CapsuleLineage {
  capsule: Capsule;
  ancestors: Capsule[];
  descendants: Capsule[];
  depth: number;
  trust_gradient: number[];
}

export interface CreateCapsuleRequest {
  type: CapsuleType;
  title: string;
  content: string;
  tags?: string[];
  parent_id?: UUID;
  metadata?: Record<string, unknown>;
}

export interface UpdateCapsuleRequest {
  title?: string;
  content?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

// ============================================================================
// Governance Types
// ============================================================================

export interface Proposal {
  id: UUID;
  title: string;
  description: string;
  proposal_type: string;
  status: ProposalStatus;
  proposer_id: UUID;
  action: Record<string, unknown>;
  voting_period_days: number;
  quorum_percent: number;
  pass_threshold: number;
  votes_for: number;
  votes_against: number;
  votes_abstain: number;
  weight_for: number;
  weight_against: number;
  weight_abstain: number;
  created_at: string | null;
  voting_starts_at: string | null;
  voting_ends_at: string | null;
}

export interface Vote {
  id: UUID;
  proposal_id: UUID;
  user_id: UUID;
  username?: string;
  choice: VoteChoice;
  weight: number;
  rationale: string | null;
  created_at: string;
}

export interface GhostCouncilRecommendation {
  recommendation: VoteChoice;
  confidence: number;
  reasoning: string;
  historical_patterns: {
    similar_proposals: number;
    typical_outcome: string;
    participation_rate: number;
  };
}

export interface CreateProposalRequest {
  title: string;
  description: string;
  proposal_type: ProposalType;
  action?: Record<string, unknown>;
  voting_period_days?: number;
  quorum_percent?: number;
  pass_threshold?: number;
}

export interface CastVoteRequest {
  choice: VoteChoice;
  rationale?: string;
}

// ============================================================================
// Overlay Types
// ============================================================================

export interface Overlay {
  id: string;
  name: string;
  description: string;
  version: string;
  phase: number;
  priority: number;
  enabled: boolean;
  critical: boolean;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface OverlayMetrics {
  overlay_id: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  average_duration_ms: number;
  error_rate: number;
  last_executed: string | null;
}

export interface CanaryDeployment {
  overlay_id: string;
  current_stage: number;
  total_stages: number;
  traffic_percentage: number;
  started_at: string;
  current_stage_started_at: string;
  last_advanced_at: string | null;
  success_count: number;
  failure_count: number;
  rollback_on_failure: boolean;
  is_complete: boolean;
  can_advance: boolean;
}

// ============================================================================
// System/Health Types
// ============================================================================

export interface SystemHealth {
  status: HealthStatus;
  timestamp: string;
  uptime_seconds: number;
  version: string;
  components: Record<string, ComponentHealth>;
  checks: Record<string, boolean>;
}

export interface ComponentHealth {
  status: HealthStatus;
  [key: string]: unknown;
}

export interface SystemMetrics {
  timestamp: string;
  events_emitted_total: number;
  events_processed_total: number;
  active_overlays: number;
  pipeline_executions: number;
  average_pipeline_duration_ms: number;
  open_circuit_breakers: number;
  active_anomalies: number;
  canary_deployments: number;
  db_connected: boolean;
  memory_usage_mb: number | null;
  cpu_usage_percent: number | null;
}

export interface CircuitBreaker {
  name: string;
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  failure_count: number;
  success_count: number;
  last_failure_time: string | null;
  last_success_time: string | null;
  reset_timeout: number;
  failure_threshold: number;
  success_threshold: number;
}

export interface Anomaly {
  id: string;
  metric_name: string;
  anomaly_type: string;
  severity: AnomalySeverity;
  anomaly_score: number;
  value: number;
  expected_value: number | null;
  detected_at: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
  context: Record<string, unknown>;
}

export interface SystemEvent {
  event_type: string;
  timestamp: string;
  data: Record<string, unknown>;
  correlation_id: string | null;
}

// ============================================================================
// Pagination Types
// ============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;  // Backend uses page_size
  total_pages: number;  // Computed: Math.ceil(total / page_size)
  has_more: boolean;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;  // Backend uses page_size
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}
