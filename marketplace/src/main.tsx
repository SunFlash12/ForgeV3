import React, { Component, ErrorInfo, ReactNode } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GoogleOAuthProvider } from '@react-oauth/google';
import * as Sentry from '@sentry/react';
import { AuthProvider } from './contexts/AuthContext';
import { CartProvider } from './contexts/CartContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { Web3Provider } from './contexts/Web3Context';
import App from './App';
import './index.css';

// Initialize Sentry for error tracking
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE,
    release: 'forge-marketplace@1.0.0',
    tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
    beforeSend(event) {
      if (import.meta.env.DEV && !import.meta.env.VITE_SENTRY_DEV) {
        return null;
      }
      return event;
    },
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
  });
}

// Error Boundary Component
interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    if (SENTRY_DSN) {
      Sentry.captureException(error, {
        extra: { componentStack: errorInfo.componentStack },
      });
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center p-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Something went wrong</h1>
            <p className="text-gray-600 mb-4">We're sorry, but something unexpected happened.</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Wrapper component to conditionally include GoogleOAuthProvider
const AppWithProviders = () => {
  const app = (
    <ErrorBoundary>
      <ThemeProvider>
        <Web3Provider>
          <QueryClientProvider client={queryClient}>
            <BrowserRouter>
              <AuthProvider>
                <CartProvider>
                  <App />
                </CartProvider>
              </AuthProvider>
            </BrowserRouter>
          </QueryClientProvider>
        </Web3Provider>
      </ThemeProvider>
    </ErrorBoundary>
  );

  // Wrap with GoogleOAuthProvider if configured
  if (GOOGLE_CLIENT_ID) {
    return (
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        {app}
      </GoogleOAuthProvider>
    );
  }

  return app;
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppWithProviders />
  </React.StrictMode>
);
