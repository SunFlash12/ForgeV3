import { useState, useMemo } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { Eye, EyeOff, Loader2, Sparkles, Check, X } from 'lucide-react';
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import { useAuthStore } from '../stores/authStore';
import { LogoIcon } from '../components/common';
import { NetworkBackground } from '../components/common/NetworkBackground';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

type AuthMode = 'login' | 'register';

// Password validation constants (mirroring backend rules from password.py)
const BANNED_SUBSTRINGS = [
  'forge', 'cascade', 'admin', 'root', 'test', 'demo',
  'user', 'pass', 'login', 'guest', 'temp', 'default',
];

const COMMON_WEAK_PASSWORDS = new Set([
  'password', '123456', '12345678', 'qwerty', 'abc123', 'monkey', 'master',
  'dragon', '111111', 'baseball', 'iloveyou', 'trustno1', 'sunshine',
  'letmein', 'welcome', 'shadow', 'superman', 'michael', 'football',
  'password1', 'password123', 'batman', 'access', 'hello', 'charlie',
  'donald', '123456789', '1234567', '12345', '1234', 'qwerty123',
  'starwars', 'passw0rd', 'zaq1zaq1', 'mustang', 'jennifer', 'joshua',
  'whatever', 'hunter', 'george', 'harley', 'ranger', 'thomas',
  'soccer', 'hockey', 'killer', 'andrew', 'robert', 'jordan',
]);

function findBannedSubstring(password: string): string | null {
  const lower = password.toLowerCase();
  for (const banned of BANNED_SUBSTRINGS) {
    if (lower.includes(banned)) return banned;
  }
  return null;
}

function hasSequentialOrRepeatedPattern(password: string): boolean {
  const lower = password.toLowerCase();

  // All same character
  if (lower.length >= 2 && new Set(lower).size === 1) return true;

  // Sequential numbers (e.g., 12345678)
  if (/^\d+$/.test(lower) && lower.length >= 4) {
    const diffs = [...lower].slice(1).map((c, i) => parseInt(c) - parseInt(lower[i]));
    if (new Set(diffs).size === 1 && Math.abs(diffs[0]) <= 1) return true;
  }

  // Sequential letters (e.g., abcdefgh)
  if (/^[a-z]+$/.test(lower) && lower.length >= 4) {
    const diffs = [...lower].slice(1).map((c, i) => c.charCodeAt(0) - lower.charCodeAt(i));
    if (new Set(diffs).size === 1 && Math.abs(diffs[0]) <= 1) return true;
  }

  // Repeated pattern (e.g., abcabc)
  for (let len = 1; len <= Math.floor(lower.length / 2); len++) {
    const pattern = lower.slice(0, len);
    const reps = Math.floor(lower.length / len);
    const built = pattern.repeat(reps);
    if (built === lower.slice(0, built.length)) {
      const remaining = lower.slice(built.length);
      if (remaining === pattern.slice(0, remaining.length)) return true;
    }
  }

  return false;
}

// Password strength calculation
interface PasswordStrength {
  score: number; // 0-5
  label: string;
  color: string;
  requirements: { met: boolean; text: string }[];
}

function calculatePasswordStrength(
  password: string,
  username: string,
  email: string,
): PasswordStrength {
  const lower = password.toLowerCase();
  const bannedWord = findBannedSubstring(password);

  const requirements: { met: boolean; text: string }[] = [
    { met: password.length >= 8, text: 'At least 8 characters' },
    { met: /[A-Z]/.test(password), text: 'One uppercase letter' },
    { met: /[a-z]/.test(password), text: 'One lowercase letter' },
    { met: /[0-9]/.test(password), text: 'One number' },
    { met: /[^A-Za-z0-9]/.test(password), text: 'One special character' },
    { met: !bannedWord, text: bannedWord ? `No banned words ("${bannedWord}")` : 'No banned words' },
    { met: !COMMON_WEAK_PASSWORDS.has(lower), text: 'Not a common password' },
    { met: !hasSequentialOrRepeatedPattern(password), text: 'No sequential/repeated patterns' },
  ];

  // Context-aware checks
  if (username.length >= 3) {
    requirements.push({
      met: !lower.includes(username.toLowerCase()),
      text: 'Cannot contain username',
    });
  }
  if (email) {
    const emailLocal = email.split('@')[0]?.toLowerCase();
    if (emailLocal && emailLocal.length >= 3) {
      requirements.push({
        met: !lower.includes(emailLocal),
        text: 'Cannot contain email name',
      });
    }
  }

  const metCount = requirements.filter((r) => r.met).length;
  const total = requirements.length;
  const ratio = total > 0 ? metCount / total : 0;

  let score: number;
  if (ratio === 1) score = 5;
  else if (ratio >= 0.85) score = 4;
  else if (ratio >= 0.7) score = 3;
  else if (ratio >= 0.5) score = 2;
  else if (ratio >= 0.3) score = 1;
  else score = 0;

  const strengthMap: Record<number, { label: string; color: string }> = {
    0: { label: 'Very Weak', color: 'bg-red-500' },
    1: { label: 'Weak', color: 'bg-red-400' },
    2: { label: 'Fair', color: 'bg-amber-500' },
    3: { label: 'Good', color: 'bg-yellow-500' },
    4: { label: 'Strong', color: 'bg-green-500' },
    5: { label: 'Very Strong', color: 'bg-green-600' },
  };

  return {
    score,
    label: strengthMap[score].label,
    color: strengthMap[score].color,
    requirements,
  };
}

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const { login, loginWithGoogle, register, isAuthenticated, isLoading, error, clearError } = useAuthStore();
  const navigate = useNavigate();
  const [googleLoading, setGoogleLoading] = useState(false);

  // Calculate password strength in register mode
  const passwordStrength = useMemo(() => {
    if (mode === 'register' && password) {
      return calculatePasswordStrength(password, username, email);
    }
    return null;
  }, [password, mode, username, email]);

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
      // Validate all password requirements before submitting
      const strength = calculatePasswordStrength(password, username, email);
      const failedReqs = strength.requirements.filter((r) => !r.met);
      if (failedReqs.length > 0) {
        setLocalError(failedReqs.map((r) => r.text).join('. '));
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

  const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
    if (!credentialResponse.credential) {
      setLocalError('Google authentication failed - no credential received');
      return;
    }

    setGoogleLoading(true);
    setLocalError(null);
    clearError();

    try {
      await loginWithGoogle(credentialResponse.credential);
      navigate('/');
    } catch {
      setLocalError('Google authentication failed. Please try again.');
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleGoogleError = () => {
    setLocalError('Google Sign-In was cancelled or failed');
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen flex bg-surface-900">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-3/5 bg-gradient-to-br from-surface-800 to-surface-900 p-12 flex-col justify-between relative overflow-hidden">
        {/* Network Background */}
        <NetworkBackground />

        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <LogoIcon size={48} className="drop-shadow-lg" />
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
          &copy; 2026 Forge Cascade. Built for institutional memory.
        </div>
      </div>

      {/* Right Panel - Auth Form */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="lg:hidden text-center mb-10">
            <div className="inline-flex items-center justify-center mb-4">
              <LogoIcon size={56} />
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-forge-500 via-indigo-500 to-violet-500 bg-clip-text text-transparent">FORGE</h1>
            <p className="text-slate-400 mt-1 text-sm">Cognitive Architecture Platform</p>
          </div>

          {/* Welcome Text */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-slate-100">
              {mode === 'login' ? 'Welcome back!' : 'Join Forge'}
            </h2>
            <p className="text-slate-400 mt-2">
              {mode === 'login'
                ? 'Sign in to access your knowledge dashboard'
                : 'Start building your institutional memory today'}
            </p>
          </div>

          {/* Mode Tabs */}
          <div className="flex mb-8 bg-white/5 rounded-xl p-1.5">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                mode === 'login'
                  ? 'bg-white/10 text-slate-100 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setMode('register')}
              className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                mode === 'register'
                  ? 'bg-white/10 text-slate-100 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Register
            </button>
          </div>

          {/* Error Message */}
          {displayError && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm font-medium">
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
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>

              {/* Password Strength Indicator */}
              {mode === 'register' && password && passwordStrength && (
                <div className="mt-3 space-y-2">
                  {/* Strength Bar */}
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden flex gap-0.5">
                      {[1, 2, 3, 4, 5].map((level) => (
                        <div
                          key={level}
                          className={`flex-1 h-full rounded-full transition-colors ${
                            level <= passwordStrength.score ? passwordStrength.color : 'bg-white/10'
                          }`}
                        />
                      ))}
                    </div>
                    <span className={`text-xs font-medium ${
                      passwordStrength.score <= 1 ? 'text-red-500' :
                      passwordStrength.score <= 2 ? 'text-amber-500' :
                      passwordStrength.score <= 3 ? 'text-yellow-400' :
                      'text-green-400'
                    }`}>
                      {passwordStrength.label}
                    </span>
                  </div>

                  {/* Requirements List */}
                  <div className="grid grid-cols-2 gap-1">
                    {passwordStrength.requirements.map((req, idx) => (
                      <div key={idx} className="flex items-center gap-1.5 text-xs">
                        {req.met ? (
                          <Check className="w-3.5 h-3.5 text-green-500" />
                        ) : (
                          <X className="w-3.5 h-3.5 text-slate-400" />
                        )}
                        <span className={req.met ? 'text-slate-300' : 'text-slate-400'}>
                          {req.text}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
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
              disabled={isLoading || googleLoading}
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

          {/* Google Sign-In */}
          {GOOGLE_CLIENT_ID && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/10" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-surface-900 text-slate-400">Or continue with</span>
                </div>
              </div>

              <div className="mt-4 flex justify-center">
                {googleLoading ? (
                  <div className="flex items-center justify-center gap-2 py-3 text-slate-300">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Signing in with Google...</span>
                  </div>
                ) : (
                  <GoogleLogin
                    onSuccess={handleGoogleSuccess}
                    onError={handleGoogleError}
                    theme="outline"
                    size="large"
                    text={mode === 'login' ? 'signin_with' : 'signup_with'}
                    shape="rectangular"
                    width="100%"
                  />
                )}
              </div>
            </div>
          )}

          {/* Footer Info */}
          <div className="mt-8 p-4 bg-white/5 rounded-xl border border-white/10">
            <p className="text-xs text-slate-400 text-center leading-relaxed">
              {mode === 'register' ? (
                <>
                  New accounts start at <span className="font-semibold text-amber-400">SANDBOX</span> trust level.
                  Contribute quality knowledge to grow your trust and unlock more features.
                </>
              ) : (
                <>
                  Forge uses trust-based access control. Your contributions determine your capabilities.
                </>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
