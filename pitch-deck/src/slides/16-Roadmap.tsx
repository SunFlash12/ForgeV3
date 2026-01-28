import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { roadmapPhases } from '../data/features';
import { motion } from 'framer-motion';
import { CheckCircle, Radio, Clock } from 'lucide-react';

const statusConfig = {
  complete: {
    badge: 'COMPLETE',
    badgeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    dotClass: 'bg-emerald-400',
    icon: CheckCircle,
    iconColor: 'text-emerald-400',
    cardBorder: 'border-emerald-500/20',
  },
  current: {
    badge: 'CURRENT',
    badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    dotClass: 'bg-cyan-400',
    icon: Radio,
    iconColor: 'text-cyan-400',
    cardBorder: 'border-cyan-500/30',
  },
  planned: {
    badge: 'PLANNED',
    badgeClass: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    dotClass: 'bg-slate-500',
    icon: Clock,
    iconColor: 'text-slate-500',
    cardBorder: 'border-white/5',
  },
};

export default function Roadmap({ slideKey }: { slideKey: number }) {
  return (
    <SlideLayout slideKey={slideKey} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        <StaggerContainer className="flex flex-col gap-8">
          {/* Headline */}
          <FadeInItem>
            <h1 className="slide-title text-center">
              <span className="gradient-text">Foundation Complete.</span>{' '}
              <span className="text-slate-100">Now Scaling.</span>
            </h1>
            <p className="slide-subtitle text-center">
              12+ months of production engineering already delivered
            </p>
          </FadeInItem>

          {/* Timeline */}
          <FadeInItem>
            <div className="relative">
              {/* Horizontal connecting line */}
              <div className="hidden lg:block absolute top-[38px] left-[calc(12.5%)] right-[calc(12.5%)] h-[2px] bg-gradient-to-r from-emerald-500/60 via-cyan-500/40 to-slate-600/30 z-0" />

              {/* Phase cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 relative z-10">
                {roadmapPhases.map((phase, index) => {
                  const config = statusConfig[phase.status];
                  const Icon = config.icon;
                  const isPlanned = phase.status === 'planned';

                  return (
                    <div key={index} className="flex flex-col items-center">
                      {/* Timeline dot */}
                      <div className="relative mb-4">
                        {phase.status === 'current' ? (
                          <div className="relative">
                            <motion.div
                              className="w-4 h-4 sm:w-5 sm:h-5 rounded-full bg-cyan-400"
                              animate={{
                                boxShadow: [
                                  '0 0 0 0 rgba(0, 212, 255, 0.4)',
                                  '0 0 0 12px rgba(0, 212, 255, 0)',
                                ],
                              }}
                              transition={{
                                duration: 1.5,
                                repeat: Infinity,
                                ease: 'easeOut',
                              }}
                            />
                          </div>
                        ) : (
                          <div
                            className={`w-4 h-4 sm:w-5 sm:h-5 rounded-full ${config.dotClass} ${
                              phase.status === 'complete'
                                ? 'ring-2 ring-emerald-400/30'
                                : ''
                            }`}
                          />
                        )}
                      </div>

                      {/* Phase card */}
                      <div
                        className={`glass-card w-full border ${config.cardBorder} ${
                          isPlanned ? 'opacity-60' : ''
                        }`}
                      >
                        {/* Status badge */}
                        <div className="flex items-center justify-between mb-3">
                          <Icon
                            className={`w-4 h-4 ${config.iconColor}`}
                          />
                          <span
                            className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border ${config.badgeClass}`}
                          >
                            {config.badge}
                          </span>
                        </div>

                        {/* Phase name */}
                        <h3
                          className={`text-sm font-bold mb-3 ${
                            isPlanned ? 'text-slate-400' : 'text-slate-100'
                          }`}
                        >
                          {phase.phase}
                        </h3>

                        {/* Items */}
                        <ul className="space-y-1.5">
                          {phase.items.map((item, itemIndex) => (
                            <li
                              key={itemIndex}
                              className={`text-xs leading-relaxed flex items-start gap-1.5 ${
                                isPlanned
                                  ? 'text-slate-500'
                                  : 'text-slate-300'
                              }`}
                            >
                              <span
                                className={`mt-1.5 w-1 h-1 rounded-full shrink-0 ${
                                  phase.status === 'complete'
                                    ? 'bg-emerald-400/60'
                                    : phase.status === 'current'
                                      ? 'bg-cyan-400/60'
                                      : 'bg-slate-600'
                                }`}
                              />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </FadeInItem>
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
