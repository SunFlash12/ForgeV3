// Forge Logo - Futuristic Hexagonal Design
import { useId } from 'react';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showText?: boolean;
  className?: string;
}

const sizes = {
  sm: { icon: 36, text: 'text-lg' },
  md: { icon: 44, text: 'text-xl' },
  lg: { icon: 56, text: 'text-2xl' },
  xl: { icon: 72, text: 'text-3xl' },
};

export function Logo({ size = 'md', showText = true, className = '' }: LogoProps) {
  const id = useId();
  const { icon, text } = sizes[size];

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className="relative flex-shrink-0">
        {/* Outer glow effect */}
        <div
          className="absolute inset-0 blur-md opacity-50"
          style={{
            background: 'linear-gradient(135deg, #00d4ff 0%, #8b5cf6 100%)',
            borderRadius: '30%',
          }}
        />

        {/* Main logo SVG */}
        <svg
          width={icon}
          height={icon}
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="relative z-10"
        >
          {/* Gradient definitions with unique IDs */}
          <defs>
            <linearGradient id={`forgeGradient-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00d4ff" />
              <stop offset="50%" stopColor="#6366f1" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
            <linearGradient id={`innerGlow-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00d4ff" />
              <stop offset="100%" stopColor="#a78bfa" />
            </linearGradient>
          </defs>

          {/* Outer hexagon */}
          <path
            d="M32 4L56 18V46L32 60L8 46V18L32 4Z"
            fill={`url(#forgeGradient-${id})`}
            stroke={`url(#innerGlow-${id})`}
            strokeWidth="1.5"
          />

          {/* Inner hexagon pattern - creates depth */}
          <path
            d="M32 12L48 22V42L32 52L16 42V22L32 12Z"
            fill="none"
            stroke="rgba(255,255,255,0.3)"
            strokeWidth="1"
          />

          {/* Center geometric pattern - stylized 'F' / forge symbol */}
          <g>
            {/* Vertical line */}
            <path
              d="M26 24V44"
              stroke="white"
              strokeWidth="3.5"
              strokeLinecap="round"
            />
            {/* Top horizontal */}
            <path
              d="M26 24H40"
              stroke="white"
              strokeWidth="3.5"
              strokeLinecap="round"
            />
            {/* Middle horizontal */}
            <path
              d="M26 33H36"
              stroke="white"
              strokeWidth="3.5"
              strokeLinecap="round"
            />
          </g>

          {/* Accent nodes - tech feel */}
          <circle cx="40" cy="24" r="2.5" fill="white" />
          <circle cx="36" cy="33" r="2" fill="white" opacity="0.8" />
          <circle cx="26" cy="44" r="2.5" fill="white" />
        </svg>
      </div>

      {showText && (
        <span className={`font-bold ${text} bg-gradient-to-r from-[#00d4ff] via-forge-400 to-[#7c3aed] bg-clip-text text-transparent`}>
          FORGE
        </span>
      )}
    </div>
  );
}

// Compact version for small spaces
export function LogoIcon({ size = 36, className = '' }: { size?: number; className?: string }) {
  const id = useId();

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id={`forgeGradientIcon-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#00d4ff" />
          <stop offset="50%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>

      {/* Outer hexagon */}
      <path
        d="M32 4L56 18V46L32 60L8 46V18L32 4Z"
        fill={`url(#forgeGradientIcon-${id})`}
      />

      {/* Inner hexagon pattern */}
      <path
        d="M32 12L48 22V42L32 52L16 42V22L32 12Z"
        fill="none"
        stroke="rgba(255,255,255,0.3)"
        strokeWidth="1"
      />

      {/* Stylized F */}
      <path
        d="M26 24V44"
        stroke="white"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      <path
        d="M26 24H40"
        stroke="white"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      <path
        d="M26 33H36"
        stroke="white"
        strokeWidth="3.5"
        strokeLinecap="round"
      />

      {/* Accent nodes */}
      <circle cx="40" cy="24" r="2.5" fill="white" />
      <circle cx="36" cy="33" r="2" fill="white" opacity="0.8" />
      <circle cx="26" cy="44" r="2.5" fill="white" />
    </svg>
  );
}

export default Logo;
