import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
const HEALTH_BASE_URL = (() => {
  try {
    return new URL(API_URL).origin;
  } catch {
    return 'http://localhost:8001';
  }
})();

interface HealthResponse {
  status: string;
}

interface DetailedHealthResponse {
  status: string;
  components?: {
    llm_provider?: {
      is_mock?: boolean;
      provider?: string;
    };
    embedding_provider?: {
      is_mock?: boolean;
      provider?: string;
    };
  };
  warnings?: string[];
}

export type BackendStatus = 'connected' | 'disconnected' | 'checking';

export interface BackendHealthInfo {
  status: BackendStatus;
  backendStatus?: string;
  isUsingMockLLM: boolean;
  isUsingMockEmbeddings: boolean;
  warnings: string[];
}

export function useBackendHealth(): BackendHealthInfo {
  // Basic health check (fast, for connectivity)
  const { data, isError, isLoading } = useQuery<HealthResponse>({
    queryKey: ['backend-health-ping'],
    queryFn: async () => {
      const response = await axios.get<HealthResponse>(`${HEALTH_BASE_URL}/health`, {
        timeout: 5000,
      });
      return response.data;
    },
    refetchInterval: 15000,
    retry: 1,
    retryDelay: 2000,
    refetchOnWindowFocus: false,
    staleTime: 10000,
  });

  // Detailed health check (for mock provider detection)
  const { data: detailedData } = useQuery<DetailedHealthResponse>({
    queryKey: ['backend-health-detailed'],
    queryFn: async () => {
      const response = await axios.get<DetailedHealthResponse>(
        `${HEALTH_BASE_URL}/health/detailed`,
        { timeout: 10000 }
      );
      return response.data;
    },
    refetchInterval: 60000, // Less frequent - every 60s
    retry: 0, // Don't retry - detailed endpoint is optional
    refetchOnWindowFocus: false,
    staleTime: 55000,
    enabled: !isError && !isLoading, // Only fetch if basic health passed
  });

  const status: BackendStatus = isLoading
    ? 'checking'
    : isError
      ? 'disconnected'
      : 'connected';

  // Extract mock provider info from detailed response
  const isUsingMockLLM = detailedData?.components?.llm_provider?.is_mock ?? false;
  const isUsingMockEmbeddings = detailedData?.components?.embedding_provider?.is_mock ?? false;
  const warnings = detailedData?.warnings ?? [];

  return {
    status,
    backendStatus: data?.status,
    isUsingMockLLM,
    isUsingMockEmbeddings,
    warnings,
  };
}
