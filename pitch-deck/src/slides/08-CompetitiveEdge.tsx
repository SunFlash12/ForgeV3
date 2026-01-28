import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { motion } from 'framer-motion';
import { Fingerprint, TrendingUp, ShieldCheck, Code2 } from 'lucide-react';

/** Competitors plotted on the 2x2 matrix (positions are percentages) */
const matrixPlots = [
  { name: 'Traditional RAG', x: 20, y: 12, color: '#64748b' },
  { name: 'Custom Build', x: 45, y: 35, color: '#64748b' },
  { name: 'ChatGPT Enterprise', x: 75, y: 10, color: '#64748b' },
  { name: 'Forge', x: 85, y: 88, color: '#00d4ff', highlight: true },
];

const moatItems = [
  {
    icon: Fingerprint,
    title: 'Isnad Lineage System',
    detail: 'Patent-pending',
    color: '#00d4ff',
  },
  {
    icon: TrendingUp,
    title: 'Data Flywheel',
    detail: 'More users \u2192 richer graphs \u2192 better AI',
    color: '#7c3aed',
  },
  {
    icon: ShieldCheck,
    title: '400+ Compliance Controls',
    detail: '8\u00d7 industry average',
    color: '#10b981',
  },
  {
    icon: Code2,
    title: '50,000+ LOC',
    detail: '4 security audits passed',
    color: '#6366f1',
  },
];

export default function CompetitiveEdge({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-4 md:gap-5">
        {/* Headline */}
        <StaggerContainer className="text-center mb-1">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">Uncontested Position.</span> Deepening Moats.
            </h1>
          </FadeInItem>
        </StaggerContainer>

        {/* Main content: two columns */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-5">
          {/* Left: 2x2 Positioning Matrix */}
          <FadeInItem>
            <div className="glass-card flex flex-col items-center">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3 text-center">
                Competitive Positioning
              </h3>
              <div className="relative w-[220px] h-[220px] sm:w-[250px] sm:h-[250px]">
                {/* Grid background */}
                <div className="absolute inset-0 border border-white/10 rounded-lg overflow-hidden">
                  {/* Quadrant lines */}
                  <div className="absolute top-1/2 left-0 right-0 h-px bg-white/10" />
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/10" />

                  {/* Highlight quadrant (top-right) */}
                  <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-cyan-500/5 border-b border-l border-cyan-500/10" />
                </div>

                {/* Axis labels */}
                <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-slate-500 font-medium">
                  AI Depth &rarr;
                </div>
                <div className="absolute -left-4 top-1/2 -translate-y-1/2 -rotate-90 text-[10px] text-slate-500 font-medium whitespace-nowrap">
                  Blockchain-Native Ownership &rarr;
                </div>

                {/* Corner labels */}
                <span className="absolute bottom-1 left-1 text-[9px] text-slate-600">Low / Low</span>
                <span className="absolute top-1 right-1 text-[9px] text-cyan-400/60">High / High</span>

                {/* Competitor dots */}
                {matrixPlots.map((comp) => (
                  <motion.div
                    key={comp.name}
                    className="absolute flex flex-col items-center"
                    style={{
                      left: `${comp.x}%`,
                      bottom: `${comp.y}%`,
                      transform: 'translate(-50%, 50%)',
                    }}
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: comp.highlight ? 1.0 : 0.6, duration: 0.5 }}
                  >
                    {comp.highlight && (
                      <motion.div
                        className="absolute w-10 h-10 rounded-full bg-cyan-400/10"
                        animate={{ scale: [1, 1.5, 1], opacity: [0.3, 0.1, 0.3] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    )}
                    <div
                      className="w-3.5 h-3.5 rounded-full border-2 z-10"
                      style={{
                        backgroundColor: comp.highlight ? comp.color : 'transparent',
                        borderColor: comp.color,
                        boxShadow: comp.highlight ? `0 0 16px ${comp.color}40` : 'none',
                      }}
                    />
                    <span
                      className="text-[9px] mt-1 font-medium whitespace-nowrap"
                      style={{ color: comp.highlight ? '#00d4ff' : '#94a3b8' }}
                    >
                      {comp.name}
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>
          </FadeInItem>

          {/* Right: Moat items list */}
          <StaggerContainer className="flex flex-col gap-3" delay={0.3}>
            {moatItems.map((item) => {
              const Icon = item.icon;
              return (
                <FadeInItem key={item.title}>
                  <div className="glass-card flex items-center gap-4 py-4">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                      style={{ backgroundColor: `${item.color}20` }}
                    >
                      <Icon size={20} style={{ color: item.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-bold text-white">{item.title}</h4>
                      <p className="text-xs text-slate-400">{item.detail}</p>
                    </div>
                  </div>
                </FadeInItem>
              );
            })}
          </StaggerContainer>
        </div>

        {/* Bottom bar */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.9 }}
          className="glass-card text-center"
          style={{ border: '1px solid rgba(255,255,255,0.08)' }}
        >
          <p className="text-sm md:text-base text-slate-300 leading-relaxed">
            No one else combines{' '}
            <span className="text-white font-semibold">deep AI</span> +{' '}
            <span className="text-white font-semibold">blockchain ownership</span> +{' '}
            <span className="text-white font-semibold">regulatory compliance</span> +{' '}
            <span className="text-white font-semibold">democratic governance</span>
          </p>
        </motion.div>
      </div>
    </SlideLayout>
  );
}
