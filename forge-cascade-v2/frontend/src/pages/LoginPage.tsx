import { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { Shield, Eye, EyeOff, Loader2, Sparkles } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';

type AuthMode = 'login' | 'register';

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const { login, register, isAuthenticated, isLoading, error, clearError } = useAuthStore();
  const navigate = useNavigate();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    if (mode === 'register') {
      if (password !== confirmPassword) {
        setLocalError('Passwords do not match');
        return;
      }
      if (password.length < 8) {
        setLocalError('Password must be at least 8 characters');
        return;
      }
    }

    try {
      if (mode === 'login') {
        await login(username, password);
      } else {
        await register(username, email, password);
      }
      navigate('/');
    } catch {
      // Error is handled by the store
    }
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen flex bg-gradient-to-br from-slate-50 via-sky-50/30 to-violet-50/30">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-3/5 bg-gradient-to-br from-sky-500 to-violet-600 p-12 flex-col justify-between relative overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-20 w-72 h-72 bg-white rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-20 w-96 h-96 bg-white rounded-full blur-3xl" />
        </div>
        
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">FORGE</span>
          </div>
        </div>
        
        <div className="relative z-10">
          <h1 className="text-4xl xl:text-5xl font-bold text-white leading-tight mb-6">
            Cognitive Architecture
            <br />
            <span className="text-white/80">for Digital Societies</span>
          </h1>
          <p className="text-lg text-white/70 max-w-md">
            Build, govern, and evolve knowledge systems with trust-weighted consensus and AI-powered intelligence overlays.
          </p>
          
          <div className="mt-10 flex items-center gap-6">
            <div className="flex items-center gap-2 text-white/80">
              <Sparkles className="w-5 h-5" />
              <span className="text-sm">6 Intelligence Overlays</span>
            </div>
            <div className="w-1 h-1 bg-white/40 rounded-full" />
            <div className="text-sm text-white/80">Democratic Governance</div>
            <div className="w-1 h-1 bg-white/40 rounded-full" />
            <div className="text-sm text-white/80">Trust-Based Access</div>
          </div>
        </div>
        
        <div className="relative z-10 text-sm text-white/50">
          © 2025 Forge Cascade. Built for institutional memory.
        </div>
      </div>

      {/* Right Panel - Auth Form */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden text-center mb-10">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500 to-violet-500 mb-4 shadow-lg shadow-sky-500/30">
              <Shield className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gradient">FORGE</h1>
            <p className="text-slate-500 mt-1 text-sm">Cognitive Architecture Platform</p>
          </div>

          {/* Welcome Text */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-slate-800">
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p className="text-slate-500 mt-2">
              {mode === 'login' 
                ? 'Sign in to continue to your dashboard' 
                : 'Join the cognitive architecture community'}
            </p>
          </div>

          {/* Mode Tabs */}
          <div className="flex mb-8 bg-slate-100 rounded-xl p-1.5">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                mode === 'login'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setMode('register')}
              className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                mode === 'register'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Register
            </button>
          </div>

          {/* Error Message */}
          {displayError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm font-medium">
              {displayError}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="label">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
                placeholder="Enter your username"
                required
                autoComplete="username"
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="label">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input"
                  placeholder="Enter your email"
                  required
                  autoComplete="email"
                />
              </div>
            )}

            <div>
              <label className="label">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input pr-12"
                  placeholder="Enter your password"
                  required
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label className="label">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input"
                  placeholder="Confirm your password"
                  required
                  autoComplete="new-password"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn-primary btn-lg mt-2"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {mode === 'login' ? 'Signing in...' : 'Creating account...'}
                </span>
              ) : (
                mode === 'login' ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>

          {/* Footer Info */}
          <div className="mt-8 p-4 bg-slate-50 rounded-xl border border-slate-100">
            <p className="text-xs text-slate-500 text-center leading-relaxed">
              {mode === 'register' ? (
                <>
                  New accounts start at <span className="font-semibold text-amber-600">SANDBOX</span> trust level.
                  Contribute to the community to increase your trust score and unlock more capabilities.
                </>
              ) : (
                <>
                  Forge uses a trust-based permission system. Your access level determines which features and operations are available to you.
                </>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
