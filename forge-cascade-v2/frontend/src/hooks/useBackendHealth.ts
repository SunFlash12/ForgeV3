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

export type BackendStatus = 'connected' | 'disconnected' | 'checking';

export function useBackendHealth() {
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

  const status: BackendStatus = isLoading
    ? 'checking'
    : isError
      ? 'disconnected'
      : 'connected';

  return {
    status,
    backendStatus: data?.status,
  };
}
