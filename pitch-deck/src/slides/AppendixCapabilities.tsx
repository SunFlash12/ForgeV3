import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { coreCapabilities } from '../data/features';
import {
  complianceFrameworks,
  totalControls,
  totalJurisdictions,
  forgeAdvantage,
} from '../data/compliance';
import {
  Box, Users, Shield, CheckCircle, Globe, GitBranch, CheckCircle2, Lock, Brain, Building,
  Layers, Key, Fingerprint, Workflow, ArrowRight,
} from 'lucide-react';

const capIconMap: Record<string, React.FC<{ size?: number; style?: React.CSSProperties }>> = {
  box: Box, users: Users, shield: Shield, check: CheckCircle, globe: Globe, 'git-branch': GitBranch,
};

const categoryMeta: Record<string, { label: string; icon: typeof Shield; color: string }> = {
  privacy: { label: 'Privacy', icon: Lock, color: '#00d4ff' },
  security: { label: 'Security', icon: Shield, color: '#10b981' },
  ai: { label: 'AI Governance', icon: Brain, color: '#7c3aed' },
  industry: { label: 'Industry', icon: Building, color: '#f59e0b' },
};

const pipelinePhases = [
  { name: 'Ingestion', time: '~50ms', color: '#00d4ff' },
  { name: 'Analysis', time: '~100ms', color: '#3b82f6' },
  { name: 'Validation', time: '~50ms', color: '#6366f1' },
  { name: 'Consensus', time: '~300ms', color: '#7c3aed' },
  { name: 'Execution', time: '~200ms', color: '#a855f7' },
  { name: 'Propagation', time: '~100ms', color: '#ec4899' },
  { name: 'Settlement', time: '~50ms', color: '#f59e0b' },
];

const securityLayers = [
  { name: 'Authentication', detail: 'JWT + MFA, Ed25519 key pairs', icon: Key, color: '#00d4ff' },
  { name: 'Authorization', detail: 'RBAC, resource-level ACLs', icon: Lock, color: '#7c3aed' },
  { name: 'Trust System', detail: '4 trust tiers, anomaly detection', icon: Fingerprint, color: '#10b981' },
  { name: 'Data Integrity', detail: 'SHA-256, Merkle trees, Isnad chains', icon: Shield, color: '#f59e0b' },
];

export default function AppendixCapabilities({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="dark">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-3">
          {/* Title */}
          <FadeInItem>
            <div className="flex items-center gap-3 mb-1">
              <Layers className="w-5 h-5 text-cyan-400" />
              <h1 className="text-lg md:text-xl lg:text-2xl font-bold text-slate-100">
                Appendix A:{' '}
                <span className="gradient-text">Technical Deep Dive</span>
              </h1>
            </div>
          </FadeInItem>

          {/* Row 1: 6 capability cards (compact 2x3) */}
          <FadeInItem>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 md:gap-2">
              {coreCapabilities.map((cap) => {
                const Icon = capIconMap[cap.icon];
                return (
                  <div
                    key={cap.title}
                    className="bg-white/[0.03] border border-white/[0.06] rounded-lg px-2.5 py-2"
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <div
                        className="w-6 h-6 rounded-md flex items-center justify-center shrink-0"
                        style={{ backgroundColor: `${cap.color}12` }}
                      >
                        {Icon && <Icon size={12} style={{ color: cap.color }} />}
                      </div>
                      <span
                        className="text-[8px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide"
                        style={{ backgroundColor: `${cap.color}12`, color: cap.color }}
                      >
                        {cap.metric}
                      </span>
                    </div>
                    <h3 className="text-[10px] font-semibold text-slate-200">{cap.title}</h3>
                    <p className="text-[9px] text-slate-500 leading-tight line-clamp-1">{cap.description}</p>
                  </div>
                );
              })}
            </div>
          </FadeInItem>

          {/* Row 2: Pipeline strip + Security layers side by side */}
          <FadeInItem>
            <div className="flex flex-col md:flex-row gap-2 md:gap-3">
              {/* 7-Phase Pipeline */}
              <div className="glass-card flex-1 py-2.5 px-3">
                <div className="flex items-center gap-2 mb-2">
                  <Workflow className="w-3.5 h-3.5 text-cyan-400" />
                  <h3 className="text-[9px] font-bold text-slate-300 uppercase tracking-wider">
                    7-Phase Pipeline &mdash; 1.2s Total
                  </h3>
                </div>
                <div className="flex items-center gap-0.5 flex-wrap">
                  {pipelinePhases.map((phase, i) => (
                    <div key={i} className="flex items-center">
                      <div
                        className="rounded-md px-2 py-1 border border-white/5"
                        style={{ backgroundColor: `${phase.color}10`, borderColor: `${phase.color}20` }}
                      >
                        <p className="text-[9px] font-bold" style={{ color: phase.color }}>
                          {phase.name}
                        </p>
                        <p className="text-[8px] text-slate-500 font-mono">{phase.time}</p>
                      </div>
                      {i < pipelinePhases.length - 1 && (
                        <ArrowRight className="w-2.5 h-2.5 text-slate-600 shrink-0 mx-0.5" />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Security layers */}
              <div className="glass-card w-full md:w-[280px] shrink-0 py-2.5 px-3">
                <div className="flex items-center gap-2 mb-2">
                  <Shield className="w-3.5 h-3.5 text-emerald-400" />
                  <h3 className="text-[9px] font-bold text-slate-300 uppercase tracking-wider">
                    4-Layer Security
                  </h3>
                </div>
                <div className="space-y-1.5">
                  {securityLayers.map((layer, i) => {
                    const Icon = layer.icon;
                    return (
                      <div key={i} className="flex items-center gap-2">
                        <div
                          className="w-5 h-5 rounded flex items-center justify-center shrink-0"
                          style={{ backgroundColor: `${layer.color}15` }}
                        >
                          <Icon className="w-3 h-3" style={{ color: layer.color }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="text-[9px] font-bold" style={{ color: layer.color }}>
                            {layer.name}
                          </span>
                          <span className="text-[9px] text-slate-500 ml-1.5">{layer.detail}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </FadeInItem>

          {/* Row 3: Compliance metrics + framework badges */}
          <FadeInItem>
            <div className="glass-card py-2.5 px-3">
              <div className="flex flex-wrap items-center justify-center gap-3 md:gap-5 mb-3">
                <div className="flex items-center gap-1.5">
                  <Shield size={14} className="text-cyber-blue" />
                  <span className="text-xs font-extrabold text-white">{totalControls}+</span>
                  <span className="text-[9px] text-slate-400">Controls</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Globe size={14} className="text-purple-400" />
                  <span className="text-xs font-extrabold text-white">{totalJurisdictions}+</span>
                  <span className="text-[9px] text-slate-400">Jurisdictions</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle size={14} className="text-emerald-400" />
                  <span className="text-xs font-extrabold text-white">{forgeAdvantage}</span>
                  <span className="text-[9px] text-slate-400">Industry Avg</span>
                </div>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                {(Object.keys(complianceFrameworks) as Array<keyof typeof complianceFrameworks>).map(
                  (category) => {
                    const meta = categoryMeta[category];
                    const frameworks = complianceFrameworks[category];
                    return (
                      <div key={category}>
                        <div className="flex items-center gap-1 mb-1">
                          <meta.icon size={10} style={{ color: meta.color }} />
                          <h4
                            className="text-[8px] font-bold uppercase tracking-wider"
                            style={{ color: meta.color }}
                          >
                            {meta.label}
                          </h4>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {frameworks.map((fw) => (
                            <div
                              key={fw.name}
                              className="flex items-center gap-0.5 bg-white/5 rounded px-1.5 py-0.5"
                            >
                              <CheckCircle2
                                size={8}
                                className={
                                  fw.status === 'compliant'
                                    ? 'text-emerald-400'
                                    : fw.status === 'ready'
                                      ? 'text-yellow-400'
                                      : 'text-blue-400'
                                }
                              />
                              <span className="text-[8px] font-medium text-slate-300">
                                {fw.name}
                              </span>
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
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
