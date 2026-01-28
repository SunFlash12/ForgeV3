import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { moatLayers } from '../data/features';
import { motion } from 'framer-motion';
import { ShieldCheck } from 'lucide-react';

/** Concentric ring radii as percentage of container size (outermost first) */
const ringPct = [46.77, 39.35, 32.26, 25.81, 20.0, 14.84];

export default function Moat() {
  return (
    <SlideLayout slideKey={12} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center gap-5">
        {/* Title */}
        <StaggerContainer className="text-center mb-1">
          <FadeInItem>
            <h1 className="slide-title">
              <span className="gradient-text">6 Layers of Defensibility</span>
            </h1>
            <p className="slide-subtitle">
              Compounding moats that widen with every user, every query, every audit
            </p>
          </FadeInItem>
        </StaggerContainer>

        {/* Main content: Concentric rings + Layer list */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 items-center">
          {/* Left: Concentric rings visualization */}
          <FadeInItem>
            <div className="glass-card flex items-center justify-center py-6">
              <div className="relative w-56 h-56 sm:w-72 sm:h-72 md:w-[310px] md:h-[310px]">
                {/* Center icon */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                  <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                    <ShieldCheck size={24} className="text-cyan-400" />
                  </div>
                </div>

                {/* Rings - innermost layers have smallest radius */}
                {moatLayers
                  .slice()
                  .reverse()
                  .map((layer, idx) => {
                    const pct = ringPct[moatLayers.length - 1 - idx];
                    return (
                      <motion.div
                        key={layer.layer}
                        className="absolute top-1/2 left-1/2 rounded-full border-2"
                        style={{
                          width: `${pct * 2}%`,
                          height: `${pct * 2}%`,
                          marginTop: `-${pct}%`,
                          marginLeft: `-${pct}%`,
                          borderColor: `${layer.color}50`,
                          backgroundColor: `${layer.color}08`,
                        }}
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{
                          delay: 0.3 + idx * 0.15,
                          duration: 0.6,
                          ease: 'easeOut',
                        }}
                      />
                    );
                  })}

                {/* Labels placed around the rings */}
                {moatLayers.map((layer, idx) => {
                  // Place labels at evenly spaced angles (percentage-based)
                  const angle = -90 + idx * 60;
                  const rad = (angle * Math.PI) / 180;
                  const labelRadiusPct = ringPct[idx] + 5.81; // ~18/310*100
                  const xPct = 50 + labelRadiusPct * Math.cos(rad);
                  const yPct = 50 + labelRadiusPct * Math.sin(rad);

                  return (
                    <motion.div
                      key={layer.layer}
                      className="absolute text-center"
                      style={{
                        left: `${xPct}%`,
                        top: `${yPct}%`,
                        transform: 'translate(-50%, -50%)',
                      }}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.8 + idx * 0.1 }}
                    >
                      <span
                        className="text-[10px] font-bold whitespace-nowrap px-2 py-0.5 rounded-full"
                        style={{
                          color: layer.color,
                          backgroundColor: `${layer.color}15`,
                          border: `1px solid ${layer.color}30`,
                        }}
                      >
                        {layer.layer}
                      </span>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          </FadeInItem>

          {/* Right: Layer details */}
          <StaggerContainer className="flex flex-col gap-3" delay={0.3}>
            {moatLayers.map((layer, idx) => (
              <FadeInItem key={layer.layer}>
                <div className="glass-card flex items-start gap-4 py-4">
                  {/* Layer number */}
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 text-sm font-bold"
                    style={{
                      backgroundColor: `${layer.color}20`,
                      color: layer.color,
                    }}
                  >
                    {idx + 1}
                  </div>

                  {/* Content */}
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="text-sm font-bold text-white">{layer.layer}</h4>
                      <span
                        className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                        style={{
                          color: layer.strength === 'Very Strong' ? '#10b981' : '#f59e0b',
                          backgroundColor:
                            layer.strength === 'Very Strong'
                              ? 'rgba(16, 185, 129, 0.15)'
                              : 'rgba(245, 158, 11, 0.15)',
                        }}
                      >
                        {layer.strength}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{layer.description}</p>
                  </div>
                </div>
              </FadeInItem>
            ))}
          </StaggerContainer>
        </div>
      </div>
    </SlideLayout>
  );
}
