// Forge Shop - Capsule Hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { CapsuleFilters } from '../types';

export function useCapsules(filters?: CapsuleFilters) {
  return useQuery({
    queryKey: ['capsules', filters],
    queryFn: () => api.getCapsules(filters),
  });
}

export function useCapsule(id: string) {
  return useQuery({
    queryKey: ['capsule', id],
    queryFn: () => api.getCapsule(id),
    enabled: !!id,
  });
}

export function useFeaturedCapsules(limit: number = 4) {
  return useQuery({
    queryKey: ['capsules', 'featured', limit],
    queryFn: () => api.getFeaturedCapsules(limit),
  });
}

export function useSearchCapsules() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ query, filters }: { query: string; filters?: CapsuleFilters }) =>
      api.searchCapsules(query, filters),
    onSuccess: (data) => {
      // Cache individual capsules from search results
      data.capsules.forEach(capsule => {
        queryClient.setQueryData(['capsule', capsule.id], capsule);
      });
    },
  });
}

export function usePurchaseCapsule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (capsuleId: string) => api.purchaseCapsule(capsuleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] });
    },
  });
}

export function useMyPurchases() {
  return useQuery({
    queryKey: ['purchases'],
    queryFn: () => api.getMyPurchases(),
  });
}
