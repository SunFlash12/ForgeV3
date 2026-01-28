import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Search, Bell, AlertCircle, CheckCircle, AlertTriangle, RefreshCw, X, ExternalLink, Trash2, ShoppingCart, Menu } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import api from '../../api/client';
import { useCartStore } from '../../stores/cartStore';

interface HeaderProps {
  onOpenMobileSidebar: () => void;
  isPhone: boolean;
}

export function Header({ onOpenMobileSidebar, isPhone }: HeaderProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);
  const notificationRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const cartItemCount = useCartStore((s) => s.itemCount);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.getSystemHealth(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: anomalies } = useQuery({
    queryKey: ['active-anomalies'],
    queryFn: () => api.getAnomalies({ resolved: false }),
    refetchInterval: 60000,
  });

  // Fetch notifications
  const { data: notificationsData, refetch: refetchNotifications } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.getNotifications({ limit: 10 }),
    refetchInterval: 30000,
  });

  // Mark notification as read
  const markReadMutation = useMutation({
    mutationFn: (id: string) => api.markNotificationRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  // Delete notification
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteNotification(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const notifications = notificationsData?.notifications || [];
  const unreadCount = notificationsData?.unread_count || 0;
  const unresolvedCount = anomalies?.length || 0;
  const totalBadgeCount = unreadCount + unresolvedCount;

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'CRITICAL': return 'bg-red-500/10 text-red-400 border-red-500/30';
      case 'HIGH': return 'bg-orange-500/10 text-orange-400 border-orange-500/30';
      case 'MEDIUM': return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      default: return 'bg-white/5 text-slate-400 border-white/10';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'CAPSULE_CREATED':
      case 'CAPSULE_UPDATED':
        return '📦';
      case 'PROPOSAL_SUBMITTED':
      case 'VOTE_CAST':
        return '🗳️';
      case 'ANOMALY_DETECTED':
        return '⚠️';
      case 'TRUST_CHANGED':
        return '⬆️';
      default:
        return '🔔';
    }
  };

  const getStatusIcon = () => {
    if (healthLoading) {
      return <RefreshCw className="w-4 h-4 text-slate-400 animate-spin" />;
    }
    switch (health?.status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case 'degraded':
        return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      case 'unhealthy':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <AlertCircle className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusText = () => {
    if (healthLoading) return 'Checking...';
    switch (health?.status) {
      case 'healthy': return 'All Systems Operational';
      case 'degraded': return 'Degraded Performance';
      case 'unhealthy': return 'System Issues Detected';
      default: return 'Status Unknown';
    }
  };

  const getStatusBg = () => {
    switch (health?.status) {
      case 'healthy': return 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400';
      case 'degraded': return 'bg-amber-500/15 border-amber-500/30 text-amber-400';
      case 'unhealthy': return 'bg-red-500/15 border-red-500/30 text-red-400';
      default: return 'bg-white/5 border-white/10 text-slate-400';
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Navigate to search results
      window.location.href = `/capsules?search=${encodeURIComponent(searchQuery)}`;
    }
  };

  return (
    <header className="h-14 sm:h-16 border-b border-white/10 bg-surface-800/60 backdrop-blur-md px-3 sm:px-4 lg:px-6 flex items-center justify-between gap-2 sm:gap-4">
      {/* Hamburger (phone only) */}
      {isPhone && (
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          className="p-2.5 rounded-xl hover:bg-white/5 text-slate-400 transition-colors focus:outline-none focus:ring-2 focus:ring-forge-500 shrink-0"
          aria-label="Open navigation menu"
        >
          <Menu className="w-6 h-6" aria-hidden="true" />
        </button>
      )}

      {/* Search */}
      <form onSubmit={handleSearch} className="flex-1 max-w-xl min-w-0" role="search">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" aria-hidden="true" />
          <input
            type="search"
            placeholder={isPhone ? 'Search...' : 'Search capsules, governance, or system...'}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search capsules, governance, or system"
            className="w-full pl-10 pr-4 py-2 sm:py-2.5 bg-white/5 border border-white/10 rounded-xl text-slate-200 placeholder-slate-500 focus:outline-none focus:border-forge-400 focus:ring-2 focus:ring-forge-500/20 transition-all text-sm sm:text-base"
          />
        </div>
      </form>

      {/* Status & Notifications */}
      <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
        {/* Cart */}
        <button
          type="button"
          onClick={() => navigate('/marketplace/cart')}
          className="relative p-3 sm:p-2.5 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/10 focus:outline-none focus:ring-2 focus:ring-forge-500 focus:ring-offset-2"
          aria-label={cartItemCount > 0 ? `Shopping cart: ${cartItemCount} items` : 'Shopping cart: empty'}
        >
          <ShoppingCart className="w-5 h-5 text-slate-400" aria-hidden="true" />
          {cartItemCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-cyber-blue rounded-full text-xs text-surface-900 flex items-center justify-center font-bold shadow-lg shadow-cyan-500/30" aria-hidden="true">
              {cartItemCount > 9 ? '9+' : cartItemCount}
            </span>
          )}
        </button>

        {/* System Status */}
        <button
          type="button"
          onClick={() => refetchHealth()}
          className={`flex items-center gap-2 p-2.5 sm:px-4 sm:py-2 rounded-xl border transition-all hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-forge-500 focus:ring-offset-2 ${getStatusBg()}`}
          aria-label={`System status: ${getStatusText()}. Click to refresh`}
        >
          {getStatusIcon()}
          <span className="text-sm font-medium hidden sm:inline">{getStatusText()}</span>
        </button>

        {/* Notifications */}
        <div className="relative" ref={notificationRef}>
          <button
            type="button"
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-3 sm:p-2.5 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/10 focus:outline-none focus:ring-2 focus:ring-forge-500 focus:ring-offset-2"
            aria-label={totalBadgeCount > 0 ? `Notifications: ${totalBadgeCount} unread` : 'Notifications: No new alerts'}
            aria-expanded={showNotifications}
          >
            <Bell className="w-5 h-5 text-slate-400" aria-hidden="true" />
            {totalBadgeCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs text-white flex items-center justify-center font-semibold shadow-lg shadow-red-500/30" aria-hidden="true">
                {totalBadgeCount > 9 ? '9+' : totalBadgeCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 top-full mt-2 w-[min(24rem,calc(100vw-2rem))] bg-surface-800 rounded-xl shadow-2xl border border-white/10 backdrop-blur-md overflow-hidden z-50">
              {/* Header */}
              <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between bg-surface-700">
                <h3 className="font-semibold text-slate-100">Notifications</h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => refetchNotifications()}
                    className="p-1.5 hover:bg-white/5 rounded-lg transition-colors"
                    title="Refresh"
                  >
                    <RefreshCw className="w-4 h-4 text-slate-400" />
                  </button>
                  <button
                    onClick={() => setShowNotifications(false)}
                    className="p-1.5 hover:bg-white/5 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4 text-slate-400" />
                  </button>
                </div>
              </div>

              {/* Notification List */}
              <div className="max-h-96 overflow-y-auto">
                {/* Anomalies Section */}
                {unresolvedCount > 0 && (
                  <div className="p-3 bg-red-500/10 border-b border-red-500/20">
                    <a
                      href="/system"
                      className="flex items-center gap-3 text-red-400 hover:text-red-300"
                      onClick={() => setShowNotifications(false)}
                    >
                      <AlertCircle className="w-5 h-5" />
                      <div>
                        <div className="font-medium">{unresolvedCount} Active Anomalies</div>
                        <div className="text-xs text-red-400">Click to view in System Monitor</div>
                      </div>
                      <ExternalLink className="w-4 h-4 ml-auto" />
                    </a>
                  </div>
                )}

                {/* Notifications */}
                {notifications.length === 0 && unresolvedCount === 0 ? (
                  <div className="p-8 text-center">
                    <Bell className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                    <p className="text-slate-400 text-sm">No notifications</p>
                  </div>
                ) : (
                  notifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`px-4 py-3 border-b border-white/10 hover:bg-white/5 transition-colors ${
                        !notification.read ? 'bg-forge-500/10' : ''
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-lg">{getTypeIcon(notification.type)}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-slate-100 text-sm truncate">
                              {notification.title}
                            </span>
                            {!notification.read && (
                              <span className="w-2 h-2 bg-forge-500 rounded-full flex-shrink-0" />
                            )}
                          </div>
                          <p className="text-sm text-slate-400 line-clamp-2">{notification.message}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${getPriorityColor(notification.priority)}`}>
                              {notification.priority}
                            </span>
                            <span className="text-xs text-slate-500">
                              {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                            </span>
                          </div>
                        </div>
                        <div className="flex flex-col gap-1">
                          {!notification.read && (
                            <button
                              onClick={() => markReadMutation.mutate(notification.id)}
                              className="p-1 hover:bg-white/5 rounded transition-colors"
                              title="Mark as read"
                            >
                              <CheckCircle className="w-4 h-4 text-slate-500" />
                            </button>
                          )}
                          <button
                            onClick={() => deleteMutation.mutate(notification.id)}
                            className="p-1 hover:bg-red-500/10 rounded transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4 text-slate-500 hover:text-red-400" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Footer */}
              {notifications.length > 0 && (
                <div className="px-4 py-2 border-t border-white/10 bg-surface-700">
                  <a
                    href="/settings?tab=notifications"
                    className="text-sm text-cyber-blue hover:text-cyan-300 font-medium"
                    onClick={() => setShowNotifications(false)}
                  >
                    Manage notification preferences
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
