import { WifiOff, LogIn, ServerCrash, AlertTriangle, RefreshCw, FileQuestion } from 'lucide-react';
import { Link } from 'react-router-dom';
import { classifyError } from '../../utils/apiErrors';
import type { ClassifiedError } from '../../utils/apiErrors';
import type { ComponentType } from 'react';

interface ApiErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  compact?: boolean;
}

interface ErrorConfig {
  icon: ComponentType<{ className?: string }>;
  iconColor: string;
  iconBg: string;
  title: string;
}

function getErrorConfig(classified: ClassifiedError): ErrorConfig {
  switch (classified.category) {
    case 'NETWORK':
      return {
        icon: WifiOff,
        iconColor: 'text-red-400',
        iconBg: 'bg-red-500/15',
        title: 'Connection Error',
      };
    case 'AUTH':
      return {
        icon: LogIn,
        iconColor: 'text-amber-400',
        iconBg: 'bg-amber-500/15',
        title: 'Authentication Required',
      };
    case 'SERVER':
      return {
        icon: ServerCrash,
        iconColor: 'text-red-400',
        iconBg: 'bg-red-500/15',
        title: 'Server Error',
      };
    case 'NOT_FOUND':
      return {
        icon: FileQuestion,
        iconColor: 'text-slate-400',
        iconBg: 'bg-white/5',
        title: 'Not Found',
      };
    default:
      return {
        icon: AlertTriangle,
        iconColor: 'text-amber-400',
        iconBg: 'bg-amber-500/15',
        title: 'Something Went Wrong',
      };
  }
}

export function ApiErrorState({ error, onRetry, title, compact = false }: ApiErrorStateProps) {
  const classified = classifyError(error);
  const config = getErrorConfig(classified);
  const Icon = config.icon;

  if (compact) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-lg bg-white/5 border border-white/10">
        <Icon className={`w-5 h-5 ${config.iconColor} flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-300">{title || config.title}</p>
          <p className="text-xs text-slate-500 mt-0.5">{classified.message}</p>
        </div>
        {classified.retryable && onRetry && (
          <button
            onClick={onRetry}
            className="text-forge-400 hover:text-forge-300 p-1.5 rounded-lg hover:bg-white/5 flex-shrink-0"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className={`w-16 h-16 rounded-2xl ${config.iconBg} flex items-center justify-center mb-4`}>
        <Icon className={`w-8 h-8 ${config.iconColor}`} />
      </div>
      <h3 className="text-lg font-semibold text-slate-100 mb-2">
        {title || config.title}
      </h3>
      <p className="text-slate-400 max-w-md mb-6">
        {classified.message}
      </p>
      <div className="flex gap-3">
        {classified.retryable && onRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-200 hover:bg-white/10 transition flex items-center gap-2 text-sm font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        )}
        {classified.category === 'AUTH' && (
          <Link
            to="/login"
            className="px-4 py-2 rounded-lg bg-forge-500 text-white hover:bg-forge-600 transition flex items-center gap-2 text-sm font-medium"
          >
            <LogIn className="w-4 h-4" />
            Sign In
          </Link>
        )}
      </div>
    </div>
  );
}
