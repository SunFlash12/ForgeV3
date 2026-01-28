import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { pipelinePhases, totalLatency } from '../data/features';
import { motion } from 'framer-motion';

const phaseColors = [
  '#00d4ff',
  '#3b9eff',
  '#5c7afc',
  '#7c5af0',
  '#8b4be0',
  '#9b3cd0',
  '#7c3aed',
];

export default function ProductSlide() {
  return (
    <SlideLayout slideKey={5} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="slide-title text-center mb-10"
        >
          7-Phase Pipeline.{' '}
          <span className="gradient-text">Sub-1.2 Second Latency.</span>
        </motion.h2>

        {/* Pipeline visualization */}
        <StaggerContainer className="w-full mb-10" delay={0.3}>
          {/* Desktop: horizontal pipeline */}
          <div className="hidden lg:block">
            <div className="flex items-stretch gap-0 w-full">
              {pipelinePhases.map((phase, index) => (
                <FadeInItem key={phase.name} className="flex-1 relative">
                  {/* Phase card */}
                  <div
                    className="relative border border-white/10 px-3 py-5 text-center h-full flex flex-col justify-between"
                    style={{
                      backgroundColor: `${phaseColors[index]}08`,
                      borderLeft: index === 0 ? undefined : 'none',
                      borderRadius:
                        index === 0
                          ? '12px 0 0 12px'
                          : index === pipelinePhases.length - 1
                            ? '0 12px 12px 0'
                            : '0',
                    }}
                  >
                    {/* Phase number */}
                    <div
                      className="text-xs font-bold mb-2 uppercase tracking-wider"
                      style={{ color: phaseColors[index] }}
                    >
                      Phase {index + 1}
                    </div>

                    {/* Phase name */}
                    <h4 className="text-sm font-semibold text-slate-100 mb-1">
                      {phase.name}
                    </h4>

                    {/* Time */}
                    <div
                      className="text-lg font-bold mb-1"
                      style={{ color: phaseColors[index] }}
                    >
                      {phase.time}
                    </div>

                    {/* Description */}
                    <p className="text-xs text-slate-500 leading-snug">
                      {phase.description}
                    </p>

                    {/* Connector arrow */}
                    {index < pipelinePhases.length - 1 && (
                      <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-10">
                        <div
                          className="w-0 h-0"
                          style={{
                            borderTop: '8px solid transparent',
                            borderBottom: '8px solid transparent',
                            borderLeft: `8px solid ${phaseColors[index]}40`,
                          }}
                        />
                      </div>
                    )}
                  </div>
                </FadeInItem>
              ))}
            </div>

            {/* Gradient bar underneath */}
            <motion.div
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 1.2, delay: 1.2, ease: [0.22, 1, 0.36, 1] }}
              className="h-1 mt-2 rounded-full origin-left"
              style={{
                background: `linear-gradient(to right, ${phaseColors[0]}, ${phaseColors[6]})`,
              }}
            />
          </div>

          {/* Mobile/Tablet: stacked list */}
          <div className="lg:hidden space-y-2 sm:space-y-3">
            {pipelinePhases.map((phase, index) => (
              <FadeInItem key={phase.name}>
                <div className="glass-card flex items-center gap-3 sm:gap-4">
                  <div
                    className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center shrink-0 text-xs sm:text-sm font-bold"
                    style={{
                      backgroundColor: `${phaseColors[index]}15`,
                      color: phaseColors[index],
                    }}
                  >
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-slate-100">{phase.name}</h4>
                      <span
                        className="text-sm font-bold shrink-0 ml-2"
                        style={{ color: phaseColors[index] }}
                      >
                        {phase.time}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{phase.description}</p>
                  </div>
                </div>
              </FadeInItem>
            ))}
          </div>
        </StaggerContainer>

        {/* Total latency metric */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 1.5 }}
          className="text-center"
        >
          <div className="inline-flex items-baseline gap-2">
            <span className="metric-value gradient-text">{totalLatency}</span>
            <span className="text-base sm:text-xl text-slate-400 font-light">total latency</span>
          </div>
          <p className="text-sm text-slate-500 mt-3 max-w-xl mx-auto">
            From raw input to verified, governed, searchable knowledge
          </p>
        </motion.div>
      </div>
    </SlideLayout>
  );
}
