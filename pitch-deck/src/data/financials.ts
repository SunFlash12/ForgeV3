// Funding ask derived from TECHNICAL STRENGTH:
// - 50,000+ lines of production-ready code
// - 93+ backend modules, 12 API routes, 14 services, 10 overlays
// - Full microservices architecture (3 APIs)
// - 400+ compliance controls across 25+ jurisdictions
// - 4 completed security audits
// - Two complete frontend applications
// - Smart contracts deployed (Solidity)
// - Multi-chain integration (Base L2, Ethereum, Solana)
// - Immune system (self-healing infrastructure)
// - Ghost Council AI governance framework
// - Federation protocol for multi-instance sync
// - Comprehensive test suite (195+ tests)
//
// Engineering replacement cost estimate: $3-5M (15-20 senior engineers x 12-18 months)
// Technical moat value: Production-ready platform with no direct competitor equivalent
// Funding ask: $8M Seed/Pre-Series A to capitalize on technical advantage

export const fundingAsk = {
  amount: 8_000_000,
  formatted: '$8M',
  stage: 'Seed / Pre-Series A',
  runway: '18-24 months',
};

export const useOfFunds = [
  { category: 'Engineering & Product', percentage: 40, amount: 3_200_000, color: '#00d4ff', detail: 'Scale to 12-person engineering team, ML/AI infrastructure' },
  { category: 'Go-to-Market', percentage: 25, amount: 2_000_000, color: '#7c3aed', detail: 'Enterprise sales team, marketing, partner development' },
  { category: 'Compliance & Certifications', percentage: 15, amount: 1_200_000, color: '#10b981', detail: 'SOC 2, ISO 27001, FedRAMP certification processes' },
  { category: 'Operations & Infrastructure', percentage: 12, amount: 960_000, color: '#f59e0b', detail: 'Cloud infrastructure, DevOps, legal, admin' },
  { category: 'Reserve', percentage: 8, amount: 640_000, color: '#64748b', detail: 'Strategic opportunities, contingency' },
];

export const milestones = [
  { label: '10 Enterprise Pilots', timeline: 'Q2 2026', track: 'product' as const },
  { label: 'SOC 2 Type II Certified', timeline: 'Q3 2026', track: 'compliance' as const },
  { label: '$1M ARR', timeline: 'Q4 2026', track: 'revenue' as const },
  { label: 'Virtuals Protocol Mainnet Launch', timeline: 'Q2 2026', track: 'web3' as const },
  { label: '50+ Paying Customers', timeline: 'Q1 2027', track: 'product' as const },
  { label: '$3M ARR', timeline: 'Q2 2027', track: 'revenue' as const },
];

export const revenueProjections = [
  // Year 1 quarterly
  { period: 'Q1 Y1', revenue: 50_000, customers: 15, label: 'Q1' },
  { period: 'Q2 Y1', revenue: 150_000, customers: 40, label: 'Q2' },
  { period: 'Q3 Y1', revenue: 280_000, customers: 85, label: 'Q3' },
  { period: 'Q4 Y1', revenue: 420_000, customers: 160, label: 'Q4' },
  // Year 2 quarterly
  { period: 'Q1 Y2', revenue: 620_000, customers: 250, label: 'Y2 Q1' },
  { period: 'Q2 Y2', revenue: 900_000, customers: 380, label: 'Y2 Q2' },
  { period: 'Q3 Y2', revenue: 1_250_000, customers: 520, label: 'Y2 Q3' },
  { period: 'Q4 Y2', revenue: 1_700_000, customers: 700, label: 'Y2 Q4' },
  // Year 3 quarterly
  { period: 'Q1 Y3', revenue: 2_200_000, customers: 900, label: 'Y3 Q1' },
  { period: 'Q2 Y3', revenue: 2_800_000, customers: 1_150, label: 'Y3 Q2' },
  { period: 'Q3 Y3', revenue: 3_500_000, customers: 1_400, label: 'Y3 Q3' },
  { period: 'Q4 Y3', revenue: 4_500_000, customers: 1_800, label: 'Y3 Q4' },
];

export const annualRevenue = [
  { year: 'Year 1', revenue: 900_000, label: '$900K' },
  { year: 'Year 2', revenue: 4_470_000, label: '$4.5M' },
  { year: 'Year 3', revenue: 13_000_000, label: '$13M' },
];

export const unitEconomics = {
  grossMargin: 85,
  avgContractValue: 5_350, // $535/mo Business tier
  cacPayback: 6, // months
  ltv: 64_200, // $535 x 120 months (10 year) x 85% margin
  ltvCacRatio: 5.3,
  costPerQuery: 0.0013, // VIRTUAL
  inferenceMargin: 92, // %
};

export const pricingTiers = [
  { tier: 'Starter', price: 50, queries: '100/mo', target: 'Individual / Small teams' },
  { tier: 'Growth', price: 101, queries: '1K/mo', target: 'Growing teams' },
  { tier: 'Business', price: 535, queries: '10K/mo', target: 'Mid-market' },
  { tier: 'Enterprise', price: 3_625, queries: '100K/mo', target: 'Large organizations' },
  { tier: 'Enterprise+', price: 16_000, queries: '1M/mo', target: 'Global enterprises' },
];

export const revenueStreams = [
  { name: 'SaaS Subscriptions', percentage: 45, color: '#00d4ff' },
  { name: 'Inference Fees', percentage: 20, color: '#7c3aed' },
  { name: 'Service Fees (5%)', percentage: 15, color: '#10b981' },
  { name: 'Tokenization', percentage: 12, color: '#f59e0b' },
  { name: 'Trading (Sentient Tax)', percentage: 8, color: '#ec4899' },
];

export const technicalAssetValue = {
  linesOfCode: 50_000,
  backendModules: 93,
  apiEndpoints: 25,
  complianceControls: 400,
  securityAudits: 4,
  testCases: 195,
  frontendPages: 23, // 15 main + 8 marketplace
  smartContracts: 3,
  engineeringMonths: 180, // estimated 15 engineers x 12 months
  replacementCost: 4_500_000, // $4.5M
};
