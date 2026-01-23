import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Search, Bell, AlertCircle, CheckCircle, AlertTriangle, RefreshCw, X, ExternalLink, Trash2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import api from '../../api/client';

export function Header() {
  const [searchQuery, setSearchQuery] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);
  const notificationRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

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
      case 'CRITICAL': return 'bg-red-100 text-red-700 border-red-200';
      case 'HIGH': return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'MEDIUM': return 'bg-amber-100 text-amber-700 border-amber-200';
      default: return 'bg-slate-100 text-slate-600 border-slate-200';
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
      case 'healthy': return 'bg-emerald-50 border-emerald-200 text-emerald-700';
      case 'degraded': return 'bg-amber-50 border-amber-200 text-amber-700';
      case 'unhealthy': return 'bg-red-50 border-red-200 text-red-700';
      default: return 'bg-slate-50 border-slate-200 text-slate-600';
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
    <header className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur-sm px-6 flex items-center justify-between">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex-1 max-w-xl" role="search">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search capsules, governance, or system..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search capsules, governance, or system"
            className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 placeholder-slate-400 focus:outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 transition-all"
          />
        </div>
      </form>

      {/* Status & Notifications */}
      <div className="flex items-center gap-3">
        {/* System Status */}
        <button
          type="button"
          onClick={() => refetchHealth()}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl border transition-all hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 ${getStatusBg()}`}
          aria-label={`System status: ${getStatusText()}. Click to refresh`}
        >
          {getStatusIcon()}
          <span className="text-sm font-medium">{getStatusText()}</span>
        </button>

        {/* Notifications */}
        <div className="relative" ref={notificationRef}>
          <button
            type="button"
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-2.5 rounded-xl hover:bg-slate-100 transition-colors border border-transparent hover:border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
            aria-label={totalBadgeCount > 0 ? `Notifications: ${totalBadgeCount} unread` : 'Notifications: No new alerts'}
            aria-expanded={showNotifications}
          >
            <Bell className="w-5 h-5 text-slate-500" aria-hidden="true" />
            {totalBadgeCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs text-white flex items-center justify-center font-semibold shadow-lg shadow-red-500/30" aria-hidden="true">
                {totalBadgeCount > 9 ? '9+' : totalBadgeCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 top-full mt-2 w-96 bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden z-50">
              {/* Header */}
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50">
                <h3 className="font-semibold text-slate-800">Notifications</h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => refetchNotifications()}
                    className="p-1.5 hover:bg-slate-200 rounded-lg transition-colors"
                    title="Refresh"
                  >
                    <RefreshCw className="w-4 h-4 text-slate-500" />
                  </button>
                  <button
                    onClick={() => setShowNotifications(false)}
                    className="p-1.5 hover:bg-slate-200 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4 text-slate-500" />
                  </button>
                </div>
              </div>

              {/* Notification List */}
              <div className="max-h-96 overflow-y-auto">
                {/* Anomalies Section */}
                {unresolvedCount > 0 && (
                  <div className="p-3 bg-red-50 border-b border-red-100">
                    <a
                      href="/system"
                      className="flex items-center gap-3 text-red-700 hover:text-red-800"
                      onClick={() => setShowNotifications(false)}
                    >
                      <AlertCircle className="w-5 h-5" />
                      <div>
                        <div className="font-medium">{unresolvedCount} Active Anomalies</div>
                        <div className="text-xs text-red-600">Click to view in System Monitor</div>
                      </div>
                      <ExternalLink className="w-4 h-4 ml-auto" />
                    </a>
                  </div>
                )}

                {/* Notifications */}
                {notifications.length === 0 && unresolvedCount === 0 ? (
                  <div className="p-8 text-center">
                    <Bell className="w-10 h-10 text-slate-200 mx-auto mb-2" />
                    <p className="text-slate-400 text-sm">No notifications</p>
                  </div>
                ) : (
                  notifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition-colors ${
                        !notification.read ? 'bg-sky-50/50' : ''
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-lg">{getTypeIcon(notification.type)}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-slate-800 text-sm truncate">
                              {notification.title}
                            </span>
                            {!notification.read && (
                              <span className="w-2 h-2 bg-sky-500 rounded-full flex-shrink-0" />
                            )}
                          </div>
                          <p className="text-sm text-slate-500 line-clamp-2">{notification.message}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${getPriorityColor(notification.priority)}`}>
                              {notification.priority}
                            </span>
                            <span className="text-xs text-slate-400">
                              {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                            </span>
                          </div>
                        </div>
                        <div className="flex flex-col gap-1">
                          {!notification.read && (
                            <button
                              onClick={() => markReadMutation.mutate(notification.id)}
                              className="p-1 hover:bg-slate-200 rounded transition-colors"
                              title="Mark as read"
                            >
                              <CheckCircle className="w-4 h-4 text-slate-400" />
                            </button>
                          )}
                          <button
                            onClick={() => deleteMutation.mutate(notification.id)}
                            className="p-1 hover:bg-red-100 rounded transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4 text-slate-400 hover:text-red-500" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Footer */}
              {notifications.length > 0 && (
                <div className="px-4 py-2 border-t border-slate-100 bg-slate-50">
                  <a
                    href="/settings?tab=notifications"
                    className="text-sm text-sky-600 hover:text-sky-700 font-medium"
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
