import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { competitorComparison } from '../data/features';
import { motion } from 'framer-motion';
import { Crown, Check, Minus, X } from 'lucide-react';

/** Competitors plotted on the 2x2 matrix (positions are percentages) */
const matrixPlots = [
  { name: 'Traditional RAG', x: 35, y: 15, color: '#64748b' },
  { name: 'Custom Build', x: 45, y: 30, color: '#64748b' },
  { name: 'ChatGPT Enterprise', x: 75, y: 10, color: '#64748b' },
  { name: 'Forge', x: 85, y: 88, color: '#00d4ff', highlight: true },
];

function statusIcon(val: string) {
  if (val === 'best' || val === '400+' || val === '1.2s' || val === 'yes')
    return <Check size={14} className="text-emerald-400" />;
  if (val === 'partial' || val === 'limited' || val === '~50' || val === '~20' || val === 'varies')
    return <Minus size={14} className="text-yellow-400" />;
  return <X size={14} className="text-red-400" />;
}

function statusColor(val: string) {
  if (val === 'best' || val === '400+' || val === '1.2s' || val === 'yes') return 'text-emerald-400';
  if (val === 'partial' || val === 'limited' || val === '~50' || val === '~20' || val === 'varies')
    return 'text-yellow-400';
  return 'text-red-400';
}

export default function Competition() {
  return (
    <SlideLayout slideKey={11} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-5">
        {/* Title */}
        <StaggerContainer className="text-center mb-1">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">No One Occupies Our Intersection</span>
            </h1>
            <p className="slide-subtitle">
              Deep AI + Blockchain-native ownership = uncontested market position
            </p>
          </FadeInItem>
        </StaggerContainer>

        {/* Main content */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-5">
          {/* Left: 2x2 Matrix */}
          <FadeInItem>
            <div className="glass-card">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3 text-center">
                Competitive Positioning
              </h3>
              <div className="relative w-full aspect-square max-w-full sm:max-w-[340px] mx-auto">
                {/* Grid background */}
                <div className="absolute inset-0 border border-white/10 rounded-lg overflow-hidden">
                  {/* Quadrant lines */}
                  <div className="absolute top-1/2 left-0 right-0 h-px bg-white/10" />
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/10" />

                  {/* Highlight quadrant (top-right) */}
                  <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-cyan-500/5 border-b border-l border-cyan-500/10" />
                </div>

                {/* Axis labels */}
                <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-xs text-slate-500 font-medium">
                  AI Depth &rarr;
                </div>
                <div className="absolute -left-5 top-1/2 -translate-y-1/2 -rotate-90 text-xs text-slate-500 font-medium whitespace-nowrap">
                  Blockchain Ownership &rarr;
                </div>

                {/* Corner labels */}
                <span className="absolute bottom-1 left-1 text-[10px] text-slate-600">
                  Shallow AI / No Blockchain
                </span>
                <span className="absolute top-1 right-1 text-[10px] text-cyan-400/60">
                  Deep AI + Full Blockchain
                </span>

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
                        className="absolute w-12 h-12 rounded-full bg-cyan-400/10"
                        animate={{ scale: [1, 1.5, 1], opacity: [0.3, 0.1, 0.3] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    )}
                    <div
                      className="w-4 h-4 rounded-full border-2 z-10"
                      style={{
                        backgroundColor: comp.highlight ? comp.color : 'transparent',
                        borderColor: comp.color,
                        boxShadow: comp.highlight ? `0 0 16px ${comp.color}40` : 'none',
                      }}
                    />
                    <span
                      className="text-[10px] mt-1 font-medium whitespace-nowrap"
                      style={{ color: comp.highlight ? '#00d4ff' : '#94a3b8' }}
                    >
                      {comp.name}
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>
          </FadeInItem>

          {/* Right: Feature comparison table */}
          <FadeInItem>
            <div className="glass-card overflow-hidden">
              <div className="flex items-center gap-2 mb-3 justify-center">
                <Crown size={16} className="text-yellow-400" />
                <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                  Feature Comparison
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs sm:text-sm">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="text-left py-2 px-2 text-slate-400 font-medium text-xs">
                        Capability
                      </th>
                      <th className="text-center py-2 px-2 text-cyan-400 font-bold text-xs">
                        Forge
                      </th>
                      <th className="text-center py-2 px-2 text-slate-500 font-medium text-xs">
                        ChatGPT Ent
                      </th>
                      <th className="text-center py-2 px-2 text-slate-500 font-medium text-xs">
                        RAG
                      </th>
                      <th className="text-center py-2 px-2 text-slate-500 font-medium text-xs">
                        Custom
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {competitorComparison.map((row) => (
                      <tr key={row.feature} className="border-b border-white/5">
                        <td className="py-2 px-2 text-slate-300 text-xs">{row.feature}</td>
                        <td className="py-2 px-2 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {statusIcon(row.forge)}
                            <span className={`text-xs font-semibold ${statusColor(row.forge)}`}>
                              {row.forge === 'best' ? 'Best' : row.forge}
                            </span>
                          </div>
                        </td>
                        <td className="py-2 px-2 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {statusIcon(row.chatgpt)}
                            <span className={`text-xs ${statusColor(row.chatgpt)}`}>
                              {row.chatgpt}
                            </span>
                          </div>
                        </td>
                        <td className="py-2 px-2 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {statusIcon(row.rag)}
                            <span className={`text-xs ${statusColor(row.rag)}`}>{row.rag}</span>
                          </div>
                        </td>
                        <td className="py-2 px-2 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {statusIcon(row.custom)}
                            <span className={`text-xs ${statusColor(row.custom)}`}>
                              {row.custom}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </FadeInItem>
        </div>
      </div>
    </SlideLayout>
  );
}
