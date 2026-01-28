export const colors = {
  forge: {
    primary: '#6366f1',
    light: '#818cf8',
    dark: '#4338ca',
    darker: '#312e81',
  },
  cyber: {
    blue: '#00d4ff',
    purple: '#7c3aed',
    pink: '#ec4899',
    green: '#10b981',
    orange: '#f59e0b',
    red: '#ef4444',
  },
  surface: {
    900: '#0a0a1a',
    800: '#0f0f2e',
    700: '#161640',
    600: '#1e1e52',
  },
  text: {
    primary: '#f1f5f9',
    secondary: '#94a3b8',
    muted: '#64748b',
  },
} as const;

export const chartColors = [
  '#00d4ff', // cyber blue
  '#7c3aed', // cyber purple
  '#10b981', // cyber green
  '#f59e0b', // cyber orange
  '#ec4899', // cyber pink
  '#ef4444', // cyber red
  '#6366f1', // forge primary
  '#818cf8', // forge light
];

export const gradients = {
  primary: 'linear-gradient(135deg, #00d4ff, #6366f1, #7c3aed)',
  warm: 'linear-gradient(135deg, #f59e0b, #ec4899, #7c3aed)',
  cool: 'linear-gradient(135deg, #00d4ff, #10b981)',
  dark: 'linear-gradient(180deg, #0a0a1a, #0f0f2e, #161640)',
  card: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(124, 58, 237, 0.05))',
};
