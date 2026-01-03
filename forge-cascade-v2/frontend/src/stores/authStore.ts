import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../api/client';
import type { User, TrustInfo } from '../types';

interface AuthState {
  user: User | null;
  trustInfo: TrustInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchCurrentUser: () => Promise<void>;
  fetchTrustInfo: () => Promise<void>;
  updateProfile: (data: { display_name?: string; email?: string }) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      trustInfo: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          await api.login(username, password);
          const user = await api.getCurrentUser();
          const trustInfo = await api.getTrustInfo();
          set({ 
            user, 
            trustInfo, 
            isAuthenticated: true, 
            isLoading: false 
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Login failed';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      register: async (username: string, email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          await api.register(username, email, password);
          // Auto-login after registration
          await get().login(username, password);
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Registration failed';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        set({ isLoading: true });
        try {
          await api.logout();
        } finally {
          set({ 
            user: null, 
            trustInfo: null, 
            isAuthenticated: false, 
            isLoading: false,
            error: null 
          });
        }
      },

      fetchCurrentUser: async () => {
        if (!localStorage.getItem('access_token')) {
          set({ isAuthenticated: false });
          return;
        }
        
        set({ isLoading: true });
        try {
          const user = await api.getCurrentUser();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch {
          set({ 
            user: null, 
            isAuthenticated: false, 
            isLoading: false 
          });
        }
      },

      fetchTrustInfo: async () => {
        try {
          const trustInfo = await api.getTrustInfo();
          set({ trustInfo });
        } catch {
          // Ignore errors
        }
      },

      updateProfile: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const user = await api.updateProfile(data);
          set({ user, isLoading: false });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Update failed';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      changePassword: async (currentPassword: string, newPassword: string) => {
        set({ isLoading: true, error: null });
        try {
          await api.changePassword(currentPassword, newPassword);
          set({ isLoading: false });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Password change failed';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'forge-auth',
      partialize: (state) => ({ 
        isAuthenticated: state.isAuthenticated,
        // Don't persist user data, refetch on load
      }),
    }
  )
);
