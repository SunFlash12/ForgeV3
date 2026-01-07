import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Database,
  Vote,
  Ghost,
  Layers,
  Activity,
  Settings,
  LogOut,
  Shield,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useState } from 'react';
import { useAuthStore } from '../../stores/authStore';

interface NavItem {
  icon: React.ElementType;
  label: string;
  path: string;
  requiredTrust?: string[];
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Database, label: 'Capsules', path: '/capsules' },
  { icon: Vote, label: 'Governance', path: '/governance' },
  { icon: Ghost, label: 'Ghost Council', path: '/ghost-council' },
  { icon: Layers, label: 'Overlays', path: '/overlays', requiredTrust: ['TRUSTED', 'CORE'] },
  { icon: Activity, label: 'System', path: '/system', requiredTrust: ['TRUSTED', 'CORE'] },
];

const bottomNavItems: NavItem[] = [
  { icon: Settings, label: 'Settings', path: '/settings' },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuthStore();

  const canAccess = (item: NavItem) => {
    if (!item.requiredTrust) return true;
    if (!user) return false;
    return item.requiredTrust.includes(user.trust_level);
  };

  const getTrustBadgeClass = () => {
    switch (user?.trust_level) {
      case 'QUARANTINE': return 'badge-trust-untrusted';
      case 'SANDBOX': return 'badge-trust-sandbox';
      case 'STANDARD': return 'badge-trust-standard';
      case 'TRUSTED': return 'badge-trust-trusted';
      case 'CORE': return 'badge-trust-core';
      default: return 'badge-trust-sandbox';
    }
  };

  return (
    <aside
      className={`flex flex-col bg-white border-r border-slate-200 transition-all duration-300 ${
        collapsed ? 'w-[72px]' : 'w-64'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center justify-between p-4 border-b border-slate-100">
        {!collapsed && (
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500 flex items-center justify-center shadow-lg shadow-sky-500/20">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl text-gradient">FORGE</span>
          </div>
        )}
        {collapsed && (
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500 flex items-center justify-center shadow-lg shadow-sky-500/20 mx-auto">
            <Shield className="w-5 h-5 text-white" />
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors ${collapsed ? 'hidden' : ''}`}
        >
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* User Info */}
      {user && (
        <div className={`p-4 border-b border-slate-100 ${collapsed ? 'hidden' : ''}`}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-sky-500 to-violet-500 flex items-center justify-center text-white font-semibold shadow-md">
              {user.display_name?.[0] || user.username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 truncate">
                {user.display_name || user.username}
              </p>
              <span className={`${getTrustBadgeClass()} badge-sm mt-1`}>
                {user.trust_level}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Expand button when collapsed */}
      {collapsed && (
        <div className="p-3 border-b border-slate-100">
          <button
            onClick={() => setCollapsed(false)}
            className="w-full p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors flex justify-center"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.filter(canAccess).map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 ${
                isActive
                  ? 'bg-sky-50 text-sky-600 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              } ${collapsed ? 'justify-center px-2' : ''}`
            }
            title={collapsed ? item.label : undefined}
          >
            <item.icon size={20} />
            {!collapsed && <span className="text-sm">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Bottom Navigation */}
      <div className="p-3 border-t border-slate-100 space-y-1">
        {bottomNavItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 ${
                isActive
                  ? 'bg-sky-50 text-sky-600 font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              } ${collapsed ? 'justify-center px-2' : ''}`
            }
            title={collapsed ? item.label : undefined}
          >
            <item.icon size={20} />
            {!collapsed && <span className="text-sm">{item.label}</span>}
          </NavLink>
        ))}
        
        <button
          onClick={() => logout()}
          className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-slate-500 hover:text-red-600 hover:bg-red-50 transition-all duration-200 w-full ${
            collapsed ? 'justify-center px-2' : ''
          }`}
          title={collapsed ? 'Logout' : undefined}
        >
          <LogOut size={20} />
          {!collapsed && <span className="text-sm">Logout</span>}
        </button>
      </div>
    </aside>
  );
}
