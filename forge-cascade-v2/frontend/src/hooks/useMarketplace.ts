// Forge Cascade - Marketplace Hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { CapsuleFilters, FeaturedListing } from '../types/marketplace';

export function useMarketplaceCapsules(filters?: CapsuleFilters) {
  return useQuery({
    queryKey: ['marketplace-capsules', filters],
    queryFn: () => api.getMarketplaceCapsules(filters),
  });
}

export function useMarketplaceCapsule(id: string) {
  return useQuery({
    queryKey: ['marketplace-capsule', id],
    queryFn: () => api.getCapsule(id),
    enabled: !!id,
  });
}

export function useFeaturedCapsules(limit: number = 6) {
  return useQuery<FeaturedListing[]>({
    queryKey: ['marketplace-capsules', 'featured', limit],
    queryFn: () => api.getFeaturedCapsules(limit),
  });
}

export function useMarketplaceSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ query, filters }: { query: string; filters?: CapsuleFilters }) =>
      api.searchMarketplaceCapsules(query, filters),
    onSuccess: (data) => {
      data.capsules.forEach(capsule => {
        queryClient.setQueryData(['marketplace-capsule', capsule.id], capsule);
      });
    },
  });
}

export function usePurchaseCapsule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (capsuleId: string) => api.purchaseCapsule(capsuleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-purchases'] });
    },
  });
}

export function useMyPurchases() {
  return useQuery({
    queryKey: ['marketplace-purchases'],
    queryFn: () => api.getMyPurchases(),
  });
}
