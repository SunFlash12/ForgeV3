export const tokenDistribution = [
  { name: 'Public Circulation', percentage: 60, tokens: 600_000_000, color: '#00d4ff' },
  { name: 'Ecosystem Treasury', percentage: 35, tokens: 350_000_000, color: '#7c3aed' },
  { name: 'Liquidity Pool', percentage: 5, tokens: 50_000_000, color: '#10b981' },
];

export const totalSupply = 1_000_000_000;

export const revenueDistribution = [
  { name: 'Creator Rewards', percentage: 30, color: '#00d4ff', description: 'Direct to knowledge creators' },
  { name: 'Contributor Share', percentage: 20, color: '#7c3aed', description: 'Proportional to contributions' },
  { name: 'Operations', percentage: 25, color: '#10b981', description: 'Platform development & maintenance' },
  { name: 'Buyback & Burn', percentage: 25, color: '#f59e0b', description: 'Deflationary token value accrual' },
];

export const bondingCurve = {
  formula: 'avg_price = 0.001 × (1 + current_supply / 10,000)',
  description: 'Progressive pricing rewards early participants',
  dataPoints: Array.from({ length: 20 }, (_, i) => ({
    supply: (i + 1) * 5000,
    price: 0.001 * (1 + ((i + 1) * 5000) / 10000),
  })),
};

export const graduationTiers = [
  { tier: 'Genesis Tier 1', threshold: 21_000, benefit: '50% faster launch', color: '#00d4ff' },
  { tier: 'Standard', threshold: 42_000, benefit: 'Default graduation', color: '#7c3aed' },
  { tier: 'Genesis Tier 3', threshold: 100_000, benefit: 'Premium launch', color: '#f59e0b' },
];

export const acpFeatures = [
  {
    name: 'Agent Commerce Protocol',
    description: 'Standardized inter-agent transactions on Virtuals Protocol',
  },
  {
    name: 'Multi-Chain Support',
    description: 'Base L2 (primary), Ethereum (bridge), Solana (alt trading)',
  },
  {
    name: 'Smart Contracts',
    description: 'CapsuleMarketplace, SimpleEscrow, CapsuleRegistry deployed',
  },
  {
    name: 'Autonomous Revenue',
    description: 'AI agents earn, transact, and pay service fees independently',
  },
];

export const feeStructure = [
  { type: 'Inference Fee', rate: '0.001 VIRTUAL/query', description: 'Per knowledge access' },
  { type: 'Service Fee', rate: '5% of value', description: 'Overlay-as-a-Service' },
  { type: 'Tokenization Fee', rate: '100 VIRTUAL min', description: 'Agent/entity creation' },
  { type: 'Trading Fee', rate: '1% Sentient Tax', description: 'On all trades' },
  { type: 'Governance Reward', rate: '0.01-0.5 VIRTUAL', description: 'Participation incentive' },
];
