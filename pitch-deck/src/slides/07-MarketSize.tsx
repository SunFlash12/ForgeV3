import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { AnimatedCounter } from '../components/AnimatedCounter';
import { tamSegments, totalTAM } from '../data/market';
import { motion } from 'framer-motion';

export default function MarketSizeSlide({ slideKey }: { slideKey: number }) {
  const maxTAM = Math.max(...tamSegments.map((s) => s.tam));

  return (
    <SlideLayout slideKey={slideKey} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="slide-title text-center mb-4"
        >
          <span className="gradient-text">$127B+</span>{' '}
          Total Addressable Market
        </motion.h2>

        {/* Large animated counter */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="text-center mb-12"
        >
          <AnimatedCounter
            value={totalTAM}
            prefix="$"
            suffix="B+"
            className="metric-value gradient-text"
          />
          <p className="metric-label">Combined TAM across four segments</p>
        </motion.div>

        {/* Segment bars */}
        <StaggerContainer className="space-y-3 md:space-y-5 max-w-4xl mx-auto w-full" delay={0.5}>
          {tamSegments.map((segment) => {
            const barWidth = (segment.tam / maxTAM) * 100;
            const displayName = segment.name.replace('\n', ' ');

            return (
              <FadeInItem key={segment.name}>
                <div className="flex items-center gap-2 md:gap-4">
                  {/* Segment label */}
                  <div className="w-32 sm:w-48 shrink-0 text-right">
                    <p className="text-xs sm:text-sm font-medium text-slate-200 leading-tight">
                      {displayName}
                    </p>
                  </div>

                  {/* Bar + metrics */}
                  <div className="flex-1 flex items-center gap-2 md:gap-4">
                    <div className="flex-1 h-8 sm:h-10 bg-white/5 rounded-lg overflow-hidden relative">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${barWidth}%` }}
                        transition={{ duration: 1, delay: 0.8, ease: [0.22, 1, 0.36, 1] }}
                        className="h-full rounded-lg flex items-center justify-end pr-3"
                        style={{
                          background: `linear-gradient(90deg, ${segment.color}30, ${segment.color}80)`,
                        }}
                      >
                        <span className="text-sm font-bold text-white whitespace-nowrap">
                          ${segment.tam}B
                        </span>
                      </motion.div>
                    </div>

                    {/* CAGR badge */}
                    <div
                      className="shrink-0 px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap"
                      style={{
                        backgroundColor: `${segment.color}15`,
                        color: segment.color,
                      }}
                    >
                      {segment.cagr}% CAGR
                    </div>
                  </div>
                </div>
              </FadeInItem>
            );
          })}
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
