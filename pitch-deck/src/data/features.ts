export const coreCapabilities = [
  {
    title: 'Knowledge Capsules',
    description: '11 typed knowledge containers with versioning, cryptographic signing, and semantic embeddings',
    metric: '11 Types',
    icon: 'box',
    color: '#00d4ff',
  },
  {
    title: 'Ghost Council',
    description: '5 AI advisors providing democratic governance with weighted voting and constitutional compliance',
    metric: '5 Advisors',
    icon: 'users',
    color: '#7c3aed',
  },
  {
    title: 'Immune System',
    description: 'Self-healing infrastructure with circuit breakers, anomaly detection, and canary deployments',
    metric: 'Auto-Recovery',
    icon: 'shield',
    color: '#10b981',
  },
  {
    title: 'Compliance Engine',
    description: 'GDPR, HIPAA, EU AI Act, SOC 2, ISO 27001, and 20+ more regulatory frameworks built-in',
    metric: '400+ Controls',
    icon: 'check',
    color: '#f59e0b',
  },
  {
    title: 'Federation Protocol',
    description: 'Cross-organization knowledge sharing with trust-based P2P sync and conflict resolution',
    metric: 'Multi-Node',
    icon: 'globe',
    color: '#ec4899',
  },
  {
    title: 'Isnad Lineage',
    description: 'Complete chain of custody for every piece of knowledge with Merkle tree verification',
    metric: 'Immutable',
    icon: 'git-branch',
    color: '#6366f1',
  },
];

export const pipelinePhases = [
  { name: 'Ingestion', time: '~50ms', description: 'Validation & normalization' },
  { name: 'Analysis', time: '~100ms', description: 'ML classification & embeddings' },
  { name: 'Validation', time: '~50ms', description: 'Security & trust checks' },
  { name: 'Consensus', time: '~300ms', description: 'Ghost Council governance' },
  { name: 'Execution', time: '~200ms', description: 'Core state changes' },
  { name: 'Propagation', time: '~100ms', description: 'Cascade effects & events' },
  { name: 'Settlement', time: '~50ms', description: 'Audit logging & finalization' },
];

export const totalLatency = '1.2s';

export const techStack = {
  backend: [
    { name: 'Python 3.12', category: 'Language' },
    { name: 'FastAPI', category: 'Framework' },
    { name: 'Neo4j 5.x', category: 'Database' },
    { name: 'Redis 7.x', category: 'Cache' },
    { name: 'Pydantic v2', category: 'Validation' },
  ],
  frontend: [
    { name: 'React 19', category: 'UI Framework' },
    { name: 'TypeScript 5.9', category: 'Language' },
    { name: 'Tailwind CSS v4', category: 'Styling' },
    { name: 'Zustand + TanStack', category: 'State' },
    { name: 'Vite 7.3', category: 'Build' },
  ],
  infrastructure: [
    { name: 'Docker / K8s', category: 'Containers' },
    { name: 'Prometheus + Grafana', category: 'Monitoring' },
    { name: 'Jaeger', category: 'Tracing' },
    { name: 'GitHub Actions', category: 'CI/CD' },
    { name: 'Sentry', category: 'Errors' },
  ],
  blockchain: [
    { name: 'Base L2', category: 'Primary Chain' },
    { name: 'Ethereum', category: 'Bridge' },
    { name: 'Solana', category: 'Alt Trading' },
    { name: 'Virtuals Protocol', category: 'ACP' },
    { name: 'Solidity 0.8.20', category: 'Contracts' },
  ],
  security: [
    { name: 'JWT + MFA', category: 'Auth' },
    { name: 'Ed25519', category: 'Signatures' },
    { name: 'SHA-256 + Merkle', category: 'Integrity' },
    { name: 'RBAC + Trust Tiers', category: 'Access' },
    { name: 'bcrypt-12', category: 'Passwords' },
  ],
};

export const microservices = [
  { name: 'Cascade API', port: 8001, description: 'Core engine: capsules, governance, overlays, system', color: '#00d4ff' },
  { name: 'Compliance API', port: 8002, description: 'GDPR, DSAR, consent, breach notification, AI governance', color: '#10b981' },
  { name: 'Virtuals API', port: 8003, description: 'Blockchain: tokenization, ACP, agents, revenue tracking', color: '#f59e0b' },
];

export const competitorComparison = [
  { feature: 'Persistent Memory', forge: 'best', chatgpt: 'limited', rag: 'partial', custom: 'partial' },
  { feature: 'Complete Lineage', forge: 'best', chatgpt: 'none', rag: 'none', custom: 'partial' },
  { feature: 'Democratic Governance', forge: 'best', chatgpt: 'none', rag: 'none', custom: 'none' },
  { feature: 'Self-Healing Infra', forge: 'best', chatgpt: 'none', rag: 'none', custom: 'partial' },
  { feature: 'Compliance Controls', forge: '400+', chatgpt: '~50', rag: '0', custom: '~20' },
  { feature: 'Tokenization', forge: 'best', chatgpt: 'none', rag: 'none', custom: 'none' },
  { feature: 'Sub-2s Latency', forge: '1.2s', chatgpt: 'yes', rag: 'varies', custom: 'varies' },
];

export const moatLayers = [
  {
    layer: 'Patent-Pending Isnad',
    description: 'Unique knowledge lineage tracking system with no direct competitor equivalent',
    strength: 'Very Strong',
    color: '#00d4ff',
  },
  {
    layer: 'Data Flywheel',
    description: 'More usage creates richer knowledge graphs, better AI, attracting more users',
    strength: 'Strong',
    color: '#7c3aed',
  },
  {
    layer: 'Compliance Depth',
    description: '400+ controls (8x industry average) creating massive switching costs',
    strength: 'Very Strong',
    color: '#10b981',
  },
  {
    layer: 'Ghost Council IP',
    description: 'First democratic AI governance with Constitutional AI principles',
    strength: 'Strong',
    color: '#f59e0b',
  },
  {
    layer: 'Virtuals Integration',
    description: 'First-mover in tokenized institutional memory with blockchain revenue',
    strength: 'Strong',
    color: '#ec4899',
  },
  {
    layer: 'Production Codebase',
    description: '50,000+ LOC, 4 security audits, 195+ tests - massive head start',
    strength: 'Very Strong',
    color: '#6366f1',
  },
];

export const roadmapPhases = [
  {
    phase: 'Phase 1: Foundation',
    status: 'complete' as const,
    items: [
      'Core engine & 7-phase pipeline',
      'Ghost Council governance',
      '400+ compliance controls',
      'Virtuals Protocol integration',
      'Two complete frontends',
      '4 security audits passed',
    ],
  },
  {
    phase: 'Phase 2: Market Entry',
    status: 'current' as const,
    items: [
      'Enterprise pilot programs',
      'SOC 2 & ISO 27001 certification',
      'Partner ecosystem development',
      'Go-to-market execution',
    ],
  },
  {
    phase: 'Phase 3: Scale',
    status: 'planned' as const,
    items: [
      'Multi-region deployment',
      'Additional blockchain integrations',
      'Knowledge marketplace launch',
      'API ecosystem expansion',
    ],
  },
  {
    phase: 'Phase 4: Ecosystem',
    status: 'planned' as const,
    items: [
      'Third-party overlay marketplace',
      'Cross-org knowledge federation',
      'Autonomous agent networks',
      'Advanced ML capabilities',
    ],
  },
];
