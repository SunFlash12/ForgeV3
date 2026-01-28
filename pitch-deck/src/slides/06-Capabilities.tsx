import { SlideLayout, StaggerContainer, FadeInItem } from '../components/SlideLayout';
import { coreCapabilities } from '../data/features';
import { Box, Users, Shield, CheckCircle, Globe, GitBranch } from 'lucide-react';
import { motion } from 'framer-motion';

const iconMap: Record<string, React.FC<{ size?: number; style?: React.CSSProperties }>> = {
  box: Box,
  users: Users,
  shield: Shield,
  check: CheckCircle,
  globe: Globe,
  'git-branch': GitBranch,
};

export default function CapabilitiesSlide() {
  return (
    <SlideLayout slideKey={6} background="gradient">
      <div className="slide-content flex flex-col md:h-full md:justify-center">
        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="slide-title text-center mb-10"
        >
          Built for Enterprise.{' '}
          <span className="gradient-text">Designed for AI Agents.</span>
        </motion.h2>

        {/* 2x3 grid */}
        <StaggerContainer className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-5" delay={0.3}>
          {coreCapabilities.map((capability) => {
            const Icon = iconMap[capability.icon];
            return (
              <FadeInItem key={capability.title}>
                <div className="glass-card flex flex-col h-full">
                  {/* Top row: icon + metric badge */}
                  <div className="flex items-center justify-between mb-4">
                    <div
                      className="w-9 h-9 md:w-11 md:h-11 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: `${capability.color}15` }}
                    >
                      {Icon && <Icon size={22} style={{ color: capability.color }} />}
                    </div>
                    <span
                      className="text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wide"
                      style={{
                        backgroundColor: `${capability.color}15`,
                        color: capability.color,
                      }}
                    >
                      {capability.metric}
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="text-lg font-semibold text-slate-100 mb-2">
                    {capability.title}
                  </h3>

                  {/* Description */}
                  <p className="text-sm text-slate-400 leading-relaxed">
                    {capability.description}
                  </p>
                </div>
              </FadeInItem>
            );
          })}
        </StaggerContainer>
      </div>
    </SlideLayout>
  );
}
