import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import { RefreshCw, UserX, ShieldAlert, Shield, Brain, Coins, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';

const scenarios = [
  {
    icon: RefreshCw,
    title: 'Model Updates Erase Everything',
    description:
      'Your team spent months training AI on proprietary processes, domain expertise, and internal docs. The model updates. All that institutional knowledge? Gone.',
    stat: { value: 4.5, prefix: '$', suffix: 'M', decimals: 1 },
    statLabel: 'avg annual cost re-training AI systems',
    color: '#00d4ff',
  },
  {
    icon: UserX,
    title: 'Knowledge Walks Out the Door',
    description:
      'Senior engineer leaves after 8 years. Their undocumented decisions, tribal knowledge, and AI workflows? Irreplaceable.',
    stat: { value: 31.5, prefix: '$', suffix: 'B', decimals: 1 },
    statLabel: 'lost annually to knowledge drain',
    color: '#7c3aed',
  },
  {
    icon: ShieldAlert,
    title: 'Regulators Want Receipts',
    description:
      'EU AI Act (Aug 2026): Full traceability for every AI decision. Who created the knowledge? Who approved it? When did it change?',
    stat: { value: 35, prefix: '€', suffix: 'M', decimals: 0 },
    statLabel: 'per violation',
    color: '#f59e0b',
  },
];

const whyNowForces = [
  { icon: Shield, stat: '€35M', label: 'EU AI Act penalties — enforcement Aug 2026', color: '#00d4ff' },
  { icon: Brain, stat: '72%', label: 'of enterprises now deploying AI', color: '#7c3aed' },
  { icon: Coins, stat: '40%', label: 'CAGR autonomous AI agent market', color: '#10b981' },
  { icon: AlertTriangle, stat: '$31.5B', label: 'lost annually to knowledge drain', color: '#f59e0b' },
];

export default function ProblemSlide() {
  return (
    <SlideLayout slideKey={2} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="slide-title text-center mb-4"
        >
          Your AI Has <span className="gradient-text">Amnesia.</span>{' '}
          Regulators Are Coming.
        </motion.h2>

        {/* Scenario cards */}
        <StaggerContainer
          className="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4 mb-4"
          delay={0.3}
        >
          {scenarios.map((scenario) => {
            const Icon = scenario.icon;
            return (
              <FadeInItem key={scenario.title}>
                <div className="glass-card flex flex-col items-start h-full">
                  {/* Icon */}
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                    style={{ backgroundColor: `${scenario.color}15` }}
                  >
                    <Icon size={20} style={{ color: scenario.color }} />
                  </div>

                  {/* Title */}
                  <h3
                    className="text-base font-semibold mb-1.5"
                    style={{ color: scenario.color }}
                  >
                    {scenario.title}
                  </h3>

                  {/* Description */}
                  <p className="text-xs text-slate-400 leading-relaxed mb-3 flex-1">
                    {scenario.description}
                  </p>

                  {/* Stat */}
                  <div
                    className="w-full pt-2.5 mt-auto"
                    style={{ borderTop: `1px solid ${scenario.color}25` }}
                  >
                    <AnimatedCounter
                      value={scenario.stat.value}
                      prefix={scenario.stat.prefix}
                      suffix={scenario.stat.suffix}
                      decimals={scenario.stat.decimals}
                      className="text-xl font-bold"
                    />
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      {scenario.statLabel}
                    </p>
                  </div>
                </div>
              </FadeInItem>
            );
          })}
        </StaggerContainer>

        {/* Why Now strip */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.7 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3"
        >
          {whyNowForces.map((force) => {
            const Icon = force.icon;
            return (
              <div
                key={force.label}
                className="flex items-center gap-2 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2"
              >
                <Icon size={14} style={{ color: force.color }} className="shrink-0" />
                <div className="min-w-0">
                  <span
                    className="text-sm font-extrabold block"
                    style={{ color: force.color }}
                  >
                    {force.stat}
                  </span>
                  <span className="text-[9px] text-slate-500 leading-tight block">
                    {force.label}
                  </span>
                </div>
              </div>
            );
          })}
        </motion.div>

        {/* Bottom callout */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.9 }}
          className="glass-card text-center py-3"
          style={{ border: '1px solid rgba(255,255,255,0.08)' }}
        >
          <p className="text-xs md:text-sm text-slate-300 leading-relaxed">
            <span className="text-white font-semibold">ChatGPT can link files.</span>{' '}
            It can&apos;t version them, track who contributed what, govern what AI
            uses, or prove compliance to regulators.{' '}
            <span className="gradient-text font-semibold">That&apos;s the gap.</span>
          </p>
        </motion.div>
      </div>
    </SlideLayout>
  );
}
