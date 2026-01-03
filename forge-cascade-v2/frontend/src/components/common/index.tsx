import React from 'react';
import { Loader2, TrendingUp, TrendingDown } from 'lucide-react';
import type { TrustLevel, HealthStatus, AnomalySeverity } from '../../types';

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
// Trust Badge Component
// ============================================================================

interface TrustBadgeProps {
  level: TrustLevel;
  score?: number;
  showScore?: boolean;
}

export function TrustBadge({ level, score, showScore = false }: TrustBadgeProps) {
  const badgeClass = {
    UNTRUSTED: 'badge-trust-untrusted',
    SANDBOX: 'badge-trust-sandbox',
    STANDARD: 'badge-trust-standard',
    TRUSTED: 'badge-trust-trusted',
    CORE: 'badge-trust-core',
  }[level];

  return (
    <span className={`badge ${badgeClass}`}>
      {level}
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
    HIGH: 'bg-orange-50 text-orange-600 border border-orange-200',
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
    sky: 'bg-sky-500',
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
      <div className={`w-full bg-slate-100 rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`${colorClasses[color]} ${sizeClasses[size]} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <div className="mt-1.5 text-xs text-slate-500 text-right font-medium">
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
        <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4 text-slate-400">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold text-slate-800 mb-2">{title}</h3>
      {description && (
        <p className="text-slate-500 max-w-md mb-6">{description}</p>
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
      <div className={`${sizeClasses[size]} border-sky-500 border-t-transparent rounded-full animate-spin`} />
      {label && <p className="text-slate-500 text-sm font-medium">{label}</p>}
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
    success: 'border-emerald-200 bg-emerald-50/50',
    warning: 'border-amber-200 bg-amber-50/50',
    danger: 'border-red-200 bg-red-50/50',
  };

  const iconBgClasses = {
    default: 'bg-slate-100 text-slate-500',
    success: 'bg-emerald-100 text-emerald-600',
    warning: 'bg-amber-100 text-amber-600',
    danger: 'bg-red-100 text-red-600',
  };

  return (
    <div className={`card ${colorClasses[color]}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500 mb-1">{label}</p>
          <p className="text-2xl font-bold text-slate-800">{value}</p>
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
  if (!isOpen) return null;

  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-2xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className={`relative ${sizeClasses[size]} w-full bg-white rounded-2xl shadow-2xl animate-scale-in`}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-100 bg-slate-50 rounded-b-2xl">
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
