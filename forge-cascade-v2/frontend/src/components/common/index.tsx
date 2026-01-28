import React, { Component, useEffect, useRef, useCallback } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { Loader2, TrendingUp, TrendingDown, AlertTriangle, RefreshCw } from 'lucide-react';
import type { TrustLevel, HealthStatus, AnomalySeverity } from '../../types';


// ============================================================================
// Error Boundary Component
// ============================================================================

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log the error to console in development
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // Call the onError callback if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="min-h-[400px] flex items-center justify-center p-8">
          <div className="max-w-md w-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-red-500/15 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-xl font-semibold text-slate-100 mb-2">
              Something went wrong
            </h2>
            <p className="text-slate-400 mb-6">
              An unexpected error occurred. Please try again or refresh the page.
            </p>
            {this.state.error && (
              <details className="mb-6 text-left p-4 bg-white/5 rounded-lg">
                <summary className="cursor-pointer text-sm font-medium text-slate-300 mb-2">
                  Error details
                </summary>
                <pre className="text-xs text-red-400 overflow-auto whitespace-pre-wrap">
                  {this.state.error.message}
                </pre>
              </details>
            )}
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="btn btn-secondary"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Try Again
              </button>
              <button
                onClick={() => window.location.reload()}
                className="btn btn-primary"
              >
                Refresh Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// ============================================================================
// Card Component
// ============================================================================

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
  accent?: boolean;
}

export function Card({ children, className = '', hover = false, onClick, accent = false }: CardProps) {
  const baseClass = hover ? 'card-hover' : accent ? 'card-accent' : 'card';
  return (
    <div className={`${baseClass} ${className}`} onClick={onClick}>
      {children}
    </div>
  );
}

// ============================================================================
// Button Component
// ============================================================================

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  const variantClasses = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    ghost: 'btn-ghost',
    danger: 'btn-danger',
    success: 'btn-success',
    outline: 'btn-outline',
  };

  const sizeClasses = {
    sm: 'btn-sm',
    md: '',
    lg: 'btn-lg',
  };

  return (
    <button
      className={`btn ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

// ============================================================================
// Generic Badge Component
// ============================================================================

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'secondary';
  className?: string;
  style?: React.CSSProperties;
}

export function Badge({ children, variant = 'default', className = '', style }: BadgeProps) {
  const variantClasses = {
    default: 'bg-white/5 text-slate-300 border border-white/10',
    success: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
    danger: 'bg-red-500/15 text-red-400 border border-red-500/30',
    info: 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30',
    secondary: 'bg-violet-500/15 text-violet-400 border border-violet-500/30',
  };

  return (
    <span className={`badge ${variantClasses[variant]} ${className}`} style={style}>
      {children}
    </span>
  );
}

// ============================================================================
// Trust Badge Component
// ============================================================================

interface TrustBadgeProps {
  level: TrustLevel | string;  // Accept string for backend enum names
  score?: number;
  showScore?: boolean;
}

export function TrustBadge({ level, score, showScore = false }: TrustBadgeProps) {
  // Normalize level string and handle both QUARANTINE and legacy UNTRUSTED
  const normalizedLevel = String(level).toUpperCase();

  const badgeClasses: Record<string, string> = {
    QUARANTINE: 'badge-trust-untrusted',  // QUARANTINE uses untrusted styling
    UNTRUSTED: 'badge-trust-untrusted',   // Legacy support
    SANDBOX: 'badge-trust-sandbox',
    STANDARD: 'badge-trust-standard',
    TRUSTED: 'badge-trust-trusted',
    CORE: 'badge-trust-core',
  };

  const badgeClass = badgeClasses[normalizedLevel] || 'badge-trust-sandbox';

  // Display user-friendly name (QUARANTINE shows as "QUARANTINE")
  const displayName = normalizedLevel;

  return (
    <span className={`badge ${badgeClass}`}>
      {displayName}
      {showScore && score !== undefined && (
        <span className="ml-1.5 opacity-70">({score})</span>
      )}
    </span>
  );
}

// ============================================================================
// Status Badge Component
// ============================================================================

interface StatusBadgeProps {
  status: HealthStatus;
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const statusConfig = {
    healthy: {
      dot: 'status-healthy',
      badge: 'badge-success',
    },
    degraded: {
      dot: 'status-degraded',
      badge: 'badge-warning',
    },
    unhealthy: {
      dot: 'status-unhealthy',
      badge: 'badge-danger',
    },
  };

  const config = statusConfig[status];

  return (
    <span className={`badge ${config.badge}`}>
      <span className={`status-dot ${config.dot}`} />
      <span className="ml-2">{label || status}</span>
    </span>
  );
}

// ============================================================================
// Severity Badge Component
// ============================================================================

interface SeverityBadgeProps {
  severity: AnomalySeverity;
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const severityConfig = {
    LOW: 'badge-info',
    MEDIUM: 'badge-warning',
    HIGH: 'bg-orange-500/15 text-orange-400 border border-orange-500/30',
    CRITICAL: 'badge-danger',
  };

  return (
    <span className={`badge ${severityConfig[severity]}`}>
      {severity}
    </span>
  );
}

// ============================================================================
// Progress Bar Component
// ============================================================================

interface ProgressBarProps {
  value: number;
  max?: number;
  color?: 'sky' | 'violet' | 'emerald' | 'amber' | 'red';
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export function ProgressBar({
  value,
  max = 100,
  color = 'sky',
  size = 'md',
  showLabel = false,
}: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const colorClasses = {
    sky: 'bg-forge-500',
    violet: 'bg-violet-500',
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  };

  const sizeClasses = {
    sm: 'h-1.5',
    md: 'h-2',
    lg: 'h-3',
  };

  return (
    <div className="w-full">
      <div className={`w-full bg-white/10 rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`${colorClasses[color]} ${sizeClasses[size]} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <div className="mt-1.5 text-xs text-slate-400 text-right font-medium">
          {value} / {max} ({percentage.toFixed(1)}%)
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Empty State Component
// ============================================================================

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      {icon && (
        <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4 text-slate-400">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold text-slate-100 mb-2">{title}</h3>
      {description && (
        <p className="text-slate-400 max-w-md mb-6">{description}</p>
      )}
      {action}
    </div>
  );
}

// ============================================================================
// Loading Spinner Component
// ============================================================================

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

export function LoadingSpinner({ size = 'md', label }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-5 h-5 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div className={`${sizeClasses[size]} border-forge-500 border-t-transparent rounded-full animate-spin`} />
      {label && <p className="text-slate-400 text-sm font-medium">{label}</p>}
    </div>
  );
}

// ============================================================================
// Stat Card Component
// ============================================================================

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: { value: number; isPositive: boolean };
  color?: 'default' | 'success' | 'warning' | 'danger';
}

export function StatCard({ label, value, icon, trend, color = 'default' }: StatCardProps) {
  const colorClasses = {
    default: '',
    success: 'border-emerald-500/30 bg-emerald-500/10',
    warning: 'border-amber-500/30 bg-amber-500/10',
    danger: 'border-red-500/30 bg-red-500/10',
  };

  const iconBgClasses = {
    default: 'bg-white/5 text-slate-400',
    success: 'bg-emerald-500/10 text-emerald-400',
    warning: 'bg-amber-500/10 text-amber-400',
    danger: 'bg-red-500/10 text-red-400',
  };

  return (
    <div className={`card ${colorClasses[color]}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-400 mb-1">{label}</p>
          <p className="text-2xl font-bold text-slate-100">{value}</p>
          {trend && (
            <div className={`flex items-center gap-1 mt-2 text-sm font-medium ${trend.isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
              {trend.isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              <span>{Math.abs(trend.value)}%</span>
            </div>
          )}
        </div>
        {icon && (
          <div className={`p-3 rounded-xl ${iconBgClasses[color]}`}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Modal Component
// ============================================================================

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export function Modal({ isOpen, onClose, title, children, footer, size = 'md' }: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Handle Escape key to close modal
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  }, [onClose]);

  // Focus trap and keyboard handling
  useEffect(() => {
    if (!isOpen) return;

    // Add escape key listener
    document.addEventListener('keydown', handleKeyDown);

    // Focus the close button when modal opens
    closeButtonRef.current?.focus();

    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  const sizeClasses = {
    sm: 'max-w-[calc(100vw-1rem)] sm:max-w-sm',
    md: 'max-w-[calc(100vw-1rem)] sm:max-w-md',
    lg: 'max-w-[calc(100vw-1rem)] sm:max-w-lg',
    xl: 'max-w-[calc(100vw-1rem)] sm:max-w-2xl',
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className={`relative ${sizeClasses[size]} w-full bg-surface-800 rounded-2xl shadow-2xl border border-white/10 animate-scale-in max-h-[95vh] sm:max-h-[90vh] overflow-y-auto`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-white/10 sticky top-0 bg-surface-800 rounded-t-2xl">
          <h2 id="modal-title" className="text-base sm:text-lg font-semibold text-slate-100">{title}</h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-white/5 text-slate-400 hover:text-slate-200 transition-colors focus:outline-none focus:ring-2 focus:ring-forge-500"
            aria-label="Close dialog"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-4 sm:px-6 py-4 sm:py-5">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-4 sm:px-6 py-3 sm:py-4 border-t border-white/10 bg-surface-700 rounded-b-2xl sticky bottom-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Input Component
// ============================================================================

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helpText?: string;
}

export function Input({ label, error, helpText, className = '', ...props }: InputProps) {
  return (
    <div className="w-full">
      {label && (
        <label className={`label ${props.required ? 'label-required' : ''}`}>
          {label}
        </label>
      )}
      <input
        className={`input ${error ? 'input-error' : ''} ${className}`}
        {...props}
      />
      {helpText && !error && <p className="help-text">{helpText}</p>}
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

// ============================================================================
// Select Component
// ============================================================================

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string }[];
}

export function Select({ label, error, options, className = '', ...props }: SelectProps) {
  return (
    <div className="w-full">
      {label && (
        <label className={`label ${props.required ? 'label-required' : ''}`}>
          {label}
        </label>
      )}
      <select
        className={`input ${error ? 'input-error' : ''} ${className}`}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

// ============================================================================
// Textarea Component
// ============================================================================

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helpText?: string;
}

export function Textarea({ label, error, helpText, className = '', ...props }: TextareaProps) {
  return (
    <div className="w-full">
      {label && (
        <label className={`label ${props.required ? 'label-required' : ''}`}>
          {label}
        </label>
      )}
      <textarea
        className={`input ${error ? 'input-error' : ''} ${className}`}
        {...props}
      />
      {helpText && !error && <p className="help-text">{helpText}</p>}
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

// ============================================================================
// Skeleton Component
// ============================================================================

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
}

export function Skeleton({ className = '', variant = 'text', width, height }: SkeletonProps) {
  const variantClasses = {
    text: 'h-4 rounded',
    circular: 'rounded-full',
    rectangular: 'rounded-xl',
  };

  return (
    <div
      className={`skeleton ${variantClasses[variant]} ${className}`}
      style={{ width, height }}
    />
  );
}

// Re-export Logo component
export { Logo, LogoIcon } from './Logo';
export { NetworkBackground } from './NetworkBackground';
export { ConnectionBanner } from './ConnectionBanner';
export { ApiErrorState } from './ApiErrorState';
