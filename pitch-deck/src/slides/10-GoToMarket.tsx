import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { motion } from 'framer-motion';
import {
  Shield,
  Brain,
  Globe,
  ArrowRight,
  Building2,
  Handshake,
  Store,
} from 'lucide-react';

const gtmPhases = [
  {
    phase: 'LAND',
    title: 'Compliance-First Entry',
    description:
      'Regulated industries face existential compliance risk. Forge solves their most urgent pain: EU AI Act, HIPAA, SOX.',
    targets: ['Legal & Professional Services', 'Biotechnology & Pharma', 'Financial Services'],
    icon: Shield,
    color: '#00d4ff',
    gradient: 'from-cyan-500/20 to-cyan-500/5',
  },
  {
    phase: 'EXPAND',
    title: 'Full Intelligence Platform',
    description:
      'Once embedded for compliance, expand to full institutional memory: knowledge capsules, governance, AI advisors.',
    targets: ['Knowledge Management', 'AI Governance', 'Decision Intelligence'],
    icon: Brain,
    color: '#7c3aed',
    gradient: 'from-purple-500/20 to-purple-500/5',
  },
  {
    phase: 'NETWORK',
    title: 'Ecosystem & Web3',
    description:
      'Cross-organization federation creates network effects. Tokenized knowledge marketplace unlocks Web3 revenue.',
    targets: ['Cross-Org Federation', 'Knowledge Marketplace', 'Autonomous AI Agents'],
    icon: Globe,
    color: '#10b981',
    gradient: 'from-emerald-500/20 to-emerald-500/5',
  },
];

const channels = [
  {
    name: 'Direct Enterprise Sales',
    detail: 'Outbound to regulated verticals',
    icon: Building2,
    color: '#00d4ff',
  },
  {
    name: 'Web3 Partnerships',
    detail: 'Virtuals Protocol ecosystem',
    icon: Handshake,
    color: '#7c3aed',
  },
  {
    name: 'Knowledge Marketplace',
    detail: 'Self-service + viral adoption',
    icon: Store,
    color: '#10b981',
  },
];

export default function GoToMarket({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-6">
        {/* Title */}
        <StaggerContainer className="text-center mb-1">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">Land with Compliance.</span>{' '}
              <span className="text-white">Expand with Intelligence.</span>
            </h1>
            <p className="slide-subtitle">
              3-phase go-to-market from compliance wedge to ecosystem dominance
            </p>
          </FadeInItem>
        </StaggerContainer>

        {/* 3-Phase Expansion */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4" delay={0.2}>
          {gtmPhases.map((phase, idx) => (
            <FadeInItem key={phase.phase}>
              <div className="relative h-full">
                <div className={`glass-card h-full bg-gradient-to-b ${phase.gradient}`}>
                  {/* Phase badge */}
                  <div className="flex items-center gap-2 mb-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
                      style={{ backgroundColor: `${phase.color}25`, color: phase.color }}
                    >
                      {idx + 1}
                    </div>
                    <span
                      className="text-xs font-extrabold uppercase tracking-widest"
                      style={{ color: phase.color }}
                    >
                      {phase.phase}
                    </span>
                  </div>

                  {/* Icon + Title */}
                  <div className="flex items-center gap-2 mb-2">
                    <phase.icon size={20} style={{ color: phase.color }} />
                    <h3 className="text-lg font-bold text-white">{phase.title}</h3>
                  </div>

                  {/* Description */}
                  <p className="text-sm text-slate-300 mb-3 leading-relaxed">
                    {phase.description}
                  </p>

                  {/* Targets */}
                  <div className="space-y-1.5">
                    {phase.targets.map((target) => (
                      <div key={target} className="flex items-center gap-2">
                        <div
                          className="w-1.5 h-1.5 rounded-full shrink-0"
                          style={{ backgroundColor: phase.color }}
                        />
                        <span className="text-xs text-slate-400">{target}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Arrow connector between phases */}
                {idx < gtmPhases.length - 1 && (
                  <motion.div
                    className="hidden lg:flex absolute -right-4 top-1/2 -translate-y-1/2 z-10"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 + idx * 0.2, duration: 0.4 }}
                  >
                    <ArrowRight size={20} className="text-slate-500" />
                  </motion.div>
                )}
              </div>
            </FadeInItem>
          ))}
        </StaggerContainer>

        {/* Channel Strategy */}
        <FadeInItem>
          <div className="glass-card">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">
              Channel Strategy
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 md:gap-4">
              {channels.map((channel) => (
                <div
                  key={channel.name}
                  className="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3"
                >
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${channel.color}15` }}
                  >
                    <channel.icon size={20} style={{ color: channel.color }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{channel.name}</p>
                    <p className="text-xs text-slate-400">{channel.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </FadeInItem>
      </div>
    </SlideLayout>
  );
}
