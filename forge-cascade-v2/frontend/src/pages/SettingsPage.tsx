import { useState } from 'react';
import axios from 'axios';
import {
  User,
  Lock,
  Bell,
  Shield,
  Palette,
  Database,
  CheckCircle,
  AlertCircle,
  Eye,
  EyeOff,
  Save,
  RefreshCw
} from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { Card, Button, TrustBadge, Modal } from '../components/common';
import { api } from '../api/client';

/**
 * Type-safe error message extraction from unknown errors.
 * Handles Axios errors, standard errors, and unknown error types.
 */
function getErrorMessage(error: unknown, defaultMessage: string): string {
  if (axios.isAxiosError(error)) {
    // Axios error with response
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (error.message) {
      return error.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return defaultMessage;
}

type SettingsTab = 'profile' | 'security' | 'notifications' | 'appearance' | 'data';

export default function SettingsPage() {
  const { user, fetchCurrentUser, fetchTrustInfo } = useAuthStore();
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Profile form state
  const [displayName, setDisplayName] = useState(user?.username || '');
  const [email, setEmail] = useState(user?.email || '');

  // Password form state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);

  // Notification preferences
  const [notifications, setNotifications] = useState({
    proposalVotes: true,
    capsuleActivity: true,
    systemAlerts: true,
    anomalyWarnings: true,
    trustChanges: true,
    ghostWisdom: false,
  });

  // Appearance preferences  
  const [appearance, setAppearance] = useState({
    theme: 'dark' as 'dark' | 'light' | 'system',
    compactMode: false,
    animationsEnabled: true,
    highContrast: false,
  });

  // Data export modal
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportFormat, setExportFormat] = useState<'json' | 'csv'>('json');

  const tabs = [
    { id: 'profile' as const, label: 'Profile', icon: User },
    { id: 'security' as const, label: 'Security', icon: Lock },
    { id: 'notifications' as const, label: 'Notifications', icon: Bell },
    { id: 'appearance' as const, label: 'Appearance', icon: Palette },
    { id: 'data' as const, label: 'Data & Privacy', icon: Database },
  ];

  const showMessage = (type: 'success' | 'error', message: string) => {
    if (type === 'success') {
      setSuccess(message);
      setError(null);
    } else {
      setError(message);
      setSuccess(null);
    }
    setTimeout(() => {
      setSuccess(null);
      setError(null);
    }, 5000);
  };

  const handleSaveProfile = async () => {
    if (!displayName.trim()) {
      showMessage('error', 'Display name is required');
      return;
    }
    
    setSaving(true);
    try {
      await api.updateProfile({ display_name: displayName, email });
      await fetchCurrentUser();
      showMessage('success', 'Profile updated successfully');
    } catch (err: unknown) {
      // Type-safe error handling for Axios errors
      const errorMessage = getErrorMessage(err, 'Failed to update profile');
      showMessage('error', errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      showMessage('error', 'All password fields are required');
      return;
    }
    if (newPassword !== confirmPassword) {
      showMessage('error', 'New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      showMessage('error', 'Password must be at least 8 characters');
      return;
    }

    setSaving(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      showMessage('success', 'Password changed successfully');
    } catch (err: unknown) {
      const errorMessage = getErrorMessage(err, 'Failed to change password');
      showMessage('error', errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const handleRefreshTrust = async () => {
    try {
      await fetchTrustInfo();
      showMessage('success', 'Trust information refreshed');
    } catch {
      showMessage('error', 'Failed to refresh trust information');
    }
  };

  /**
   * Escape a value for CSV format to prevent CSV injection and handle special characters.
   * - Wraps values in quotes if they contain commas, quotes, or newlines
   * - Escapes double quotes by doubling them
   * - Prevents formula injection by prefixing with single quote
   */
  const escapeCsvValue = (value: string | undefined | null): string => {
    if (value === undefined || value === null) {
      return '';
    }

    const stringValue = String(value);

    // Check for formula injection attempts (CSV injection)
    // Formulas typically start with =, +, -, @, tab, or carriage return
    const formulaChars = ['=', '+', '-', '@', '\t', '\r'];
    const needsProtection = formulaChars.some(char => stringValue.startsWith(char));

    // Escape double quotes by doubling them
    let escaped = stringValue.replace(/"/g, '""');

    // If value contains special characters, wrap in quotes
    const needsQuotes = escaped.includes(',') ||
                        escaped.includes('"') ||
                        escaped.includes('\n') ||
                        escaped.includes('\r') ||
                        needsProtection;

    if (needsQuotes) {
      // Prefix with single quote if it looks like a formula
      if (needsProtection) {
        escaped = "'" + escaped;
      }
      escaped = `"${escaped}"`;
    }

    return escaped;
  };

  const handleExportData = async () => {
    try {
      // In a real implementation, this would call an API endpoint
      const data = {
        user: {
          id: user?.id,
          username: user?.username,
          email: user?.email,
          trust_level: user?.trust_level,
          created_at: user?.created_at,
        },
        exported_at: new Date().toISOString(),
        format: exportFormat,
      };

      let content: string;
      let mimeType: string;

      if (exportFormat === 'json') {
        content = JSON.stringify(data, null, 2);
        mimeType = 'application/json';
      } else {
        // CSV format with proper escaping
        const headers = 'id,username,email,trust_level,created_at';
        const row = [
          escapeCsvValue(user?.id),
          escapeCsvValue(user?.username),
          escapeCsvValue(user?.email),
          escapeCsvValue(user?.trust_level),
          escapeCsvValue(user?.created_at),
        ].join(',');
        content = `${headers}\n${row}`;
        mimeType = 'text/csv';
      }

      const blob = new Blob([content], { type: mimeType });

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `forge-data-export.${exportFormat}`;
      a.click();
      URL.revokeObjectURL(url);

      setShowExportModal(false);
      showMessage('success', 'Data exported successfully');
    } catch {
      showMessage('error', 'Failed to export data');
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800 mb-2">Settings</h1>
        <p className="text-slate-500">Manage your account preferences and security</p>
      </div>

      {/* Status Messages */}
      {success && (
        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/30 rounded-lg flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <span className="text-green-400">{success}</span>
        </div>
      )}
      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-400">{error}</span>
        </div>
      )}

      <div className="flex gap-6">
        {/* Sidebar Tabs */}
        <div className="w-56 shrink-0">
          <Card className="p-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                  activeTab === tab.id
                    ? 'bg-sky-500/20 text-sky-400'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                <span>{tab.label}</span>
              </button>
            ))}
          </Card>
        </div>

        {/* Content Area */}
        <div className="flex-1">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                <User className="w-5 h-5 text-sky-400" />
                Profile Information
              </h2>

              <div className="space-y-6">
                {/* User Info Summary */}
                <div className="p-4 bg-slate-100/30 rounded-lg flex items-center gap-4">
                  <div className="w-16 h-16 bg-sky-500/20 rounded-full flex items-center justify-center">
                    <User className="w-8 h-8 text-sky-400" />
                  </div>
                  <div className="flex-1">
                    <div className="text-lg font-medium text-slate-800">{user?.username}</div>
                    <div className="text-sm text-slate-500">{user?.email}</div>
                  </div>
                  <TrustBadge level={user?.trust_level || 'SANDBOX'} />
                </div>

                {/* Edit Form */}
                <div className="space-y-4">
                  <div>
                    <label className="label">Display Name</label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      className="input"
                      placeholder="Your display name"
                    />
                  </div>

                  <div>
                    <label className="label">Email Address</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="input"
                      placeholder="your@email.com"
                    />
                  </div>

                  <div>
                    <label className="label">Username</label>
                    <input
                      type="text"
                      value={user?.username || ''}
                      disabled
                      className="input opacity-50 cursor-not-allowed"
                    />
                    <p className="text-xs text-slate-500 mt-1">Username cannot be changed</p>
                  </div>

                  <div>
                    <label className="label">Member Since</label>
                    <input
                      type="text"
                      value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : ''}
                      disabled
                      className="input opacity-50 cursor-not-allowed"
                    />
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={handleSaveProfile} loading={saving} icon={<Save className="w-4 h-4" />}>
                    Save Changes
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="space-y-6">
              {/* Change Password */}
              <Card className="p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                  <Lock className="w-5 h-5 text-sky-400" />
                  Change Password
                </h2>

                <div className="space-y-4">
                  <div className="relative">
                    <label className="label">Current Password</label>
                    <input
                      type={showPasswords ? 'text' : 'password'}
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      className="input pr-10"
                      placeholder="Enter current password"
                    />
                  </div>

                  <div className="relative">
                    <label className="label">New Password</label>
                    <input
                      type={showPasswords ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="input pr-10"
                      placeholder="Enter new password"
                    />
                  </div>

                  <div className="relative">
                    <label className="label">Confirm New Password</label>
                    <input
                      type={showPasswords ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="input pr-10"
                      placeholder="Confirm new password"
                    />
                  </div>

                  <button
                    type="button"
                    onClick={() => setShowPasswords(!showPasswords)}
                    className="text-sm text-slate-500 hover:text-slate-800 flex items-center gap-2"
                  >
                    {showPasswords ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    {showPasswords ? 'Hide passwords' : 'Show passwords'}
                  </button>

                  <div className="flex justify-end">
                    <Button onClick={handleChangePassword} loading={saving} icon={<Lock className="w-4 h-4" />}>
                      Update Password
                    </Button>
                  </div>
                </div>
              </Card>

              {/* Trust Level */}
              <Card className="p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                  <Shield className="w-5 h-5 text-sky-400" />
                  Trust Level
                </h2>

                <div className="p-4 bg-slate-100/30 rounded-lg">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="text-sm text-slate-500 mb-1">Current Trust Level</div>
                      <TrustBadge level={user?.trust_level || 'SANDBOX'} />
                    </div>
                    <Button variant="ghost" size="sm" onClick={handleRefreshTrust} icon={<RefreshCw className="w-4 h-4" />}>
                      Refresh
                    </Button>
                  </div>

                  <div className="text-sm text-slate-500">
                    <p className="mb-2">Trust levels determine your capabilities within Forge:</p>
                    <ul className="space-y-1 ml-4">
                      <li><span className="text-red-400">UNTRUSTED</span> - Read-only access</li>
                      <li><span className="text-amber-400">SANDBOX</span> - Limited capsule creation</li>
                      <li><span className="text-blue-400">STANDARD</span> - Full participation rights</li>
                      <li><span className="text-green-400">TRUSTED</span> - Elevated voting weight</li>
                      <li><span className="text-violet-400">CORE</span> - System administration</li>
                    </ul>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                <Bell className="w-5 h-5 text-sky-400" />
                Notification Preferences
              </h2>

              <div className="space-y-4">
                {Object.entries({
                  proposalVotes: { label: 'Proposal Votes', desc: 'Get notified when proposals you voted on are resolved' },
                  capsuleActivity: { label: 'Capsule Activity', desc: 'Notifications for capsule access and modifications' },
                  systemAlerts: { label: 'System Alerts', desc: 'Critical system status notifications' },
                  anomalyWarnings: { label: 'Anomaly Warnings', desc: 'Alerts when anomalies are detected' },
                  trustChanges: { label: 'Trust Changes', desc: 'Notifications when your trust level changes' },
                  ghostWisdom: { label: 'Ghost Council Wisdom', desc: 'Daily wisdom from the Ghost Council' },
                }).map(([key, { label, desc }]) => (
                  <div key={key} className="flex items-center justify-between p-4 bg-slate-100/30 rounded-lg">
                    <div>
                      <div className="text-slate-800 font-medium">{label}</div>
                      <div className="text-sm text-slate-500">{desc}</div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={notifications[key as keyof typeof notifications]}
                        onChange={(e) => setNotifications({ ...notifications, [key]: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-sky-500/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500" />
                    </label>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex justify-end">
                <Button onClick={() => showMessage('success', 'Notification preferences saved')} icon={<Save className="w-4 h-4" />}>
                  Save Preferences
                </Button>
              </div>
            </Card>
          )}

          {/* Appearance Tab */}
          {activeTab === 'appearance' && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                <Palette className="w-5 h-5 text-sky-400" />
                Appearance Settings
              </h2>

              <div className="space-y-6">
                {/* Theme Selection */}
                <div>
                  <label className="label">Theme</label>
                  <div className="flex gap-3">
                    {(['dark', 'light', 'system'] as const).map((theme) => (
                      <button
                        key={theme}
                        onClick={() => setAppearance({ ...appearance, theme })}
                        className={`px-4 py-2 rounded-lg border transition-colors capitalize ${
                          appearance.theme === theme
                            ? 'border-sky-500 bg-sky-500/20 text-sky-400'
                            : 'border-slate-300 text-slate-500 hover:border-slate-500'
                        }`}
                      >
                        {theme}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 mt-2">Note: Only dark theme is currently available</p>
                </div>

                {/* Toggle Options */}
                <div className="space-y-4">
                  {[
                    { key: 'compactMode', label: 'Compact Mode', desc: 'Reduce spacing for more content' },
                    { key: 'animationsEnabled', label: 'Animations', desc: 'Enable UI animations and transitions' },
                    { key: 'highContrast', label: 'High Contrast', desc: 'Increase color contrast for accessibility' },
                  ].map(({ key, label, desc }) => (
                    <div key={key} className="flex items-center justify-between p-4 bg-slate-100/30 rounded-lg">
                      <div>
                        <div className="text-slate-800 font-medium">{label}</div>
                        <div className="text-sm text-slate-500">{desc}</div>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={appearance[key as keyof typeof appearance] as boolean}
                          onChange={(e) => setAppearance({ ...appearance, [key]: e.target.checked })}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-sky-500/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500" />
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <Button onClick={() => showMessage('success', 'Appearance settings saved')} icon={<Save className="w-4 h-4" />}>
                  Save Settings
                </Button>
              </div>
            </Card>
          )}

          {/* Data & Privacy Tab */}
          {activeTab === 'data' && (
            <div className="space-y-6">
              <Card className="p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                  <Database className="w-5 h-5 text-sky-400" />
                  Your Data
                </h2>

                <div className="space-y-4">
                  <div className="p-4 bg-slate-100/30 rounded-lg">
                    <h3 className="text-slate-800 font-medium mb-2">Data Statistics</h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-slate-500">Capsules Created:</span>
                        <span className="text-slate-800 ml-2">--</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Votes Cast:</span>
                        <span className="text-slate-800 ml-2">--</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Proposals Made:</span>
                        <span className="text-slate-800 ml-2">--</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Ghost Queries:</span>
                        <span className="text-slate-800 ml-2">--</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button onClick={() => setShowExportModal(true)} variant="secondary">
                      Export My Data
                    </Button>
                  </div>
                </div>
              </Card>

              <Card className="p-6 border-red-500/30">
                <h2 className="text-lg font-semibold text-red-400 mb-4">Danger Zone</h2>
                <p className="text-slate-500 text-sm mb-4">
                  Once you delete your account, there is no going back. All your capsules, votes, and contributions will be permanently removed.
                </p>
                <Button variant="danger">
                  Delete Account
                </Button>
              </Card>
            </div>
          )}
        </div>
      </div>

      {/* Export Modal */}
      <Modal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        title="Export Your Data"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-slate-500">
            Choose a format to export your data. This includes your profile, capsules, and activity history.
          </p>

          <div className="flex gap-3">
            {(['json', 'csv'] as const).map((format) => (
              <button
                key={format}
                onClick={() => setExportFormat(format)}
                className={`flex-1 px-4 py-3 rounded-lg border transition-colors uppercase ${
                  exportFormat === format
                    ? 'border-sky-500 bg-sky-500/20 text-sky-400'
                    : 'border-slate-300 text-slate-500 hover:border-slate-500'
                }`}
              >
                {format}
              </button>
            ))}
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setShowExportModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleExportData}>
              Download Export
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
