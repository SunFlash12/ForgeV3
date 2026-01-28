import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import {
  complianceFrameworks,
  totalControls,
  totalJurisdictions,
  forgeAdvantage,
  maxPenalties,
} from '../data/compliance';
import { Shield, CheckCircle2, AlertTriangle, Lock, Brain, Building } from 'lucide-react';

const categoryMeta: Record<
  string,
  { label: string; icon: typeof Shield; color: string }
> = {
  privacy: { label: 'Privacy', icon: Lock, color: '#00d4ff' },
  security: { label: 'Security', icon: Shield, color: '#10b981' },
  ai: { label: 'AI Governance', icon: Brain, color: '#7c3aed' },
  industry: { label: 'Industry', icon: Building, color: '#f59e0b' },
};

const topMetrics = [
  { value: totalControls, suffix: '+', label: 'Controls Implemented', color: '#00d4ff' },
  { value: totalJurisdictions, suffix: '+', label: 'Jurisdictions Covered', color: '#7c3aed' },
  { value: 8, suffix: 'x', label: 'Industry Average', color: '#10b981' },
];

export default function Compliance() {
  return (
    <SlideLayout slideKey={14} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-5">
        {/* Title */}
        <StaggerContainer className="text-center mb-1">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">400+ Controls. 25+ Jurisdictions.</span>{' '}
              <span className="text-white">Protected.</span>
            </h1>
            <p className="slide-subtitle">
              The most comprehensive compliance engine in enterprise AI
            </p>
          </FadeInItem>
        </StaggerContainer>

        {/* Top metrics */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4" delay={0.2}>
          {topMetrics.map((metric) => (
            <FadeInItem key={metric.label}>
              <div className="glass-card text-center py-4">
                <Shield
                  size={20}
                  style={{ color: metric.color }}
                  className="mx-auto mb-2"
                />
                <AnimatedCounter
                  value={metric.value}
                  suffix={metric.suffix}
                  className="metric-value text-3xl md:text-4xl"
                  decimals={0}
                />
                <p className="metric-label text-xs mt-1">{metric.label}</p>
              </div>
            </FadeInItem>
          ))}
        </StaggerContainer>

        {/* Framework badges by category */}
        <FadeInItem>
          <div className="glass-card">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">
              Regulatory Frameworks
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
              {(Object.keys(complianceFrameworks) as Array<keyof typeof complianceFrameworks>).map(
                (category) => {
                  const meta = categoryMeta[category];
                  const frameworks = complianceFrameworks[category];
                  return (
                    <div key={category}>
                      <div className="flex items-center gap-2 mb-2">
                        <meta.icon size={14} style={{ color: meta.color }} />
                        <h4
                          className="text-xs font-bold uppercase tracking-wider"
                          style={{ color: meta.color }}
                        >
                          {meta.label}
                        </h4>
                      </div>
                      <div className="space-y-1.5">
                        {frameworks.map((fw) => (
                          <div
                            key={fw.name}
                            className="flex items-center gap-2 bg-white/5 rounded-lg px-2.5 py-1.5"
                          >
                            <CheckCircle2
                              size={12}
                              className={
                                fw.status === 'compliant'
                                  ? 'text-emerald-400'
                                  : fw.status === 'ready'
                                    ? 'text-yellow-400'
                                    : 'text-blue-400'
                              }
                            />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-slate-200 truncate">
                                {fw.name}
                              </p>
                              <p className="text-[10px] text-slate-500">{fw.region}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                },
              )}
            </div>
          </div>
        </FadeInItem>

        {/* Penalty protection */}
        <FadeInItem>
          <div className="glass-card">
            <div className="flex items-center gap-2 justify-center mb-3">
              <AlertTriangle size={16} className="text-red-400" />
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                Penalties Forge Protects Against
              </h3>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 md:gap-3">
              {maxPenalties.map((penalty) => (
                <div
                  key={penalty.regulation}
                  className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-center"
                >
                  <p className="text-xs text-slate-400 mb-1">{penalty.regulation}</p>
                  <p className="text-xl font-extrabold" style={{ color: penalty.color }}>
                    {penalty.amount}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-0.5">max penalty</p>
                </div>
              ))}
            </div>
            <p className="text-center text-xs text-slate-500 mt-3">
              Forge compliance advantage:{' '}
              <span className="text-emerald-400 font-bold">{forgeAdvantage}</span> the industry
              average coverage
            </p>
          </div>
        </FadeInItem>
      </div>
    </SlideLayout>
  );
}
