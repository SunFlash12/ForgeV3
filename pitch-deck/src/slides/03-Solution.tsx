import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { Box, Users, Coins, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

const steps = [
  {
    icon: Box,
    title: 'Capture',
    description: 'Knowledge Capsules with complete version history and cryptographic integrity.',
    color: '#00d4ff',
  },
  {
    icon: Users,
    title: 'Govern',
    description: 'Ghost Council AI governance with democratic voting and constitutional compliance.',
    color: '#7c3aed',
  },
  {
    icon: Coins,
    title: 'Monetize',
    description: 'Tokenized knowledge assets via Virtuals Protocol with automated revenue sharing.',
    color: '#10b981',
  },
];

export default function SolutionSlide() {
  return (
    <SlideLayout slideKey={3} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="slide-title text-center mb-12"
        >
          Forge Makes Organizational Knowledge{' '}
          <span className="gradient-text">Permanent</span>
        </motion.h2>

        {/* 3-step flow */}
        <StaggerContainer className="flex flex-col md:flex-row items-stretch justify-center gap-6 md:gap-4 mb-12" delay={0.3}>
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <FadeInItem key={step.title} className="flex items-center gap-4 md:gap-3 flex-1">
                {/* Card */}
                <div className="glass-card flex flex-col items-center text-center flex-1 py-5 md:py-8 px-4 md:px-5">
                  <div
                    className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5"
                    style={{ backgroundColor: `${step.color}15` }}
                  >
                    <Icon size={28} style={{ color: step.color }} />
                  </div>
                  <h3 className="text-lg md:text-xl font-bold text-slate-100 mb-3">{step.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{step.description}</p>
                </div>

                {/* Arrow connector (not after last) */}
                {index < steps.length - 1 && (
                  <div className="hidden md:flex items-center justify-center shrink-0">
                    <ArrowRight size={24} className="text-slate-600" />
                  </div>
                )}
              </FadeInItem>
            );
          })}
        </StaggerContainer>

        {/* Bottom statement */}
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.9 }}
          className="text-center text-base md:text-lg text-slate-400 max-w-3xl mx-auto leading-relaxed"
        >
          Every piece of knowledge is{' '}
          <span className="text-slate-200 font-medium">versioned</span>,{' '}
          <span className="text-slate-200 font-medium">traceable</span>, and{' '}
          <span className="text-slate-200 font-medium">permanently preserved</span>.
        </motion.p>
      </div>
    </SlideLayout>
  );
}
