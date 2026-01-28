export const complianceFrameworks = {
  privacy: [
    { name: 'GDPR', region: 'EU/EEA', penalty: '\u20AC20M / 4% revenue', status: 'compliant' },
    { name: 'CCPA/CPRA', region: 'California', penalty: '$7,500 per violation', status: 'compliant' },
    { name: 'LGPD', region: 'Brazil', penalty: '2% revenue', status: 'compliant' },
    { name: 'PIPL', region: 'China', penalty: '\u00A550M', status: 'compliant' },
    { name: 'PDPA', region: 'Singapore', penalty: 'S$1M', status: 'compliant' },
  ],
  security: [
    { name: 'SOC 2 Type II', region: 'Global', penalty: 'Loss of enterprise contracts', status: 'ready' },
    { name: 'ISO 27001', region: 'Global', penalty: 'Loss of enterprise contracts', status: 'ready' },
    { name: 'NIST 800-53', region: 'US Federal', penalty: 'Contract disqualification', status: 'compliant' },
    { name: 'PCI-DSS 4.0.1', region: 'Global', penalty: '$100K/month', status: 'ready' },
    { name: 'FedRAMP', region: 'US Federal', penalty: 'Government exclusion', status: 'ready' },
  ],
  ai: [
    { name: 'EU AI Act', region: 'EU', penalty: '\u20AC35M / 7% revenue', status: 'compliant' },
    { name: 'Colorado AI Act', region: 'Colorado', penalty: '$20K per violation', status: 'compliant' },
    { name: 'NYC Local Law 144', region: 'NYC', penalty: '$1,500 per violation', status: 'compliant' },
    { name: 'NIST AI RMF', region: 'US', penalty: 'N/A (voluntary)', status: 'aligned' },
  ],
  industry: [
    { name: 'HIPAA', region: 'US Healthcare', penalty: '$1.5M per violation', status: 'compliant' },
    { name: 'FERPA', region: 'US Education', penalty: 'Funding loss', status: 'compliant' },
    { name: 'GLBA', region: 'US Financial', penalty: '$100K per violation', status: 'compliant' },
  ],
};

export const totalControls = 400;
export const totalJurisdictions = 25;
export const industryAverage = 50;
export const forgeAdvantage = '8x';

export const maxPenalties = [
  { regulation: 'EU AI Act', amount: '\u20AC35M', color: '#ef4444' },
  { regulation: 'GDPR', amount: '\u20AC20M', color: '#f59e0b' },
  { regulation: 'HIPAA', amount: '$1.5M', color: '#ec4899' },
  { regulation: 'PCI-DSS', amount: '$100K/mo', color: '#7c3aed' },
];
