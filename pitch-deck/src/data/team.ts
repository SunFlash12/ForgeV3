export interface TeamMember {
  name: string;
  role: string;
  background: string;
  highlights: string[];
  initials: string;
  color: string;
}

export const teamMembers: TeamMember[] = [
  {
    name: 'Idean Moslehi',
    role: 'CEO & Founder',
    background:
      'Frowg Systems, Inc. 9 years as a professional university tutor across all subjects — deep expertise in knowledge transfer and retention systems.',
    highlights: [
      'Co-founded Akita Inu on Algorand — $30M marketcap in 3 days',
      'Onboarded thousands into Algorand, DeFi & crypto',
      'Founding member, Algorand Foundation NFT Council',
    ],
    initials: 'IM',
    color: '#00d4ff',
  },
  {
    name: 'Matthew Hoe',
    role: 'CTO & CPO',
    background:
      'Senior software engineer & technical founder with 10+ years of experience. Took a company from founding to successful exit.',
    highlights: [
      'Led teams delivering production systems for FAANG & Fortune 500',
      'Work featured at SIGGRAPH',
      'Specializes in AI agents & neuro-symbolic systems (knowledge graphs + LLMs)',
    ],
    initials: 'MH',
    color: '#7c3aed',
  },
];

export const teamStats = [
  { label: 'Combined Years Experience', value: '20+' },
  { label: 'Previous Exit', value: '1' },
  { label: 'Domain Expertise', value: 'AI, Web3, Knowledge Systems' },
];
