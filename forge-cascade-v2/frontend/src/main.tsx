/* eslint-disable react-refresh/only-export-components */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GoogleOAuthProvider } from '@react-oauth/google';
import * as Sentry from '@sentry/react';
import './index.css';
import App from './App';
import { ErrorBoundary } from './components/common';
import { ThemeProvider } from './contexts/ThemeContext';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

// Initialize Sentry for error tracking
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE,
    release: 'forge-cascade-frontend@2.0.0',
    // Sample rate for performance monitoring
    tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
    // Don't send PII
    beforeSend(event) {
      // Filter out development errors if needed
      if (import.meta.env.DEV && !import.meta.env.VITE_SENTRY_DEV) {
        return null;
      }
      return event;
    },
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    // Session replay sample rate
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Global error handler for uncaught errors
const handleGlobalError = (error: Error) => {
  console.error('Uncaught application error:', error);
  // Send to Sentry
  if (SENTRY_DSN) {
    Sentry.captureException(error);
  }
};

// App with all providers
const AppWithProviders = () => {
  const app = (
    <StrictMode>
      <ErrorBoundary onError={handleGlobalError}>
        <ThemeProvider>
          <QueryClientProvider client={queryClient}>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </QueryClientProvider>
        </ThemeProvider>
      </ErrorBoundary>
    </StrictMode>
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

createRoot(document.getElementById('root')!).render(<AppWithProviders />);
